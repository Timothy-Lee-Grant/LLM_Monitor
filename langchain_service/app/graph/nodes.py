"""Graph nodes. Each node: ChatState -> partial state update dict.

Nodes share the same building blocks as the chain pipelines
(ModelFactory / PromptFactory / vector_store) — one set of components,
two execution engines.

Retired policy_check_node / blocked_node live in
old_implementations/graph_policy_nodes_v1.py (policy checking is a
non-goal for plan 001; the prompt remains in PromptFactory).
"""

from langchain_core.messages import AIMessage

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
    # Imported here (not at module top) to avoid a circular import:
    # pipelines -> build_graph -> nodes -> pipelines.
    from app.orchestration.pipelines import extract_usage

    user_msg = state["messages"][-1].content
    context = "\n\n".join(doc.page_content for doc in state.get("retrieved_chunks", []))

    model = ModelFactory.get_chat_model(state["desired_model"])
    # Raw AIMessage (no StrOutputParser) so usage_metadata survives — same
    # reasoning as the chain pipelines in plan 002 Step 4.
    message = (PromptFactory.get_assistant_prompt() | model).invoke(
        {"user_message": user_msg, "context": context}
    )
    prompt_tokens, completion_tokens = extract_usage(message)

    return {
        "answer": message.content,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
    }


def respond_node(state: ChatState) -> dict:
    """Commit the answer into conversation history as an AIMessage.

    Deliberately separate from agent_node: this is the seam where
    post-processing (citation formatting, output filtering, response
    grading) slots in later without touching model invocation.
    """
    return {"messages": [AIMessage(content=state["answer"])]}


# ---- tool-loop nodes (plan 003 Step 3) ------------------------------------

def make_tool_agent_node(tools):
    """Factory: a tool-aware agent node closed over the discovered toolset.

    A factory (vs a module-level function like agent_node) because the node
    must bind the SAME tools the graph's ToolNode executes — both are fixed
    at graph-build time, mirroring how build_graph wires retrieval at build
    time instead of checking flags per request.

    ASYNC on purpose: the MCP adapter tools are async-only (Step 2 finding),
    so the whole tool graph runs under ainvoke; a sync node here would work
    but would force LangGraph to thread-hop for no benefit.
    """

    async def tool_agent_node(state: ChatState) -> dict:
        # Late import to avoid the circular pipelines -> build_graph -> nodes
        # -> pipelines chain (same reasoning as agent_node above).
        from app.orchestration.pipelines import extract_usage

        model = ModelFactory.get_chat_model(state["desired_model"]).bind_tools(tools)

        # Raw message-list invocation (not the assistant template): the loop's
        # history (human -> ai(tool_calls) -> tool -> ...) must reach the model
        # intact, and templates can't represent a growing message list.
        message = await model.ainvoke(
            [PromptFactory.get_tool_agent_system()] + list(state["messages"])
        )
        prompt_tokens, completion_tokens = extract_usage(message)

        # ACCUMULATE tokens across loop iterations (default reducer is
        # last-write-wins, so we add explicitly): every trip around the loop
        # is a model call, and the lean tier's cost claim depends on the
        # metadata reporting ALL of them, not just the final call.
        return {
            "messages": [message],
            "prompt_tokens": state.get("prompt_tokens", 0) + prompt_tokens,
            "completion_tokens": state.get("completion_tokens", 0) + completion_tokens,
        }

    return tool_agent_node


def tool_respond_node(state: ChatState) -> dict:
    """Tool-loop twin of respond_node. The final AIMessage is ALREADY in
    messages (the agent node appends every model reply, unlike agent_node
    which stashes content in `answer`), so this only extracts — appending
    again would duplicate it."""
    return {"answer": state["messages"][-1].content}
