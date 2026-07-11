#!/usr/bin/env bash
# Container startup sequence (plan 001 Step 6):
#   1. Idempotent RAG ingestion — exactly once, BEFORE any worker exists,
#      so a request can never race a half-populated vector store and
#      per-worker imports can never double-ingest.
#   2. exec gunicorn — `exec` replaces this shell so gunicorn becomes PID 1
#      and receives docker's SIGTERM directly (clean shutdowns).
set -euo pipefail

echo "[entrypoint] Running idempotent RAG ingestion..."
python -c "from app.rag.Ingestion import RunIdempotentRagIngestion; RunIdempotentRagIngestion()"

echo "[entrypoint] Starting gunicorn (2 workers) on :5000..."
exec gunicorn --workers 2 --bind 0.0.0.0:5000 --access-logfile - wsgi:app
