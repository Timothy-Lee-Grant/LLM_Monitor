"""Vector store access layer.

Design rules (plan 001, Step 3):
- NO module-level side effects: importing this module never touches the network
  or the database. All connections happen inside initialize(), which main.py
  calls explicitly at startup (after compose reports pgvector healthy).
- Mode-agnostic: mock vs live differs ONLY in which embedding model the
  ModelFactory hands us. pgvector itself runs identically in both modes,
  so the full RAG path is exercisable (and CI-testable) without Ollama.
"""

import os
import hashlib

from langchain_postgres import PGVector
from langchain_core.documents import Document

from app.models.factory import ModelFactory
from app.observability import get_tracer


class VectorStoreManager:

    def __init__(self):
        self._store: PGVector | None = None
        self.collection_name: str | None = None

    def initialize(self) -> None:
        """Connect to pgvector and bind the collection. Called once, at startup.

        Collections are per-mode ("company_policies_mock" / "company_policies_live")
        so fake-embedding rows can never pollute live similarity searches when both
        modes share the same docker volume.
        """
        mode = os.getenv("LLM_MODE", "mock")
        db_user = os.getenv("POSTGRES_USER", "admin")
        db_pass = os.getenv("POSTGRES_PASSWORD", "secret_pass")
        db_name = os.getenv("POSTGRES_DB", "vectordb")
        db_host = os.getenv("POSTGRES_HOST", "pgvector-service")  # compose service name

        connection_string = f"postgresql+psycopg://{db_user}:{db_pass}@{db_host}:5432/{db_name}"

        self.collection_name = f"company_policies_{mode}"

        embeddings = ModelFactory.get_embedding_model(os.getenv("EMBEDDING_MODEL", "nomic-embed-text"))

        self._store = PGVector(
            embeddings=embeddings,
            connection=connection_string,
            collection_name=self.collection_name,
        )

    def add_documents_idempotent(self, docs: list[Document]) -> list[str]:
        """Add documents with deterministic IDs, embedding ONLY what's genuinely new.

        id = sha256(page_content), which buys two guarantees:
        - idempotency: same content -> same id -> re-runs can never duplicate rows;
        - safe skipping: if an id already exists, its content is BY DEFINITION
          identical, so we don't re-embed it (embedding is the expensive step —
          one get_by_ids SELECT replaces N embedding computations).
          (Timothy's found-issue #2, plan 001.)

        Known, deliberate limitation: an EDITED document gets a new id, so its
        old row remains as an orphan. Delta-sync with deletion (LangChain
        RecordManager / indexing API) belongs to the future document-ingestion
        plan — see plan 001 Found Issues discussion.

        Returns the ids that were actually added (empty list = everything
        was already present).
        """
        store = self._require_initialized()
        ids = [self.deterministic_id(d) for d in docs]

        existing_ids = {doc.id for doc in store.get_by_ids(ids)}
        missing = [(doc_id, doc) for doc_id, doc in zip(ids, docs) if doc_id not in existing_ids]

        if missing:
            store.add_documents([doc for _, doc in missing], ids=[doc_id for doc_id, _ in missing])

        return [doc_id for doc_id, _ in missing]

    def find_similar(self, message: str, k: int = 4, score_threshold: float | None = None) -> list[Document]:
        """Return up to k most similar documents to `message`.

        score_threshold guards against erroneous retrievals (a nearest neighbor
        always exists, even for off-topic queries — "nearest" does not mean "near").
        PGVector returns cosine DISTANCE: lower = closer, so we keep docs with
        distance <= threshold. None disables the guard (current default).
        """
        # Span is a no-op unless observability is enabled (see app/observability.py).
        # rag.top_score is the distance of the BEST hit — watching it across queries
        # is the raw material for tuning score_threshold with data (plan 002 eval).
        with get_tracer().start_as_current_span("rag.retrieve") as span:
            span.set_attribute("rag.k", k)
            span.set_attribute("rag.collection", self.collection_name or "uninitialized")

            results = self._require_initialized().similarity_search_with_score(message, k=k)
            if score_threshold is not None:
                results = [(doc, score) for doc, score in results if score <= score_threshold]

            span.set_attribute("rag.results", len(results))
            if results:
                span.set_attribute("rag.top_score", float(results[0][1]))

            return [doc for doc, _score in results]

    @staticmethod
    def deterministic_id(doc: Document) -> str:
        return hashlib.sha256(doc.page_content.encode("utf-8")).hexdigest()

    def _require_initialized(self) -> PGVector:
        if self._store is None:
            raise RuntimeError(
                "VectorStoreManager used before initialize() — main.py must call "
                "vector_store.initialize() before the server accepts traffic."
            )
        return self._store


# Shared singleton: one connection pool per process, stateless across requests.
vector_store = VectorStoreManager()
