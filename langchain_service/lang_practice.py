import os
from langchain_core.prompts import ChatPromptTemplate
from langchain_code.output_parsers import StrOutputParser
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