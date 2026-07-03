



import requests



# All this function should do is ensure that the user's desired model is successfully pulled / downloaded inside the ollama container.
def TryGetOllamaModel(desired_model:str, base_url:str) -> bool:
    
    try:
        print(f"Checking if model {desired_model} is locally available in my ollama service docker container.")
        response = requests.get(f"{base_url}/api/tags", timeout=10)
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

            response = requests.post(f"{base_url}/api/pull", json=payload, timeout=None) # timeout none to avoid timing out for networking when we are pulling and download a large model.

            if response.json().get("status") != "success":
                print("Unable to download model")
                return False
        
        return True

    except requests.RequestException as e:
        print(f"Error communicating with the ollama service container during get_chat_model creation")
        return False