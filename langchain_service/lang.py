





from langchain_core.language_models import FakeListChatModel


#NOTE: As of right now, this server is STATEFUL!
# It assumes that there is only one user (does not check based on userId)
# It also does not load previous chat messages which the user gave from a data base (we have not yet implemented the data base in this project)
# So we will for now, keep the system such that we assume only one user, and keep their message hisory in RAM
def invoke_langchain(userId, chatMessage):
    model = FakeListChatModel(responses = ["Hello from mock agent"])
    response = model.invoke("what is the wheather like over there?")
    return model.response

def test_langchain_implementation(userId, chatMessage):
    # First I need to ensure that the user's message is in conformance with the company's policies.
    # This means that I will need to have a RAG where I store my company policies in a vector database (pgvector)
    # I will then do a semantic search of the vector database and send the user's chatMessage to an llm to classify if it breaks policy
    policySystemPrompt = ["You are a classifier who is determing if a user's message is breaking company policy"]
    augentedDataFromRag = SearchVectorDatabaseBySemanticSearch(chatMessage)
    policyResult = invoke(policySystemPrompt, augentedDataFromRag)
    if policyResult == "Policy Violated":
        return None
    
    #check if there is a prompt injection
    # Follow the exact same steps as above but for prompt injection
    .....

    #Check for need of augmented data
    # Search vector database and get that info
    # Provide it to LLM

    # Check if we need to invoke tool
    # Send prompt to LLM tool selector
    # Give llm avaialble tools and if llm decided it needs the tool, keep invoking until the llm determines it is finished

    # Provide llm friendly response
    # Give system prompt to be friendly
    # Give user's message along with RAG info and tool info
    # Also need to give the user's previous messages (this will need to be searched for in the database of userID)
    return LlmRespose














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

