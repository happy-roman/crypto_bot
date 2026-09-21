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
        task = self.tasks.pop(key, None)
        if task:
            task.cancel()
            try:
                await task
            except Exception:
                pass
        self.prices.pop(key, None)

    async def _run_stream(self, exchange, symbol):
        adapter = WS_ADAPTERS[exchange]
        key = self._key(exchange, symbol)
        url = adapter.build_url(symbol)
        backoff = 1
        max_backoff = 60

        while True:
            try:
                async with websockets.connect(
                    url, ping_interval=20, ping_timeout=10,
                    compression=None, max_size=2 ** 23, open_timeout=15,
                ) as ws:
                    sub = adapter.subscribe_msg(symbol)
                    if sub:
                        await ws.send(json.dumps(sub))
                    backoff = 1
                    logger.info(f"[WS] {key} подключён")

                    async for raw in ws:
                        text = decode(raw)
                        if not text:
                            continue
                        try:
                            msg = json.loads(text)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(msg, dict):
                            if msg.get("op") == "subscribe":
                                continue
                        try:
                            snap = adapter.parse(msg)
                        except Exception:
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
                logger.warning(f"[WS] {key} ошибка: {e}")
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def shutdown(self):
        tasks = list(self.tasks.values())
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self.tasks.clear()
