import os
import requests
from langchain_ollama import ChatOllama
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.outputs import ChatResult, ChatGeneration
from langchain_core.messages import AIMessage





# This should act just as a real llm but give back messages which are probabalistic out of a list of predefined message responses.
# We will need to respect the shape which the response will need to be (so it will need to conform to the same shape which our normal ChatModel is. I think BaseChatModel will help with this.....)

# TODO: I am concerned because I know that my project will have different models doing different things. 
# For example, I will have a llm judge, a friendly assistant, a tool selector, a policy violation checker, etc
# Therefore my responses can not be probabalistic wholly through return a single index of a list. (maybe I can have many different litst based on each of those llm types??)
# OR should that be part of the system or some other compoent in my project???
class MockChatModel(BaseChatModel):
    _a = []

class ModelFactory:

    knownPulledModels = {}

    # The user's post request will have a option for the model which they want to talk with.
    @staticmethod
    def get_chat_model(userDesiredModel: str) -> ChatOllama:

        if os.getenv("LLM_MODE") == "mock":
            return MockChatModel
        
        # I need to do a POST request to my ollama service (if not in mock mode)

        # Not 'localhost' but I am still shaking on docker networking
        base_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        try:
            print(f"Checking if model {userDesiredModel} is locally available in my ollama service docker container.")
            response = requests.get(f"{base_url}/api/tags", timeout=10)
            response.raise_for_status()

            #parse the local model list which ollama service gave back to me
            local_models = response.json().get("models", [])

            # look through downloaded tags (ollama uses exact name matching or maps to :latest)
            downloaded_names = [m["name"] for m in local_models]
            
            # standardize tag check: if no tag given, chekc both raw name and ':latest'
            has_model = (userDesiredModel in downloaded_names) or (f"{userDesiredModel}:latest" in downloaded_names)

            if not has_model:
                # Now we need to send a POST request to our ollama docker container telling it to pull the requested user's model
                # TODO: In the future I will need to secure this so that only 'accepted' models are allowed to be passed in by the user
                print("Model was NOT found in ollama")
                print("Pulling Model Now")
                payload = {
                    "model":userDesiredModel,
                    "stream": False     #setting stream to false will cause this to wait until ollama has finished fully pulling the model
                }

                response = requests.post(f"{base_url}/api/pull", json=payload, timeout=None) # timeout none to avoid timing out for networking when we are pulling and download a large model.

                if response.json().get("status") != "success":
                    print("Unable to download model")
                    assert(False)

        except requests.RequestException as e:
            print(f"Error communicating with the ollama service container during get_chat_model creation")
            return None
        
        #


    @staticmethod
    def get_embedding_model():
        # nomic-embed-text
        return None














class MockChatModel_old(BaseChatModel):
    ''' A minimial, local mock llm wrapper for isolated pipeline validation.'''

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