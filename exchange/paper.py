# exchange/paper.py
import logging
import time

logger = logging.getLogger(__name__)


class PaperClient:

    def __init__(self, real_client, initial_balance=1000.0):
        self.real = real_client
        self.balance = float(initial_balance)

    # Прокси к реальному CCXTClient
    def get_exchange(self, name, market_type="spot"):
        return self.real.get_exchange(name, market_type)

    def list_exchanges(self):
        return self.real.list_exchanges()

    def has_market(self, name, market_type):
        return self.real.has_market(name, market_type)

    def get_ohlcv(self, *a, **kw):
        return self.real.get_ohlcv(*a, **kw)

    def get_ticker(self, name, symbol, market_type="spot"):
        return self.real.get_ticker(name, symbol, market_type)

    # Виртуальные операции
    def fetch_balance(self, name, market_type="spot"):
        return {"USDT": {"free": self.balance, "total": self.balance}}

    def create_order(self, name, symbol, order_type, side,
                     amount, price=None, market_type="spot"):
        if price is None:
            t = self.real.get_ticker(name, symbol, market_type)
            if not t:
                logger.warning(f"[PAPER] no ticker {symbol}")
                return None
            price = float(t["last"])
        notional = float(amount) * float(price)
        if side == "buy":
            self.balance -= notional
        else:
            self.balance += notional
        oid = f"paper_{int(time.time() * 1000)}"
        logger.info(f"[PAPER] {side.upper():4s} {amount:.6f} {symbol} "
                    f"@ {price:.6f} bal={self.balance:.2f}")
        return {"id": oid, "price": price, "amount": amount,
                "side": side, "status": "closed", "paper": True}

    def cancel_order(self, name, order_id, symbol, market_type="spot"):
        return {"id": order_id, "status": "canceled"}