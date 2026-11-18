"""Evaluate previously recorded YMC decisions against future *closed* BTC candles.

Offline research only. Never uses future candles when constructing a signal.
Prices are Coinbase spot, NOT Kalshi settlement prices.
"""
from datetime import datetime, timezone
from backend.btcmarket.ymc_signal import evaluate


def evaluate_history(candles, horizons=(10, 15)):
    """Chronological 1m OHLCV with Unix opening timestamps.

    Returns only fully observed outcomes. Invalid/gapped history is skipped.
    """
    results = []
    if not candles:
        return results
    rows = sorted(candles, key=lambda c: c["time"])
    for idx in range(39, len(rows)):
        window = rows[idx - 39:idx + 1]
        # One second after candle close; avoids evaluating an open candle.
        decision_time = int(window[-1]["time"]) + 61
        signal = evaluate(window, now=decision_time)
        if not signal["validated"] or signal["direction"] == "ESPERAR":
            continue
        entry = float(window[-1]["close"])
        for horizon in horizons:
            if not isinstance(horizon, int) or horizon <= 0 or idx + horizon >= len(rows):
                continue
            future_window = rows[idx:idx + horizon + 1]
            if any(int(b["time"]) - int(a["time"]) != 60
                   for a, b in zip(future_window, future_window[1:])):
                continue
            future = future_window[-1]
            exit_price = float(future["close"])
            move = exit_price - entry
            correct = (move > 0 if signal["direction"] == "ALCISTA" else move < 0)
            results.append({
                "decision_utc": datetime.fromtimestamp(decision_time, timezone.utc).isoformat(),
                "direction": signal["direction"],
                "votes": signal["votes"],
                "pattern": signal.get("candle_context", {}).get("pattern", "NINGUNO"),
                "volume_elevated": signal.get("candle_context", {}).get("volume_elevated", False),
                "sideways_watch": signal.get("candle_context", {}).get("sideways_watch", False),
                "horizon_minutes": horizon,
                "entry_spot": entry,
                "exit_spot": exit_price,
                "spot_change": move,
                "correct": correct if move != 0 else None,
                "actual_direction": "ALCISTA" if move > 0 else "BAJISTA" if move < 0 else "PLANO",
                "note": "Offline Coinbase spot outcome; not Kalshi contract profitability",
            })
    return results


def summarize(results):
    """Ignore flat moves when computing directional hit rate."""
    summary = {}
    for horizon in sorted({r["horizon_minutes"] for r in results}):
        group = [r for r in results if r["horizon_minutes"] == horizon]
        scored = [r for r in group if r["correct"] is not None]
        baseline_up = sum(r.get("actual_direction") == "ALCISTA" for r in scored) / len(scored) if scored else None
        baseline_down = sum(r.get("actual_direction") == "BAJISTA" for r in scored) / len(scored) if scored else None
        # Adjacent decisions share most of their future window. Report a non-overlapping
        # diagnostic so a large count of correlated decisions is not mistaken for
        # independent evidence.
        independent = []
        next_allowed = None
        for row in sorted((r for r in group if r.get("decision_utc")), key=lambda r: r["decision_utc"]):
            t = datetime.fromisoformat(row["decision_utc"]).timestamp()
            if next_allowed is None or t >= next_allowed:
                independent.append(row)
                next_allowed = t + horizon * 60
        independent_scored = [r for r in independent if r["correct"] is not None]
        independent_up = sum(r.get("actual_direction") == "ALCISTA" for r in independent_scored) / len(independent_scored) if independent_scored else None
        independent_down = sum(r.get("actual_direction") == "BAJISTA" for r in independent_scored) / len(independent_scored) if independent_scored else None
        summary[horizon] = {
            "signals": len(group),
            "non_overlapping_signals": len(independent),
            "non_overlapping_scored": len(independent_scored),
            "non_overlapping_hit_rate": (sum(r["correct"] is True for r in independent_scored) / len(independent_scored)) if independent_scored else None,
            "non_overlapping_always_up_baseline": independent_up,
            "non_overlapping_always_down_baseline": independent_down,
            "scored": len(scored),
            "correct": sum(r["correct"] is True for r in scored),
            "hit_rate": (sum(r["correct"] is True for r in scored) / len(scored)) if scored else None,
            "always_up_baseline": baseline_up,
            "always_down_baseline": baseline_down,
            "validated_predictive_accuracy": False,
        }
    return summary


def breakdown(results):
    """Exploratory performance by pattern, volume, and sideways market.

    Each subgroup is descriptive; it is NOT a tuned trading rule or
    independent evidence of predictive skill.
    """
    output = {}
    for horizon in sorted({r["horizon_minutes"] for r in results}):
        group = [r for r in results if r["horizon_minutes"] == horizon]
        groups = {}
        for field in ("pattern", "volume_elevated", "sideways_watch", "votes"):
            values = sorted({str(r.get(field, "UNKNOWN")) for r in group})
            for value in values:
                selected = [r for r in group if str(r.get(field, "UNKNOWN")) == value]
                scored = [r for r in selected if r["correct"] is not None]
                groups[f"{field}={value}"] = {
                    "signals": len(selected),
                    "scored": len(scored),
                    "hit_rate": sum(r["correct"] is True for r in scored) / len(scored) if scored else None,
                }
        output[horizon] = groups
    return output
