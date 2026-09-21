def sma(values, period):
    if len(values) < period or period <= 0:
        return 0.0
    return sum(values[-period:]) / period
