






def FindWeather(city:str):
    # In the future I can attempt to hit a real API, but for now I will return mock data.
    return "12*C, cloudy"

def TellTime():
    return "14:22"

# eventually this I think should also need to implement a RAG that allows the function itself to check the user's message and see if it violates.
def policy_check_fn(userInputMessage:str):
    return True


# I know that I need these two functions for my LangGraph, but don't know what they should do.
def retrieve_fn():
    pass
def agent_fn():
    pass