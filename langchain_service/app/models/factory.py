import os

from langchain_ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.messages import AIMessage
from app.models.Instructions import TryGetOllamaModel




# This should act just as a real llm but give back messages which are probabalistic out of a list of predefined message responses.
# We will need to respect the shape which the response will need to be (so it will need to conform to the same shape which our normal ChatModel is. I think BaseChatModel will help with this.....)

# TODO: I am concerned because I know that my project will have different models doing different things. 
# For example, I will have a llm judge, a friendly assistant, a tool selector, a policy violation checker, etc
# Therefore my responses can not be probabalistic wholly through return a single index of a list. (maybe I can have many different litst based on each of those llm types??)
# OR should that be part of the system or some other compoent in my project???
class MockChatModel(BaseChatModel):
    _a = []

    # Let me think about what I want for this method, then I hope it will be clear what I should do.
    '''
    This class is going to give the caller a object which is pretending to be a OllamaChat object.
    First meta observation: I should think about things in terms of contracts. When I don't know what I should do. I should think about the question 'what is the contract of this method or class?'
    This means that I will need to know what type of model the user is trying to get. This requires me to have a modelType parameter passed in.
    Now I am thinking about where modelType should come from. To me it makes sense that it would be in the file that has the standard prompts because this is where the different types of chat types will be enumerated.
    '''
    def _generate(self, modelType):
        pass

class ModelFactory:

    knownPulledModels = {}

    # The user's post request will have a option for the model which they want to talk with.
    @staticmethod
    def get_chat_model(userDesiredModel: str) -> ChatOllama:

        if os.getenv("LLM_MODE") == "mock":
            return MockChatModel
        
        base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        res = TryGetOllamaModel(userDesiredModel, base_url)

        if not res:
            # There was an issue durring the instruction to get ollama service to pull the model
            return None # Or maybe we return a mock?

        # As of this point we know that we do have a model in ollama that matches the user's desired model

        # I should now come in and get that connection wrapper with ollama using the langchain wrapper

        chatConnection = ChatOllama(
            model=userDesiredModel,
            temperature=0
        )

        return chatConnection




    @staticmethod
    def get_embedding_model():
        # nomic-embed-text
        return None














class MockChatModel_old(BaseChatModel):
    ''' A minimial, local mock llm wrapper for isolated pipeline validation.'''

    # I am still shaky on undersanding the idea of **kwargs I know they are used so much in EVERY languae, but I dont know much about how argument variables. What are they, where are they passed in from, how do we manipulate them, etc.
    # I think this idea scared me when I was first learning programming (in C) because it was something with a dynamic something (I think it had a ... inside of a function which took an indefinate number of items into it), like the printf(...)
    # so when I first saw it I didn't understand it and was so confused. but now I am strong in the concepts so I should revisit it.
    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        # always return a clean mock response structure instantly without calling out to the network (docker)
        mock_text = "[MOCK RESPONSE] Policy analysis evaluation bypassed. Environment configuration set to mock."
        generation = ChatGeneration(messages=AIMessage(content=mock_text))

        return ChatResult(generation=[generation])
    
    @property
    def _llm_type(self) -> str:
        return "mock-stub-provider"

class ModelFactory_old:
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
    

# This demonstrates a Multiton / Registry Pattern
# But I will not use it because creating a ChatOllama object is not heavy.
'''
class ModelFactory2:
    _instances = {}

    @classmethod
    def get_models(cls, codel_name: str) -> BaseChatModel:
        # if we aready created a client for this model, reuse it.
        if model_name not in cls._instances:
            cls._instances[model_name] = ChatOllama(model=model_name, temperature=0)
        return cls._instances[model_name]
'''