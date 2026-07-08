import os
import requests

# Actually, would this be a good place for me to have my global dictionaries for this namespace

knownPulledOllamaChatModels = set()
knownPulledOllamaEmbeddingModels = set()

# All this function should do is ensure that the user's desired model is successfully pulled / downloaded inside the ollama container.
def TryGetOllamaChatModel(desired_model:str, base_ollama_url:str) -> bool:
    if os.getenv("LLM_MODE") == "mock":
        return True
    
    try:
        print(f"Checking if model {desired_model} is locally available in my ollama service docker container.")
        response = requests.get(f"{base_ollama_url}/api/tags", timeout=10)
        response.raise_for_status()

        #parse the local model list which ollama service gave back to me
        local_models = response.json().get("models", [])

        # look through downloaded tags (ollama uses exact name matching or maps to :latest)
        downloaded_names = [m["name"] for m in local_models]
        
        # standardize tag check: if no tag given, chekc both raw name and ':latest'
        has_model = (desired_model in downloaded_names) or (f"{desired_model}:latest" in downloaded_names)

        if not has_model:
            # Now we need to send a POST request to our ollama docker container telling it to pull the requested user's model
            # TODO: In the future I will need to secure this so that only 'accepted' models are allowed to be passed in by the user
            print("Model was NOT found in ollama")
            print("Pulling Model Now")
            payload = {
                "model":desired_model,
                "stream": False     #setting stream to false will cause this to wait until ollama has finished fully pulling the model
            }

            response = requests.post(f"{base_ollama_url}/api/pull", json=payload, timeout=None) # timeout none to avoid timing out for networking when we are pulling and download a large model.

            if response.json().get("status") != "success":
                print("Unable to download model")
                return False
        knownPulledOllamaChatModels.add(desired_model)
        return True

    except requests.RequestException as e:
        print(f"Error communicating with the ollama service container during get_chat_model creation")
        return False
    
def TryGetOllamaEmbeddingModel(desired_model:str, base_ollama_url:str) -> bool:

    if os.getenv("LLM_MODE") == "mock":
        return True
    
    #desired_model = "nomic-embed-text"
    if desired_model in knownPulledOllamaEmbeddingModels:
        return True
    
    try:
        response = requests.get(f"{base_ollama_url}/api/tags", timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error communicating with the ollama service container during checking of if embedding model is within ollama's container")
        return False
    
    # parse the response to see if we already have the embedding model
    local_models = response.json().get("models", [])
    downloaded_models = [m["name"] for m in local_models]
    already_downloaded = desired_model in downloaded_models or f"{desired_model}:latest" in downloaded_models
    if not already_downloaded:
        #send pull api request to ollama service
        payload = {
            "model": desired_model,
            "stream": False
        }
        response = requests.post(f"{base_ollama_url}/api/pull", json=payload, timeout=None)
        if response.json().get("status", "bad") != "success":
            return False
        knownPulledOllamaEmbeddingModels.add(desired_model)
        return True
    return True