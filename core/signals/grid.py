# core/signals/grid.py
import logging
from config.loader import CONFIG
from core.indicators import rsi, turtle_zone, supertrend, roc, macd
from core.resample import resample

logger = logging.getLogger(__name__)


class GridSignal:

    def __init__(self):
        cfg = CONFIG.grid
        self.grid_distances = cfg.get("grid_distances",
                                       [0.0, -2.0, -4.0, -5.0, -10.0])
        self.grid_volumes = cfg.get("grid_volumes", [10, 10, 20, 20, 40])
        self.min_tp_pct = cfg.get("min_tp_pct", 0.8)
        self.turtle_lower_period = cfg.get("turtle_lower_period", 200)
        self.turtle_lower_mult = cfg.get("turtle_lower_mult", 5.6)
        self.st_1m_period = cfg.get("st_1m_period", 100)
        self.st_1m_mult = cfg.get("st_1m_mult", 3.0)
        self.rsi_10m_period = cfg.get("rsi_10m_period", 9)
        self.rsi_10m_threshold = cfg.get("rsi_10m_threshold", 40)
        self.roc_4h_period = cfg.get("roc_4h_period", 100)
        self.roc_4h_threshold = cfg.get("roc_4h_threshold", -0.5)
        self.st_15m_period = cfg.get("st_15m_period", 10)
        self.st_15m_mult = cfg.get("st_15m_mult", 3.0)
        self.roc_1m_period = cfg.get("roc_1m_period", 100)
        self.roc_1m_threshold = cfg.get("roc_1m_threshold", 1.0)
        self.turtle_upper_15m_period = cfg.get("turtle_upper_15m_period", 200)
        self.turtle_upper_15m_mult = cfg.get("turtle_upper_15m_mult", 5.6)
        self.macd_2m_fast = cfg.get("macd_2m_fast", 12)
        self.macd_2m_slow = cfg.get("macd_2m_slow", 26)
        self.macd_2m_signal = cfg.get("macd_2m_signal", 9)

    def compute(self, ohlcv_1m, direction="long"):
        if len(ohlcv_1m) < 300:
            return None
        c_10m = resample(ohlcv_1m, 10)
        c_15m = resample(ohlcv_1m, 15)
        c_4h = resample(ohlcv_1m, 240)
        if len(c_10m) < 15 or len(c_15m) < 15 or len(c_4h) < 110:
            return None

        price = ohlcv_1m[-1][4]
        highs_1m = [c[2] for c in ohlcv_1m]
        lows_1m = [c[3] for c in ohlcv_1m]
        closes_1m = [c[4] for c in ohlcv_1m]
        closes_10m = [c[4] for c in c_10m]
        closes_15m = [c[4] for c in c_15m]
        highs_15m = [c[2] for c in c_15m]
        lows_15m = [c[3] for c in c_15m]
        closes_4h = [c[4] for c in c_4h]

        tl_lower, _ = turtle_zone(highs_1m, lows_1m, closes_1m,
                                   self.turtle_lower_period,
                                   self.turtle_lower_mult)
        st_1m_val, st_1m_dir = supertrend(highs_1m, lows_1m, closes_1m,
                                           self.st_1m_period, self.st_1m_mult)
        st_15m_val, st_15m_dir = supertrend(highs_15m, lows_15m, closes_15m,
                                             self.st_15m_period, self.st_15m_mult)
        r_10m = rsi(closes_10m, self.rsi_10m_period)
        r_4h = roc(closes_4h, self.roc_4h_period)

        base = {"side": None, "entry": price, "tp": 0.0, "reason": ""}
        g1 = (r_10m < self.rsi_10m_threshold and
              tl_lower > 0 and price < tl_lower and
              r_4h < self.roc_4h_threshold and
              st_1m_dir == -1 and price < st_1m_val)
        g2 = (tl_lower > 0 and price < tl_lower and
              st_15m_dir == -1 and closes_15m[-1] < st_15m_val)

        if not (g1 or g2):
            base["reason"] = (f"no_signal rsi={r_10m:.1f} "
                              f"roc4h={r_4h:.2f}")
            return base

        grid_orders = []
        for i, (dist_pct, vol) in enumerate(zip(self.grid_distances,
                                                 self.grid_volumes)):
            grid_orders.append({
                "level": i,
                "price": round(price * (1 + dist_pct / 100), 8),
                "volume_pct": vol,
                "filled": i == 0,
            })

        base["side"] = "buy"
        base["entry"] = price
        base["grid_orders"] = grid_orders
        base["min_tp_pct"] = self.min_tp_pct
        base["tp"] = price * 1.05
        base["reason"] = (f"GRID LONG rsi={r_10m:.1f} roc4h={r_4h:.2f}")
        return base

    def close_signal(self, ohlcv_1m):
        if len(ohlcv_1m) < 300:
            return False, ""
        c_2m = resample(ohlcv_1m, 2)
        c_15m = resample(ohlcv_1m, 15)
        if len(c_2m) < 30 or len(c_15m) < 15:
            return False, ""
        closes_1m = [c[4] for c in ohlcv_1m]
        closes_2m = [c[4] for c in c_2m]
        closes_15m = [c[4] for c in c_15m]
        highs_15m = [c[2] for c in c_15m]
        lows_15m = [c[3] for c in c_15m]

        m_line, m_sig = macd(closes_2m, self.macd_2m_fast,
                             self.macd_2m_slow, self.macd_2m_signal)
        if m_line < m_sig:
            return True, "CLOSE_MACD"
        r_1m = roc(closes_1m, self.roc_1m_period)
        if r_1m > self.roc_1m_threshold:
            return True, "CLOSE_ROC"
        _, tu_upper = turtle_zone(highs_15m, lows_15m, closes_15m,
                                   self.turtle_upper_15m_period,
                                   self.turtle_upper_15m_mult)
        if tu_upper > 0 and closes_1m[-1] > tu_upper:
            return True, "CLOSE_TURTLE_UPPER"
        return False, ""
