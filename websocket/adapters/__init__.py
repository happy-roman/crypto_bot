from websocket.adapters.binance import BinanceWS
from websocket.adapters.bybit import BybitWS
from websocket.adapters.okx import OKXWS
from websocket.adapters.bingx import BingXWS

WS_ADAPTERS = {
    "binance": BinanceWS,
    "bybit": BybitWS,
    "okx": OKXWS,
    "bingx": BingXWS,
}

__all__ = ["WS_ADAPTERS"]
