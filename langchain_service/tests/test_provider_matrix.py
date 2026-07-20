"""Provider-matrix tests (plan 003 Step 7): LLM_MODE x LLM_PROVIDER -> model.

Same lesson as test_factory.py (found-issue #1): factory branches that no
test CALLS are branches that can hide NameErrors behind green CI. Every
branch of the Step 4 matrix gets called here — construction only, offline;
no test in this file touches the network (fake keys satisfy the SDK
constructors, which validate config shape, not credentials).
"""

import os

import pytest

from app.models.factory import ModelFactory, MockChatModel

AZURE_ENV = {
    "AZURE_OPENAI_ENDPOINT": "https://example.openai.azure.com/",
    "AZURE_OPENAI_API_KEY": "fake-key",
    "AZURE_OPENAI_API_VERSION": "2024-10-21",
    "AZURE_OPENAI_CHAT_DEPLOYMENT": "gpt-4o-mini",
    "AZURE_OPENAI_EMBED_DEPLOYMENT": "text-embedding-3-small",
}
COMPAT_ENV = {
    "OPENAI_COMPAT_BASE_URL": "https://api.groq.com/openai/v1",
    "OPENAI_COMPAT_API_KEY": "fake-key",
    "OPENAI_COMPAT_MODEL": "llama-3.3-70b-versatile",
}


@pytest.fixture()
def live(monkeypatch):
    monkeypatch.setenv("LLM_MODE", "live")
    return monkeypatch


# ---- mock overrides everything ----

@pytest.mark.parametrize("provider", ["azure", "openai_compat", "ollama", None])
def test_mock_mode_ignores_provider(monkeypatch, provider):
    monkeypatch.setenv("LLM_MODE", "mock")
    if provider:
        monkeypatch.setenv("LLM_PROVIDER", provider)
    assert isinstance(ModelFactory.get_chat_model("x"), MockChatModel)


# ---- azure ----

def test_live_azure_chat_constructs(live):
    from langchain_openai import AzureChatOpenAI
    for k, v in AZURE_ENV.items():
        live.setenv(k, v)
    model = ModelFactory.get_chat_model("ignored", provider="azure")
    assert isinstance(model, AzureChatOpenAI)
    assert model.deployment_name == "gpt-4o-mini"   # deployment IS the model choice


def test_live_azure_embeddings_construct_with_768_dims(live):
    from langchain_openai import AzureOpenAIEmbeddings
    for k, v in AZURE_ENV.items():
        live.setenv(k, v)
    emb = ModelFactory.get_embedding_model("ignored", provider="azure")
    assert isinstance(emb, AzureOpenAIEmbeddings)
    assert emb.dimensions == 768   # pgvector column schema survives the migration


@pytest.mark.parametrize("missing", sorted(set(AZURE_ENV) - {"AZURE_OPENAI_EMBED_DEPLOYMENT"}))
def test_live_azure_fails_loudly_naming_the_missing_variable(live, missing):
    for k, v in AZURE_ENV.items():
        if k != missing:
            live.setenv(k, v)
    live.delenv(missing, raising=False)
    with pytest.raises(RuntimeError, match=missing):
        ModelFactory.get_chat_model("x", provider="azure")


def test_live_azure_empty_string_counts_as_missing(live):
    """The compose `${VAR:-}` subtlety: unset host vars arrive as EMPTY
    strings — present to a KeyError check, useless as config."""
    for k, v in AZURE_ENV.items():
        live.setenv(k, v)
    live.setenv("AZURE_OPENAI_API_KEY", "")
    with pytest.raises(RuntimeError, match="AZURE_OPENAI_API_KEY"):
        ModelFactory.get_chat_model("x", provider="azure")


# ---- openai_compat ----

def test_live_compat_chat_constructs_with_env_model(live):
    from langchain_openai import ChatOpenAI
    for k, v in COMPAT_ENV.items():
        live.setenv(k, v)
    model = ModelFactory.get_chat_model("request-model-ignored-when-env-set", provider="openai_compat")
    assert isinstance(model, ChatOpenAI)
    assert model.model_name == "llama-3.3-70b-versatile"


def test_live_compat_embeddings_refuse_by_design(live):
    for k, v in COMPAT_ENV.items():
        live.setenv(k, v)
    with pytest.raises(RuntimeError, match="no embeddings path"):
        ModelFactory.get_embedding_model("x", provider="openai_compat")


# ---- unknown ----

def test_unknown_provider_raises_value_error(live):
    with pytest.raises(ValueError, match="bogus"):
        ModelFactory.get_chat_model("x", provider="bogus")
    with pytest.raises(ValueError, match="bogus"):
        ModelFactory.get_embedding_model("x", provider="bogus")


# ---- default resolution ----

def test_provider_arg_beats_env(live, monkeypatch):
    """The per-pipeline binding must WIN over the deployment default —
    that's the whole routing mechanism."""
    from langchain_openai import ChatOpenAI
    monkeypatch.setenv("LLM_PROVIDER", "azure")
    for k, v in COMPAT_ENV.items():
        live.setenv(k, v)
    model = ModelFactory.get_chat_model("x", provider="openai_compat")
    assert isinstance(model, ChatOpenAI)
