# Purpose

The purpose of this project is to build a system which utilizes langchain to learn about and get the opportunity to demonstrate cababilities within this space that I am EXTREMELY interested in. I want all the actual code in this project to be my own, but I use Claude as a mentor who ONLY creates documentation (found in the Documentation folder), this is where I get evaluations on concepts that it feels I am weak or missing, code reviews, suggestions for targeting my specific goal of getting into Microsoft as a software engineer, and full lecture notes on those concepts which Claude has found that I am weak on.

# Technologies Used

## Dotnet Server and Middleware

The main server for this project is written in C# and will take user requests and route them to the apporiate service.

## LangChain

The interactions with AI models and agents will be orchastrated with Langchian

## Docker 

All microservices are contained in their own seperate docker container and can be started using the docker-compose file. A useful start up script allows you to just invoke the script (by doing ./build) and it will take care of tearing down the old containers and images, and building, comiling and starting the new containers.

# Milestones