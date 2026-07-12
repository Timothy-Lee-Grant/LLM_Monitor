#!/usr/bin/env bash
# Container startup sequence (plan 001 Step 6; extended plan 002 Step 4):
#   1. Prepare the prometheus multiprocess dir — gunicorn workers are forked
#      processes with separate memory, so counters live in shared mmap files
#      here instead (see app/metrics.py for the full explanation). Cleared on
#      every boot: stale files from a previous run would double-count.
#   2. Idempotent RAG ingestion — exactly once, BEFORE any worker exists,
#      so a request can never race a half-populated vector store and
#      per-worker imports can never double-ingest.
#   3. exec gunicorn — `exec` replaces this shell so gunicorn becomes PID 1
#      and receives docker's SIGTERM directly (clean shutdowns).
set -euo pipefail

export PROMETHEUS_MULTIPROC_DIR=/tmp/prometheus_multiproc
rm -rf "$PROMETHEUS_MULTIPROC_DIR" && mkdir -p "$PROMETHEUS_MULTIPROC_DIR"

echo "[entrypoint] Running idempotent RAG ingestion..."
python -c "from app.rag.Ingestion import RunIdempotentRagIngestion; RunIdempotentRagIngestion()"

echo "[entrypoint] Starting gunicorn (2 workers) on :5000..."
# gunicorn auto-loads gunicorn.conf.py from the working directory
# (worker-exit hook for prometheus multiprocess cleanup lives there).
exec gunicorn --workers 2 --bind 0.0.0.0:5000 --access-logfile - wsgi:app
