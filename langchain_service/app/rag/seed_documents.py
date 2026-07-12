"""Seed documents ingested at startup.

Data only — no logic. Real document loading (loader -> chunker -> ingest)
is future work; these two policies exercise the full RAG path until then.
"""

from langchain_core.documents import Document

SEED_DOCUMENTS = [
    Document(
        page_content="Employees are permitted to use local scripting tools for local automation, provided no proprietary source code leaves company assets.",
        metadata={"source": "security_policy_v2.md", "category": "it_safety"},
    ),
    Document(
        page_content="Building, designing, or testing explosive devices or physical hazards on site is strictly prohibited and results in immediate termination.",
        metadata={"source": "hr_conduct_v1.md", "category": "physical_safety"},
    ),
]
