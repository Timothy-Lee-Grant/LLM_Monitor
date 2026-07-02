





from langgraph.graph import StateGraph, END
from lang_tools import policy_check_fn, retrieve_fn, agent_fn

g = StateGraph(MyState) # I have no idea where mystate variable comes from. I guess I would need to create this variable based on the state which was described in the documentio. 

g.add_node("policy_check", policy_check_fn) # but actually this policy check returns a boolean, but I think our conditional edge is checking if the response is a string of the word "violated"
g.add_node("retrieve", retrieve_fn)
g.add_node("agent", agent_fn)

g.add_conditional_edges("policy_check", lambda s: "END" if s["violated"] else "retrieve",
                        {"END":END, "retrieve":"retrieve"})

app = g.compile()
result = app.invoke({"user_msg": msg, "userId": uid})

# Here is the LangGraph suggested to me, but I have don't know how to invoke it, when to use it, how to hook everything up for the entire pipeline between a user sending a request and me doing anything successful with this langgraph framework.