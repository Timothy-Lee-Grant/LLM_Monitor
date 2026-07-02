







import os
from langchain_ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.messages import AIMessage

class MockChatModel(BaseChatModel):
    ''' A minimial, local mock llm wrapper for isolated pipeline validation.'''

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # always return a clean mock response structure instantly without calling out to the network (docker)
        mock_text = "[MOCK RESPONSE] Policy analysis evaluation bypassed. Environment configuration set to mock."
        generation = ChatGeneration(messages=AIMessage(content=mock_text))

        return ChatResult(generation=[generation])
    
    @property
    def _llm_type(self) -> str:
        return "mock-stub-provider"

class ModelFactory:
    @staticmethod
    def get_model() -> BaseChatModel:
        ''' determines model intialization strategy based on host environment variables '''
        env = os.getenv("LLM_MODE", "mock").lower()
        
        if env == "live":
            model_name = os.getenv("LLM_MODEL", "llama3.3:8b")
            print("[Factory] Constructing live interface link to actual llm model", flush=True)

            return ChatOllama(
                model=model_name,
                temperature=0.0,
                base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
            )
        print("[Factory] Instantiating low resource mock validation layer", flush=True)
        return MockChatModel()