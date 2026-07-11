# Retired from app/api/FlaskServer.py during plan 001 Step 6 (2026_07_11). Replaced by the registry-driven API layer. Kept for reference only.

from flask import Flask, jsonify
from flask import request
import time, uuid

import app.orchestration.pipelines  # noqa: F401 — importing this module registers all pipelines
from app.orchestration.registry import get_pipeline
from app.orchestration.contracts import ChatRequest


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
    # NOTE (Step 4): these two routes now dispatch through the pipeline registry and
    # return the CONTRACTS.md §2 response shape (previously {"status", "message_response"}).
    # Route paths themselves are renamed to the canonical CONTRACTS.md layout in Step 6.
    def _parse_chat_request(data: dict) -> ChatRequest:
        return ChatRequest(
            user_message=data.get("user_message", "hello!"),
            user_id=str(data.get("user_id", "anonymous")),
            requested_model=data.get("requested_model") or data.get("user_requested_model"),
        )

    @app.route("/test/langchain/chatnosecurity", methods=['POST'])
    def test_langchain_chatnosecurity_endpoint():
        chat_request = _parse_chat_request(request.get_json())
        chat_response = get_pipeline("chat-basic").handler(chat_request)
        return jsonify(chat_response.to_dict())

    @app.route("/test/langchain/chatnosecurityrag", methods=['POST'])
    def test_langchain_chatnosecurity_rag_endpoint():
        chat_request = _parse_chat_request(request.get_json())
        chat_response = get_pipeline("chat-rag").handler(chat_request)
        return jsonify(chat_response.to_dict())
    
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