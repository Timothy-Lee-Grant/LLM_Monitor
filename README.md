# Purpose

The purpose of this project is to build a system which utilizes langchain to learn about and get the opportunity to demonstrate capabilities within this space that I am EXTREMELY interested in. I want all the actual code in this project to be my own, but I use Claude as a mentor who ONLY creates documentation (found in the Documentation folder), this is where I get evaluations on concepts that it feels I am weak or missing, code reviews, suggestions for targeting my specific goal of getting into **Microsoft** as a software engineer, and full lecture notes on those concepts which Claude has found that I am weak on.

This project was developed in two stages.
## First Stage: Hand Written Scaffolding
This stage was my opportunity to get my hands dirty and develop out the system that I wanted. I developed by hand all of the components which I wanted in my project, got the system working to a reasonable level, created a good base scaffolding for the AI to understand exactly what this project is, and where it is going.

## Second Stage: AI Assisted Development
The second stage is taking the base scaffolding which was developed by hand and rolling it out into a full application. This stage is driven by the implementation plan process in Documentation/AI_Implementation_Plans, where I write the design goals, the AI and I discuss and agree on a plan, and then I give step by step permission for each piece to be implemented so I can verify and understand everything that goes in.

## Hand Written Components
### Docker System
A build.sh script invokes the Docker Compose file which builds up all required containers (dotnet server, langchain_service, postgres vector database, Ollama service, openwebui). The build script injects environment variables into the containers, which supports both live and mock modes (mock exists because my computer is not very powerful, so it can't run heavy llms).

### Dotnet Server
A .NET server written in C# that uses YARP to direct traffic from the outside world to the docker network inner services. It also has a telemetry middleware which every request passes through before being forwarded.

### Langchain / LangGraph
Langchain service has multiple roles. This service will take in requests coming from the dotnet YARP server. Requests will consist of the message which the user wishes to send to the llm. Langchain_service will take this request in, pick the appropriate pipeline to invoke for the user's request, and handle the logic of parsing, prompt creation, obtaining the correct llm model, RAG injection, and response.

There are currently four pipelines in the registry: chat-basic, chat-rag, graph-basic, and graph-rag. The chat pipelines are plain LangChain chains and the graph pipelines run through LangGraph. The service also exposes an OpenAI-compatible surface (/v1/models and /v1/chat/completions) so OpenWebUI can talk to it like any OpenAI provider, with the model id selecting which pipeline runs.

# Service Contracts

Every HTTP boundary in the system is defined in CONTRACTS.md. That file is the single source of truth for the request and response shapes, error codes, the pipeline registry, and the network topology. Any change to a wire shape has to be made there first, and has to be additive.

# Concepts Implemented

## General Software Engineering

Docker, microservice architecture, middleware, client / server, http, REST, API, endpoints, reverse proxy (YARP), health checks, CI (GitHub Actions), contract-first API design, unit and contract testing (pytest, xUnit)

## AI Orchestration Concepts

Vector database (ingesting documents, vectorizing documents, querying database for semantic top k closest elements), idempotent ingestion (documents are only vectorized once instead of on every startup), langchain, langgraph, RAG, prompt templating, mock model providers for lightweight development

# Technologies Used

## Dotnet Server and Middleware

The main server for this project is written in C# and takes user requests, runs them through telemetry middleware, and routes them through YARP to the appropriate service.

## LangChain

The interactions with AI models and agents are orchestrated with Langchain and LangGraph, running in a Flask service.

## Docker

All microservices are contained in their own separate docker container and can be started using the docker-compose file. A useful start up script allows you to just invoke the script (by doing ./build.sh --mode mock or ./build.sh --mode live) and it will take care of tearing down the old containers and images, and building, compiling and starting the new containers. There is also an acceptance script (scripts/acceptance_check.sh) which runs a PASS/FAIL check against the running system.

# Milestones

## June 23, 2026: Initial Launch Date
This is the day I originally decided to start working on the project.

## July 2, 2026: Basic Docker System Configuration
The build script will gracefully invoke the docker compose file with preset environment variables, the docker compose file will spin up the basic services of the dotnet server, the langchain container, the postgres (pgvector) database, and a container to invoke llm model pulling.

## July 8, 2026: Hook up all components within the langchain container
As of now, langchain has been proven out in parts, but it needs to have the full pipeline set up and built.

## July 10, 2026: Switching from Complete Hand Developing to AI Collaborative Dev
I was able to get the framework such that my system is able to communicate to my langchain service through the Openwebui frontend. I am then able to invoke my LLM, and provide injected system prompts and targeted model invocations.

## July 11, 2026: First AI Implementation Plan Merged (PR #2)
Merged the ai_dev branch into main after reviewing it step by step. This brought in the pipeline registry, the LangGraph pipelines, the rebuilt Flask API layer, the real YARP gateway, the OpenAI-compatible surface for OpenWebUI, honest tests with CI wiring, and idempotent ingestion so documents are not revectorized on every startup.

## Coming Soon: Observability, Metrics Collection, and Evals

Retrieval and judge based evaluation with a golden dataset is in progress on the ai_dev branch, along with observability documentation.
