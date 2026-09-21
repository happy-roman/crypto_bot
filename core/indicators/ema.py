def ema(values, period):
    if len(values) < period or period <= 0:
        return 0.0
    k = 2 / (period + 1)
    e = sum(values[:period]) / period
    for v in values[period:]:
        e = v * k + e * (1 - k)
    return e
