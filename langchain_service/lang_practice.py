import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_code.output_parsers import StrOutputParser
#from langchain_anthropic import ChatAnthropic
#from langchain_google_genai import ChatGoogleGenAI

def OllamaInvokation():
    from langchain_ollama import ChatOllama
    #this requires no api keys. 
    #defaults to hit: http://localhost:11434
    model = ChatOllama(model="llama3.2", temperature=0.7)



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