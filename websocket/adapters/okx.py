from websocket.adapters.base import BaseWSAdapter, safe_float


def _sym(s):
    return s.replace("/", "-")


class OKXWS(BaseWSAdapter):
    name = "okx"
    URL = "wss://ws.okx.com:8443/ws/v5/public"

    @staticmethod
    def build_url(symbol):
        return OKXWS.URL

    @staticmethod
    def subscribe_msg(symbol):
        return {"op": "subscribe",
                "args": [{"channel": "tickers", "instId": _sym(symbol)}]}

    @staticmethod
    def parse(msg):
        if msg.get("arg", {}).get("channel") == "tickers" and msg.get("data"):
            d = msg["data"][0]
            last = safe_float(d.get("last"))
            return {
                "price": last,
                "bid": safe_float(d.get("bidPx"), last),
                "ask": safe_float(d.get("askPx"), last),
                "change_24h": safe_float(d.get("sodUtc0")) * 100,
                "ts": int(safe_float(d.get("ts"))),
            }
        return None
