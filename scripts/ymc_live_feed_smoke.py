"""Read-only public live-feed smoke test. No credentials, orders or DB writes."""
import json
from datetime import datetime, timezone
from urllib.request import Request, urlopen


def fetch(url):
    with urlopen(Request(url, headers={"User-Agent": "YMC-Live-Smoke/1.0", "Accept": "application/json"}), timeout=20) as response:
        return json.load(response)


def main():
    now = datetime.now(timezone.utc)
    result = {"checked_at_utc": now.isoformat(), "orders_placed": 0}
    candles = fetch("https://api.exchange.coinbase.com/products/BTC-USD/candles?granularity=60")
    closed = [row for row in candles if int(row[0]) + 60 <= now.timestamp() - 30]
    if not closed:
        raise RuntimeError("Coinbase: no safely closed BTC-USD minute candles")
    latest = max(closed, key=lambda row: row[0])
    age = now.timestamp() - (latest[0] + 60)
    result["coinbase"] = {"closed_candle_age_seconds": round(age), "close_usd": latest[4], "ok": age <= 180}
    if not result["coinbase"]["ok"]:
        raise RuntimeError("Coinbase closed candle stale")
    try:
        market_data = fetch("https://api.elections.kalshi.com/trade-api/v2/markets?series_ticker=KXBTC15M&status=open&limit=10")
        markets = market_data.get("markets", [])
        active = [m for m in markets if m.get("ticker", "").startswith("KXBTC15M")]
        result["kalshi"] = {"markets_returned": len(markets), "matching_contracts": len(active)}
        if active:
            m = active[0]
            result["kalshi"].update({"ticker": m.get("ticker"), "yes_bid": m.get("yes_bid_dollars"), "yes_ask": m.get("yes_ask_dollars"), "close_time": m.get("close_time")})
        else:
            result["kalshi"]["warning"] = "No open KXBTC15M contract returned"
    except Exception as exc:
        result["kalshi"] = {"error": str(exc)}
    print(json.dumps(result, indent=2))
    if not result["kalshi"].get("matching_contracts"):
        raise RuntimeError("Kalshi active BTC 15m contract not confirmed")


if __name__ == "__main__":
    main()
