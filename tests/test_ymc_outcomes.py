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
    assert report["by_votes_exploratory"] == {}
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


def test_aligned_vote_groups_partition_signals():
    rows = [
        {"decision_utc": "2026-11-18T12:00:01+00:00", "horizon_minutes": 15, "votes": 5, "correct": True, "actual_direction": "ALCISTA"},
        {"decision_utc": "2026-11-18T12:15:01+00:00", "horizon_minutes": 15, "votes": 0, "correct": False, "actual_direction": "BAJISTA"},
    ]
    report = aligned_quarter_hour_report(rows)
    assert set(report["by_votes_exploratory"]) == {"0", "5"}
    assert sum(v["signals"] for v in report["by_votes_exploratory"].values()) == 2
    assert set(report["by_direction_exploratory"]) == {"ALCISTA", "BAJISTA"}


def test_aligned_direction_breakdown_matches_all_signals():
    rows = [
        {"decision_utc": "2026-11-18T12:00:01+00:00", "horizon_minutes": 15, "direction": "ALCISTA", "correct": True, "actual_direction": "ALCISTA"},
        {"decision_utc": "2026-11-18T12:15:01+00:00", "horizon_minutes": 15, "direction": "BAJISTA", "correct": False, "actual_direction": "ALCISTA"},
    ]
    report = aligned_quarter_hour_report(rows)
    assert sum(v["summary"]["signals"] for v in report["by_direction_exploratory"].values()) == report["aligned_decisions"]


def test_momentum_comparison_uses_same_subset():
    from backend.btcmarket.ymc_outcomes import summarize
    rows = [
        {"decision_utc": "2026-11-18T12:00:01+00:00", "horizon_minutes": 15, "correct": True, "actual_direction": "ALCISTA", "momentum_baseline_direction": "BAJISTA"},
        {"decision_utc": "2026-11-18T12:15:01+00:00", "horizon_minutes": 15, "correct": False, "actual_direction": "BAJISTA", "momentum_baseline_direction": "ESPERAR"},
    ]
    stats = summarize(rows)[15]
    assert stats["non_overlapping_momentum_baseline_scored"] == 1
    assert stats["non_overlapping_ymc_on_momentum_subset_hit_rate"] == 1
    assert stats["non_overlapping_momentum_baseline_hit_rate"] == 0
    assert stats["non_overlapping_edge_vs_momentum_on_same_subset"] == 1
    assert stats["best_baseline_is_hindsight_only"] is True


def test_chronological_holdout_keeps_last_day_separate():
    from backend.btcmarket.ymc_outcomes import chronological_holdout_report
    rows = [
        {"decision_utc": "2026-11-17T12:00:01+00:00", "horizon_minutes": 15, "direction": "ALCISTA", "correct": True, "actual_direction": "ALCISTA"},
        {"decision_utc": "2026-11-18T12:00:01+00:00", "horizon_minutes": 15, "direction": "BAJISTA", "correct": False, "actual_direction": "ALCISTA"},
        {"decision_utc": "2026-11-18T12:01:01+00:00", "horizon_minutes": 15, "direction": "ALCISTA", "correct": True, "actual_direction": "ALCISTA"},
    ]
    report = chronological_holdout_report(rows)
    assert report["reference_dates_utc"] == ["2026-11-17"]
    assert report["holdout_date_utc"] == "2026-11-18"
    assert report["reference"]["summary"]["signals"] == 1
    assert report["holdout"]["summary"]["signals"] == 1
    assert report["holdout"]["by_direction"]["BAJISTA"]["signals"] == 1
    assert chronological_holdout_report(rows[:1])["holdout"] == {}


def test_daily_coverage_partitions_all_valid_slots():
    coverage = quarter_hour_coverage(sample(), [])
    days = coverage["daily_utc"]
    assert sum(day["eligible_slots"] for day in days.values()) == coverage["eligible_slots"]
    assert sum(day["directional_slots"] for day in days.values()) == coverage["directional_slots"]
    assert sum(day["wait_slots"] for day in days.values()) == coverage["wait_slots"]
    for day in days.values():
        assert day["eligible_slots"] == day["directional_slots"] + day["wait_slots"]


def test_early_watch_diagnostic_groups_aligned_rows():
    from backend.btcmarket.ymc_outcomes import early_watch_diagnostic
    rows = [
        {"decision_utc": "2026-11-18T12:00:01+00:00", "horizon_minutes": 15, "early_watch": "POSIBLE_AGOTAMIENTO_ALCISTA", "correct": False, "actual_direction": "BAJISTA"},
        {"decision_utc": "2026-11-18T12:15:01+00:00", "horizon_minutes": 15, "early_watch": "NINGUNA", "correct": True, "actual_direction": "ALCISTA"},
        {"decision_utc": "2026-11-18T12:16:01+00:00", "horizon_minutes": 15, "early_watch": "NINGUNA", "correct": True, "actual_direction": "ALCISTA"},
    ]
    report = early_watch_diagnostic(rows)
    assert report["total_aligned_signals"] == 2
    assert report["by_early_watch"]["POSIBLE_AGOTAMIENTO_ALCISTA"]["signals"] == 1
    assert sum(x["signals"] for x in report["by_early_watch"].values()) == 2


def test_early_reversal_hypothesis_counts_spot_direction_not_ymc_correctness():
    from backend.btcmarket.ymc_outcomes import early_watch_diagnostic
    rows = [
        {"decision_utc": "2026-11-18T12:00:01+00:00", "horizon_minutes": 15, "early_watch": "POSIBLE_AGOTAMIENTO_ALCISTA", "correct": False, "actual_direction": "BAJISTA"},
        {"decision_utc": "2026-11-18T12:15:01+00:00", "horizon_minutes": 15, "early_watch": "POSIBLE_AGOTAMIENTO_BAJISTA", "correct": False, "actual_direction": "ALCISTA"},
    ]
    report = early_watch_diagnostic(rows)["reversal_hypotheses_exploratory"]
    assert report["POSIBLE_AGOTAMIENTO_ALCISTA"]["match_rate"] == 1
    assert report["POSIBLE_AGOTAMIENTO_BAJISTA"]["matches"] == 1
    assert report["POSIBLE_AGOTAMIENTO_ALCISTA"]["wilson_95"]["upper"] == 1
