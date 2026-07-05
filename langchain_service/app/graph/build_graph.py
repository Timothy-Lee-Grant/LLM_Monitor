

# TODO: These two are practice.

from langgraph.graph import StateGraph, START, END

def build_graph(chekcpointer=None):
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