#!/bin/bash
# Production start script for Kanji SRS
set -e

cd "$(dirname "$0")"
export PYTHONPATH=""

exec uvicorn backend.main:app \
    --host 0.0.0.0 \
    --port 8000 \
    --workers 2 \
    --log-level info
