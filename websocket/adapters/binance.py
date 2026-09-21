from websocket.adapters.base import BaseWSAdapter, safe_float


def _sym(s):
    return s.replace("/", "").lower()


class BinanceWS(BaseWSAdapter):
    name = "binance"
    URL = "wss://fstream.binance.com/ws"

    @staticmethod
    def build_url(symbol):
        return f"{BinanceWS.URL}/{_sym(symbol)}@ticker"

    @staticmethod
    def parse(msg):
        if msg.get("e") != "24hrTicker":
            return None
        return {
            "price": safe_float(msg.get("c")),
            "bid": safe_float(msg.get("b")),
            "ask": safe_float(msg.get("a")),
            "change_24h": safe_float(msg.get("P")),
            "ts": msg.get("E"),
        }
