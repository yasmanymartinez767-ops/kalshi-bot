from backend.btcmarket.ymc_outcomes import evaluate_history, summarize, daily_report, forward_day_check, aligned_quarter_hour_report, wilson_95_interval, quarter_hour_coverage


def sample(n=65):
    return [
        {"time": 1800000000 + i * 60, "open": 100 + i,
         "high": 102 + i, "low": 99 + i,
         "close": 101 + i, "volume": 10}
        for i in range(n)
    ]


def test_horizons_are_future_only():
    outcomes = evaluate_history(sample())
    assert outcomes
    assert {r["horizon_minutes"] for r in outcomes} == {10, 15}
    assert all(r["exit_spot"] > r["entry_spot"] for r in outcomes)
    assert all(r["direction"] == "ALCISTA" for r in outcomes)


def test_missing_future_candle_never_scored():
    data = sample()
    data[50]["time"] += 1
    outcomes = evaluate_history(data)
    assert all(r["entry_spot"] < r["exit_spot"] for r in outcomes)
    assert any(r["entry_spot"] == 140 and r["horizon_minutes"] == 10 for r in outcomes)
    assert not any(r["entry_spot"] == 140 and r["horizon_minutes"] == 15 for r in outcomes)


def test_summary_empty_is_safe():
    assert summarize([]) == {}
    result = summarize([{"horizon_minutes": 10, "correct": None}])
    assert result[10]["hit_rate"] is None
    assert result[10]["validated_predictive_accuracy"] is False


def test_non_overlapping_signal_counts():
    rows = evaluate_history(sample())
    summary = summarize(rows)
    for horizon in (10, 15):
        assert summary[horizon]["non_overlapping_signals"] <= summary[horizon]["signals"]
        assert summary[horizon]["non_overlapping_scored"] <= summary[horizon]["scored"]
        assert 0 <= summary[horizon]["non_overlapping_always_up_baseline"] <= 1
        assert 0 <= summary[horizon]["non_overlapping_always_down_baseline"] <= 1
        assert summary[horizon]["non_overlapping_best_baseline"] == max(summary[horizon]["non_overlapping_always_up_baseline"], summary[horizon]["non_overlapping_always_down_baseline"])
        assert abs(summary[horizon]["non_overlapping_edge_vs_best_baseline"] - (summary[horizon]["non_overlapping_hit_rate"] - summary[horizon]["non_overlapping_best_baseline"])) < 1e-12


def test_daily_report_groups_by_utc_date():
    rows = evaluate_history(sample())
    daily = daily_report(rows)
    assert daily
    assert all(len(day) == 10 for day in daily)
    assert sum(v["signals"] for horizons in daily.values() for v in horizons.values()) == len(rows)


def test_forward_day_check_does_not_count_reference_day():
    assert forward_day_check([])["forward_day_count"] == 0
    rows = [
        {"decision_utc": "2026-11-15T12:00:00+00:00", "horizon_minutes": 15, "correct": True, "actual_direction": "ALCISTA"},
        {"decision_utc": "2026-11-16T12:00:00+00:00", "horizon_minutes": 15, "correct": False, "actual_direction": "BAJISTA"},
    ]
    report = forward_day_check(rows)
    assert report["reference_day_utc"] == "2026-11-15"
    assert report["forward_day_count"] == 1
    assert list(report["forward_days"]) == ["2026-11-16"]


def test_quarter_hour_report_only_uses_15m_boundary():
    rows = [
        {"decision_utc": "2026-11-18T12:00:01+00:00", "horizon_minutes": 15, "correct": True, "actual_direction": "ALCISTA"},
        {"decision_utc": "2026-11-18T12:01:01+00:00", "horizon_minutes": 15, "correct": False, "actual_direction": "BAJISTA"},
        {"decision_utc": "2026-11-18T12:15:01+00:00", "horizon_minutes": 10, "correct": True, "actual_direction": "ALCISTA"},
    ]
    report = aligned_quarter_hour_report(rows)
    assert report["aligned_decisions"] == 1
    assert report["summary"]["signals"] == 1
    assert report["daily_utc"]["2026-11-18"][15]["signals"] == 1
    assert aligned_quarter_hour_report([])["aligned_decisions"] == 0


def test_momentum_baseline_is_reported_from_past_only():
    rows = evaluate_history(sample())
    assert rows
    assert all(r["momentum_baseline_direction"] in ("ALCISTA", "BAJISTA", "ESPERAR") for r in rows)
    report = summarize(rows)
    for stats in report.values():
        assert stats["non_overlapping_momentum_baseline_scored"] <= stats["non_overlapping_scored"]
        rate = stats["non_overlapping_momentum_baseline_hit_rate"]
        assert rate is None or 0 <= rate <= 1


def test_wilson_uncertainty_bounds():
    assert wilson_95_interval(0, 0) is None
    for wins, total in [(0, 10), (5, 10), (10, 10), (92, 216)]:
        interval = wilson_95_interval(wins, total)
        assert 0 <= interval["lower"] <= wins / total <= interval["upper"] <= 1
    assert wilson_95_interval(5, 100)["upper"] - wilson_95_interval(5, 100)["lower"] < wilson_95_interval(1, 20)["upper"] - wilson_95_interval(1, 20)["lower"]


def test_quarter_hour_coverage_includes_wait_slots():
    assert quarter_hour_coverage([], [])["directional_coverage"] is None
    coverage = quarter_hour_coverage(sample(), [])
    assert coverage["eligible_slots"] == coverage["directional_slots"] + coverage["wait_slots"]
    assert coverage["directional_coverage"] is None or 0 <= coverage["directional_coverage"] <= 1
