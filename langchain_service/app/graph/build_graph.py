from langgraph.graph import StateGraph, START, END
from app.graph.state import ChatState
from app.graph.nodes import *
# NOTE: removed `from langgraph.prebuilt import ToolNode, tool_condition` —
# the real symbol is `tools_condition`, and tool usage is a non-goal for this cleanup anyway.


# TODO(Step 5 of plan 001): incomplete — becomes build_graph(with_rag: bool) with
# retrieve -> agent -> respond wiring. Not called anywhere yet.
def build_graph(checkpointer=None):
    g = StateGraph(ChatState)
    g.add_node("policy_check", policy_check_node)
    g.add_node("blocked", blocked_node)

# build_graph_old (practice version) moved to old_implementations/build_graph_old.py