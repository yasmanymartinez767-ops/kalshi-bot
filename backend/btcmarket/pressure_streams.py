"""Read-only low-latency BTC market pressure collectors.

Coinbase and Kraken websocket orderbook snapshots/updates. Kalshi KXBTC15M
quotes are already polled by backend.btcmarket.kalshi_poll; combine those
observations downstream only if timestamps and contract ticker are valid.
Never submits orders or produces calibrated probabilities.
"""
import asyncio
import json
import logging
import time
from collections import deque

import aiohttp

LOG = logging.getLogger(__name__)


class PressureFeed:
    def __init__(self):
        self.books = {"coinbase": {"bids": {}, "asks": {}}, "kraken": {"bids": {}, "asks": {}}}
        self.received = {}
        self.history = deque(maxlen=300)
        self.status = {"coinbase": "connecting", "kraken": "connecting"}

    def _update(self, venue, side, price, size):
        if price <= 0 or size < 0:
            return
        levels = self.books[venue][side]
        if size == 0:
            levels.pop(price, None)
        else:
            levels[price] = size

    def _record(self, venue):
        book = self.books[venue]
        bids = sorted(book["bids"].items(), reverse=True)[:10]
        asks = sorted(book["asks"].items())[:10]
        if not bids or not asks or bids[0][0] >= asks[0][0]:
            return
        buy = sum(size for _, size in bids)
        sell = sum(size for _, size in asks)
        if buy + sell <= 0:
            return
        at = time.time()
        self.received[venue] = at
        self.history.append({"venue": venue, "received_at": at,
                             "imbalance": (buy - sell) / (buy + sell),
                             "mid": (bids[0][0] + asks[0][0]) / 2})
        self.status[venue] = "live"

    def snapshot(self):
        now = time.time()
        latest = {}
        for venue in self.books:
            age = now - self.received.get(venue, 0)
            observations = [x for x in reversed(self.history) if x["venue"] == venue]
            if age <= 3 and observations:
                latest[venue] = {**observations[0], "age_ms": round(age * 1000)}
            else:
                latest[venue] = {"status": "stale_or_disconnected"}
        valid = [x for x in latest.values() if "imbalance" in x]
        # This is orderbook depth imbalance, NOT executed buy/sell pressure.
        avg = sum(x["imbalance"] for x in valid) / len(valid) if len(valid) == 2 else None
        label = ("PRESIÓN COMPRADORA" if avg is not None and avg >= .2 else
                 "PRESIÓN VENDEDORA" if avg is not None and avg <= -.2 else
                 "SIN CONFIRMACIÓN")
        return {"sources": latest, "depth_imbalance": avg, "watch": label,
                "validated_prediction": False, "execution_enabled": False}

    async def coinbase(self, session):
        async with session.ws_connect("wss://ws-feed.exchange.coinbase.com", heartbeat=20) as ws:
            await ws.send_json({"type": "subscribe", "product_ids": ["BTC-USD"],
                                "channels": ["level2", "heartbeat"]})
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    break
                data = json.loads(msg.data)
                if data.get("product_id") != "BTC-USD":
                    continue
                if data.get("type") == "snapshot":
                    self.books["coinbase"] = {"bids": {}, "asks": {}}
                    for side, key in (("bids", "bids"), ("asks", "asks")):
                        for p, s in data.get(key, []):
                            self._update("coinbase", side, float(p), float(s))
                    self._record("coinbase")
                elif data.get("type") == "l2update":
                    for side, p, s in data.get("changes", []):
                        self._update("coinbase", "bids" if side == "buy" else "asks", float(p), float(s))
                    self._record("coinbase")

    async def kraken(self, session):
        async with session.ws_connect("wss://ws.kraken.com/v2", heartbeat=20) as ws:
            await ws.send_json({"method": "subscribe", "params": {
                "channel": "book", "symbol": ["BTC/USD"], "depth": 10, "snapshot": True}})
            async for msg in ws:
                if msg.type != aiohttp.WSMsgType.TEXT:
                    break
                data = json.loads(msg.data)
                if data.get("channel") != "book":
                    continue
                if data.get("type") == "snapshot":
                    self.books["kraken"] = {"bids": {}, "asks": {}}
                for item in data.get("data", []):
                    if item.get("symbol") != "BTC/USD":
                        continue
                    for side in ("bids", "asks"):
                        for level in item.get(side, []):
                            self._update("kraken", side, float(level["price"]), float(level["qty"]))
                    # Kraken checksum verification is required before using
                    # this as a trading-grade feed; treat as exploratory only.
                    self._record("kraken")

    async def run_source(self, name, session):
        delay = 1
        while True:
            try:
                await getattr(self, name)(session)
                self.status[name] = "disconnected"
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self.status[name] = "disconnected"
                LOG.warning("%s feed disconnected: %s", name, exc)
            self.books[name] = {"bids": {}, "asks": {}}
            await asyncio.sleep(delay)
            delay = min(delay * 2, 30)

    async def run(self):
        async with aiohttp.ClientSession() as session:
            await asyncio.gather(self.run_source("coinbase", session),
                                 self.run_source("kraken", session))
