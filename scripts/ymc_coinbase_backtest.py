"""One-day Coinbase BTC-USD 1m research run; no orders or API credentials.

Run: python scripts/ymc_coinbase_backtest.py
Outputs a JSON summary; spot direction is not Kalshi P&L.
"""
import json
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from backend.btcmarket.ymc_outcomes import evaluate_history, summarize


def download_closed_minutes(minutes=1440):
    # Two-minute buffer prevents Coinbase's latest incomplete candle entering research.
    end = (int(time.time()) // 60 - 2) * 60
    start = end - minutes * 60
    by_time = {}
    for beginning in range(start, end, 300 * 60):
        finish = min(beginning + 300 * 60, end)
        params = urlencode({
            "start": datetime.fromtimestamp(beginning, timezone.utc).isoformat(),
            "end": datetime.fromtimestamp(finish, timezone.utc).isoformat(),
            "granularity": 60,
        })
        request = Request(
            "https://api.exchange.coinbase.com/products/BTC-USD/candles?" + params,
            headers={"User-Agent": "YMC-Research/1.0", "Accept": "application/json"},
        )
        with urlopen(request, timeout=25) as response:
            data = json.load(response)
        for t, low, high, opening, close, volume in data:
            t = int(t)
            if start <= t < end:
                by_time[t] = {"time": t, "open": opening, "high": high,
                              "low": low, "close": close, "volume": volume}
        time.sleep(0.3)
    return [by_time[t] for t in sorted(by_time)]


if __name__ == "__main__":
    candles = download_closed_minutes()
    results = evaluate_history(candles)
    print(json.dumps({
        "source": "Coinbase BTC-USD 1m closed candles",
        "downloaded_candles": len(candles),
        "observed_start_utc": datetime.fromtimestamp(candles[0]["time"], timezone.utc).isoformat() if candles else None,
        "observed_end_utc": datetime.fromtimestamp(candles[-1]["time"] + 60, timezone.utc).isoformat() if candles else None,
        "horizons": summarize(results),
        "warning": "Overlapping in-sample signals; exploratory only, not out-of-sample accuracy or Kalshi returns",
    }, indent=2))
