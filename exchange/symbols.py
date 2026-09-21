def to_swap(symbol):
    if ":" in symbol:
        return symbol
    return f"{symbol}:USDT"


def to_plain(symbol):
    return symbol.split(":")[0]
