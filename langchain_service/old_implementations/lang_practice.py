import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
#from langchain_anthropic import ChatAnthropic
#from langchain_google_genai import ChatGoogleGenAI
from langchain_ollama import OllamaEmbeddings
from langchain_postgres import PGVector
from lang_tools import FindWeather, TellTime
from models/ChatModelFactory import ChatModelFactory

global lModel
global store

@tool
tool_list = [FindWeather, TellTime]

def TestInit():
    # Now I realize I need to worry about making these global
    # or I could just put this entire thing in a class...
    # but then if I do it in a class, do I need to worry about the same kind of thing that I need to do in C# where I need to register the services with DI, and this way I can have the scoped object?
    lModel = ChatModelFactory(model="llama3.2", temperature=0.7)
    embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_BASE_URL)
    store = PGVector(embeddings=embeddings, connection=PG_CONN, collection_name="policies")
    store.add_documents(splitter.split_documents(loader.load()))

def OllamaInvokation():
    from langchain_ollama import ChatOllama
    #this requires no api keys. 
    #defaults to hit: http://localhost:11434
    model = ChatModelFactory(model="llama3.2", temperature=0.7)

def TestingMethod(userId, userMessage):
    from langchain_ollama import ChatOllama
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = ChatModelFactory(
        model = "qwen2.5:1.5b",
        base_url=base_url,
        temperature=0
    )

    # Now I need to get the components and put them together.
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", "You are a helpful agent who loves poems"),
        ("user", "What is your favorite time of year?")
    ])
    chain = prompt_template | model | StrOutputParser()

    response = chain.invoke({})
    print(response)
    return response


def TestRagSystem(userId:str, userMessage:str):
    #embeddings = OllamaEmbeddings(model="nomic-embed-text", base_url=OLLAMA_BASE_URL)

    #injecting data into our vector data base to be able to retrieve it by chunks later
    # Note: I have absolutely no idea what is going on here. I don't know what this loader is, I don't see how I am creating a vector database schema. I don't see how I am putting any data into my database
    # I think this is revealing a core weakness that I have regarding dealing with, starting up, connecting to, building, databases in general.
    # store = PGVector(embeddings=embeddings, connection=PG_CONN, collection_name="policies")
    # store.add_documents(splitter.split_documents(loader.load()))
    # Because I created an Init() I think these two should go up there. Instead of being here.

    # Use the user's message to do a semantic search to find the top k elements which alligh
    # to the user's message most similiar chunks which are found in my database.
    retriever = store.as_retriever(search_kwargs{"k":4})
    chunks = retriever.invoke(userMessage)
    

    #what I think I would actually need to do is have an init function which initializes my models one time, and then from there I will be able to use those models in any of my functions.
    # but I don't really know how this will operate regarding memory management. Especially if I am having multiple request, and there are multiple people who are sending multiple requests.
    # I would think that as the model is just weights loaded into RAM, I would be able to reuse this section in memory, and therefor as long as my hardware has enough space while operating, 
    # then then model will be in there? What happens if we run out of memebory, and then attempt to reuse that model as a varialbe? Does it just get reloaded into memory?

    # Now I shoudl be able to invoke on my model.
    createdPrompt = ChatPromptTemplate(
        ("system", "You are happy and cheerful encouraging assistent."),
        ("system", "here is some extra information found in our documentation {chunks}")
        ("user", userMessage)
    )
    chain = createdPrompt | lModel | StrOutputParser()

    response = chain.invoke({"message":userMessage})

    return response

def TestToolUseSystem(user_id:str, user_message:str):
    # now I want to be able to register tools and ask the llm to see if it needs them.

    createdPrompt = ChatPromptTemplate(
        ("system", "You are a agent that has access to tool."),
        ("system", "Here are the available tools which you are allowed access to: {tool_list}"),
        ("system", "If you would like to call a tool give the format of '\{tool_name\}'")
        ("user", user_message)
    )
    chain = createdPrompt | lModel | StrOutputParser()
    res = chain.invoke({})
    #while res != # How would I even check to see if it is a JSON or not ....
    max_itters = 5
    curr_itters = 0
    while res[0] != '{' and curr_itters < max_itters:
        # Now I need to parse the string given to me so that I can get the tool name, then I need to invoke it.
        tool_name = _ # This also indicates that I have a problem with if I am asked this type of string manipulation question for a leetcoding interview. I need to be good at these kinds of topics.....
        # Now I guess I need try to invoke this tool based on the string name which I am given.......
        # So now I need to know hwo to map a string value to the variable that I called it, so that I can invoke the function that it points to.... I really think this is incorrect.
        tool_result = tool_list[foundIndex]
        createdPrompt.append(("tool", tool_result))
        chain = createdPrompt | lModel | StrOutputParser()
        res = chain.invoke({})
        curr_itters += 1
    
    return res



'''
Types of LangChain Components to investigate:

Prompt Template
Chat Model
Output Parser
Document Loader
Text Splitter
Vector Store
Retriever
Tools
'''

def OpenAiInvokation():
    from langchain_openai import ChatOpenAI
    os.environ["OPENAI_API_KEY"] = 7

    #define a template with a placeholder variable
    prompt_template = ChatPromptTemplate.from_message([
        ("system", "You are a helpful culinary assistant."),
        ("user", "What is a unique twist I can add to a standard {dish} recipe?")
    ])

    #initialize the model
    model = ChatOpenAI(model="gpt-40-mini", temperature=0.7)

    #create the chain using LCEL (which is this pipe operator that is similiar to how Linux does passing of inputs to outputs)
    chain = prompt_template | model | StrOutputParser()

    # Rus the chain by passing the variable
    response = chain.invoke({"dish":"Lasagna"})
    print(response)

def AzureInvoke():
    from langchain_openai import AzureChatOpenAI
    model = AzureChatOpenAI(
        azure_deployment="My_development_name",
        api_version="My aip version",
        azure_endpoint="my azure endpoint",
        api_key="my api key"
    )