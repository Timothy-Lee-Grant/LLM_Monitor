from flask import Flask, jsonify
from flask import request
import time, uuid
from app.orchestration.OrchestrationLogic import *


def IntializeFlaskEndpoints():
    app = Flask(__name__)

    @app.route("/")
    def Llm_Request():
        return jsonify({"status":"success", "data":"Hello!! You successfully reached my flask main API"})

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
    
    # Eventually openwebui will only talk to our dotnet server. But for now will do testing like this
    @app.route("/v1/models", methods=["GET"])
    def list_models():
        return jsonify({
            "object": "list",
            "data": [
                {"id": "llm-monitor-agent", "object": "model", "owned_by": "timothy"},
                {"id": "llm-monitor-agent-mock", "object": "model", "owned_by": "timothy"}
            ]
        })
    
    # (Draft dispatch-dict sketch for this route moved to old_implementations/notes_v1_dispatch_draft.py —
    #  the idea itself is now the registry pattern in CONTRACTS.md §4, implemented in plan 001 Step 4/6.)
    @app.route("/v1/chat/completions", methods=["POST"])
    def chat_completions():
        data = request.get_json()
        user_message = data["messages"][-1]["content"]

        return jsonify({
            "id": f"chatcmpl-{uuid.uuid4()}",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": data.get("model", "llm-monitor-agent"),
            "choices": [{
                "index": 0,
                "message": {"role": "assistant", "content": "Here is your FAKE answer reponse my myself!!!"},
                "finish_reason": "stop"
            }],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        })

    return app 