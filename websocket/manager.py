# websocket/manager.py
import asyncio
import json
import logging
from typing import Callable, Dict, Optional

import websockets

from websocket.adapters import WS_ADAPTERS
from websocket.decoder import decode

logger = logging.getLogger(__name__)


class WSManager:

    def __init__(self):
        self.prices: Dict[str, dict] = {}
        self.callbacks: Dict[str, list] = {}
        self.tasks: Dict[str, asyncio.Task] = {}
        self._ping_tasks: Dict[str, asyncio.Task] = {}

    @staticmethod
    def _key(exchange, symbol):
        return f"{exchange}:{symbol}"

    def get_price(self, exchange, symbol) -> Optional[dict]:
        return self.prices.get(self._key(exchange, symbol))

    def add_callback(self, exchange, symbol, cb: Callable):
        key = self._key(exchange, symbol)
        lst = self.callbacks.setdefault(key, [])
        if cb not in lst:
            lst.append(cb)

    async def subscribe(self, exchange, symbol):
        if exchange not in WS_ADAPTERS:
            logger.warning(f"WS не поддерживает {exchange}")
            return False
        key = self._key(exchange, symbol)
        if key in self.tasks and not self.tasks[key].done():
            return True
        self.tasks[key] = asyncio.create_task(
            self._run_stream(exchange, symbol))
        return True

    async def unsubscribe(self, exchange, symbol):
        key = self._key(exchange, symbol)
        for tasks_dict in (self.tasks, self._ping_tasks):
            task = tasks_dict.pop(key, None)
            if task:
                task.cancel()
                try:
                    await task
                except Exception:
                    pass
        self.prices.pop(key, None)

    # ---------- Proactive ping ----------

    async def _ping_loop(self, key, ws):
        """Отправляем heartbeat раз в 25 сек, пока живём."""
        try:
            while True:
                await asyncio.sleep(25)
                try:
                    await ws.send("Ping")
                    logger.debug(f"[WS] {key} → Ping (proactive)")
                except Exception as e:
                    logger.debug(f"[WS] {key} ping failed: {e}")
                    return
        except asyncio.CancelledError:
            return

    # ---------- Основной стрим ----------

    async def _run_stream(self, exchange, symbol):
        adapter = WS_ADAPTERS[exchange]
        key = self._key(exchange, symbol)
        url = adapter.build_url(symbol)
        backoff = 1
        max_backoff = 60
        fail_streak = 0

        while True:
            ping_task = None
            try:
                async with websockets.connect(
                    url,
                    ping_interval=None,
                    ping_timeout=None,
                    compression=None,
                    max_size=2 ** 23,
                    open_timeout=15,
                ) as ws:
                    sub = adapter.subscribe_msg(symbol)
                    if sub:
                        await ws.send(json.dumps(sub))

                    backoff = 1
                    fail_streak = 0
                    logger.info(f"[WS] {key} подключён")

                    # Запускаем proactive ping
                    ping_task = asyncio.create_task(self._ping_loop(key, ws))
                    self._ping_tasks[key] = ping_task

                    msg_count = 0
                    async for raw in ws:
                        text = decode(raw)
                        if not text:
                            continue

                        # ⚡️ Логируем первые 3 сообщения для диагностики
                        if msg_count < 3:
                            logger.info(
                                f"[WS] {key} raw#{msg_count}: "
                                f"{repr(text[:120])}")
                            msg_count += 1

                        stripped = text.strip()
                        low = stripped.lower()

                        # ===== 1. Plain text Ping/Pong =====
                        if low in ("ping", "\"ping\"", "ping\n"):
                            try:
                                await ws.send("Pong")
                                logger.debug(f"[WS] {key} → Pong (text)")
                            except Exception as e:
                                logger.warning(f"send Pong: {e}")
                            continue
                        if low in ("pong", "\"pong\"", "pong\n"):
                            continue

                        # ===== 2. JSON Ping/Pong =====
                        try:
                            msg = json.loads(text)
                        except json.JSONDecodeError:
                            # Не текст, не JSON — возможно это ping в бинарной форме
                            logger.debug(f"[WS] {key} non-json: {text[:60]}")
                            try:
                                await ws.send("Pong")
                            except Exception:
                                pass
                            continue

                        if isinstance(msg, dict):
                            # JSON ping/pong
                            if "ping" in msg:
                                try:
                                    await ws.send(
                                        json.dumps({"pong": msg["ping"]}))
                                    logger.debug(
                                        f"[WS] {key} → Pong (json)")
                                except Exception:
                                    pass
                                continue
                            if "pong" in msg:
                                continue

                            # Подтверждение подписки
                            if msg.get("op") == "subscribe":
                                continue
                            if msg.get("code") == 0 and "dataType" in msg:
                                logger.debug(
                                    f"[WS] {key} sub-ack: "
                                    f"{msg.get('dataType')}")
                                continue
                            if msg.get("success") is True:
                                continue

                        # ===== 3. Парсинг данных =====
                        try:
                            snap = adapter.parse(msg)
                        except Exception as e:
                            logger.debug(f"parse error: {e}")
                            continue
                        if not snap or not snap.get("price"):
                            continue

                        self.prices[key] = snap

                        for cb in list(self.callbacks.get(key, [])):
                            try:
                                res = cb(snap)
                                if asyncio.iscoroutine(res):
                                    await res
                            except Exception as e:
                                logger.error(f"callback {key}: {e}")

            except asyncio.CancelledError:
                logger.info(f"[WS] {key} остановлен")
                return
            except Exception as e:
                fail_streak += 1
                if fail_streak >= 10:
                    logger.error(f"[WS] {key} {fail_streak} ошибок — стоп")
                    self.tasks.pop(key, None)
                    return
                logger.warning(
                    f"[WS] {key} ошибка ({fail_streak}/10): {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)
            finally:
                if ping_task:
                    ping_task.cancel()
                    try:
                        await ping_task
                    except Exception:
                        pass
                self._ping_tasks.pop(key, None)

    async def shutdown(self):
        for tasks_dict in (self._ping_tasks, self.tasks):
            for t in list(tasks_dict.values()):
                t.cancel()
            if tasks_dict:
                await asyncio.gather(*tasks_dict.values(),
                                      return_exceptions=True)
            tasks_dict.clear()