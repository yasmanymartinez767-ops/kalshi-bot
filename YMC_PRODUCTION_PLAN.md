# YMC BTC Predictor AI Pro — Production improvement plan

## Product contract
- BTC/USD and Kalshi KXBTC15M only. No weather, stocks, or other markets in the user interface.
- Read-only analysis. No automatic orders, buying, selling, or execution buttons.
- One-screen Android-first interface: large candlesticks, prominent trend, early reversal watch, 5/10/15-minute forecast status, minimal copy.
- SÍ = BTC above Kalshi settlement threshold at expiry; NO = BTC not above that threshold. Neither means "buy" or "do not buy". WAIT means insufficient evidence.
- Never claim accuracy, calibrated probability, or milliseconds of advantage without measurements.

## Data architecture
1. Coinbase Exchange BTC-USD level2 websocket: primary price/depth observations.
2. Kraken BTC/USD book websocket: independent corroboration; verify sequence/checksum before relying on depth for signals.
3. Kalshi KXBTC15M contract orderbook and bid/ask: compare contract quote changes, contract identifier, expiry, and reference strike. Spot price is not Kalshi settlement BRTI.
4. Timestamp each source on arrival using a monotonic clock; track age, gaps, outliers, reconnect count and latency distributions. Discard stale/untrusted inputs. Compare actual event timestamps where supplied.
5. Reconnect with exponential backoff and resubscribe; never fill missing data with fabricated candles.

## Predictive engine
- Features from fully closed candles: body/wick ratios, rejection, follow-through, volatility, EMA, RSI, MACD and volume changes.
- Streaming features: bid/ask depth imbalance, aggressive executed trade flow where available, spread and rapid changes. Depth imbalance alone is NOT executed buy/sell pressure.
- Independent horizons 5, 10 and 15 minutes. Distinguish early reversal watch from confirmed trend.
- Validate with walk-forward, purged time splits, fees/spread, slippage, and out-of-sample performance. No look-ahead leakage.
- Until calibrated: show qualitative watch + EVALUANDO; no invented percentages.

## UI priorities
- Charcoal/navy, muted borders, restrained green/red, readable typography.
- Header BTC + expiry timer; three compact IA tiles: trend, votes, RSI; one concise early-watch message.
- One dominant candle chart, 1/5/15 minute chart selector; optional advanced data collapsed.
- No Target label, decorative animations or legacy weather dashboard.
- On data failure: WAIT / SIN DATOS, never a stale BUY/SELL signal.

## Release gates
- TypeScript build passes; Python tests pass.
- Live Coinbase/Kraken websocket integration verified with checksums/sequence.
- Kalshi active contract and quote freshness verified, including contract roll.
- Time-to-signal measured end-to-end on Android, p50/p95/p99, across multiple sessions.
- Out-of-sample reversal precision/recall and false-alert rate published with sample sizes.
- No automatic order submission code path reachable from the BTC UI or API.
- Verify deployed URL and Android scrolling, chart pinch/pan and first paint.

## Current status
- BTC-only app shell and compact AI display committed.
- Read-only Coinbase/Kraken exploratory collector committed, not yet connected to application lifecycle or validated with Kraken checksum.
- Existing Kalshi polling remains separate. Three-way synchronized predictive fusion is not yet operational.
- No verified live latency edge, predictive accuracy, deployment, or production readiness.
