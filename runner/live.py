# runner/live.py
import asyncio
import logging
import time

from config.loader import CONFIG
from core.logger import C, USE_COLOR
from exchange.ccxt_client import CCXTClient
from exchange.paper import PaperClient
from exchange.symbols import to_swap
from trading.manager import TradingManager
from websocket import WSManager

logger = logging.getLogger(__name__)


WATCHLIST = [
    {"exchange": "binance", "symbol": "TAO/USDT",
     "market_type": "swap", "leverage": 2},
    {"exchange": "binance", "symbol": "ARB/USDT",
     "market_type": "swap", "leverage": 2},
    {"exchange": "binance", "symbol": "XRP/USDT",
     "market_type": "swap", "leverage": 2},
    {"exchange": "binance", "symbol": "NEAR/USDT",
     "market_type": "swap", "leverage": 2},
    {"exchange": "binance", "symbol": "UNI/USDT",
     "market_type": "swap", "leverage": 2},
]


def _banner(paper, watchlist):
    mode = "PAPER" if paper else "LIVE"
    if USE_COLOR:
        print(f"{C.BRIGHT_CYAN}{'=' * 60}{C.RESET}")
        print(f"  Grid Bot — {C.BOLD}{mode}{C.RESET}")
        print(f"  Watching {len(watchlist)} pairs")
        print(f"{C.BRIGHT_CYAN}{'=' * 60}{C.RESET}")
    else:
        print("=" * 60)
        print(f"  Grid Bot — {mode}")
        print(f"  Watching {len(watchlist)} pairs")
        print("=" * 60)


def run_live(paper=None):
    if paper is None:
        paper = CONFIG.trading.get("paper_trading", True)
    asyncio.run(_run(paper))


async def _run(paper):
    _banner(paper, WATCHLIST)

    # 1. Exchange client
    real = CCXTClient()
    if paper:
        balance = CONFIG.trading.get("test_balance", 50.0)
        client = PaperClient(real, initial_balance=balance)
        logger.warning(f"PAPER TRADING — balance ${balance:.2f}")
    else:
        client = real
        logger.warning("LIVE TRADING — real orders!")

    # 2. Trading manager
    tm = TradingManager(client)

    # 3. WebSocket manager
    ws = WSManager()

    # 4. Подписка на все пары из watchlist
    async def make_cb(exch, sym):
        async def cb(snap):
            price = snap["price"]
            # Каждый тик — проверяем открытые позиции
            events = await asyncio.to_thread(
                tm.on_price, exch, sym, price)
            for ev in events:
                _log_event(ev)
        return cb

    for item in WATCHLIST:
        exch = item["exchange"]
        pair = item["symbol"]
        if exch not in ("binance", "bybit", "okx", "bingx"):
            continue
        # WS-символ без :USDT
        ws_symbol = to_swap(pair)
        try:
            await ws.subscribe(exch, ws_symbol)
            ws.add_callback(exch, ws_symbol, await make_cb(exch, pair))
            logger.info(f"WS: подписан на {exch}:{pair}")
        except Exception as e:
            logger.warning(f"WS subscribe {pair}: {e}")

    # Даём WS время на установку
    await asyncio.sleep(3)

    # 5. Основной цикл — скан сигналов + heartbeat
    scan_interval = CONFIG.trading.get("scan_interval_sec", 60)
    poll_interval = CONFIG.trading.get("poll_interval_sec", 5)
    last_scan = 0
    last_status = 0

    try:
        while True:
            now = time.time()

            if now - last_scan >= scan_interval:
                await _scan_signals(client, tm)
                last_scan = now

            if now - last_status >= 60:
                _print_status(ws, tm)
                last_status = now

            await asyncio.sleep(poll_interval)

    except asyncio.CancelledError:
        pass
    finally:
        await ws.shutdown()


async def _scan_signals(client, tm):
    """Скан сигналов на открытие по watchlist."""
    open_symbols = {p["symbol"] for p in tm.get_open()}

    for item in WATCHLIST:
        pair = item["symbol"]
        if pair in open_symbols:
            continue

        exch = item["exchange"]
        mt = item["market_type"]
        lev = item["leverage"]
        symbol = to_swap(pair)

        ohlcv = await asyncio.to_thread(
            client.get_ohlcv, exch, symbol, "1m", 1000, None, mt)
        if not ohlcv or len(ohlcv) < 300:
            continue

        result = await asyncio.to_thread(
            tm.open_by_signal,
            exch, pair, ohlcv, mt, lev, 0, None)
        if result.get("ok"):
            _log_open(result["position"])


def _log_open(pos):
    msg = (f"OPEN #{pos['id']} {pos['side'].upper()} {pos['symbol']} "
           f"@ {pos['entry_price']:.6f} TP={pos['tp_price']:.6f}")
    if USE_COLOR:
        print(f"{C.BRIGHT_GREEN}▶ {msg}{C.RESET}")
    else:
        print(msg)


def _log_event(ev):
    pos = ev["position"]
    if ev["type"] == "tp":
        msg = f"TP #{pos['id']} {pos['symbol']} @ {ev['price']:.6f}"
        if USE_COLOR:
            print(f"{C.BRIGHT_GREEN}✓ {msg}{C.RESET}")
        else:
            print(msg)


def _print_status(ws, tm):
    """Периодический статус в консоль."""
    prices = len(ws.prices)
    positions = len(tm.get_open())
    if USE_COLOR:
        print(f"{C.DIM}[status] WS:{prices} positions:{positions}{C.RESET}")
    else:
        print(f"[status] WS:{prices} positions:{positions}")
