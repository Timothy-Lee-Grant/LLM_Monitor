from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from app.models.factory import ModelFactory
from app.rag.vector_store import vector_store
from app.graph.state import ChatState
from app.prompts.MyPromptTemplates import PromptFactory

# Here we will define the nodes that flow from one to the other.

def policy_check_node(state: ChatState) -> dict:
    user_msg = state["messages"][-1].content

    #perform RAG on system for company policy based on intenal documents
    policy_chunks = vector_store.find_similar(user_msg, k=2)
    policy_text = "\n\n".join(d.page_content for d in policy_chunks)

    model = ModelFactory.get_chat_model(state["desired_model"])
    # get_policy_checker_prompt is a method: call it, then pipe the *returned template* into the model
    chain = PromptFactory.get_policy_checker_prompt() | model

    # invoke keys must match the template's placeholder names exactly
    raw = chain.invoke({"injected_company_policies": policy_text,
                        "user_message": user_msg})

    content_raw = raw.content
    # str.partition(":") splits on the FIRST colon only, returning a 3-tuple
    # (before, ":", after) — so "violated: reason: with colons" keeps the full reason intact.
    verdict, _, reason = content_raw.partition(":")

    return {"policy_verdict": verdict.strip().lower(),
            "policy_reason": reason.strip()}

def retrieve_node(state: ChatState) -> dict:
    usr_msg = state["messages"][-1].content
    chunks = vector_store.find_similar(usr_msg, k=4)
    return {"retrieved_chunks": chunks}

def blocked_node(state: ChatState) -> dict:
    msg = f"I can't help with that. Policy check result: {state['policy_reason']}"
    return {"answer": msg, "messages": [AIMessage(content=msg)]}
