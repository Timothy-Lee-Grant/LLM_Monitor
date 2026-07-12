"""Startup ingestion. Thin orchestration over the vector store layer:
connect, then upsert the seed documents. Genuinely idempotent now —
deterministic IDs mean restarts can never create duplicate rows.

Runs in BOTH modes: in mock mode the embeddings are deterministic fakes
(see ModelFactory.get_embedding_model), but pgvector is real.
"""

from app.rag.vector_store import vector_store
from app.rag.seed_documents import SEED_DOCUMENTS


def RunIdempotentRagIngestion() -> bool:
    vector_store.initialize()
    added_ids = vector_store.add_documents_idempotent(SEED_DOCUMENTS)
    skipped = len(SEED_DOCUMENTS) - len(added_ids)
    print(
        f"RAG ingestion complete: {len(added_ids)} added, {skipped} already present "
        f"(skipped, no re-embedding) in '{vector_store.collection_name}'."
    )
    return True
