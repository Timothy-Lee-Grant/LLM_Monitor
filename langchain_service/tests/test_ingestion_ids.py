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


# ---- skip-existing behavior (Timothy's found-issue #2) ----

class _FakeStore:
    """Stands in for PGVector: remembers rows, counts add_documents calls."""

    def __init__(self):
        self.rows: dict[str, Document] = {}
        self.add_calls = 0

    def get_by_ids(self, ids):
        return [
            Document(page_content=self.rows[i].page_content, id=i)
            for i in ids if i in self.rows
        ]

    def add_documents(self, docs, ids):
        self.add_calls += 1
        for doc_id, doc in zip(ids, docs):
            self.rows[doc_id] = doc


def _manager_with_fake_store():
    manager = VectorStoreManager()
    manager._store = _FakeStore()
    return manager, manager._store


def test_first_ingestion_adds_everything():
    manager, store = _manager_with_fake_store()
    added = manager.add_documents_idempotent(SEED_DOCUMENTS)
    assert len(added) == len(SEED_DOCUMENTS)
    assert len(store.rows) == len(SEED_DOCUMENTS)


def test_second_ingestion_adds_nothing_and_never_hits_the_embedding_path():
    manager, store = _manager_with_fake_store()
    manager.add_documents_idempotent(SEED_DOCUMENTS)

    added_again = manager.add_documents_idempotent(SEED_DOCUMENTS)

    assert added_again == []                       # nothing new
    assert len(store.rows) == len(SEED_DOCUMENTS)  # no duplicates
    assert store.add_calls == 1                    # add_documents (the embedding
    # path) was NOT invoked on the second run — this is the compute saving.


def test_partial_overlap_only_adds_the_new_document():
    manager, store = _manager_with_fake_store()
    manager.add_documents_idempotent(SEED_DOCUMENTS)

    new_doc = Document(page_content="A brand new policy about parking.", metadata={"source": "parking_v1.md"})
    added = manager.add_documents_idempotent(SEED_DOCUMENTS + [new_doc])

    assert added == [VectorStoreManager.deterministic_id(new_doc)]
    assert len(store.rows) == len(SEED_DOCUMENTS) + 1
