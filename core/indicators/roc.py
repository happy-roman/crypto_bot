def roc(closes, period=100):
    if len(closes) < period + 1:
        return 0.0
    prev = closes[-(period + 1)]
    if prev == 0:
        return 0.0
    return (closes[-1] / prev - 1) * 100
