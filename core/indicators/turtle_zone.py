from core.indicators.sma import sma
from core.indicators.atr import atr


def turtle_zone(highs, lows, closes, period=200, mult=5.6):
    if len(closes) < period + 1:
        return 0.0, 0.0
    mid = sma(closes, period)
    a = atr(highs, lows, closes, period)
    if mid <= 0 or a <= 0:
        return 0.0, 0.0
    return mid - a * mult, mid + a * mult
