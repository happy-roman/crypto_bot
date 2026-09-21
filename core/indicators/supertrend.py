def _atr_series(highs, lows, closes, period):
    n = len(closes)
    out = [None] * n
    if n < period + 1:
        return out
    trs = [0.0] * n
    for i in range(1, n):
        trs[i] = max(highs[i] - lows[i],
                     abs(highs[i] - closes[i - 1]),
                     abs(lows[i] - closes[i - 1]))
    atr_val = sum(trs[1:period + 1]) / period
    out[period] = atr_val
    for i in range(period + 1, n):
        atr_val = (atr_val * (period - 1) + trs[i]) / period
        out[i] = atr_val
    return out


def supertrend(highs, lows, closes, period=10, mult=3.0):
    n = len(closes)
    if n < period + 3:
        return 0.0, 0
    atr_arr = _atr_series(highs, lows, closes, period)
    fu, fl = [0.0] * n, [0.0] * n
    trend, st = [1] * n, [0.0] * n
    for i in range(period, n):
        if atr_arr[i] is None:
            continue
        hl2 = (highs[i] + lows[i]) / 2
        bu = hl2 + mult * atr_arr[i]
        bl = hl2 - mult * atr_arr[i]
        if i == period:
            fu[i], fl[i] = bu, bl
            if closes[i] > bu:
                trend[i], st[i] = 1, bl
            elif closes[i] < bl:
                trend[i], st[i] = -1, bu
            else:
                trend[i], st[i] = 1, bl
            continue
        fu[i] = bu if (bu < fu[i - 1] or closes[i - 1] > fu[i - 1]) else fu[i - 1]
        fl[i] = bl if (bl > fl[i - 1] or closes[i - 1] < fl[i - 1]) else fl[i - 1]
        if trend[i - 1] == 1:
            if closes[i] < fl[i]:
                trend[i], st[i] = -1, fu[i]
            else:
                trend[i], st[i] = 1, fl[i]
        else:
            if closes[i] > fu[i]:
                trend[i], st[i] = 1, fl[i]
            else:
                trend[i], st[i] = -1, fu[i]
    return st[n - 1], trend[n - 1]
