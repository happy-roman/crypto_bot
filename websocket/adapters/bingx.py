from websocket.adapters.base import BaseWSAdapter, safe_float


def _sym(s):
    return s.replace("/", "-")


class BingXWS(BaseWSAdapter):
    name = "bingx"
    URL = "wss://open-api-ws.bingx.com/market"

    @staticmethod
    def build_url(symbol):
        return BingXWS.URL

    @staticmethod
    def subscribe_msg(symbol):
        return {"id": "sub_ticker", "reqType": "sub",
                "dataType": f"{_sym(symbol)}@ticker"}

    @staticmethod
    def parse(msg):
        d = msg.get("data") if isinstance(msg.get("data"), dict) else msg
        if not isinstance(d, dict) or "c" not in d:
            return None
        last = safe_float(d.get("c"))
        return {
            "price": last,
            "bid": safe_float(d.get("b"), last),
            "ask": safe_float(d.get("a"), last),
            "change_24h": safe_float(d.get("P")),
            "ts": d.get("E") or d.get("T"),
        }
