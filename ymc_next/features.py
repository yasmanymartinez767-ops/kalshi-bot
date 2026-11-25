"""Causal features from validated closed one-minute candles."""
import numpy as np
import pandas as pd

def features(candles):
    d = pd.DataFrame([vars(c) for c in candles]).set_index("ts")
    p = d.close
    span = (d.high-d.low).replace(0,np.nan)
    f = pd.DataFrame(index=d.index)
    f["body"] = ((d.close-d.open)/span).fillna(0)
    f["upper_wick"] = ((d.high-d[["open","close"]].max(axis=1))/span).fillna(0)
    f["lower_wick"] = ((d[["open","close"]].min(axis=1)-d.low)/span).fillna(0)
    f["range"] = (d.high-d.low)/p
    for n in (1,3,5,10,15):
        f[f"return_{n}"] = p.pct_change(n)
    f["acceleration"] = f.return_3-f.return_3.shift(3)
    f["ema_gap"] = (p.ewm(span=9,adjust=False).mean()-p.ewm(span=21,adjust=False).mean())/p
    f["volume_ratio"] = d.volume/d.volume.rolling(20).mean().replace(0,np.nan)
    f["volatility"] = f.return_1.rolling(15).std()
    f["signed_volume_proxy"] = (np.sign(d.close-d.open)*d.volume).rolling(5).sum()/d.volume.rolling(5).sum().replace(0,np.nan)
    return f.replace([np.inf,-np.inf],np.nan).iloc[30:]

def targets(candles, horizon, neutral_band=0.0005):
    if horizon not in (5,10,15):
        raise ValueError("Unsupported horizon")
    p = pd.Series({c.ts:c.close for c in candles})
    future = p.shift(-horizon)/p-1
    y = pd.Series(np.nan,index=p.index)
    valid = future.notna() & (p.index.to_series().shift(-horizon)-p.index.to_series()==horizon*60)
    y.loc[valid] = np.select([future[valid]<-neutral_band,future[valid]>neutral_band],[0,2],default=1)
    return y

def chronological_split(index,horizon):
    """Separate training, calibration and test with horizon embargo."""
    n=len(index)
    a,b=int(n*.6),int(n*.8)
    if min(a,b-a,n-b)<=horizon:
        raise ValueError("Insufficient history")
    return index[:a-horizon],index[a:b-horizon],index[b:]
