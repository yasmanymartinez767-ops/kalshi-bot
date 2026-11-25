import asyncio
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
    candles=sorted([Candle(int(r[0]),float(r[3]),float(r[2]),float(r[1]),float(r[4]),float(r[5])) for r in rows if int(r[0])+60<=now],key=lambda c:c.ts)
    validate(candles,now)
    if kraken.get("error"):
        raise ValueError("Kraken error")
    series=next(v for k,v in kraken["result"].items() if k!="last")
    matching=[r for r in series if int(r[0])==candles[-1].ts]
    if not matching or not crosscheck(candles[-1].close,float(matching[0][4])):
        raise ValueError("Exchange mismatch")
    return {"candles":[vars(c) for c in candles],"checked_at":now,
            "kalshi":None if isinstance(kalshi,Exception) else kalshi.get("markets",[]),
            "signal":"EN EVALUACION"}

async def fetch_snapshot():
    async with httpx.AsyncClient(timeout=8) as client:
        return await snapshot(client)
