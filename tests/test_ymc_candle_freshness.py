"""Regression tests: only closed, recent Coinbase candles may drive YMC signals."""
from datetime import datetime, timezone

from backend.btcmarket.ymc_signal import evaluate


def candles_ending_at(last_open):
    return [
        {
            "time": last_open - (39 - i) * 60,
            "open": 60000 + i,
            "high": 60002 + i,
            "low": 59999 + i,
            "close": 60001 + i,
            "volume": 2.0,
        }
        for i in range(40)
    ]


def test_recent_closed_candle_is_accepted():
    now = 1_800_000_000
    last_open = (now // 60) * 60 - 60
    result = evaluate(candles_ending_at(last_open), now=last_open + 65)
    assert result["validated"] is True
    assert result["votes"] is not None


def test_forming_candle_is_rejected():
    last_open = 1_800_000_000 // 60 * 60
    result = evaluate(candles_ending_at(last_open), now=last_open + 30)
    assert result["validated"] is False


def test_stale_candle_is_rejected():
    last_open = 1_800_000_000 // 60 * 60
    result = evaluate(candles_ending_at(last_open), now=last_open + 200)
    assert result["reason"] == "unclosed_or_stale_candles"


def test_zero_volume_is_rejected():
    last_open = 1_800_000_000 // 60 * 60
    rows = candles_ending_at(last_open)
    rows[-1]["volume"] = 0
    result = evaluate(rows, now=last_open + 65)
    assert result["validated"] is False
    assert result["reason"] == "unverified_zero_volume_candle"
