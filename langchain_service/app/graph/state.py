from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages


class ChatState(TypedDict):
    """Shared state flowing through the graph. Each node returns a PARTIAL
    update dict; LangGraph merges it into this state.

    About `add_messages` (answering the old "Investigate this" comment):
    it is a REDUCER. Without it, a node returning {"messages": [x]} would
    OVERWRITE the whole list. With it, LangGraph appends (and de-duplicates
    by message id) — so conversation history accumulates across nodes and,
    later, across turns when a checkpointer is added. Every other field uses
    the default reducer: last write wins.
    """

    user_id: str
    desired_model: str
    retrieved_chunks: list  # list[Document]; empty for non-RAG runs
    messages: Annotated[list, add_messages]
    answer: str
    # plan 002 Step 4: agent_node records model token usage here so the
    # pipeline layer can report it in ChatMetadata (zeros in mock mode).
    prompt_tokens: int
    completion_tokens: int
