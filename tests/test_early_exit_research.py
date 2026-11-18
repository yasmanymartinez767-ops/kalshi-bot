from backend.btcmarket.early_exit_research import evaluate_bid_drop_alerts


def test_falling_bid_then_further_decline():
    rows = [
        {"ticker": "A", "time": 0, "yes_bid": .50},
        {"ticker": "A", "time": 6, "yes_bid": .49},
        {"ticker": "A", "time": 12, "yes_bid": .47},
        {"ticker": "A", "time": 72, "yes_bid": .44},
    ]
    result = evaluate_bid_drop_alerts(rows)
    assert result["alerts"] == 1
    assert result["further_declines"] == 1
    assert result["false_alarms"] == 0
    assert result["decline_rate"] == 1


def test_no_cross_market_leakage():
    rows = [
        {"ticker": "A", "time": 0, "yes_bid": .50},
        {"ticker": "B", "time": 5, "yes_bid": .48},
        {"ticker": "A", "time": 12, "yes_bid": .46},
    ]
    assert evaluate_bid_drop_alerts(rows)["alerts"] == 0


def test_unresolved_and_rebound():
    rows = [
        {"ticker": "A", "time": 0, "yes_bid": .50},
        {"ticker": "A", "time": 6, "yes_bid": .49},
        {"ticker": "A", "time": 12, "yes_bid": .47},
        {"ticker": "A", "time": 72, "yes_bid": .52},
        {"ticker": "B", "time": 0, "yes_bid": .60},
        {"ticker": "B", "time": 6, "yes_bid": .59},
        {"ticker": "B", "time": 12, "yes_bid": .57},
    ]
    result = evaluate_bid_drop_alerts(rows)
    assert result["resolved"] == 1
    assert result["unresolved"] == 1
    assert result["false_alarms"] == 1


def test_excludes_expired_quotes_and_stale_outcomes():
    rows = [
        {"ticker": "A", "time": 0, "yes_bid": .50, "close_time": 60},
        {"ticker": "A", "time": 6, "yes_bid": .49, "close_time": 60},
        {"ticker": "A", "time": 12, "yes_bid": .47, "close_time": 60},
        {"ticker": "A", "time": 72, "yes_bid": .40, "close_time": 60},
        {"ticker": "B", "time": 0, "yes_bid": .50},
        {"ticker": "B", "time": 6, "yes_bid": .49},
        {"ticker": "B", "time": 12, "yes_bid": .47},
        {"ticker": "B", "time": 200, "yes_bid": .40},
    ]
    result = evaluate_bid_drop_alerts(rows)
    assert result["alerts"] == 2
    assert result["unresolved"] == 2
    assert result["resolved"] == 0
