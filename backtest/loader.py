# backtest/loader.py
import asyncio
import time


class DataLoader:

    def __init__(self, client, symbol, timeframe="1m"):
        self.client = client
        self.symbol = symbol
        self.timeframe = timeframe

    @staticmethod
    def _tf_ms(tf):
        units = {"m": 60_000, "h": 3_600_000, "d": 86_400_000}
        return int(tf[:-1]) * units.get(tf[-1], 60_000)

    async def fetch(self, exchange_name, days, market_type="swap",
                    max_iter=120):
        tf_ms = self._tf_ms(self.timeframe)
        since = int(time.time() * 1000 - days * 86_400_000)
        all_candles = []
        for _ in range(max_iter):
            batch = await asyncio.to_thread(
                self.client.get_ohlcv, exchange_name, self.symbol,
                self.timeframe, 1000, since, market_type)
            if not batch:
                break
            all_candles.extend(batch)
            since = batch[-1][0] + tf_ms
            if len(batch) < 1000:
                break
            if since >= time.time() * 1000:
                break
        seen = set()
        unique = []
        for c in all_candles:
            if c[0] in seen:
                continue
            seen.add(c[0])
            unique.append(c)
        unique.sort(key=lambda x: x[0])
        return unique
