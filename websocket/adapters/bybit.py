from websocket.adapters.base import BaseWSAdapter, safe_float


def _sym(s):
    return s.replace("/", "").upper()


class BybitWS(BaseWSAdapter):
    name = "bybit"
    URL = "wss://stream.bybit.com/v5/public/linear"

    @staticmethod
    def build_url(symbol):
        return BybitWS.URL

    @staticmethod
    def subscribe_msg(symbol):
        return {"op": "subscribe", "args": [f"tickers.{_sym(symbol)}"]}

    @staticmethod
    def parse(msg):
        if msg.get("topic", "").startswith("tickers") and "data" in msg:
            d = msg["data"]
            last = safe_float(d.get("lastPrice"))
            return {
                "price": last,
                "bid": safe_float(d.get("bid1Price"), last),
                "ask": safe_float(d.get("ask1Price"), last),
                "change_24h": safe_float(d.get("price24hPcnt")) * 100,
                "ts": msg.get("ts"),
            }
        return None
