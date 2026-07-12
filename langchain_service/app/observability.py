"""Observability wiring for the langchain_service (plan 002 Step 3).

The pattern to understand here is OTel's API/SDK SPLIT:

- The API (`opentelemetry.trace`) is always importable and always safe:
  if no SDK provider has been configured, every span it hands out is a
  NO-OP — nanoseconds of overhead, no network, no errors.
- The SDK (provider + exporter) is only configured inside
  init_observability(), and only when OBSERVABILITY_ENABLED=true.

Consequence: application code (registry, vector_store) creates spans
UNCONDITIONALLY, with no `if enabled:` checks scattered around — the
provider gate does the gating. This is the idiomatic OTel design, and
it's also why the unit tests exercise the instrumented code paths for
free (spans are no-ops there).
"""

import os

from opentelemetry import trace

# Lazy proxy: binds to the real provider if/when init_observability() sets one.
_tracer = trace.get_tracer("llm_monitor.langchain_service")


def get_tracer():
    return _tracer


def observability_enabled() -> bool:
    return os.getenv("OBSERVABILITY_ENABLED", "false").lower() == "true"


def init_observability(app=None) -> bool:
    """Configure the OTel SDK (push traces to the collector) and instrument Flask.

    Called once per process (each gunicorn worker via wsgi.py; local dev via
    main.py). SDK imports live inside the function so the disabled path never
    pays for them. Returns True when observability is active.
    """
    if not observability_enabled():
        return False

    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    # Standard OTEL env var wins; container-network default otherwise
    # (mirrors the gateway's logic in Program.cs).
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://otel-collector:4317")

    # "langchain_service" = our label in Jaeger's service dropdown, next to "gateway".
    provider = TracerProvider(resource=Resource.create({"service.name": "langchain_service"}))
    # Batch processor = same decoupling idea as the collector's batch stage:
    # spans buffer briefly instead of one network call per span.
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True)))
    trace.set_tracer_provider(provider)

    if app is not None:
        # Auto-instruments Flask: a server span per request, AND — the headline —
        # extraction of the gateway's `traceparent` header, so our spans CONTINUE
        # the gateway's trace instead of starting a fresh one.
        from opentelemetry.instrumentation.flask import FlaskInstrumentor
        FlaskInstrumentor().instrument_app(app)

    return True
