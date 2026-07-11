from app.api.FlaskServer import IntializeFlaskEndpoints
from app.rag.Ingestion import RunIdempotentRagIngestion

if __name__ == "__main__":
    # Ingestion runs BEFORE the server accepts traffic: a request must never race
    # against a half-populated vector store.
    RunIdempotentRagIngestion()

    app = IntializeFlaskEndpoints()

    # debug=True removed: the Flask reloader imports the module twice, which
    # double-executes module-level code (and would double-run ingestion).
    # Step 6 replaces this dev server with gunicorn entirely.
    app.run(host="0.0.0.0", port=5000)
