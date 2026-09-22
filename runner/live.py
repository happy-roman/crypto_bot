# runner/live.py
"""Live-трейдинг через REST-поллинг цен (WS не нужен)."""
import asyncio
import logging
import time

from config.loader import CONFIG
from core.logger import C, USE_COLOR
from exchange.ccxt_client import CCXTClient
from exchange.paper import PaperClient
from exchange.symbols import to_swap
from trading.manager import TradingManager

logger = logging.getLogger(__name__)


WATCHLIST = [
    {"exchange": "bingx", "symbol": "TAO/USDT",
     "market_type": "swap", "leverage": 2},
    {"exchange": "bingx", "symbol": "ARB/USDT",
     "market_type": "swap", "leverage": 2},
    {"exchange": "bingx", "symbol": "XRP/USDT",
     "market_type": "swap", "leverage": 2},
    {"exchange": "bingx", "symbol": "NEAR/USDT",
     "market_type": "swap", "leverage": 2},
    {"exchange": "bingx", "symbol": "UNI/USDT",
     "market_type": "swap", "leverage": 2},
]


def _banner(paper, watchlist):
    mode = "PAPER" if paper else "LIVE"
    if USE_COLOR:
        print(f"{C.BRIGHT_CYAN}{'=' * 60}{C.RESET}")
        print(f"  Grid Bot — {C.BOLD}{mode}{C.RESET}")
        print(f"  Exchange: {watchlist[0]['exchange'] if watchlist else '?'}")
        print(f"  Watching {len(watchlist)} pairs (REST polling)")
        print(f"{C.BRIGHT_CYAN}{'=' * 60}{C.RESET}")
    else:
        print("=" * 60)
        print(f"  Grid Bot — {mode}")
        print(f"  Watching {len(watchlist)} pairs (REST polling)")
        print("=" * 60)


def run_live(paper=None):
    if paper is None:
        paper = CONFIG.trading.get("paper_trading", True)
    asyncio.run(_run(paper))


async def _run(paper):
    _banner(paper, WATCHLIST)

    real = CCXTClient()
    if paper:
        balance = CONFIG.trading.get("test_balance", 50.0)
        client = PaperClient(real, initial_balance=balance)
        logger.warning(f"PAPER TRADING — balance ${balance:.2f}")
    else:
        client = real
        logger.warning("LIVE TRADING — real orders!")

    tm = TradingManager(client)

    scan_interval = CONFIG.trading.get("scan_interval_sec", 60)
    poll_interval = CONFIG.trading.get("poll_interval_sec", 3)

    # Прогрев ccxt — грузим markets заранее
    await asyncio.to_thread(
        client._ensure_markets, "bingx", "swap")
    logger.info("Markets загружены, начинаю работу")

    last_scan = 0
    last_status = 0

    try:
        while True:
            now = time.time()

            # === Поллинг цен + проверка позиций ===
            await _poll_prices(client, tm, WATCHLIST)

            # === Скан сигналов раз в scan_interval ===
            if now - last_scan >= scan_interval:
                await _scan_signals(client, tm)
                last_scan = now

            # === Статус раз в 60 сек ===
            if now - last_status >= 60:
                _print_status(tm)
                last_status = now

            await asyncio.sleep(poll_interval)

    except asyncio.CancelledError:
        pass


async def _poll_prices(client, tm, watchlist):
    """Один тик: опрос цен и проверка позиций."""
    for item in watchlist:
        exch = item["exchange"]
        pair = item["symbol"]
        mt = item["market_type"]
        symbol = to_swap(pair)

        try:
            ticker = await asyncio.to_thread(
                client.get_ticker, exch, symbol, mt)
        except Exception as e:
            logger.debug(f"ticker {symbol}: {e}")
            continue

        if not ticker or not ticker.get("last"):
            continue

        try:
            price = float(ticker["last"])
        except (TypeError, ValueError):
            continue

        try:
            events = await asyncio.to_thread(
                tm.on_price, exch, pair, price)
            for ev in events:
                _log_event(ev)
        except Exception as e:
            logger.error(f"on_price {pair}: {e}")


async def _scan_signals(client, tm):
    open_symbols = {p["symbol"] for p in tm.get_open()}

    for item in WATCHLIST:
        pair = item["symbol"]
        if pair in open_symbols:
            continue

        exch = item["exchange"]
        mt = item["market_type"]
        lev = item["leverage"]
        symbol = to_swap(pair)

        try:
            ohlcv = await asyncio.to_thread(
                client.get_ohlcv, exch, symbol, "1m", 1000, None, mt)
        except Exception as e:
            logger.warning(f"ohlcv {pair}: {e}")
            continue

        if not ohlcv or len(ohlcv) < 300:
            continue

        try:
            result = await asyncio.to_thread(
                tm.open_by_signal,
                exch, pair, ohlcv, mt, lev, 0, None)
        except Exception as e:
            logger.error(f"open_by_signal {pair}: {e}")
            continue

        if result.get("ok"):
            _log_open(result["position"])


def _log_open(pos):
    msg = (f"OPEN #{pos['id']} {pos['side'].upper()} {pos['symbol']} "
           f"@ {pos['entry_price']:.6f} TP={pos['tp_price']:.6f}")
    if USE_COLOR:
        print(f"{C.BRIGHT_GREEN}▶ {msg}{C.RESET}", flush=True)
    else:
        print(msg, flush=True)


def _log_event(ev):
    pos = ev["position"]
    if ev["type"] == "tp":
        msg = f"TP #{pos['id']} {pos['symbol']} @ {ev['price']:.6f}"
        if USE_COLOR:
            print(f"{C.BRIGHT_GREEN}✓ {msg}{C.RESET}", flush=True)
        else:
            print(msg, flush=True)


def _print_status(tm):
    positions = len(tm.get_open())
    if USE_COLOR:
        print(f"{C.DIM}[status] positions:{positions}{C.RESET}", flush=True)
    else:
        print(f"[status] positions:{positions}", flush=True)