# main.py
import argparse
import logging
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.logger import setup_logging


def main():
    parser = argparse.ArgumentParser(description="Crypto Grid Bot")
    parser.add_argument("mode", choices=["live", "backtest"])
    parser.add_argument("--pair", default="TAO/USDT")
    parser.add_argument("--days", type=int, default=5)
    parser.add_argument("--leverage", type=int, default=2)
    parser.add_argument("--balance", type=float, default=50.0)
    parser.add_argument("--exchange", default="binance")
    parser.add_argument("--paper", action="store_true")

    args = parser.parse_args()
    setup_logging(level=logging.INFO, log_file="bot.log")

    if args.mode == "backtest":
        from runner.backtest_cli import run_backtest
        run_backtest(
            pair=args.pair, days=args.days,
            leverage=args.leverage, balance=args.balance,
            exchange=args.exchange)
    else:
        from runner.live import run_live
        paper = args.paper or None
        run_live(paper=paper)


if __name__ == "__main__":
    main()
