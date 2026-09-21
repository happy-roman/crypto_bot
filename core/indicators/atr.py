def atr(highs, lows, closes, period=14):
    if len(closes) < period + 1:
        return 0.0
    trs = []
    for i in range(1, len(closes)):
        tr = max(highs[i] - lows[i],
                 abs(highs[i] - closes[i - 1]),
                 abs(lows[i] - closes[i - 1]))
        trs.append(tr)
    return sum(trs[-period:]) / period


def atr_pct(highs, lows, closes, period=14):
    a = atr(highs, lows, closes, period)
    if not closes or closes[-1] <= 0:
        return 0.0
    return (a / closes[-1]) * 100
