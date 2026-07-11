"""Idempotent-ingestion guarantee, tested at its root (plan 001 Step 3c/9b).

The acceptance criterion ("restart twice, row count unchanged") holds because
document IDs are a pure function of content. That purity is what these tests
pin down — no database required.
"""

import hashlib

from langchain_core.documents import Document

from app.rag.vector_store import VectorStoreManager
from app.rag.seed_documents import SEED_DOCUMENTS


def test_same_content_same_id():
    a = Document(page_content="identical text", metadata={"source": "a.md"})
    b = Document(page_content="identical text", metadata={"source": "b.md"})
    # Metadata is deliberately NOT part of the id: content defines identity.
    assert VectorStoreManager.deterministic_id(a) == VectorStoreManager.deterministic_id(b)


def test_different_content_different_id():
    a = Document(page_content="text one")
    b = Document(page_content="text two")
    assert VectorStoreManager.deterministic_id(a) != VectorStoreManager.deterministic_id(b)


def test_id_is_sha256_of_content():
    doc = Document(page_content="known text")
    expected = hashlib.sha256("known text".encode("utf-8")).hexdigest()
    assert VectorStoreManager.deterministic_id(doc) == expected


def test_seed_documents_have_unique_ids():
    ids = [VectorStoreManager.deterministic_id(d) for d in SEED_DOCUMENTS]
    assert len(ids) == len(set(ids))
