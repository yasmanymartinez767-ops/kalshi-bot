"""Evaluate observed BTC15M bid/ask paths without lookahead or hypothetical fills.

An opportunity is a later executable bid strictly more than 20 cents above
an earlier ask, within the SAME contract and side. No order is assumed filled.
"""
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

TARGET_CENTS = 20.0


def parse_price(value):
    try:
        result = float(value) * 100
        return result if 0 <= result <= 100 else None
    except (TypeError, ValueError):
        return None


def analyze(rows):
    groups = defaultdict(list)
    errors = 0
    for row in rows:
        if row.get("error"):
            errors += 1
        ticker = row.get("ticker")
        try:
            at = datetime.fromisoformat(row["observed_at_utc"].replace("Z", "+00:00"))
        except (KeyError, ValueError, TypeError):
            continue
        if not ticker or at.tzinfo is None:
            continue
        for side in ("yes", "no"):
            ask = parse_price(row.get(side + "_ask"))
            bid = parse_price(row.get(side + "_bid"))
            if ask is None or bid is None or bid > ask or ask == 0 or bid == 0:
                continue
            groups[(ticker, side.upper())].append((at, ask, bid))
    opportunities = []
    observations = 0
    for (ticker, side), quotes in sorted(groups.items()):
        quotes.sort(key=lambda q: q[0])
        observations += len(quotes)
        # Earliest ask for every candidate entry. Later bids only: no lookahead.
        for index, (entry_at, entry_ask, _) in enumerate(quotes):
            for exit_at, _, exit_bid in quotes[index + 1:]:
                if exit_at <= entry_at:
                    continue
                gain = round(exit_bid - entry_ask, 6)
                if gain > TARGET_CENTS + 1e-8:
                    opportunities.append({
                        "ticker": ticker, "side": side,
                        "entry_observed_at_utc": entry_at.isoformat(),
                        "exit_observed_at_utc": exit_at.isoformat(),
                        "entry_ask_cents": round(entry_ask, 3),
                        "later_bid_cents": round(exit_bid, 3),
                        "gross_gain_cents": round(gain, 3),
                        "hypothetical_only": True,
                    })
                    break
    return {
        "contract_sides": len(groups),
        "valid_side_quotes": observations,
        "api_errors": errors,
        "entry_points_with_later_bid_gain_over_20c": len(opportunities),
        "opportunities": opportunities[:100],
        "limitations": "Observed ask/bid only; no order fills, fees, liquidity guarantees or advance predictions. Overlapping opportunities are not independent trades.",
        "prediction_accuracy_validated": False,
    }


def main():
    paths = [Path(p) for p in sys.argv[1:]]
    if not paths:
        raise SystemExit("Usage: python scripts/ymc_analyze_kalshi_quotes.py file.jsonl [more.jsonl...]")
    rows = []
    for path in paths:
        with path.open(encoding="utf-8") as stream:
            rows.extend(json.loads(line) for line in stream if line.strip())
    print(json.dumps(analyze(rows), indent=2))


if __name__ == "__main__":
    main()
