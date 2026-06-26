# June 26, 2026:
## Stateful Langchain
I will implement langchain at first to be stateful. This will mean that I will just store the user information and chat history. I will not keep user information in an external database and grab it per request. I will also at first assume that user requesting is always the same user. 

Later implementations I will need to dynaically load that user's chat history based on their user id. This will solve both the stateless/stateful issue, and also allow for multi-user sessions on the server. But for simplicity sake, right now I will just make these two assumptions to get the system up and running and tested.