import gzip
import zlib


def decode(raw):
    if isinstance(raw, str):
        return raw
    if not isinstance(raw, (bytes, bytearray)):
        return None
    data = bytes(raw)
    if len(data) >= 2 and data[0] == 0x1F and data[1] == 0x8B:
        try:
            return gzip.decompress(data).decode("utf-8", "strict")
        except Exception:
            return None
    if len(data) >= 2 and data[0] == 0x78:
        try:
            return zlib.decompress(data).decode("utf-8", "strict")
        except Exception:
            try:
                return zlib.decompress(data, -zlib.MAX_WBITS) \
                    .decode("utf-8", "strict")
            except Exception:
                return None
    try:
        return data.decode("utf-8", "strict")
    except Exception:
        return None
