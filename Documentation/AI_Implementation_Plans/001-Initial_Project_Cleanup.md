10 July, 2026

## Stage 1 (Design Documentation)

1. Context:

**Current State**:

This is the first collaborative AI feature implementation. Previously everything had been done 100% by hand. I wrote all the code, and completely developed this project myself. But now we are changing the implemention strategy which we will be using to develop this project. Now we will be taking on a collaborative development with AI as outlined in the CLAUDE.md file for AI_Implementation_Plans. 

This project currently has many different docker components. All of them are started up within the docker compose file. A build script is able to perform the docker compose calls to build and inject environment variables into the system. The two main dynamic environment variables are 'live' and 'mock'. 'live' is for when we want to start our system up with the real LLM and Ollama service. 'mock' is when we want to start up our project, but don't want to have the heavy system of Ollama and interacting with those LLMs.

The system currently operates as follows. The langchain_service gets an HTTP request from outside the docker network. It will recieve a POST request and that POST request will have the user's message. This user's message is then sent to our internal langchain_logic. The internal logic will process the users message by getting a standardized prompt, getting a standardized model, and invoking the chain with the user's message. I then tried to implement a RAG that would allow for functionality of comparing the user's message to documents in the vector database to give extra context.

I then attempted to get langgraph operating (but this is very much not working right now).

**Current Problems**:

- The system was under active development. It was working in parts, but every day there were many new changes, logic taken out, endpoints removed, classes modified, etc. So the current state of the system is very much unstable.

- I don't think that my RAG system actually works.

- I am unsure of the architecture which this project is using. I attempted to use my best judgement to create a scalable, distributed, asyncronous system; but I am lacking in experience in this realm, so I don't know if I did it in a good way or not.

- There is no standard interface and agreements between the different docker services for how these HTTP requests will be sent.

- The system is not connected correctly. The langchain_service should not be recieving any communications from outside the docker network. (I want to have API endpoint enabled in my langchain_service which are able to be reached by outside for testing reasons, but in the actual system all requests should be going through my YARP dotnet server.)

**Direction For This Implementation**

- Refactor code within each of the docker services to be professional, scalable, and clean.
- Ensure RAG actually saves documents corrently into our vector database
- Ensure RAG successfully retrieves those documents based on user message
- Create a standardized interface and contract between all of the services in the project.
- Have multiple API endpoints inside the langchain_service such that a user can send messages to be processed in the following ways in both base langchain (no langgraph) and in langgraph (but remember that we want scalablility so the implementation you use to implement these two endpoints with langgraph should allow for easy growth of new features within the langgraph system):

A simple POST request that gets sent to the llm with that message and given response.

A POST request that has extra context injected into it from the RAG.

So in total, there will be 4 working valid (testing) API endpoints which I can hit from outside docker network, and 4 other (real) API endpoints that I can hit by routing through my dotnet YARP sever.

- Ensure Openwebui is working and compatable with our system and can call as required.

2. Interfaces & contracts

I don't know

3. Acceptance criteria

I'll think more on this.

4. Non-goals

- We do not need to attempt to implement features and functionality which does not currently exist in the project. For example, tool usage.
- Don't need to implement policy checking and blocking


## Stage 2 (Discussion)

About to start.

## Stage 3 (Implementation Planning)

Not Gotten To Yet

### Stage 3 Discussion Subsection

Not Gotten To Yet

## Stage 4 (Implementation)

Not Gotten To Yet

## Stage 5 (Final Results, Testing, Verficiation)

Not Gotten To Yet