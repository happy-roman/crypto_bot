# trading/manager.py
import logging
from core.signals import GridSignal
from storage.stores import positions_store
from trading.migration import migrate_all
from trading.position import (
    add_grid_level, close_position_record, open_position,
)

logger = logging.getLogger(__name__)


class TradingManager:

    def __init__(self, exchange_client):
        self.ex = exchange_client
        self.strategy = GridSignal()
        try:
            migrate_all()
        except Exception as e:
            logger.error(f"migration: {e}")

    def open_by_signal(self, exchange_name, symbol, ohlcv,
                       market_type="swap", leverage=2,
                       user_id=0, amount_usdt=None):
        return open_position(
            self.ex, self.strategy, exchange_name, symbol, ohlcv,
            market_type=market_type, leverage=leverage,
            user_id=user_id, amount_usdt=amount_usdt)

    def on_price(self, exchange, symbol, price):
        events = []
        for pos in positions_store.find(status="open",
                                         exchange=exchange,
                                         symbol=symbol):
            try:
                self._tick(pos, price, events)
            except Exception as e:
                logger.error(f"tick #{pos.get('id')}: {e}")
        return events

    def _tick(self, pos, price, events):
        add_grid_level(self.ex, pos, price)
        side = pos["side"]
        tp = float(pos["tp_price"])
        hit = (side == "buy" and price >= tp) or \
              (side == "sell" and price <= tp)
        if hit:
            close_position_record(pos, tp, "TP")
            events.append({"type": "tp", "position": pos, "price": tp})

    def close(self, pos_id, price):
        pos = positions_store.find_one(id=pos_id, status="open")
        if not pos:
            return {"ok": False, "error": "not found"}
        close_position_record(pos, price, "MANUAL")
        return {"ok": True}

    def get_open(self):
        return positions_store.find(status="open")

    def get_history(self, limit=20):
        from storage.stores import trades_store
        rows = [r for r in trades_store.all() if r.get("type") == "close"]
        return rows[-limit:]
