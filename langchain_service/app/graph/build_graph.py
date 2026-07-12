"""Graph assembly (plan 001 Step 5).

One builder, parameterized — compiled twice at startup by pipelines.py:

    with_rag=False:  START -> agent -> respond -> END
    with_rag=True:   START -> retrieve -> agent -> respond -> END

Growth path (this is the scalability contract for the graph engine):
- New step in a flow  -> add a node + edge here (e.g. an image-parsing node
  before `agent`, a policy gate after START).
- New flow entirely   -> new builder variant + one registry entry in
  pipelines.py; it appears in /v1/models automatically.
- Memory (future)     -> pass a checkpointer here; the parameter is already
  threaded through. Per-user state is then keyed by thread_id at invoke time
  while the compiled graph object itself stays shared and stateless.
"""

from langgraph.graph import StateGraph, START, END

from app.graph.state import ChatState
from app.graph.nodes import retrieve_node, agent_node, respond_node


def build_graph(with_rag: bool, checkpointer=None):
    g = StateGraph(ChatState)

    g.add_node("agent", agent_node)
    g.add_node("respond", respond_node)

    if with_rag:
        # Conditional WIRING (decided once, at build time) instead of a no-op
        # node checking a flag on every request: the compiled graph only
        # contains the steps it actually runs.
        g.add_node("retrieve", retrieve_node)
        g.add_edge(START, "retrieve")
        g.add_edge("retrieve", "agent")
    else:
        g.add_edge(START, "agent")

    g.add_edge("agent", "respond")
    g.add_edge("respond", END)

    return g.compile(checkpointer=checkpointer)
