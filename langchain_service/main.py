# LOCAL DEV entry point only. The container runs entrypoint.sh -> gunicorn (wsgi.py).
from app.api.FlaskServer import create_app
from app.rag.Ingestion import RunIdempotentRagIngestion
from app.observability import init_observability

if __name__ == "__main__":
    # Ingestion runs BEFORE the server accepts traffic: a request must never race
    # against a half-populated vector store. (Also initializes the vector store.)
    RunIdempotentRagIngestion()

    app = create_app()
    init_observability(app)  # no-op unless OBSERVABILITY_ENABLED=true
    app.run(host="0.0.0.0", port=5000)
