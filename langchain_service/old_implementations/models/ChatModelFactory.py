
# This should return back to me based on the enviroment variables passed in, either a real (live)
# model, or a fake model

import os

def ChatModelFactory():
    myPassedInParameter = os.getenv("LLM_MODE")
    if myPassedInParameter == "mock":
        # give the asking function a fake mock model
        from langchain_core.language_models import FakeListChatModel
        return FakeListChatModel(responses=_canned_for(scenario)) # TODO: investigate this
    if myPassedInParameter == "live":
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=os.getenv("LLM_MODEL", "qwen2.5:1.5b"),
            base_url=os.getenv("OLLAMA_BASE_URL"),
            temperature=0
        )