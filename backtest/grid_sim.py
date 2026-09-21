# backtest/grid_sim.py
import logging
import time

from config.loader import CONFIG
from core.resample import resample
from core.indicators import rsi, turtle_zone, supertrend, roc, macd

logger = logging.getLogger(__name__)

# Максимальные окна для индикаторов на каждой итерации
ST_WINDOW = 500     # supertrend (1m и 15m) — последние 500 баров
RSI_WINDOW = 100    # rsi — последние 100 баров
ROC_WINDOW = 200    # roc — последние 200 баров


def simulate_grid(candles_1m, days, initial_balance, leverage,
                  timeframe, fee, slip_pct):
    cfg = CONFIG.grid
    grid_distances = cfg.get("grid_distances",
                              [0.0, -2.0, -4.0, -5.0, -10.0])
    grid_volumes = cfg.get("grid_volumes", [10, 10, 20, 20, 40])
    min_tp_pct = cfg.get("min_tp_pct", 0.8)

    # ---- 1. Resample один раз ----
    c_2m = resample(candles_1m, 2)
    c_10m = resample(candles_1m, 10)
    c_15m = resample(candles_1m, 15)
    c_4h = resample(candles_1m, 240)

    closes_1m = [c[4] for c in candles_1m]
    highs_1m = [c[2] for c in candles_1m]
    lows_1m = [c[3] for c in candles_1m]
    closes_2m = [c[4] for c in c_2m]
    closes_10m = [c[4] for c in c_10m]
    closes_15m = [c[4] for c in c_15m]
    closes_4h = [c[4] for c in c_4h]
    highs_15m = [c[2] for c in c_15m]
    lows_15m = [c[3] for c in c_15m]

    n = len(candles_1m)
    step = 2
    warmup = min(20 * 1440, n - 100)

    balance = initial_balance
    position = None
    trades = []
    equity_curve = []
    peak = initial_balance

    print(f"  [sim] Итераций: {(n - warmup) // step}, "
          f"warmup: {warmup}")
    t_start = time.time()

    for i in range(warmup, n, step):
        # Прогресс каждые 5000 итераций
        if i % 5000 == 0:
            elapsed = time.time() - t_start
            pct = (i - warmup) / (n - warmup) * 100
            print(f"  [sim] {pct:5.1f}% ({i}/{n}) "
                  f"equity=${balance:.2f} elapsed={elapsed:.0f}s")

        bar = candles_1m[i]
        close = bar[4]
        high_max = max(c[2] for c in candles_1m[i:i + step])
        low_min = min(c[3] for c in candles_1m[i:i + step])

        # ========== Есть позиция ==========
        if position:
            # Заполнение уровней сетки
            for order in position["orders"]:
                if order["filled"]:
                    continue
                if order["dist_pct"] < 0 and low_min <= order["price"]:
                    order["filled"] = True
                    position["total_size"] += order["size"]
                    position["total_cost"] += order["size"] * order["price"]
                    position["avg_entry"] = (position["total_cost"] /
                                              position["total_size"])

            # TP
            if position["total_size"] > 0:
                avg = position["avg_entry"]
                tp_price = avg * (1 + min_tp_pct / 100)
                if high_max >= tp_price:
                    _close(position, tp_price, "TP", trades, fee)
                    balance += trades[-1]["pnl"]
                    position = None

            # CLOSE-сигналы
            if position:
                should, reason = _check_close(
                    closes_1m, closes_2m, closes_15m,
                    highs_15m, lows_15m, i, cfg,
                    avg_entry=position["avg_entry"],
                    current_price=close)
                if should:
                    _close(position, close, reason, trades, fee)
                    balance += trades[-1]["pnl"]
                    position = None

        # ========== Вход ==========
        if position is None:
            has = _check_open(
                closes_1m, highs_1m, lows_1m,
                closes_10m, closes_15m, closes_4h,
                highs_15m, lows_15m, i, cfg)
            if has:
                risk_amt = balance * leverage
                total_w = sum(grid_volumes)
                orders = []
                for k, (dp, w) in enumerate(zip(grid_distances, grid_volumes)):
                    op = close * (1 + dp / 100)
                    size = (risk_amt * w / total_w) / op if op > 0 else 0
                    orders.append({"dist_pct": dp, "price": op,
                                    "size": size, "filled": k == 0})
                filled = [o for o in orders if o["filled"]]
                ts_ = sum(o["size"] for o in filled)
                tc = sum(o["size"] * o["price"] for o in filled)
                position = {
                    "orders": orders,
                    "total_size": ts_, "total_cost": tc,
                    "avg_entry": tc / ts_ if ts_ else 0,
                    "entry_time": bar[0]}

        equity = balance + ((close - position["avg_entry"]) *
                            position["total_size"]) if position else balance
        equity_curve.append(equity)
        peak = max(peak, equity)

    print(f"  [sim] Готово за {time.time() - t_start:.1f}s")

    if position:
        _close(position, candles_1m[-1][4], "EOD", trades, fee)
        balance += trades[-1]["pnl"]

    return _metrics(initial_balance, balance, equity_curve, trades, days,
                    leverage, timeframe, fee, slip_pct,
                    grid_distances, grid_volumes, min_tp_pct)


def _check_open(closes_1m, highs_1m, lows_1m, closes_10m, closes_15m,
                closes_4h, highs_15m, lows_15m, i, cfg):
    if i < 500:
        return False

    # ---- 1m: Turtle + SuperTrend (окно 500) ----
    start_1m = max(0, i - ST_WINDOW + 1)
    w = closes_1m[start_1m:i + 1]
    wh = highs_1m[start_1m:i + 1]
    wl = lows_1m[start_1m:i + 1]

    tl_lower, _ = turtle_zone(wh, wl, w,
                              cfg.get("turtle_lower_period", 200),
                              cfg.get("turtle_lower_mult", 5.6))
    st_1m_val, st_1m_dir = supertrend(wh, wl, w,
                                       cfg.get("st_1m_period", 100),
                                       cfg.get("st_1m_mult", 3.0))

    # ---- 10m RSI (окно 100) ----
    idx_10m = min(i // 10, len(closes_10m) - 1)
    if idx_10m < 15:
        return False
    start_10m = max(0, idx_10m - RSI_WINDOW + 1)
    r_10m = rsi(closes_10m[start_10m:idx_10m + 1],
                cfg.get("rsi_10m_period", 9))

    # ---- 4h ROC (окно 200) ----
    idx_4h = min(i // 240, len(closes_4h) - 1)
    if idx_4h < 110:
        return False
    start_4h = max(0, idx_4h - ROC_WINDOW + 1)
    r_4h = roc(closes_4h[start_4h:idx_4h + 1],
               cfg.get("roc_4h_period", 100))

    # ---- 15m SuperTrend (окно 500) ----
    idx_15m = min(i // 15, len(closes_15m) - 1)
    if idx_15m < 15:
        return False
    start_15m = max(0, idx_15m - ST_WINDOW + 1)
    st_15m_val, st_15m_dir = supertrend(
        highs_15m[start_15m:idx_15m + 1],
        lows_15m[start_15m:idx_15m + 1],
        closes_15m[start_15m:idx_15m + 1],
        cfg.get("st_15m_period", 10),
        cfg.get("st_15m_mult", 3.0))

    price = closes_1m[i]

    # Group 1
    g1 = (r_10m < cfg.get("rsi_10m_threshold", 40) and
          tl_lower > 0 and price < tl_lower and
          r_4h < cfg.get("roc_4h_threshold", -0.5) and
          st_1m_dir == -1 and price < st_1m_val)

    # Group 2
    g2 = (tl_lower > 0 and price < tl_lower and
          st_15m_dir == -1 and closes_15m[idx_15m] < st_15m_val)

    return g1 or g2


def _check_close(closes_1m, closes_2m, closes_15m, highs_15m, lows_15m,
                 i, cfg, avg_entry, current_price):
    # Закрываем только в плюсе
    if current_price <= avg_entry:
        return False, ""
    pnl_pct = (current_price / avg_entry - 1) * 100
    if pnl_pct < 0.4:
        return False, ""

    # Проверяем раз в 5 баров (не чаще)
    if i % 5 != 0:
        return False, ""

    # ---- MACD 2m (окно 200) ----
    idx_2m = min(i // 2, len(closes_2m) - 1)
    if idx_2m >= 30:
        start_2m = max(0, idx_2m - 200 + 1)
        m_line, m_sig = macd(closes_2m[start_2m:idx_2m + 1],
                              cfg.get("macd_2m_fast", 12),
                              cfg.get("macd_2m_slow", 26),
                              cfg.get("macd_2m_signal", 9))
        if m_line < m_sig and (m_sig - m_line) > 0.0001:
            return True, "CLOSE_MACD"

    # ---- ROC 1m (окно 200) ----
    if i >= 100:
        start_1m = max(0, i - 200 + 1)
        r_1m = roc(closes_1m[start_1m:i + 1],
                   cfg.get("roc_1m_period", 100))
        if r_1m > cfg.get("roc_1m_threshold", 1.0):
            return True, "CLOSE_ROC"

    # ---- Turtle Upper 15m (окно 500) ----
    idx_15m = min(i // 15, len(closes_15m) - 1)
    if idx_15m >= 15:
        start_15m = max(0, idx_15m - 500 + 1)
        _, tu = turtle_zone(
            highs_15m[start_15m:idx_15m + 1],
            lows_15m[start_15m:idx_15m + 1],
            closes_15m[start_15m:idx_15m + 1],
            cfg.get("turtle_upper_15m_period", 200),
            cfg.get("turtle_upper_15m_mult", 5.6))
        if tu > 0 and closes_1m[i] > tu:
            return True, "CLOSE_TURTLE_UPPER"

    return False, ""


def _close(position, exec_price, reason, trades, fee):
    avg = position["avg_entry"]
    size = position["total_size"]
    if size <= 0:
        return
    gross = (exec_price - avg) * size
    fees = (exec_price + avg) * size * fee
    pnl = gross - fees
    notional = avg * size
    pnl_pct = (pnl / notional * 100) if notional else 0
    trades.append({
        "entry": avg, "exit": exec_price, "amount": size,
        "notional": notional, "pnl": pnl, "pnl_pct": pnl_pct,
        "reason": reason,
        "filled_count": sum(1 for o in position["orders"] if o["filled"])})


def _metrics(initial, final, equity, trades, days, leverage, timeframe,
             fee, slip_pct, gd, gv, min_tp):
    wins = [t for t in trades if t["pnl"] > 0]
    losses = [t for t in trades if t["pnl"] <= 0]
    total = sum(t["pnl"] for t in trades)
    gw = sum(t["pnl"] for t in wins)
    gl = abs(sum(t["pnl"] for t in losses))

    def max_dd(eq):
        if not eq:
            return 0.0
        peak = eq[0]
        mdd = 0.0
        for e in eq:
            peak = max(peak, e)
            if peak <= 0:
                continue
            mdd = max(mdd, (peak - e) / peak * 100)
        return mdd

    def sharpe_fn(eq):
        if len(eq) < 3:
            return 0.0
        rets = [eq[i] / eq[i - 1] - 1
                for i in range(1, len(eq)) if eq[i - 1] > 0]
        if len(rets) < 2:
            return 0.0
        mean = sum(rets) / len(rets)
        var = sum((r - mean) ** 2 for r in rets) / (len(rets) - 1)
        sd = var ** 0.5
        return (mean / sd) * (24 * 365) ** 0.5 if sd > 0 else 0.0

    avg_filled = (sum(t.get("filled_count", 1) for t in trades) / len(trades)
                  if trades else 0)
    total_fees = sum(t["notional"] * fee * 2 for t in trades)

    return {
        "period_days": days, "leverage": leverage, "timeframe": timeframe,
        "initial_balance": round(initial, 2),
        "final_equity": round(final, 2),
        "total_return_pct": round((final / initial - 1) * 100, 3),
        "max_drawdown_pct": round(max_dd(equity), 2),
        "sharpe": round(sharpe_fn(equity), 3),
        "total_trades": len(trades),
        "wins": len(wins), "losses": len(losses),
        "tp_count": len([t for t in trades if t.get("reason") == "TP"]),
        "close_signal_count": len([t for t in trades
                                    if str(t.get("reason", ""))
                                    .startswith("CLOSE_")]),
        "eod_count": len([t for t in trades if t.get("reason") == "EOD"]),
        "win_rate": round(len(wins) / len(trades) * 100, 2) if trades else 0.0,
        "avg_win": round(gw / len(wins), 6) if wins else 0.0,
        "avg_loss": round(-gl / len(losses), 6) if losses else 0.0,
        "profit_factor": round(gw / gl, 2) if gl > 0 else 999.99,
        "expectancy": round(total / len(trades), 6) if trades else 0.0,
        "total_pnl": round(total, 4),
        "avg_filled_orders": round(avg_filled, 2),
        "costs_total": round(total_fees, 2),
    }