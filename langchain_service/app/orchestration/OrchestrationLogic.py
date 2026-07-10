import app.prompts.MyPromptTemplates as pt
from app.models.factory import ModelFactory
from app.rag.Ingestion import FindSemanticlyClosestElement
from app.prompts.MyPromptTemplates import *

from langchain_core.output_parsers import StrOutputParser


'''
This will provide project an interface to perform logic
'''


# Ideally this would be wrapped up in a class which dynamically selects the operations based on parameters, but we are just trying to get things to work.
def test_langchain_chatnosecurity_worker(user_id, user_requested_model, user_message) -> str:
    # get a prompt
    friendlyAssistentPrompt = GetHappyEncouragingAssistentRagPrompt()

    # get a model
    model = ModelFactory.get_chat_model(user_requested_model)

    chain = friendlyAssistentPrompt | model | StrOutputParser()

    # invoke model and return it
    # TODO: as of now, friendlyAssistentPrompt does not take in any placeholder values for the user's message
    model_response = chain.invoke({"user_message":user_message})

    return model_response

def test_langchain_chatnosecurityrag_worker(user_id, user_requested_model, user_message) -> str:
    # get a prompt
    friendlyAssistentPrompt = GetHappyEncouragingAssistentRagPrompt()

    # get top k nearest elements
    list_of_close_documents = FindSemanticlyClosestElement(user_message,k=2)

    added_context = "\n\n".join([doc.page_content for doc in list_of_close_documents])

    # get a model
    model = ModelFactory.get_chat_model(user_requested_model)

    chain = friendlyAssistentPrompt | model | StrOutputParser()

    model_response = chain.invoke({"user_message":user_message, "context": added_context})

    return model_response
