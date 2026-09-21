# core/indicators/macd.py


def _ema_series(values, period):
    """EMA-серия (список), O(n)."""
    n = len(values)
    if n < period:
        return []
    k = 2 / (period + 1)
    out = [sum(values[:period]) / period]
    for v in values[period:]:
        out.append(v * k + out[-1] * (1 - k))
    return out


def macd(closes, fast=12, slow=26, signal=9):
    """
    O(n) вместо O(n²).
    Возвращает (macd_line, signal_line) для ПОСЛЕДНЕГО бара.
    """
    n = len(closes)
    if n < slow + signal:
        return 0.0, 0.0

    ema_fast = _ema_series(closes, fast)   # len = n - fast + 1
    ema_slow = _ema_series(closes, slow)   # len = n - slow + 1

    # Выравнивание по индексу: ema_slow начинается позже
    offset = slow - fast
    macd_line = [ema_fast[i + offset] - ema_slow[i]
                 for i in range(len(ema_slow))]

    if len(macd_line) < signal:
        return macd_line[-1], macd_line[-1]

    signal_series = _ema_series(macd_line, signal)
    return macd_line[-1], signal_series[-1]