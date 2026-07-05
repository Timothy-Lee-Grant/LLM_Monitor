# Purpose

The purpose of this project is to build a system which utilizes langchain to learn about and get the opportunity to demonstrate cababilities within this space that I am EXTREMELY interested in. I want all the actual code in this project to be my own, but I use Claude as a mentor who ONLY creates documentation (found in the Documentation folder), this is where I get evaluations on concepts that it feels I am weak or missing, code reviews, suggestions for targeting my specific goal of getting into **Microsoft** as a software engineer, and full lecture notes on those concepts which Claude has found that I am weak on.

* Note: This project was developed 100% by me (not AI). Claude is explicitly prohibited from changing any code or fixing things, and is only acting as a code reviewer and as an analyzer of gaps in my knowledge to then generate lecture documents (found in the Documents folder) which I can study to learn and grow as an engineer.
* Feel free to interregate me on ANY of the concepts found in this project

# Concepts Implemented

## General Software Engineering

Docker, microservice architecture, middleware, client / server, http, endpoints, .....

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

## Next Milestone: Hook up all components within the langchain container
As of now, langchain has been proven out in parts, but it needs to have the full pipeline set up and built.
