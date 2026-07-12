"""Factory tests — added after Timothy's found-issue #1 (plan 001, Found Issues).

The lesson encoded here: CI was green while a NameError hid in
get_embedding_model, because no test ever CALLED it (retrieval is
monkeypatched in the API tests). Python resolves names at call time,
not import time — so an import can succeed while a call site still
references a name that doesn't exist. Coverage gap, closed.
"""

from app.models.factory import ModelFactory


def test_mock_embedding_model_is_constructible_and_deterministic():
    model = ModelFactory.get_embedding_model("nomic-embed-text")

    vec_a = model.embed_query("same text")
    vec_b = model.embed_query("same text")
    vec_c = model.embed_query("different text")

    assert len(vec_a) == 768            # must match nomic-embed-text's dimension
    assert vec_a == vec_b               # deterministic: same text -> same vector
    assert vec_a != vec_c               # different text -> different vector


def test_mock_chat_model_reports_contract_label():
    model = ModelFactory.get_chat_model("anything")
    assert model._llm_type == "mock-stub-provider"  # CONTRACTS.md §2 model_used value
