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
from langgraph.prebuilt import ToolNode, tools_condition

from app.graph.state import ChatState
from app.graph.nodes import (
    retrieve_node,
    agent_node,
    respond_node,
    make_tool_agent_node,
    tool_respond_node,
    policy_check_node,
    blocked_node,
)


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


def build_tool_graph(tools, checkpointer=None, provider=None):
    """Tool-loop variant (plan 003 Step 3) — the "new flow entirely" rung of
    the growth path documented above, plus this graph's one NEW concept: a
    CONDITIONAL edge, decided per-run by the model's own output.

        START -> agent -> (emitted tool_calls?) -> tools -> agent -> ...
                       -> (no tool_calls)       -> respond -> END

    tools_condition (langgraph.prebuilt) inspects the last AIMessage:
    tool_calls present -> "tools"; absent -> END, which we remap to our
    respond node. The loop is bounded by recursion_limit at INVOKE time
    (pipelines.py) — the lean tier's runaway-cost guard lives in config,
    not topology, so the cap is tunable without recompiling the graph.

    Separate builder (not another build_graph flag): the agent node differs
    (tool-bound, message-accumulating, async) and the wiring differs; a
    with_tools flag would make build_graph two graphs wearing one function.

    provider (plan 003 Step 5b): per-pipeline model binding, threaded to the
    agent node at build time. None = LLM_PROVIDER env (Azure by default);
    graph-free compiles this same topology bound to "openai_compat" — same
    graph, different model economics, which is the routing-table point.
    """
    g = StateGraph(ChatState)

    g.add_node("agent", make_tool_agent_node(tools, provider=provider))
    g.add_node("tools", ToolNode(tools))
    g.add_node("respond", tool_respond_node)

    g.add_edge(START, "agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "respond"})
    g.add_edge("tools", "agent")
    g.add_edge("respond", END)

    return g.compile(checkpointer=checkpointer)


def _policy_gate(state: ChatState) -> str:
    """Routing function for the premium graph's FIRST conditional edge: the
    verdict written by policy_check_node decides whether the request ever
    reaches the expensive path. Unknown/missing verdict routes forward
    (fail-open, matching the node's parse posture)."""
    return "blocked" if state.get("policy_verdict") == "violated" else "retrieve"


def build_premium_graph(tools, checkpointer=None):
    """Premium/full tier (plan 003 Step 5) — the showcase flow:

        START -> policy -> (violated?) -> blocked -> END
                        -> (conformance) -> retrieve -> agent <-> tools
                                                     -> respond -> END

    Composition of everything the codebase has built so far: the revived
    plan-001 policy gate, graph-rag's retrieve node (k=4), and Step 3's tool
    loop (context-aware variant). The sampled LLM-judge is deliberately NOT
    a node: it must never add user-facing latency, so it runs post-response
    in the pipeline layer (see _spawn_sampled_judge in pipelines.py) —
    "in the graph" would mean "on the clock".

    Cost anatomy per request: 1 policy call (cheap, bounded output) +
    N agent-loop calls (recursion-capped) + 0 judge calls on the user's
    clock (sampled, async, off-path). The tier contract in the registry
    description states this out loud.
    """
    g = StateGraph(ChatState)

    g.add_node("policy", policy_check_node)
    g.add_node("blocked", blocked_node)
    g.add_node("retrieve", retrieve_node)
    g.add_node("agent", make_tool_agent_node(tools, include_context=True))
    g.add_node("tools", ToolNode(tools))
    g.add_node("respond", tool_respond_node)

    g.add_edge(START, "policy")
    g.add_conditional_edges("policy", _policy_gate, {"blocked": "blocked", "retrieve": "retrieve"})
    g.add_edge("retrieve", "agent")
    g.add_conditional_edges("agent", tools_condition, {"tools": "tools", END: "respond"})
    g.add_edge("tools", "agent")
    g.add_edge("respond", END)
    g.add_edge("blocked", END)

    return g.compile(checkpointer=checkpointer)
