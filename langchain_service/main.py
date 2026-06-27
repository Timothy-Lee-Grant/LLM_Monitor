from flask import Flask, jsonify
from flask import request
from lang import invoke_langchain

app = Flask(__name__)

@app.route("/")
def Llm_Request():
    results = invoke_langchain()
    return jsonify({"status":"success", "data":results})

#TODO: Find out how to take in a JSON object and serialize, then parse, then work with that http request body 
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        #Question: are we able to do: request.body and then try to do the deserialization?
        return do_the_login()
    else:
        return show_the_login_form()

#TODO: Figure out what will actually be ran when I start up my docker compose file
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)