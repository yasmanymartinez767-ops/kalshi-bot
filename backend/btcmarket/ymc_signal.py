"""YMC 15m transparent technical vote engine. Informational only; never places orders."""
from datetime import datetime, timezone
from math import isfinite

def evaluate(candles, now=None):
    """Input: chronological, fully CLOSED 1m OHLCV dicts with Unix-second timestamps."""
    now = datetime.now(timezone.utc).timestamp() if now is None else float(now)
    def wait(reason):
        return {"direction": "ESPERAR", "votes": None, "reason": reason, "validated": False,
                "as_of_utc": datetime.fromtimestamp(now, timezone.utc).isoformat()}
    if len(candles) < 40:
        return wait("insufficient_closed_candles")
    try:
        rows = candles[-40:]
        ts = [int(c["time"]) for c in rows]
        for a, b in zip(ts, ts[1:]):
            if b - a != 60:
                return wait("missing_or_misaligned_candles")
        if any(t % 60 for t in ts):
            return wait("unaligned_timestamp")
        if ts[-1] > now - 60 or now - (ts[-1] + 60) > 90:
            return wait("unclosed_or_stale_candles")
        for c in rows:
            o,h,l,cl,v = (float(c[k]) for k in ("open","high","low","close","volume"))
            if not all(map(isfinite,(o,h,l,cl,v))) or min(o,h,l,cl)<=0 or v<0 or l>min(o,cl) or h<max(o,cl):
                return wait("invalid_ohlcv")
        close=[float(c["close"]) for c in rows]
    except (ValueError,TypeError,KeyError,OverflowError):
        return wait("malformed_candles")
    def ema(values,period):
        alpha=2/(period+1)
        out=[values[0]]
        for x in values[1:]:
            out.append(alpha*x+(1-alpha)*out[-1])
        return out
    e9=ema(close,9)
    e21=ema(close,21)
    macd=[a-b for a,b in zip(ema(close,12),ema(close,26))]
    hist=macd[-1]-ema(macd,9)[-1]
    changes=[close[i]-close[i-1] for i in range(-14,0)]
    gains=sum(max(x,0) for x in changes)/14
    losses=sum(max(-x,0) for x in changes)/14
    rsi=100 if losses==0 and gains>0 else (50 if losses==0 else 100-100/(1+gains/losses))
    votes=sum((e9[-1]>e21[-1],close[-1]>e9[-1],rsi>50,close[-1]>close[-6],hist>0))
    direction="ALCISTA" if votes>=4 else ("BAJISTA" if votes<=1 else "ESPERAR")
    # Early *watch* flags are deliberately separate from the trend vote.
    # They identify potential exhaustion, not a validated 10/15m prediction.
    recent = rows[-3:]
    body = abs(float(recent[-1]["close"]) - float(recent[-1]["open"]))
    span = float(recent[-1]["high"]) - float(recent[-1]["low"])
    upper_wick = float(recent[-1]["high"]) - max(float(recent[-1]["open"]), float(recent[-1]["close"]))
    lower_wick = min(float(recent[-1]["open"]), float(recent[-1]["close"])) - float(recent[-1]["low"])
    warning = "NINGUNA"
    if rsi >= 70 and (upper_wick > 2 * max(body, 0.01) or close[-1] < close[-2]):
        warning = "POSIBLE_AGOTAMIENTO_ALCISTA"
    elif rsi <= 30 and (lower_wick > 2 * max(body, 0.01) or close[-1] > close[-2]):
        warning = "POSIBLE_AGOTAMIENTO_BAJISTA"
    elif span > 0 and body / span <= 0.2 and abs(close[-1] - close[-2]) > 0:
        warning = "INDECISION"
    return {"direction":direction,"votes":votes,"reason":"technical_votes_not_probability",
            "early_watch":warning,"early_watch_validated":False,
            "validated":True,"rsi14":round(rsi,2),"ema9":e9[-1],"ema21":e21[-1],
            "macd_hist":hist,"as_of_utc":datetime.fromtimestamp(ts[-1]+60,timezone.utc).isoformat()}
