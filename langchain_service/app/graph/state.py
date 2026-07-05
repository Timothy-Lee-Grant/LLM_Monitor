
# TODO: These here are practice

from typing import TypedDict, Annotated
from langgraph.graph.message import add_messages

class ChatState(TypedDict):
    user_id: str
    user_msg: str
    disired_model: str
    violated: bool
    chunks: str
    messages: Annotated[list, add_messages]
    answer: str
    telemetry: dict