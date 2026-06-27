





from langchain_core.language_models import FakeListChatModel


#NOTE: As of right now, this server is STATEFUL!
# It assumes that there is only one user (does not check based on userId)
# It also does not load previous chat messages which the user gave from a data base (we have not yet implemented the data base in this project)
# So we will for now, keep the system such that we assume only one user, and keep their message hisory in RAM
def invoke_langchain(userId, chatMessage):
    model = FakeListChatModel(responses = ["Hello from mock agent"])
    response = model.invoke("what is the wheather like over there?")
    return model.response














# from langchain.agents import create_agent

# def get_weather(city: str) -> str:
#     """Get weather for a given city."""
#     return f"It's always sunny in {city}!"

# agent = create_agent(
#     model="ollama:devstral-2",
#     tools=[get_weather],
#     system_prompt="You are a helpful assistant",
# )

# result = agent.invoke(
#     {"messages": [{"role": "user", "content": "What's the weather in San Francisco?"}]}
# )
# print(result["messages"][-1].content_blocks)

