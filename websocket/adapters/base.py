def safe_float(value, default=0.0):
    if value is None:
        return default
    if isinstance(value, (int, float)):
        try:
            return float(value)
        except (TypeError, ValueError):
            return default
    if isinstance(value, str):
        s = value.strip().replace("%", "").replace(",", "").replace(" ", "")
        if not s:
            return default
        try:
            return float(s)
        except ValueError:
            return default
    return default


class BaseWSAdapter:
    name = "base"
    URL = ""

    @staticmethod
    def build_url(symbol):
        raise NotImplementedError

    @staticmethod
    def subscribe_msg(symbol):
        return None

    @staticmethod
    def parse(msg):
        raise NotImplementedError
