# exchange/futures_setup.py
import logging
from exchange.symbols import to_swap

logger = logging.getLogger(__name__)


def setup_futures(client, exchange_name, symbol,
                  margin_mode="isolated", leverage=1):
    ex = client.get_exchange(exchange_name, "swap")
    if not ex:
        return False
    sym = to_swap(symbol)
    try:
        ex.set_margin_mode(margin_mode, sym)
    except Exception as e:
        logger.debug(f"set_margin_mode: {e}")
    try:
        ex.set_leverage(leverage, sym)
    except Exception as e:
        logger.debug(f"set_leverage: {e}")
    return True
