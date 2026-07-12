"""Observability gating tests (plan 002 Steps 3/5).

The whole design rests on "disabled = true no-op". These tests pin that:
pipelines call get_langchain_callbacks() unconditionally, so if the gate
ever leaks (e.g., tries to construct a Langfuse client without a server),
every contract test would need containers. Cheap insurance.
"""

from app.observability import observability_enabled, get_langchain_callbacks


def test_observability_disabled_in_tests():
    assert observability_enabled() is False


def test_callbacks_empty_when_disabled():
    assert get_langchain_callbacks() == []
