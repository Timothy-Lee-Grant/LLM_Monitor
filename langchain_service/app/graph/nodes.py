from app.rag.Ingestion import FindSemanticlyClosestElement

def retrieve_node(state: ChatState) -> dict:
    #Read what I need from the shared state
    user_query = state["user_msg"]

    #Execute the atomic operation
    topK_chunks = FindSemanticlyClosestElement(user_query, "supplemental_knowledge.md", 5)

    #return a dict of ONLY the keys that I want t oupdate in the shared state
    return {"chunks": topK_chunks}