





from app.api.FlaskServer import IntializeFlaskEndpoints
from app.rag.Ingestion import RunIdempotentRagIngestion

if __name__ == "__main__":
    app = IntializeFlaskEndpoints()
    RunIdempotentRagIngestion()
    app.run(host="0.0.0.0", port=5000, debug=True)