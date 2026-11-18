from backend.btcmarket.ymc_signal import evaluate

NOW = 1800000000

def candles():
    start = NOW - 41 * 60
    return [
        {"time": start + i * 60, "open": 100+i, "high": 101+i,
         "low": 99+i, "close": 100.5+i, "volume": 10}
        for i in range(40)
    ]

def test_valid_closed_data():
    result = evaluate(candles(), NOW)
    assert result["validated"]
    assert result["votes"] in range(6)
    assert result["direction"] in ("ALCISTA", "BAJISTA", "ESPERAR")

def test_gap_fails_closed():
    data = candles()
    data[20]["time"] += 60
    assert evaluate(data, NOW)["direction"] == "ESPERAR"
    assert not evaluate(data, NOW)["validated"]

def test_stale_fails_closed():
    assert not evaluate(candles(), NOW + 180)["validated"]

def test_invalid_ohlcv_fails_closed():
    data = candles()
    data[-1]["high"] = 0
    assert not evaluate(data, NOW)["validated"]

def test_partial_candle_fails_closed():
    data = candles()
    data[-1]["time"] += 60
    assert not evaluate(data, NOW)["validated"]
