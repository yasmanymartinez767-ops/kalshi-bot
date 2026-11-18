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
    expired_quotes_excluded = 0
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
        close_time = row.get("close_time")
        if close_time:
            try:
                expiry = datetime.fromisoformat(str(close_time).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if expiry.tzinfo is None or at >= expiry:
                expired_quotes_excluded += 1
                continue
        for side in ("yes", "no"):
            ask = parse_price(row.get(side + "_ask"))
            bid = parse_price(row.get(side + "_bid"))
            if ask is None or bid is None or bid > ask or ask == 0 or bid == 0:
                continue
            groups[(ticker, side.upper())].append((at, ask, bid))
    opportunities = []
    observations = 0
    best_gross_gain = {}
    first_opportunity_by_contract_side = {}
    contract_side_summaries = []
    affordable_opportunities = []
    for (ticker, side), quotes in sorted(groups.items()):
        quotes.sort(key=lambda q: q[0])
        observations += len(quotes)
        # Maximum later bid minus an earlier ask, without crossing contract boundaries.
        minimum_prior_ask = None
        maximum = None
        for _, ask, bid in quotes:
            if minimum_prior_ask is not None:
                gain = bid - minimum_prior_ask
                maximum = gain if maximum is None else max(maximum, gain)
            minimum_prior_ask = ask if minimum_prior_ask is None else min(minimum_prior_ask, ask)
        key = ticker + ":" + side
        best_gross_gain[key] = round(maximum, 3) if maximum is not None else None
        contract_side_summaries.append({"ticker": ticker, "side": side,
            "valid_quotes": len(quotes), "first_quote_utc": quotes[0][0].isoformat() if quotes else None,
            "last_quote_utc": quotes[-1][0].isoformat() if quotes else None,
            "max_observed_gross_gain_cents": best_gross_gain[key]})
        # Earliest ask for every candidate entry. Later bids only: no lookahead.
        for index, (entry_at, entry_ask, _) in enumerate(quotes):
            for exit_at, _, exit_bid in quotes[index + 1:]:
                if exit_at <= entry_at:
                    continue
                gain = round(exit_bid - entry_ask, 6)
                if gain > TARGET_CENTS + 1e-8:
                    opportunity = {
                        "ticker": ticker, "side": side,
                        "entry_observed_at_utc": entry_at.isoformat(),
                        "exit_observed_at_utc": exit_at.isoformat(),
                        "entry_ask_cents": round(entry_ask, 3),
                        "later_bid_cents": round(exit_bid, 3),
                        "gross_gain_cents": round(gain, 3),
                        "hypothetical_only": True,
                        "elapsed_seconds": round((exit_at - entry_at).total_seconds(), 3),
                    }
                    opportunities.append(opportunity)
                    if 10 <= entry_ask <= 60:
                        affordable_opportunities.append(opportunity)
                    first_opportunity_by_contract_side.setdefault(key, opportunity)
                    break
    return {
        "contract_sides": len(groups),
        "valid_side_quotes": observations,
        "api_errors": errors,
        "expired_quotes_excluded": expired_quotes_excluded,
        "best_observed_gross_gain_cents_by_contract_side": best_gross_gain,
        "entry_points_with_later_bid_gain_over_20c": len(opportunities),
        "opportunities": opportunities[:100],
        "entry_points_10_to_60c_with_later_gain_over_20c": len(affordable_opportunities),
        "distinct_contract_sides_10_to_60c_with_later_gain_over_20c": len({(o["ticker"], o["side"]) for o in affordable_opportunities}),
        "sample_10_to_60c_opportunities": affordable_opportunities[:30],
        "contract_sides_with_at_least_one_over_20c_opportunity": len(first_opportunity_by_contract_side),
        "first_opportunity_by_contract_side": list(first_opportunity_by_contract_side.values()),
        "contract_side_summaries": contract_side_summaries,
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
