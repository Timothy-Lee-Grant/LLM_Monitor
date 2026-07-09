from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.models.factory import ModelFactory
from app.rag.Ingestion import FindSemanticlyClosestElement
from app.graph.state import ChatState
from app.prompts.MyPromptTemplates import GetPolicyViolationCheckerPrompt

# Here we will define the nodes that flow from one to the other.

def policy_check_node(state: ChatState) -> dict:
    user_msg = state["messages"][-1].content

    #perform RAG on system for company policy based on intenal documents
    policy_chunks = FindSemanticlyClosestElement(user_msg, k=2)
    policy_text = "\n\n".join(d.page_content for d in policy_chunks)

    model = ModelFactory.get_chat_model(state["disired_model"])
    chain = GetPolicyViolationCheckerPrompt | model 

    raw = chain.invoke({"injectedCompanyPolicy": policy_text,
                        "user_message": user_msg})
    
    content_raw = raw.content
    verdict, _, reason = content_raw.partition(":") # I don't know what this partition command is doing.

    return {"policy_verdict": verdict.strip().lower(),
            "policy_reason": reason.strip()}

# I wrote this one a long time ago (just to get an initial feel for what langgraph is doing)
def retrieve_node(state: ChatState) -> dict:  
    #Read what I need from the shared state
    user_query = state["user_msg"]

    #Execute the atomic operation
    topK_chunks = FindSemanticlyClosestElement(user_query, "supplemental_knowledge.md", 5)

    #return a dict of ONLY the keys that I want t oupdate in the shared state
    return {"chunks": topK_chunks}