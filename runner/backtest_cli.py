# runner/backtest_cli.py
import asyncio
from config.loader import CONFIG
from exchange.ccxt_client import CCXTClient
from exchange.symbols import to_swap
from backtest.loader import DataLoader
from backtest.grid_sim import simulate_grid


def run_backtest(pair, days, leverage, balance, exchange):
    WARMUP = 20
    symbol = to_swap(pair)
    client = CCXTClient()
    loader = DataLoader(client, symbol, "1m")

    print(f"\n{'=' * 60}")
    print(f"  Grid Backtest: {pair} | {days}d + {WARMUP}d warmup")
    print(f"  Exchange: {exchange} | Lev: {leverage}x | Bal: ${balance}")
    print(f"{'=' * 60}\n")

    async def _fetch():
        return await loader.fetch(exchange, days=WARMUP + days,
                                   market_type="swap")

    try:
        candles = asyncio.run(_fetch())
    except Exception as e:
        print(f"Fetch error: {e}")
        return

    if not candles or len(candles) < 500:
        print(f"Мало свечей: {len(candles) if candles else 0}")
        return

    print(f"Свечей: {len(candles)}")

    fee = CONFIG.trading.get("fee_per_side", 0.0005)
    slip = CONFIG.trading.get("slippage", 0.0002)
    r = simulate_grid(candles, days, balance, leverage, "1m", fee, slip)

    print(f"\n{'=' * 60}")
    print(f"  РЕЗУЛЬТАТ")
    print(f"{'=' * 60}")
    print(f"  Старт:        ${r['initial_balance']}")
    print(f"  Итог:         ${r['final_equity']}")
    print(f"  Доходность:   {r['total_return_pct']:+.3f}%")
    print(f"  Net PnL:      ${r['total_pnl']:+.4f}")
    print(f"  DD:           -{r['max_drawdown_pct']:.2f}%")
    print(f"  Sharpe:       {r['sharpe']}")
    print(f"  Сделок:       {r['total_trades']}")
    print(f"  Win Rate:     {r['win_rate']}%")
    print(f"  AvgWin:       ${r['avg_win']:+.4f}")
    print(f"  AvgLoss:      ${r['avg_loss']:+.4f}")
    print(f"  PF:           {r['profit_factor']}")
    print(f"  Expectancy:   ${r['expectancy']:+.4f}")
    print(f"  TP/CLOSE/EOD: {r['tp_count']}/{r['close_signal_count']}/{r['eod_count']}")
    print(f"  Avg filled:   {r['avg_filled_orders']}")
    print(f"  Costs:        ${r['costs_total']}")
    print(f"{'=' * 60}\n")
