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



# These two are practice.
def build_graph_old(chekcpointer=None):
    g = StateGraph(ChatState)
    g.add_node("policy_check", policy_check_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("agent", agent_node)
    g.add_node("respond", respond_node)

    g.add_edge(START, "policy_check")
    g.add_conditional_edges("policy_check", 
                            lambda s: "blocked" if s["violated"] else "ok",
                            {"blocked": END, "ok": "retrieve"})
    g.add_edge("retrieve", "agent")
    g.add_edge("agent", "respond")
    g.add_edge("respond", END)

    return g.compile(checkpointer=chekcpointer)