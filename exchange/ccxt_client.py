# exchange/ccxt_client.py
import logging
import threading

import ccxt

from config.loader import CONFIG

logger = logging.getLogger(__name__)


class CCXTClient:

    def __init__(self):
        self.exchanges = {}
        self._loaded = set()
        self._locks = {}

        for name, creds in CONFIG.global_.get("exchanges", {}).items():
            for mtype in ("spot", "swap"):
                try:
                    cls = getattr(ccxt, name, None)
                    if cls is None:
                        continue

                    opts = {"defaultType": mtype}
                    if mtype == "swap":
                        opts["defaultSubType"] = "linear"
                        # ⚡️ Только linear markets — не грузим spot, не падаем
                        opts["fetchMarkets"] = {"types": ["linear"]}
                    elif mtype == "spot":
                        opts["fetchMarkets"] = {"types": ["spot"]}

                    params = {"enableRateLimit": True, "options": opts}
                    if creds.get("api_key"):
                        params["apiKey"] = creds["api_key"]
                        params["secret"] = creds["secret"]
                        if creds.get("password"):
                            params["password"] = creds["password"]

                    ex = cls(params)
                    if creds.get("sandbox"):
                        try:
                            ex.set_sandbox_mode(True)
                        except Exception:
                            pass

                    self.exchanges[f"{name}:{mtype}"] = ex
                except Exception as e:
                    logger.error(f"init {name}:{mtype}: {e}")

        logger.info(f"Инициализировано {len(self.exchanges)} инстансов ccxt")

    # ---------- Markets: ленивая загрузка ----------

    def _ensure_markets(self, name, market_type):
        key = f"{name}:{market_type}"
        ex = self.exchanges.get(key)
        if not ex:
            return None

        if key in self._loaded and getattr(ex, "markets", None):
            return ex

        lock = self._locks.setdefault(key, threading.Lock())
        with lock:
            if key in self._loaded and getattr(ex, "markets", None):
                return ex
            try:
                logger.info(f"Загружаю markets {key}...")
                ex.load_markets()
                n = len(ex.markets)
                self._loaded.add(key)
                logger.info(f"{key} markets={n}")
                if n == 0:
                    logger.warning(f"{key} markets пусто — проверь сеть/VPN")
            except Exception as e:
                logger.error(f"{key} load_markets FAILED: {type(e).__name__}: {e}")

        return ex

    # ---------- Доступ ----------

    def get_exchange(self, name, market_type="spot"):
        return self.exchanges.get(f"{name}:{market_type}")

    def list_exchanges(self):
        return sorted({k.split(":")[0] for k in self.exchanges})

    def has_market(self, name, market_type):
        return f"{name}:{market_type}" in self.exchanges

    # ---------- Данные ----------

    def get_ticker(self, name, symbol, market_type="spot"):
        ex = self._ensure_markets(name, market_type)
        if not ex:
            return None
        try:
            return ex.fetch_ticker(symbol)
        except Exception as e:
            logger.warning(f"get_ticker {name} {symbol}: {e}")
            return None

    def get_ohlcv(self, name, symbol, timeframe="1h",
                  limit=1000, since=None, market_type="spot"):
        ex = self._ensure_markets(name, market_type)
        if not ex:
            return None
        try:
            return ex.fetch_ohlcv(symbol, timeframe, since=since, limit=limit)
        except Exception as e:
            logger.warning(f"get_ohlcv {name} {symbol}: {e}")
            return None

    # ---------- Торговля ----------

    def create_order(self, name, symbol, order_type, side,
                     amount, price=None, market_type="spot"):
        ex = self._ensure_markets(name, market_type)
        if not ex:
            logger.error(f"create_order: нет {name}:{market_type}")
            return None
        try:
            return ex.create_order(symbol, order_type, side, amount, price)
        except Exception as e:
            logger.error(f"create_order {name} {symbol}: {e}")
            return None

    def cancel_order(self, name, order_id, symbol, market_type="spot"):
        ex = self._ensure_markets(name, market_type)
        if not ex:
            return None
        try:
            return ex.cancel_order(order_id, symbol)
        except Exception as e:
            logger.warning(f"cancel_order: {e}")
            return None

    def fetch_balance(self, name, market_type="spot"):
        ex = self._ensure_markets(name, market_type)
        if not ex:
            return {}
        try:
            return ex.fetch_balance()
        except Exception as e:
            logger.warning(f"fetch_balance: {e}")
            return {}