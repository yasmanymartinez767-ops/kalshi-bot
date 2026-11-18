"""Retrospective bid-drop alert evaluation; never uses future data to trigger alerts."""
from collections import defaultdict
from datetime import datetime, timezone


def evaluate_bid_drop_alerts(snapshots, side="YES", horizon_seconds=60):
    """Evaluate three descending quotes (>=2c) against future executable bids.

    snapshots: dicts with ticker, time (Unix seconds), yes_bid/no_bid (0..1).
    Alerts require 3 quotes spanning >=10s, and each quote within 120s.
    One alert per ticker; no comparisons across contract boundaries.
    Future observations must be at least horizon_seconds later.
    """
    if side not in ("YES", "NO") or horizon_seconds <= 0:
        raise ValueError("Invalid side or horizon")
    key = "yes_bid" if side == "YES" else "no_bid"
    grouped = defaultdict(list)
    expiry_by_ticker = {}
    for row in snapshots:
        try:
            ticker, at, bid = row["ticker"], int(row["time"]), float(row[key])
            close = row.get("close_time")
            if isinstance(close, str):
                close = int(datetime.fromisoformat(close.replace("Z", "+00:00")).timestamp())
            elif isinstance(close, datetime):
                close = int((close if close.tzinfo else close.replace(tzinfo=timezone.utc)).timestamp())
            elif close is not None:
                close = int(close)
            if close is not None:
                expiry_by_ticker[ticker] = min(expiry_by_ticker.get(ticker, close), close)
                if at >= close:
                    continue
        except (KeyError, TypeError, ValueError):
            continue
        if ticker and 0 < bid <= 1:
            grouped[ticker].append((at, bid))
    results = []
    baseline_results = []
    for ticker, rows in grouped.items():
        rows.sort()
        # Baseline: fixed observation at the third quote, independent of any alert.
        # Compare the same 60-second outcome definition, only before expiry.
        if len(rows) >= 3:
            base = rows[2]
            expiry = expiry_by_ticker.get(ticker)
            if expiry is None or base[0] + horizon_seconds < expiry:
                next_base = next((r for r in rows if r[0] >= base[0] + horizon_seconds), None)
                if next_base and next_base[0] <= base[0] + horizon_seconds + 30:
                    baseline_results.append(next_base[1] < base[1])
        trigger = None
        for i in range(2, len(rows)):
            a, b, c = rows[i - 2:i + 1]
            if not (10 <= c[0] - a[0] <= 120 and a[1] > b[1] > c[1]
                    and (a[1] - c[1]) >= 0.02 - 1e-9):
                continue
            trigger = c
            break
        if trigger is None:
            continue
        # A 60-second evaluation must finish while the contract is still open.
        expiry = expiry_by_ticker.get(ticker)
        if expiry is not None and trigger[0] + horizon_seconds >= expiry:
            results.append({"ticker": ticker, "outcome": "UNRESOLVED"})
            continue
        # Require a nearby observation; a quote many minutes later is not a 60s outcome.
        future = next((r for r in rows if r[0] >= trigger[0] + horizon_seconds), None)
        if future is not None and future[0] > trigger[0] + horizon_seconds + 30:
            future = None
        if future is None:
            results.append({"ticker": ticker, "outcome": "UNRESOLVED"})
            continue
        delta_cents = round((future[1] - trigger[1]) * 100, 3)
        results.append({"ticker": ticker, "outcome": "FELL" if delta_cents < 0 else "DID_NOT_FALL",
                        "future_bid_change_cents": delta_cents})
    resolved = [r for r in results if r["outcome"] != "UNRESOLVED"]
    fell = sum(r["outcome"] == "FELL" for r in resolved)
    baseline_n = len(baseline_results)
    baseline_fell = sum(baseline_results)
    return {"side": side, "horizon_seconds": horizon_seconds,
            "alerts": len(results), "resolved": len(resolved), "unresolved": len(results) - len(resolved),
            "further_declines": fell, "false_alarms": len(resolved) - fell,
            "decline_rate": fell / len(resolved) if resolved else None,
            "baseline_third_quote": {
                "resolved": baseline_n,
                "further_declines": baseline_fell,
                "decline_rate": baseline_fell / baseline_n if baseline_n else None,
                "note": "Unmatched descriptive baseline, not causal evidence of signal improvement.",
            },
            "rows": results,
            "note": "Exploratory historical diagnostic, not a validated trading edge; excludes fees, spread changes and execution."}
