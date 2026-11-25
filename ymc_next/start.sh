#!/bin/sh
set -eu
export YMC_MODEL_DIR="${YMC_MODEL_DIR:-/app/artifacts}"
mkdir -p "$YMC_MODEL_DIR"
(
  while true; do
    if python -m ymc_next.train --days 30 --output "$YMC_MODEL_DIR"; then
      sleep 86400
    else
      echo "Training failed; retrying in 15 minutes" >&2
      sleep 900
    fi
  done
) &
exec uvicorn ymc_next.api:app --host 0.0.0.0 --port "${PORT:-8000}"
