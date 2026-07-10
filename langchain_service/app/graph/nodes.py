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

def retrieve_node(state: ChatState) -> dict:
    usr_msg = state["messages"][-1].content
    chunks = FindSemanticlyClosestElement(usr_msg, k=4)
    return {"retrieved_chunks": chunks}

def blocked_node(state: ChatState) -> dict:
    msg = f"I can't help with that. Policy check result: {state['policy_reason']}"
    return {"answer": msg, "messages": [AIMessage(content=msg)]}
