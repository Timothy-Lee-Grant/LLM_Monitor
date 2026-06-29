from flask import Flask, jsonify
from flask import request
from lang import invoke_langchain
import lang_practice
#from swagger_ui import api_doc #TODO: implement this later

app = Flask(__name__)

@app.route("/")
def Llm_Request():
    return jsonify({"status":"success", "data":"Hello!! You successfully reached my flask main API"})

#TODO: Define the body which the POST request is expecting
#Conceptual question: What is a good way to showcase the expected schema of the request? Right now I have either and example (like "eia84hbfsl") or I can do the data type I am expecting. What is the industry standard?
'''
{
    "userId":"eia84hbfsl",
    "chatMessage":str
}
'''
@app.route('/api/chat', methods=['POST'])
def chat():
    data = request.get_json()
    try:
        userId = data.get("userId")
        chatMessage = data.get("chatMessage")
    except:
        return jsonify({"status":"failure"})

    langchain_result = invoke_langchain(userId, chatMessage)

    return jsonify( {"status":"success", "llmMessageResponse":langchain_result} )


@app.route('/test', methods=['POST'])
def test_endpoint():
    data = request.get_json() or {}
    user_id = data.get("userId", "default_user")
    message = data.get("chatMessage")

    try:
        result = TestingMethod(user_id, message)

        return jsonify({
            "status": "success",
            "userId":user_id,
            "input_received": message,
            "agent_response": result
        })
    except Exception as e:
        return jsonify({"status":"error", "message":str(e)}), 500

#TODO: Figure out what will actually be ran when I start up my docker compose file
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)