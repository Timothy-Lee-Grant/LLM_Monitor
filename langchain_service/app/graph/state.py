from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class ChatState(TypedDict):
    user_id: str
    user_msg: str
    desired_model: str
    policy_verdict: str
    policy_reason: str
    retrieved_chunks: list # list[Document]
    messages: Annotated[list, add_messages] # Investigate this
    answer: str