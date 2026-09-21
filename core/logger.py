# core/logger.py
import logging
import os
import sys


class C:
    RESET = "\033[0m"; BOLD = "\033[1m"; DIM = "\033[2m"
    RED = "\033[31m"; GREEN = "\033[32m"; YELLOW = "\033[33m"
    CYAN = "\033[36m"
    BRIGHT_RED = "\033[91m"; BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"; BRIGHT_CYAN = "\033[96m"
    BRIGHT_MAGENTA = "\033[95m"


def _supports_color():
    if os.environ.get("NO_COLOR"):
        return False
    if not hasattr(sys.stdout, "isatty") or not sys.stdout.isatty():
        return False
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.kernel32.SetConsoleMode(
                ctypes.windll.kernel32.GetStdHandle(-11), 7)
        except Exception:
            pass
    return True


USE_COLOR = _supports_color()

STYLE = {
    "DEBUG":    (C.DIM + C.CYAN, "DBG"),
    "INFO":     (C.BRIGHT_GREEN, "INF"),
    "WARNING":  (C.BRIGHT_YELLOW, "WRN"),
    "ERROR":    (C.BRIGHT_RED, "ERR"),
    "CRITICAL": (C.BOLD + C.BRIGHT_MAGENTA, "CRT"),
}


class Formatter(logging.Formatter):
    def format(self, record):
        ts = self.formatTime(record, "%H:%M:%S")
        color, tag = STYLE.get(record.levelname, ("", record.levelname[:3]))
        short = record.name.split(".")[-1] if record.name else "-"
        msg = record.getMessage()
        if not USE_COLOR:
            return f"{ts} {tag} [{short}] {msg}"
        return (f"{C.DIM}{ts}{C.RESET} {color}{tag}{C.RESET} "
                f"[{C.BRIGHT_CYAN}{short}{C.RESET}] {msg}")


def setup_logging(level=logging.INFO, log_file=None):
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(Formatter())
    root.addHandler(ch)
    if log_file:
        fh = logging.FileHandler(log_file, encoding="utf-8")
        fh.setFormatter(logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
        root.addHandler(fh)
    for noisy in ("httpx", "httpcore", "ccxt.base.exchange",
                  "urllib3", "websockets.client", "websockets.protocol"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return root
