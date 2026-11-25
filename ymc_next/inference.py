import os
import time
from pathlib import Path
import joblib
import numpy as np
from ymc_next.features import features
from ymc_next.market import Candle,validate

def predict(rows):
    candles=[Candle(**r) for r in rows]
    validate(candles)
    x=features(candles).tail(1)
    if x.empty or x.isna().any().any():
        return {}
    results={}
    for h in (5,10,15):
        path=Path(os.getenv("YMC_MODEL_DIR","artifacts"))/f"model_{h}.joblib"
        if not path.is_file():
            continue
        try:
            a=joblib.load(path)
            m=a["metrics"]
            if a["horizon"]!=h or not 0<=time.time()-a["trained_at"]<=86400*7:
                continue
            if m["test_samples"]<500 or not m["log_loss"]<m["baseline_loss"] or m["balanced_accuracy"]<=1/3:
                continue
            p=a["calibrator"].predict_proba(np.log(np.clip(a["model"].predict_proba(x),1e-8,1)))[0]
            if not np.isfinite(p).all():
                continue
            results[str(h)]={"down":float(p[0]),"neutral":float(p[1]),"up":float(p[2]),"as_of":candles[-1].ts+60}
        except Exception:
            continue
    return results
