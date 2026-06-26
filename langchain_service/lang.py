





from langchain_core.language_models import FakeListChatModel



def invoke_langchain():
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

