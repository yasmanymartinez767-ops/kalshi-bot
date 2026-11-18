"""Collect real, timestamped Kalshi BTC15M top-of-book quotes for research.

Read-only. No orders. A sample is NOT a validated predictive signal.
"""
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

URL = "https://api.elections.kalshi.com/trade-api/v2/markets"
INTERVAL = max(3, int(os.getenv("YMC_SAMPLE_INTERVAL_SECONDS", "5")))
DURATION = min(840, max(10, int(os.getenv("YMC_SAMPLE_DURATION_SECONDS", "180"))))
OUTPUT = os.getenv("YMC_SAMPLE_OUTPUT", "kalshi_btc15m_live_quotes.jsonl")


def collect():
    started = time.monotonic()
    count = 0
    tickers = set()
    with open(OUTPUT, "w", encoding="utf-8") as output:
        while time.monotonic() - started < DURATION:
            at = datetime.now(timezone.utc)
            row = {"observed_at_utc": at.isoformat(), "source": "kalshi_public_api"}
            try:
                query = urlencode({"series_ticker": "KXBTC15M", "status": "open", "limit": 10})
                req = Request(URL + "?" + query, headers={"User-Agent": "YMC-ReadOnly-Research/1.0", "Accept": "application/json"})
                with urlopen(req, timeout=15) as response:
                    markets = json.load(response).get("markets", [])
                active = [m for m in markets if str(m.get("ticker", "")).startswith("KXBTC15M")]
                if active:
                    m = active[0]
                    row.update({"ticker": m.get("ticker"), "close_time": m.get("close_time"),
                                "yes_bid": m.get("yes_bid_dollars"), "yes_ask": m.get("yes_ask_dollars"),
                                "no_bid": m.get("no_bid_dollars"), "no_ask": m.get("no_ask_dollars")})
                    tickers.add(m.get("ticker"))
                else:
                    row["warning"] = "No open KXBTC15M market"
            except Exception as exc:
                row["error"] = str(exc)
            output.write(json.dumps(row, separators=(",", ":")) + "\n")
            output.flush()
            count += 1
            remaining = DURATION - (time.monotonic() - started)
            if remaining > 0:
                time.sleep(min(INTERVAL, remaining))
    print(json.dumps({"observations": count, "unique_contracts": len(tickers),
                      "file": OUTPUT, "orders_placed": 0, "predictive_accuracy_validated": False}))
    if not tickers:
        raise RuntimeError("No real Kalshi BTC15M contracts captured")


if __name__ == "__main__":
    collect()
