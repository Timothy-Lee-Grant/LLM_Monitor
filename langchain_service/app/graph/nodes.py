"""Graph nodes. Each node: ChatState -> partial state update dict.

Nodes share the same building blocks as the chain pipelines
(ModelFactory / PromptFactory / vector_store) — one set of components,
two execution engines.

Retired policy_check_node / blocked_node live in
old_implementations/graph_policy_nodes_v1.py (policy checking is a
non-goal for plan 001; the prompt remains in PromptFactory).
"""

from langchain_core.messages import AIMessage
from langchain_core.output_parsers import StrOutputParser

from app.models.factory import ModelFactory
from app.prompts.MyPromptTemplates import PromptFactory
from app.rag.vector_store import vector_store
from app.graph.state import ChatState


def retrieve_node(state: ChatState) -> dict:
    """Fetch context for the latest user message. Only wired into RAG graphs."""
    user_msg = state["messages"][-1].content
    chunks = vector_store.find_similar(user_msg, k=4)
    return {"retrieved_chunks": chunks}


def agent_node(state: ChatState) -> dict:
    """Invoke the model with whatever context retrieval produced (possibly none)."""
    user_msg = state["messages"][-1].content
    context = "\n\n".join(doc.page_content for doc in state.get("retrieved_chunks", []))

    model = ModelFactory.get_chat_model(state["desired_model"])
    chain = PromptFactory.get_assistant_prompt() | model | StrOutputParser()

    answer = chain.invoke({"user_message": user_msg, "context": context})
    return {"answer": answer}


def respond_node(state: ChatState) -> dict:
    """Commit the answer into conversation history as an AIMessage.

    Deliberately separate from agent_node: this is the seam where
    post-processing (citation formatting, output filtering, response
    grading) slots in later without touching model invocation.
    """
    return {"messages": [AIMessage(content=state["answer"])]}
