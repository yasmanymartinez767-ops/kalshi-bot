"""Read-only market data primitives. UTC epoch seconds."""
from dataclasses import dataclass
import math
import time

@dataclass(frozen=True)
class Candle:
    ts: int
    open: float
    high: float
    low: float
    close: float
    volume: float

def validate(candles, now=None, max_age=90):
    now = time.time() if now is None else now
    if not candles:
        raise ValueError("No candles")
    for i, c in enumerate(candles):
        values = (c.open,c.high,c.low,c.close,c.volume)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Nonfinite candle")
        if c.ts % 60 or min(values[:4]) <= 0 or c.volume < 0:
            raise ValueError("Invalid candle")
        if c.low > min(c.open,c.close) or c.high < max(c.open,c.close):
            raise ValueError("Invalid OHLC")
        if i and c.ts - candles[i-1].ts != 60:
            raise ValueError("Missing or duplicate candle")
        if c.ts + 60 > now:
            raise ValueError("Unclosed candle")
    if now - (candles[-1].ts + 60) > max_age:
        raise ValueError("Stale candles")
    return candles

def aggregate(candles, minutes):
    if minutes not in (1,5,10,15):
        raise ValueError("Unsupported timeframe")
    width = minutes * 60
    groups = {}
    for c in candles:
        groups.setdefault(c.ts // width * width, []).append(c)
    result = []
    for start, group in sorted(groups.items()):
        if [c.ts for c in group] != list(range(start,start+width,60)):
            continue
        result.append(Candle(start,group[0].open,max(c.high for c in group),
            min(c.low for c in group),group[-1].close,sum(c.volume for c in group)))
    return result

def crosscheck(primary, secondary, tolerance=0.003):
    if not all(math.isfinite(x) and x > 0 for x in (primary,secondary)):
        return False
    return abs(primary-secondary)/primary <= tolerance
