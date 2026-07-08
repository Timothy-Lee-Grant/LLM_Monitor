import os
import random
from langchain_ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.messages import AIMessage
from app.models.Instructions import TryGetOllamaChatModel, TryGetOllamaEmbeddingModel
from app.prompts.MyPromptTemplates import MockChatTypeDictionary, number_of_chat_types
from langchain_ollama import OllamaEmbeddings


class MockChatModel(BaseChatModel):

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):

        # I looked at an example for the two lines below
        #generation = ChatGeneration(message=AIMessage(content=mockResponsesList[random.randint(0,number_of_chat_types-1)]))
        generation = ChatGeneration(message=AIMessage(content="Fake response back"))
        return ChatResult(generations=[generation])
    
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
            temperature=0
        )

        return chatConnection


    @staticmethod
    def get_embedding_model(userDesiredModel:str):
        # TODO: Does not make sense to be in mock mode and call this.
        if os.getenv("LLM_MODE") == "mock":
            return 

        base_url=os.getenv("OLLAMA_BASE_URL", "http://ollama_service:11434")

        res = TryGetOllamaEmbeddingModel("nomic-embed-text", base_url)

        embeddings = OllamaEmbeddings(
            model=userDesiredModel,
            base_url=base_url
        )
        return embeddings


