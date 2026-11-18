"""Run Kalshi bid-drop research against persisted real KXBTC15M snapshots.

Usage: python -m scripts.ymc_kalshi_exit_research
No order placement. Requires a configured database with recorded snapshots.
"""
import json
import os
from datetime import datetime, timedelta, timezone

from backend.btcmarket.early_exit_research import evaluate_bid_drop_alerts
from backend.models.database import KxBtcSnapshot, SessionLocal


def main():
    days = max(1, min(int(os.getenv("YMC_EXIT_LOOKBACK_DAYS", "7")), 30))
    cutoff = datetime.utcnow() - timedelta(days=days)
    db = SessionLocal()
    try:
        rows = (db.query(KxBtcSnapshot)
                .filter(KxBtcSnapshot.timestamp >= cutoff)
                .order_by(KxBtcSnapshot.timestamp.asc()).all())
        snapshots = [{
            "ticker": row.ticker,
            "time": int(row.timestamp.replace(tzinfo=timezone.utc).timestamp()),
            "close_time": row.close_time,
            "yes_bid": row.yes_bid,
            "no_bid": row.no_bid,
        } for row in rows]
    finally:
        db.close()
    yes = evaluate_bid_drop_alerts(snapshots, side="YES")
    no = evaluate_bid_drop_alerts(snapshots, side="NO")
    # Keep output compact; individual ticker diagnostics stay available in Python.
    yes.pop("rows", None)
    no.pop("rows", None)
    result = {
        "source": "persisted_kalshi_kxbtc15m_quotes",
        "lookback_days": days,
        "snapshots": len(snapshots),
        "unique_contracts": len({r["ticker"] for r in snapshots}),
        "yes": yes,
        "no": no,
        "method": "first three-quote drop per contract; compare next bid at 60-90s; exclude expiry",
        "limitation": "Alert success means a further decline, not proven profitability. Baseline is unmatched; fees and executable fills are not modeled.",
    }
    if snapshots and len({r["ticker"] for r in snapshots}) < 30:
        result["sample_warning"] = "FEWER THAN 30 CONTRACTS; TOO SMALL FOR RELIABLE PERFORMANCE CLAIMS"
    if not snapshots:
        result["warning"] = "NO HISTORICAL SNAPSHOTS IN CONNECTED DATABASE; NO ACCURACY CLAIM POSSIBLE"
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
