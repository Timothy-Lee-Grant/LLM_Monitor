


import os
import requests

# Actually, would this be a good place for me to have my global dictionaries for this namespace

knownPulledOllamaChatModels = {}
knownPulledOllamaEmbeddingModels = {}

# All this function should do is ensure that the user's desired model is successfully pulled / downloaded inside the ollama container.
def TryGetOllamaChatModel(desired_model:str, base_url:str) -> bool:
    
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
    
def TryGetOllamaEmbeddingModel(desired_model:str, base_url:str) -> bool:

    if os.getenv("LLM_MODE") == "mock":
        return True
    
    # desired model might or might not be passed in. I don't know about what I want as of right now.
    # I think to get this project working I will decide to just hardcode it for now
    desired_model = "nomic-embed-text"
    if desired_model in knownPulledOllamaEmbeddingModels:
        return True
    
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=10)
        response.raise_for_status()
    except requests.RequestException as e:
        print(f"Error communicating with the ollama service container during checking of if embedding model is within ollama's container")
        return False
    
    # We need to parse the response to see if we already have the embedding model

    '''
    I know that I am still really weak on understanding and working with responses from http requests and reponses
    Python and C# have different servers (C# is kestral, and python is this Flask). Both seem to abstract out different things
    and have different methods available to them.

    Looking at the way we do this. I am getting a response back from flask. It seems to be a string (which would make sense)
    I am then applying the method (from somewhere) of json() to it. I am guessing that this method will turn the string into a dictionary object.
    In C# I know that the way I do this is that I will have an object that I create myself, I will then have my controller pass in the response as an object
    of that type. So this means that kestral is doing the casting itself, and that it is casted to a specific object which I have defined.
    In this case it is not explicity casted until I do the .json() method. Then it is casted into a {} (so not a custom defined class which I myself create).
    Then I do a .get method on that dictionary and look for the key of "models" (I just realized that is is also helpful for leetcode because I didn't know in the past I could use this .get(key, default) to a default)

    the other thing I am realizing is that this response should have other components (such as headder, cookies, etc), but it seems it is only the body?
    '''
    downloaded_models = response.json().get("models", [])

    # Check if our desired model is in ollama

    if desired_model not in downloaded_models:
        # now we need to tell ollama to download it

        payload = {
            "model":desired_model,
            "stream":False
        }

        # do a post request
        # what is this request? It is a library, but it feels strange. What is the C# equivalent???
        response = requests.post(f"{base_url}/api/pull", json=payload, timeout=None)

        response.raise_for_status()

























        # If we got the success, then ollama pulled the model

        # this give me an opportunity to practice working with this response object
        # first step, it is a string. I want a dict
        # second step, it is now a dict, I want a list? Or am I trying to find if it was a success or not
        # that would mean I want to find 'status'. but how would I do that? Where would I look in this response dict?
        # so how do I search a dict? I look up the value by the key.... So lets do it!
        # Below is my attempt (I think it is actually correct as well but a different way of getting the key). I will use the other way I saw online incase it is safer. but conceptually I might have gotten it?
        # if response.json()["status"] == "success":
        #     return True
        # return False
    
        if response.json().get("status") == "success":
            return True
        return False




