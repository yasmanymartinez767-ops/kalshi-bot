import asyncio
import time
from contextlib import asynccontextmanager,suppress
import httpx
from fastapi import FastAPI,WebSocket,WebSocketDisconnect
from ymc_next.feed import snapshot

state={"status":"starting","signal":"ESPERAR","candles":[]}

async def worker():
    async with httpx.AsyncClient(timeout=8) as client:
        while True:
            try:
                data=await snapshot(client)
                state.clear()
                state.update(data,status="connected")
                delay=8
            except Exception:
                state.clear()
                state.update(status="unavailable",signal="ESPERAR",candles=[],checked_at=time.time())
                delay=15
            await asyncio.sleep(delay)

@asynccontextmanager
async def lifespan(app):
    task=asyncio.create_task(worker())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

app=FastAPI(title="YMC BTC Predictor AI Pro",lifespan=lifespan)

def current():
    if time.time()-state.get("checked_at",0)>30:
        return {"status":"stale","signal":"ESPERAR","candles":[]}
    return dict(state)

@app.get("/api/market")
async def market():
    return current()

@app.websocket("/ws/market")
async def stream(ws:WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_json(current())
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass

from pathlib import Path
from fastapi.responses import FileResponse

@app.get("/")
async def dashboard():
    return FileResponse(Path(__file__).parent / "static" / "index.html")

@app.get("/health")
async def health():
    return {"service":"ymc-next","market_status":current()["status"]}
