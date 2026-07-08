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
    friendlyAssistentPrompt = GetHappyEncouragingAssistentPrompt()

    # get a model
    model = ModelFactory.get_chat_model(user_requested_model)

    chain = friendlyAssistentPrompt | model | StrOutputParser()

    # invoke model and return it
    # TODO: as of now, friendlyAssistentPrompt does not take in any placeholder values for the user's message
    model_response = chain.invoke({"user_message":user_message})

    return model_response



'''
def ProcessNormalChatMessageRequest(user_id: str, user_msg: str, desiredModel:str):
    # This will do all of the high level operations
    policyViolationPrompt = pt.GetPolicyViolationCheckerPrompt()
    chatModel = ModelFactory.get_chat_model(userDesiredModel=desiredModel)
    #policyCheckChain = None    # This should be done in the chain file
    policyCheckChain = policyViolationPrompt | chatModel | StrOutputParser()
    result = policyCheckChain.invoke({user_msg})

    if CheckViolated():
        return None
    
    # Maybe this is the time I should do the RAG search for extra documents which would be helpful for the llm in responding to the users message.
    topK = FindSemanticlyClosestElement(user_msg, "supplemential_knowledge.md", 5)

    # Now we need to invoke tools until the task is accomplished
    .... # No idea how to do this.

    # finally we have all the information we need and can respond back to the user

    # I will now need to inject the previous chat messages which the user has already sent to me in the past
    # I think that means I need some kind of database from which to go and get that info, then when it comes back to me, I don't know what format it will be 
    # or how to get it into the format that I need. 
    # but ultimately I think the process that I should be doing is that now that I have all this information for this particular message, I need to grab the entire history object
    # and inject this current message and all of the supplemental data and information into this object which is what I will be sending to the llm
    prev_messages = _

    new_message = prev_messages.append(user_msg, topK, otherInfo)

    friendlyAssistantPrompt = pt.GetHappyEncouragingAssistentPrompt()
    chain = new_message | friendlyAssistantPrompt | StrOutputParser()

    result = chain.invoke({something})

    information_to_append = (
        "user":user_msg,
        "llm":result
    )

    prev_messages += information_to_append

    # so I think I should only perminately store the user's message and the llm's response in the chat history (maybe it is wrong)
    # then I should go and store it back into what ever database I should be using (would this be in the memory file?)

    return result
'''