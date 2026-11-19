"""API routes for the KXBTC15M market data module: candles, live market, and orderbook history."""
from datetime import timedelta

from fastapi import APIRouter, Response

from backend.btcmarket import candles as candles_mod
from backend.btcmarket import kalshi_poll

router = APIRouter(prefix="/api/btc", tags=["btc"])

HISTORY_RANGES = {
    "1h": timedelta(hours=1),
    "1d": timedelta(days=1),
    "1w": timedelta(days=7),
    "1m": timedelta(days=30),
}


@router.get("/candles")
async def get_candles(interval: str = "1m", lookback: str = "1d"):
    """
    OHLCV candles for the BTC candlestick chart.
    interval: 1m | 5m | 15m | 1h | 6h | 1d (candle width)
    lookback: 1d | 3d | 1w | 1m (how far back to fetch, ending now)
    """
    if interval not in candles_mod.INTERVAL_SECONDS:
        interval = "1m"
    if lookback not in candles_mod.LOOKBACK_TIMEDELTA:
        lookback = "1d"
    return await candles_mod.get_candles(interval, lookback)


@router.get("/market")
async def get_market():
    """The currently-open KXBTC15M market, plus the most recent recorded snapshot."""
    market = await kalshi_poll.get_current_market()
    if not market:
        return {"market": None}

    return {
        "market": {
            "ticker": market.get("ticker"),
            "event_ticker": market.get("event_ticker"),
            "title": market.get("title"),
            "floor_strike": market.get("floor_strike"),
            "open_time": market.get("open_time"),
            "close_time": market.get("close_time"),
            "yes_bid": float(market.get("yes_bid_dollars", 0) or 0),
            "yes_ask": float(market.get("yes_ask_dollars", 0) or 0),
            "no_bid": float(market.get("no_bid_dollars", 0) or 0),
            "no_ask": float(market.get("no_ask_dollars", 0) or 0),
            "volume": float(market.get("volume_fp", 0) or 0),
            "rules_primary": market.get("rules_primary"),
        }
    }


@router.get("/history")
async def get_history(range: str = "1d"):
    """Recorded yes/no probability history: real backfilled candlestick data plus live 1Hz snapshots."""
    lookback = HISTORY_RANGES.get(range, HISTORY_RANGES["1d"])
    return kalshi_poll.get_recent_snapshots(lookback)


@router.get("/kalshi-candles")
async def get_kalshi_candles(range: str = "1d"):
    """Real OHLC candlesticks of the KXBTC15M YES price, stitched across rotating 15-min windows."""
    from backend.btcmarket import kalshi_history
    lookback = HISTORY_RANGES.get(range, HISTORY_RANGES["1d"])
    return kalshi_history.get_kxbtc_candles(lookback)


@router.get("/signal")
async def get_signal():
    """
    Model-vs-market read for the currently-open KXBTC15M window: a driftless-GBM
    probability that BTC settles at/above the strike, estimated from realized
    volatility of recent 1-minute candles, compared against the live orderbook price.
    """
    from backend.btcmarket import model as model_mod
    from dataclasses import asdict

    signal = await model_mod.generate_btc_signal()
    if not signal:
        return {"signal": None}
    return {"signal": asdict(signal)}


@router.get("/ymc-technical")
async def get_ymc_technical(response: Response):
    """Coinbase BTC-USD technical votes from closed 1m candles; not a Kalshi settlement forecast."""
    response.headers["Cache-Control"] = "no-store, max-age=0"
    from datetime import datetime, timezone
    from backend.btcmarket.ymc_signal import evaluate
    await candles_mod.ensure_recent_candles(60, timedelta(hours=3))
    candles = candles_mod.get_cached_candles(60, timedelta(hours=3))
    now = datetime.now(timezone.utc).timestamp()
    # Exclude the currently forming candle inserted by the live-price poller.
    closed = [c for c in candles if c["time"] + 60 <= now - 2]
    result = evaluate(closed, now=now)
    # Poller placeholders have zero volume; do not treat them as Coinbase OHLCV.
    if result["validated"] and any(c["volume"] <= 0 for c in closed[-40:]):
        result = evaluate([], now=now)
        result["reason"] = "unverified_provisional_candles"
    result["source"] = "Coinbase BTC-USD"
    result["timeframe"] = "1m"
    result["indicators"] = {"ema_fast": 9, "ema_slow": 21, "rsi": 14,
                            "macd_fast": 12, "macd_slow": 26, "macd_signal": 9}
    result["settlement_price_warning"] = "Coinbase spot is not Kalshi's settlement reference"
    return result

@router.get("/history-status")
async def get_history_status():
    """Read-only diagnostics for persisted Kalshi snapshots and candles."""
    from datetime import datetime, timezone
    from sqlalchemy import func
    from backend.models.database import SessionLocal, KxBtcSnapshot, KxBtcCandle
    db = SessionLocal()
    try:
        snapshots = db.query(func.count(KxBtcSnapshot.id)).scalar() or 0
        candles = db.query(func.count(KxBtcCandle.id)).scalar() or 0
        latest_snapshot = db.query(func.max(KxBtcSnapshot.timestamp)).scalar()
        latest_candle = db.query(func.max(KxBtcCandle.open_time)).scalar()
        def utc_iso(dt):
            return dt.replace(tzinfo=timezone.utc).isoformat() if dt else None
        return {
            "snapshot_count": snapshots,
            "candle_count": candles,
            "latest_snapshot_utc": utc_iso(latest_snapshot),
            "latest_candle_utc": utc_iso(latest_candle),
            "recording_active": bool(latest_snapshot and
                (datetime.utcnow() - latest_snapshot).total_seconds() < 180),
        }
    finally:
        db.close()


@router.get("/openai-review")
async def get_openai_review():
    """Compatibility endpoint: paid external AI is disabled; no API call or charge."""
    return {
        "status": "disabled",
        "analysis": None,
        "reason": "paid_openai_disabled_use_ymc_technical",
        "alternative": "/api/btc/ymc-technical",
    }


@router.get("/diagnostics")
async def get_btc_diagnostics(response: Response):
    """Read-only data health report. Never exposes secrets or places orders."""
    response.headers["Cache-Control"] = "no-store, max-age=0"
    from datetime import datetime, timezone
    from backend.btcmarket.ymc_signal import evaluate
    now = datetime.now(timezone.utc).timestamp()
    try:
        await candles_mod.ensure_recent_candles(60, timedelta(hours=3))
        rows = candles_mod.get_cached_candles(60, timedelta(hours=3))
        closed = [c for c in rows if c["time"] + 60 <= now - 2]
        technical = evaluate(closed, now=now)
        return {
            "server_utc": datetime.fromtimestamp(now, timezone.utc).isoformat(),
            "coinbase_candles_cached": len(rows),
            "closed_candles": len(closed),
            "last_closed_age_seconds": round(now - (closed[-1]["time"] + 60), 1) if closed else None,
            "last_40_zero_volume_count": sum(float(c["volume"]) <= 0 for c in closed[-40:]),
            "technical_validated": technical["validated"],
            "technical_reason": technical["reason"],
            "technical_votes": technical["votes"],
            "last_closed_candle_utc": datetime.fromtimestamp(closed[-1]["time"] + 60, timezone.utc).isoformat() if closed else None,
            "last_closed_volume": float(closed[-1]["volume"]) if closed else None,
            "last_40_candle_gaps": sum(b["time"] - a["time"] != 60 for a, b in zip(closed[-40:], closed[-39:])),
            "pattern": (technical.get("candle_context") or {}).get("pattern"),
            "early_watch": technical.get("early_watch"),
            "pattern_as_of_utc": technical.get("as_of_utc") if technical.get("validated") else None,
            "technical_usable": bool(technical["validated"] and all(float(c["volume"]) > 0 for c in closed[-40:])),
            "paid_openai_enabled": False,
            "openai_forecast_calibrated": False,
        }
    except Exception:
        return {"status": "data_source_unavailable", "technical_validated": False}
