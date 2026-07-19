"""Prometheus metrics (plan 002 Step 4). PULL model: we only keep numbers in
memory; Prometheus scrapes GET /metrics on its own schedule. Nobody scraping =
near-zero cost, which is why (unlike traces) this needs no enable/disable gate.

Label discipline (concepts doc 018 §2.2): every metric is labeled by
pipeline_id — bounded cardinality, 4 values. user_id is deliberately NOT a
label: unbounded label values explode the metrics store (one time series per
unique combination). user-level questions belong to traces, not metrics.

THE GUNICORN GOTCHA (real production issue, worth remembering for interviews):
each of gunicorn's forked workers has its own process memory, so naive
prometheus_client counters live per-worker — a scrape would return whichever
worker happened to answer, and numbers would bounce around. Fix: prometheus_client
"multiprocess mode" — workers write shared mmap files under
PROMETHEUS_MULTIPROC_DIR (set in entrypoint.sh), and the /metrics handler
aggregates across all of them via MultiProcessCollector.
"""

import os

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Histogram,
    REGISTRY,
    generate_latest,
    multiprocess,
)

LLM_REQUESTS = Counter(
    "llm_requests_total",
    "Pipeline dispatches, by pipeline and outcome.",
    ["pipeline_id", "status"],
)

LLM_DURATION = Histogram(
    "llm_request_duration_seconds",
    "End-to-end pipeline dispatch duration.",
    ["pipeline_id"],
    # Wide buckets: mock replies are ms, live model calls are seconds-to-minutes.
    buckets=[0.01, 0.05, 0.1, 0.5, 1, 2.5, 5, 10, 30, 60, 120],
)

LLM_TOKENS = Counter(
    "llm_tokens_total",
    "Tokens processed, by pipeline and direction (prompt|completion). Zero in mock mode.",
    ["pipeline_id", "direction"],
)


def metrics_payload() -> tuple[bytes, str]:
    """Render current metrics in Prometheus text format (see module docstring
    for why multiprocess mode needs a purpose-built registry per scrape)."""
    if os.getenv("PROMETHEUS_MULTIPROC_DIR"):
        registry = CollectorRegistry()
        multiprocess.MultiProcessCollector(registry)
    else:
        registry = REGISTRY  # single-process: dev server, pytest
    return generate_latest(registry), CONTENT_TYPE_LATEST
