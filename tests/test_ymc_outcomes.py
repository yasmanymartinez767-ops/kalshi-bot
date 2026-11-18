from backend.btcmarket.ymc_outcomes import evaluate_history, summarize, daily_report


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
