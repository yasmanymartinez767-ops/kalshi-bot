import asyncio
import math
import time
import httpx
from ymc_next.market import Candle, validate, crosscheck

async def snapshot(client):
    async def get(url,params=None):
        response=await client.get(url,params=params)
        response.raise_for_status()
        return response.json()
    rows,kraken,kalshi=await asyncio.gather(
        get("https://api.exchange.coinbase.com/products/BTC-USD/candles",{"granularity":60}),
        get("https://api.kraken.com/0/public/OHLC",{"pair":"XBTUSD","interval":1}),
        get("https://api.elections.kalshi.com/trade-api/v2/markets",{"series_ticker":"KXBTC15M","status":"open","limit":20}),
        return_exceptions=True)
    now=time.time()
    if isinstance(rows,Exception) or isinstance(kraken,Exception):
        raise ValueError("Exchange unavailable")
    parsed=sorted([Candle(int(r[0]),float(r[3]),float(r[2]),float(r[1]),float(r[4]),float(r[5])) for r in rows],key=lambda c:c.ts)
    candles=[c for c in parsed if c.ts+60<=now]
    forming=[c for c in parsed if c.ts<=now<c.ts+60]
    partial=forming[-1] if forming else None
    if partial is not None and (partial.ts!=int(now)//60*60 or not all(math.isfinite(v) for v in (partial.open,partial.high,partial.low,partial.close,partial.volume)) or partial.low<=0 or partial.high<max(partial.open,partial.close) or partial.low>min(partial.open,partial.close) or partial.volume<0):
        partial=None
    validate(candles,now)
    if kraken.get("error"):
        raise ValueError("Kraken error")
    series=next(v for k,v in kraken["result"].items() if k!="last")
    matching=[r for r in series if int(r[0])==candles[-1].ts]
    if not matching or not crosscheck(candles[-1].close,float(matching[0][4])):
        raise ValueError("Exchange mismatch")
    return {"candles":[vars(c) for c in candles],"partial_candle":vars(partial) if partial else None,"checked_at":now,
            "kalshi":None if isinstance(kalshi,Exception) else kalshi.get("markets",[]),
            "signal":"EN EVALUACION"}

async def fetch_snapshot():
    async with httpx.AsyncClient(timeout=8) as client:
        return await snapshot(client)
