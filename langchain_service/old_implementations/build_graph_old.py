# Retired from app/graph/build_graph.py during plan 001 cleanup (2026_07_10).
# Timothy's practice graph. NOTE: references agent_node / respond_node which were
# never written in nodes.py — this would NameError if called. Kept for reference only.

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
