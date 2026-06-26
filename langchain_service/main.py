from flask import Flask
from lang import invoke_langchain

app = Flask(__name__)

@app.Route("/")
def Llm_Request():
    invoke_langchain()

def main():
    pass

if __name__ == "main":
    main()