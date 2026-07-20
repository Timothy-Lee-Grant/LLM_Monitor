import json
import os
import random
from langchain_ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.embeddings import DeterministicFakeEmbedding
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from app.models.Instructions import TryGetOllamaChatModel, TryGetOllamaEmbeddingModel
from app.prompts.mock_prompts import MOCK_RESPONSES
from langchain_ollama import OllamaEmbeddings


class MockChatModel(BaseChatModel):
    # BaseChatModel is a pydantic model, so fields are declared as class attributes
    # with type annotations (pydantic deep-copies mutable defaults per instance).
    response_pool: list = MOCK_RESPONSES["friendly_assistant"]

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        generation = ChatGeneration(message=self._respond(messages))
        return ChatResult(generations=[generation])

    def _respond(self, messages) -> AIMessage:
        """Deterministic tool-call protocol (plan 003 Step 3).

        The mock stays random-pool for normal chat, but supports two extra,
        deliberately-triggered behaviors so the tool loop is testable without
        a real (paid) model:

        1. User message "TOOLCALL <tool_name> <json_args?>" -> the mock emits
           exactly that tool call (empty content, tool_calls populated) — the
           graph then routes to the ToolNode like a live model would.
        2. Last message is a ToolMessage (the tool's result coming back
           around the loop) -> the mock answers with the result embedded, so
           tests can assert the REAL tool output (e.g. "pong: e2e") survived
           the full loop into the final answer.

        Neither trigger can fire on the existing chat/RAG paths (their
        rendered prompts never start with "TOOLCALL ", and they never carry
        ToolMessages), so prior behavior is unchanged.
        """
        last = messages[-1] if messages else None

        if isinstance(last, ToolMessage):
            return AIMessage(content=f"[mock] tool result: {last.content}")

        if (
            isinstance(last, HumanMessage)
            and isinstance(last.content, str)
            and last.content.startswith("TOOLCALL ")
        ):
            parts = last.content.split(maxsplit=2)
            name = parts[1] if len(parts) > 1 else ""
            try:
                args = json.loads(parts[2]) if len(parts) > 2 else {}
            except json.JSONDecodeError:
                args = {}
            return AIMessage(
                content="",
                tool_calls=[{"name": name, "args": args, "id": "mock-tool-call-0", "type": "tool_call"}],
            )

        return AIMessage(content=random.choice(self.response_pool))

    def bind_tools(self, tools, **kwargs):
        """Accept-and-ignore. BaseChatModel.bind_tools raises NotImplementedError
        by default, which would crash graph-tools in mock mode at bind time.
        The mock doesn't need the schemas — the TOOLCALL protocol above decides
        when to emit calls — so binding is the identity operation."""
        return self

    @property
    def _llm_type(self) -> str:
        return "mock-stub-provider"

class ModelFactory:

    knownPulledModels = {}

    # The user's post request will have a option for the model which they want to talk with.
    @staticmethod
    def get_chat_model(userDesiredModel: str) -> BaseChatModel:

        if os.getenv("LLM_MODE") == "mock":
            return MockChatModel()
        
        base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        res = TryGetOllamaChatModel(userDesiredModel, base_url)

        if not res:
            # There was an issue durring the instruction to get ollama service to pull the model
            return MockChatModel() 

        chatConnection = ChatOllama(
            model=userDesiredModel,
            base_url=base_url,
            temperature=0
        )

        return chatConnection


    @staticmethod
    def get_embedding_model(userDesiredModel:str):
        if os.getenv("LLM_MODE") == "mock":
            # Deterministic: identical text ALWAYS produces the identical vector,
            # so retrieval behavior is reproducible and assertable in tests.
            # size=768 matches nomic-embed-text's dimension, so mock and live
            # rows share the same pgvector column schema.
            # NOTE: the class name is SINGULAR (DeterministicFakeEmbedding) while its
            # sibling FakeEmbeddings is plural — inconsistent naming in langchain_core
            # itself, which is how the original typo slipped in (Timothy caught it).
            return DeterministicFakeEmbedding(size=768)

        # Fallback normalized to the compose *service* name (matches get_chat_model);
        # in practice OLLAMA_BASE_URL is always set by docker-compose.
        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")

        # (was hardcoded to "nomic-embed-text", ignoring this method's parameter)
        res = TryGetOllamaEmbeddingModel(userDesiredModel, base_url)
        if not res:
            # Fail LOUDLY at startup: silently continuing would fill pgvector
            # with garbage or crash on the first embed call mid-request.
            raise RuntimeError(f"Could not ensure embedding model '{userDesiredModel}' is available in Ollama.")

        embeddings = OllamaEmbeddings(
            model=userDesiredModel,
            base_url=base_url
        )
        return embeddings


