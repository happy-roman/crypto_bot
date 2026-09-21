# trading/position.py
import logging
import time

from exchange.futures_setup import setup_futures
from storage.stores import positions_store, trades_store

logger = logging.getLogger(__name__)


def open_position(client, strategy, exchange_name, symbol, ohlcv,
                  market_type="swap", leverage=2, user_id=0,
                  amount_usdt=None):
    sig = strategy.compute(ohlcv, direction="long")
    if not sig or not sig.get("side"):
        return {"ok": False,
                "error": f"no signal: {sig.get('reason', '?') if sig else '?'}"}

    side = sig["side"]
    price = float(sig["entry"])
    tp_pct = float(sig.get("min_tp_pct", 0.8))

    if market_type == "swap":
        setup_futures(client, exchange_name, symbol, leverage=leverage)

    if amount_usdt is None or amount_usdt <= 0:
        from exchange.balance import get_balance
        amount_usdt = get_balance(client, exchange_name, market_type)
    if amount_usdt <= 0:
        return {"ok": False, "error": "balance <= 0"}

    grid_orders = sig.get("grid_orders", [])
    grid_levels = []
    for go in grid_orders:
        w = go["volume_pct"]
        notional = amount_usdt * (w / 100) * leverage
        lvl_amount = notional / go["price"] if go["price"] > 0 else 0
        grid_levels.append({
            "level": go["level"],
            "dist_pct": (go["price"] / price - 1) * 100,
            "price": go["price"],
            "amount": lvl_amount,
            "weight": w,
            "filled": False,
        })

    if not grid_levels:
        return {"ok": False, "error": "empty grid"}

    first = grid_levels[0]
    order = client.create_order(exchange_name, symbol, "market", side,
                                 first["amount"], None,
                                 market_type=market_type)
    if not order:
        return {"ok": False, "error": "order rejected"}

    first["filled"] = True
    avg = first["price"]
    tp_price = avg * (1 + tp_pct / 100) if side == "buy" \
        else avg * (1 - tp_pct / 100)

    pos = {
        "user_id": user_id,
        "exchange": exchange_name,
        "symbol": symbol,
        "market_type": market_type,
        "leverage": leverage,
        "side": side,
        "entry_price": price,
        "avg_entry": avg,
        "amount": first["amount"],
        "total_cost": first["amount"] * first["price"],
        "tp_price": round(tp_price, 8),
        "tp_pct": tp_pct,
        "grid_levels": grid_levels,
        "reason": sig["reason"],
        "status": "open",
        "opened_at": time.time(),
        "order_id": order.get("id"),
    }
    saved = positions_store.append(pos)
    trades_store.append({**saved, "type": "open"})
    logger.info(f"OPEN #{saved['id']} {side.upper()} {symbol} "
                f"@ {price:.6f} amount={first['amount']:.6f} "
                f"TP={tp_price:.6f}")
    return {"ok": True, "position": saved}


def add_grid_level(client, pos, price):
    side = pos["side"]
    grid_levels = pos.get("grid_levels", [])
    tp_pct = float(pos.get("tp_pct", 0.8))
    changed = False

    for lvl in grid_levels:
        if lvl.get("filled"):
            continue
        hit = (side == "buy" and price <= lvl["price"]) or \
              (side == "sell" and price >= lvl["price"])
        if not hit:
            continue
        order = client.create_order(
            pos["exchange"], pos["symbol"], "market", side,
            lvl["amount"], None,
            market_type=pos.get("market_type", "swap"))
        if not order:
            logger.warning(f"grid L{lvl['level']} rejected #{pos['id']}")
            continue
        lvl["filled"] = True
        changed = True
        logger.info(f"GRID ADD L{lvl['level']} #{pos['id']} "
                    f"+{lvl['amount']:.6f} @ {lvl['price']:.6f}")

    if not changed:
        return False

    total_size = sum(l["amount"] for l in grid_levels if l.get("filled"))
    total_cost = sum(l["amount"] * l["price"]
                     for l in grid_levels if l.get("filled"))
    if total_size <= 0:
        return False

    avg = total_cost / total_size
    new_tp = avg * (1 + tp_pct / 100) if side == "buy" \
        else avg * (1 - tp_pct / 100)

    positions_store.update(pos["id"], {
        "amount": total_size,
        "total_cost": total_cost,
        "avg_entry": avg,
        "tp_price": round(new_tp, 8),
        "grid_levels": grid_levels,
    })
    pos.update({"amount": total_size, "total_cost": total_cost,
                "avg_entry": avg, "tp_price": new_tp,
                "grid_levels": grid_levels})
    logger.info(f"GRID RECALC #{pos['id']} size={total_size:.6f} "
                f"avg={avg:.6f} TP={new_tp:.6f}")
    return True


def close_position_record(pos, price, reason):
    side = pos["side"]
    entry = float(pos["avg_entry"])
    amount = float(pos["amount"])
    lev = pos.get("leverage", 1) or 1
    if side == "buy":
        pnl = (price - entry) * amount
        pnl_pct = (price / entry - 1) * 100 * lev
    else:
        pnl = (entry - price) * amount
        pnl_pct = (entry / price - 1) * 100 * lev
    positions_store.update(pos["id"], {
        "status": "closed", "exit_price": price,
        "close_reason": reason, "closed_at": time.time(),
        "pnl": round(pnl, 8), "pnl_pct": round(pnl_pct, 4)})
    trades_store.append({
        "position_id": pos["id"], "type": "close", "reason": reason,
        "symbol": pos["symbol"], "exchange": pos["exchange"],
        "market_type": pos.get("market_type", "swap"),
        "user_id": pos.get("user_id", 0), "side": side,
        "entry": entry, "exit": price, "amount": amount,
        "leverage": lev, "regime": pos.get("reason", "?"),
        "pnl": round(pnl, 8), "pnl_pct": round(pnl_pct, 4)})
    logger.info(f"CLOSE #{pos['id']} ({reason}): "
                f"{side.upper()} {pos['symbol']} -> {pnl:+.6f}")
