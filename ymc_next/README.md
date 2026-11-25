# YMC BTC Predictor AI Pro — rebuild

Isolated read-only application. Do not import or launch legacy trading schedulers or order clients. No order placement, cancellation, or account credentials required for public data.

## Acceptance gates
- Coinbase and Kraken timestamped market data; reject stale, missing or inconsistent observations.
- Candlestick chart: Lightweight Charts, mobile pinch/pan, 1/5/10/15 minute aggregation, live partial candle distinguished from closed candles.
- Forecast targets: future returns at 5/10/15 minutes, with a neutral band; distinguish early signals from already-realized moves.
- XGBoost baseline and LightGBM challenger; chronological splits with horizon embargo, separate calibration and untouched test windows. Compare against persistence and simple momentum. Suppress probabilities until validated.
- Kalshi public quotes and order book; display spread, liquidity, expiry and freshness. No automatic trading.
- Independent market ingestion, inference and UI rendering. Reconnect with backoff; suppress stale signals.
- Deployment only after tests, mobile checks and live-data verification. Legacy main remains unchanged as backup.
