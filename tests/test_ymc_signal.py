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


def test_candle_context_exposed():
    result = evaluate(candles(), NOW)
    context = result["candle_context"]
    assert context["pattern"] in (
        "NINGUNO", "INDECISION", "RECHAZO_INFERIOR", "RECHAZO_SUPERIOR",
        "CONTINUACION_REBOTE", "CONTINUACION_RECHAZO_BAJISTA",
    )
    assert context["pattern_validated"] is False
    assert context["volume_ratio_20"] == 1.0


def test_bullish_lower_wick_detected():
    data = candles()
    data[-2]["low"] = data[-2]["open"]  # no previous rejection/continuation
    last = data[-1]
    last["open"] = 140
    last["close"] = 140.2
    last["high"] = 140.3
    last["low"] = 137
    result = evaluate(data, NOW)
    assert result["validated"]
    assert result["candle_context"]["pattern"] == "RECHAZO_INFERIOR"


def test_bearish_upper_wick_detected():
    data = candles()
    data[-2]["low"] = data[-2]["open"]  # isolate the current upper-wick pattern
    last = data[-1]
    last["open"] = 140
    last["close"] = 139.8
    last["high"] = 143
    last["low"] = 139.7
    result = evaluate(data, NOW)
    assert result["validated"]
    assert result["candle_context"]["pattern"] == "RECHAZO_SUPERIOR"


def test_volume_spike_detected():
    data = candles()
    data[-1]["volume"] = 25
    result = evaluate(data, NOW)
    assert result["candle_context"]["volume_ratio_20"] == 2.5
    assert result["candle_context"]["volume_elevated"] is True


def test_invalid_data_does_not_produce_candle_context():
    data = candles()
    data[-1]["volume"] = -1
    result = evaluate(data, NOW)
    assert result["direction"] == "ESPERAR"
    assert not result["validated"]
    assert "candle_context" not in result
