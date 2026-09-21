# exchange/balance.py
import logging
from config.loader import CONFIG

logger = logging.getLogger(__name__)

QUOTES = ["USDT", "USDC", "BUSD", "FDUSD", "TUSD"]


def get_balance(client, exchange_name, market_type="spot"):
    if CONFIG.trading.get("paper_trading"):
        return float(CONFIG.trading.get("test_balance", 1000.0))
    try:
        bal = client.fetch_balance(exchange_name, market_type)
        for cur in QUOTES:
            cb = bal.get(cur, {})
            if not cb:
                continue
            v = cb.get("free") if cb.get("free") is not None \
                else (cb.get("total") or 0)
            try:
                v = float(v)
            except (TypeError, ValueError):
                continue
            if v > 0:
                return v
    except Exception as e:
        logger.warning(f"balance error: {e}")
    return 0.0
