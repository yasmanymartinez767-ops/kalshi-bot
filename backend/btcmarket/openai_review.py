"""Optional, read-only OpenAI second-opinion analyst for YMC BTC.

No trading actions. No model-generated probabilities. Server-side API key only.
"""
import asyncio
import json
import os
import time

import httpx

_cache = {"key": None, "until": 0.0, "value": None}
_lock = asyncio.Lock()


async def review(technical, candles, market):
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        return {"status": "not_configured", "analysis": None}
    if not technical.get("validated") or technical.get("votes") is None:
        return {"status": "insufficient_data", "analysis": None}
    if len(candles) < 40 or any(float(c.get("volume", 0)) <= 0 for c in candles[-40:]):
        return {"status": "insufficient_data", "analysis": None}
    ticker = market.get("ticker") if market else None
    if not ticker:
        return {"status": "insufficient_data", "analysis": None}
    fingerprint = (ticker, technical.get("as_of_utc"))
    async with _lock:
        if _cache["key"] == fingerprint and time.monotonic() < _cache["until"]:
            return _cache["value"]
        payload = {
            "ticker": ticker,
            "technical": {k: technical.get(k) for k in (
                "direction", "votes", "rsi14", "ema9", "ema21", "macd_hist",
                "early_watch", "candle_context", "as_of_utc")},
            "last_closed_candles": [
                {k: c.get(k) for k in ("time", "open", "high", "low", "close", "volume")}
                for c in candles[-12:]
            ],
            "market": {k: market.get(k) for k in (
                "close_time", "yes_bid_dollars", "yes_ask_dollars",
                "no_bid_dollars", "no_ask_dollars")},
        }
        instructions = (
            "Eres un analista secundario de BTC 15m. Solo información, no órdenes. "
            "Evalúa mechas, volumen, seguimiento de velas y contradicciones de indicadores. "
            "No inventes datos, porcentajes, predicciones calibradas ni actividad de traders. "
            "Distingue hipótesis de hechos. Responde SOLO JSON con claves "
            "direction (SUBE, BAJA o ESPERAR), summary (español, <=180 caracteres), "
            "risk (español, <=120 caracteres). Si hay conflicto, ESPERAR."
        )
        try:
            async with httpx.AsyncClient(timeout=12) as client:
                resp = await client.post(
                    "https://api.openai.com/v1/chat/completions",
                    headers={"Authorization": f"Bearer {key}"},
                    json={
                        "model": os.getenv("YMC_OPENAI_MODEL", "gpt-4.1-mini"),
                        "temperature": 0,
                        "response_format": {"type": "json_object"},
                        "messages": [
                            {"role": "system", "content": instructions},
                            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                        ],
                    },
                )
                resp.raise_for_status()
                raw = json.loads(resp.json()["choices"][0]["message"]["content"])
            direction = raw.get("direction")
            if direction not in ("SUBE", "BAJA", "ESPERAR"):
                raise ValueError("invalid model direction")
            result = {
                "status": "exploratory", "direction": direction,
                "analysis": str(raw.get("summary", ""))[:180],
                "risk": str(raw.get("risk", ""))[:120],
                "as_of_utc": technical["as_of_utc"],
                "ticker": ticker,
                "probability": None,
                "validated_prediction": False,
            }
            _cache.update(key=fingerprint, until=time.monotonic() + 60, value=result)
            return result
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError, json.JSONDecodeError):
            return {"status": "unavailable", "analysis": None}
