# core/resample.py
def resample(candles_1m, minutes):
    if minutes <= 1:
        return candles_1m
    bucket_ms = minutes * 60_000
    out = []
    cur = None
    for c in candles_1m:
        b_start = (c[0] // bucket_ms) * bucket_ms
        if cur is None or cur[0] != b_start:
            if cur is not None:
                out.append(cur)
            cur = [b_start, c[1], c[2], c[3], c[4], c[5]]
        else:
            cur[2] = max(cur[2], c[2])
            cur[3] = min(cur[3], c[3])
            cur[4] = c[4]
            cur[5] += c[5]
    if cur is not None:
        out.append(cur)
    return out
