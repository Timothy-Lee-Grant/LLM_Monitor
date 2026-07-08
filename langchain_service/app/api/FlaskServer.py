from flask import Flask, jsonify
from flask import request
from app.orchestration.OrchestrationLogic import *


def IntializeFlaskEndpoints():
    app = Flask(__name__)

    @app.route("/")
    def Llm_Request():
        return jsonify({"status":"success", "data":"Hello!! You successfully reached my flask main API"})

    """
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

    @app.route('/test/rag', methods=['POST'])
    def testRag_endpoint():
        data = request.get_json() or {}
        user_id = data.get("userId", "default_user")
        userMessage = data.get("chatMessage")
        try:
            response = TestRagSystem(user_id, userMessage)
            return jsonify({
                "status": "success",
                "userId":user_id,
                "input_received": userMessage,
                "agent_response": response
            })
        except Exception as e:
            return jsonify({"status":"error", "message":str(e)}), 500

    @app.route('/test/tool_use', methods=['POST'])
    def testToolUse_endpoint():
        data = request.get_json() or {}
        user_id = data.get("userId", "default_user")
        userMessage = data.get("chatMessage")
        try:
            response = TestToolUseSystem(user_id, userMessage)
            return jsonify({
                "status": "success",
                "userId":user_id,
                "input_received": userMessage,
                "agent_response": response
            })
        except Exception as e:
            return jsonify({"status":"error", "message":str(e)}), 500


    @app.route('/test_old', methods=['POST'])
    def test_endpoint_old():
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

    @app.route("/test/langchain/chat", methods=['POST'])
    def test_langchain_chat_endpoint():
        return jsonify({"status": "success"})

    @app.route("/test/langgraph/chat", methods=['POST'])
    def test_langgraph_chat_endpoint():
        return jsonify({"status": "success"})

    @app.route("/test/langgraph/chatnosecurity", methods=['POST'])
    def test_langgraph_chatnosecurity_endpoint():
        return jsonify({"status": "success"})
    """

    '''
    {
        "user_requested_model": str,
        "user_id": int,
        "user_message": str 
    }
    '''    
    @app.route("/test/langchain/chatnosecurity", methods=['POST'])
    def test_langchain_chatnosecurity_endpoint():
        #parse the user's message
        data = request.get_json()
        user_requested_model = data.get("user_requested_model", "mock")
        user_id = data.get("user_id", 1)
        user_message = data.get("user_message", "hello!")

        #pass user message into worker
        llm_response = test_langchain_chatnosecurity_worker(user_id=user_id, user_requested_model=user_requested_model, user_message=user_message)

        #return response
        return jsonify({"status":"success", "message_response": llm_response})
    
    @app.route("/test/langchain/chatnosecurityrag", methods=['POST'])
    def test_langchain_chatnosecurity_rag_endpoint():
        #parse the user's message
        data = request.get_json()
        user_requested_model = data.get("user_requested_model", "mock")
        user_id = data.get("user_id", 1)
        user_message = data.get("user_message", "hello!")

        #pass user message into worker
        llm_response = test_langchain_chatnosecurityrag_worker(user_id=user_id, user_requested_model=user_requested_model, user_message=user_message)

        #return response
        return jsonify({"status":"success", "message_response": llm_response})
    
    return app 