# Purpose

The purpose of this project is to build a system which utilizes langchain to learn about and get the opportunity to demonstrate cababilities within this space that I am EXTREMELY interested in. I want all the actual code in this project to be my own, but I use Claude as a mentor who ONLY creates documentation (found in the Documentation folder), this is where I get evaluations on concepts that it feels I am weak or missing, code reviews, suggestions for targeting my specific goal of getting into **Microsoft** as a software engineer, and full lecture notes on those concepts which Claude has found that I am weak on.

This project was deleloped in two stages.
## First Stage: Hand Written Scaffolding
This stage was my opportunity to get my hands dirty and develop out the system that I wanted. I developed by hand all of the components which I wanted in my project, got the system working to a reasonable level, created a good base scafoldiing for the AI to understand exactly what this project is, and where it is going.

## Second Stage: AI Assisted Development
The second stage is taking the base scaffolding which was developed by hand and rolling it out into a full application.

## Hand Written Components
### Docker System
A build.sh script invoked the Docker Compose file which built up all required containers (dotnet server, langchain_service, posgres vector database, Ollama service, openwebui). The build script injected enviornment variables into the containers which would process both live and mock (to allow for use of mock on my computer which is not very powerful, so can't run heavy llms).

### Dotnet Server 
A .NET server written in C# that uses YARP to direct traffic from the outside world to the docker network inner services.

### Langchain / LangGraph
Within the langchain_service, there is a flask web server taking in API endpoints. This is then directed to 

# Concepts Implemented

## General Software Engineering

Docker, microservice architecture, middleware, client / server, http, REST, API, endpoints, .....

## AI Orchestration Concepts

Vector database (ingesting documents, vectorizing documents, querying database for semantic top k closest elements), langchain, .....

# Technologies Used

## Dotnet Server and Middleware

The main server for this project is written in C# and will take user requests and route them to the apporiate service.

## LangChain

The interactions with AI models and agents will be orchastrated with Langchian

## Docker 

All microservices are contained in their own seperate docker container and can be started using the docker-compose file. A useful start up script allows you to just invoke the script (by doing ./build) and it will take care of tearing down the old containers and images, and building, comiling and starting the new containers.

# Milestones

## June 23, 2026 Initial Launch Date
This is the day I origionally decided to start working on the project.

## July 2, 2026 Basic Docker System Configuration
The build script will gracefully invoke the docker compose file with preset enviornment variables, the docker compose file will spin up the basic services of the dotnet server, the langchain container, the postgres (pgvector) database, and a container to invoke llm model pulling.

## July 8, 2026: Hook up all components within the langchain container
As of now, langchain has been proven out in parts, but it needs to have the full pipeline set up and built.

## July 10, 2026: Switching from Complete Hand Developing to AI Collabrative Dev
I was able to get the framework such that my system is able to communicate to my langchain service through the Openwebui frontend. I am then able to invoke my LLM, and provide injected system prompts, targeted model invocations, 
