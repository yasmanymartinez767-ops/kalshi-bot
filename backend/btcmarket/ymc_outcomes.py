"""Evaluate previously recorded YMC decisions against future *closed* BTC candles.

Offline research only. Never uses future candles when constructing a signal.
Prices are Coinbase spot, NOT Kalshi settlement prices.
"""
from datetime import datetime, timezone
from math import sqrt
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
                "momentum_baseline_direction": ("ALCISTA" if entry > float(window[-6]["close"]) else "BAJISTA" if entry < float(window[-6]["close"]) else "ESPERAR"),
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


def wilson_95_interval(successes, total):
    """95% Wilson binomial interval; assumes approximately independent trials."""
    if total <= 0:
        return None
    z = 1.959963984540054
    p = successes / total
    denominator = 1 + z * z / total
    center = (p + z * z / (2 * total)) / denominator
    half = z * sqrt((p * (1 - p) + z * z / (4 * total)) / total) / denominator
    return {"lower": 0.0 if successes == 0 else max(0.0, center - half),
            "upper": 1.0 if successes == total else min(1.0, center + half)}


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
        independent_hit_rate = (sum(r["correct"] is True for r in independent_scored) / len(independent_scored)) if independent_scored else None
        best_baseline = max(independent_up, independent_down) if independent_up is not None and independent_down is not None else None
        momentum_scored = [r for r in independent_scored if r.get("momentum_baseline_direction") in ("ALCISTA", "BAJISTA")]
        momentum_rate = (sum(r["momentum_baseline_direction"] == r.get("actual_direction") for r in momentum_scored) / len(momentum_scored)) if momentum_scored else None
        summary[horizon] = {
            "signals": len(group),
            "non_overlapping_signals": len(independent),
            "non_overlapping_scored": len(independent_scored),
            "non_overlapping_hit_rate": independent_hit_rate,
            "non_overlapping_wilson_95": wilson_95_interval(sum(r["correct"] is True for r in independent_scored), len(independent_scored)),
            "non_overlapping_always_up_baseline": independent_up,
            "non_overlapping_always_down_baseline": independent_down,
            "non_overlapping_best_baseline": best_baseline,
            "non_overlapping_momentum_baseline_scored": len(momentum_scored),
            "non_overlapping_momentum_baseline_hit_rate": momentum_rate,
            "non_overlapping_edge_vs_best_baseline": (independent_hit_rate - best_baseline) if independent_hit_rate is not None and best_baseline is not None else None,
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


def daily_report(results):
    """UTC daily diagnostics; descriptive only, no training or parameter selection."""
    output = {}
    for row in results:
        day = row.get("decision_utc", "")[:10]
        if not day:
            continue
        horizon = row["horizon_minutes"]
        output.setdefault(day, {}).setdefault(horizon, []).append(row)
    return {day: summarize([r for group in horizons.values() for r in group])
            for day, horizons in sorted(output.items())}


def forward_day_check(results):
    """Leave-one-day-forward diagnostic, no fitted thresholds or future features.

    Compare the frozen signal logic on each subsequent UTC day. The first
    observed date is a reference period, not a scored forward day.
    """
    daily = daily_report(results)
    dates = sorted(daily)
    return {
        "reference_day_utc": dates[0] if dates else None,
        "forward_days": {day: daily[day] for day in dates[1:]},
        "forward_day_count": max(0, len(dates) - 1),
        "note": "Frozen-rule forward chronological diagnostic; not true live walk-forward training or independent Kalshi validation",
    }


def aligned_quarter_hour_report(results):
    """Evaluate 15m spot predictions made just after UTC :00/:15/:30/:45.

    This is an alignment diagnostic, NOT a replay of Kalshi order books,
    entry fills, contract strike, fees, or contract settlement.
    """
    selected = []
    for row in results:
        if row.get("horizon_minutes") != 15 or not row.get("decision_utc"):
            continue
        instant = datetime.fromisoformat(row["decision_utc"])
        if instant.minute % 15 == 0:
            selected.append(row)
    by_day = daily_report(selected)
    return {"aligned_decisions": len(selected), "summary": summarize(selected).get(15, {}),
            "daily_utc": by_day,
            "note": "UTC quarter-hour Coinbase spot only; not a Kalshi backtest"}
