"""Regression: short momentum uses the closest tick at each lookback horizon."""
from datetime import datetime, timedelta

from backend.btcmarket import candles


def test_momentum_uses_nearest_prior_tick(monkeypatch):
    now = datetime.utcnow()
    original = list(candles._TICK_BUFFER)
    try:
        candles._TICK_BUFFER.clear()
        for seconds_ago, price in [
            (60, 100.0), (31, 101.0), (16, 102.0),
            (6, 103.0), (1, 104.0), (0, 105.0),
        ]:
            candles._TICK_BUFFER.append((now - timedelta(seconds=seconds_ago), price))
        result = candles.get_short_momentum()
        # 5s uses the 6s sample, 15s uses the 16s sample,
        # and 30s uses the 31s sample, never the oldest 60s tick.
        import math
        assert abs(result["mom_5s"] - round(math.log(105 / 103), 6)) < 1e-8
        assert abs(result["mom_15s"] - round(math.log(105 / 102), 6)) < 1e-8
        assert abs(result["mom_30s"] - round(math.log(105 / 101), 6)) < 1e-8
    finally:
        candles._TICK_BUFFER.clear()
        candles._TICK_BUFFER.extend(original)
