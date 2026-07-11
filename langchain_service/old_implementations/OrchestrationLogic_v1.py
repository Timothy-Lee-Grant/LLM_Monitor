# Retired from app/orchestration/OrchestrationLogic.py during plan 001 Step 4 (2026_07_11). Replaced by pipelines.py + registry.py. Kept for reference only.

from app.models.factory import ModelFactory
from app.rag.vector_store import vector_store
from app.prompts.MyPromptTemplates import PromptFactory

from langchain_core.output_parsers import StrOutputParser


'''
This will provide project an interface to perform logic
'''


# NOTE (Step 4 of the plan): these workers get refactored into registry pipelines
# with a uniform signature. Step 2 only makes them correct.
def test_langchain_chatnosecurity_worker(user_id, user_requested_model, user_message) -> str:
    # get a prompt
    friendlyAssistentPrompt = PromptFactory.get_assistant_prompt()

    # get a model
    model = ModelFactory.get_chat_model(user_requested_model)

    chain = friendlyAssistentPrompt | model | StrOutputParser()

    # The unified assistant prompt always declares {context}; the non-RAG path
    # satisfies it with an empty string (per the PromptFactory docstring).
    model_response = chain.invoke({"user_message": user_message, "context": ""})

    return model_response

def test_langchain_chatnosecurityrag_worker(user_id, user_requested_model, user_message) -> str:
    # get a prompt
    friendlyAssistentPrompt = PromptFactory.get_assistant_prompt()

    # get top k nearest elements
    list_of_close_documents = vector_store.find_similar(user_message, k=2)

    added_context = "\n\n".join([doc.page_content for doc in list_of_close_documents])

    # get a model
    model = ModelFactory.get_chat_model(user_requested_model)

    chain = friendlyAssistentPrompt | model | StrOutputParser()

    model_response = chain.invoke({"user_message":user_message, "context": added_context})

    return model_response
