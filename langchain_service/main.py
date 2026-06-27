from flask import Flask, jsonify
from lang import invoke_langchain

app = Flask(__name__)

@app.route("/")
def Llm_Request():
    results = invoke_langchain()
    return jsonify({"status":"success", "data":results})

#TODO: Figure out what will actually be ran when I start up my docker compose file
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)