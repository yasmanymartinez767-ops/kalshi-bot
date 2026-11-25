import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
import httpx
import joblib
from ymc_next.market import Candle,validate
from ymc_next.model import train

def history(days):
    end=int(time.time())//60*60-120
    start=end-days*86400
    rows={}
    with httpx.Client(timeout=20) as client:
        for a in range(start,end, 250*60):
            b=min(a+250*60,end)
            for attempt in range(5):
                try:
                    response=client.get("https://api.exchange.coinbase.com/products/BTC-USD/candles",
                                        params={"granularity":60,"start":datetime.fromtimestamp(a,timezone.utc).isoformat(),"end":datetime.fromtimestamp(b,timezone.utc).isoformat()})
                    if response.status_code in (429,500,502,503,504):
                        if attempt==4:
                            response.raise_for_status()
                        time.sleep(min(20,2**attempt))
                        continue
                    response.raise_for_status()
                    break
                except (httpx.TimeoutException,httpx.NetworkError):
                    if attempt==4:
                        raise
                    time.sleep(min(20,2**attempt))
            for r in response.json():
                t=int(r[0])
                if start<=t<end:
                    rows[t]=Candle(t,float(r[3]),float(r[2]),float(r[1]),float(r[4]),float(r[5]))
            time.sleep(.4)
    candles=[rows[t] for t in sorted(rows)]
    validate(candles,now=end)
    if len(candles)!=(end-start)//60:
        raise ValueError("Incomplete historical coverage")
    return candles

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--days",type=int,default=30)
    p.add_argument("--output",default="artifacts")
    args=p.parse_args()
    if args.days<7:
        raise ValueError("At least seven days required")
    candles=history(args.days)
    output=Path(args.output)
    output.mkdir(parents=True,exist_ok=True)
    for horizon in (5,10,15):
        model,calibrator,metrics=train(candles,horizon)
        print(horizon,metrics,flush=True)
        joblib.dump({"model":model,"calibrator":calibrator,"metrics":metrics,
                     "horizon":horizon,"trained_at":time.time()},output/f"model_{horizon}.joblib")

if __name__=="__main__":
    main()
