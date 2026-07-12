"""Gunicorn entry point:  gunicorn wsgi:app

Process model (why this file does what it does):
- entrypoint.sh runs RAG ingestion ONCE, in its own process, before gunicorn starts.
- Then gunicorn forks N workers; each worker imports this module, so each gets
  its OWN vector store connection pool via initialize() — connections must not
  be shared across forked processes.
- create_app() itself never touches the DB, so unit tests can build an app
  without any containers running.
"""

from app.rag.vector_store import vector_store
from app.api.FlaskServer import create_app
from app.observability import init_observability

vector_store.initialize()
app = create_app()
# Per-worker, like the connection pool: each forked process needs its own
# tracer provider + exporter. No-op unless OBSERVABILITY_ENABLED=true.
init_observability(app)
