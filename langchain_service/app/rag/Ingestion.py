








import os
from flask import request
from langchain_postgres import PGVector
from langchain_core.documents import Document 

from app.models.factory import ModelFactory





db_user = os.getenv("POSTGRES_USER","admin")
db_pass = os.getenv("POSTGRES_PASSWORD","secret_pass")
db_name = os.getenv("POSTGRES_DB","secret_pass")
mode = os.getenv("LLM_MODE")

connection_string = f"postgresql+psycopg://{db_user}:{db_pass}@pgvector_service:5432/{db_name}"

# I need to investigate what this is doing and how this is working.
embeddings = ModelFactory.get_embedding_model("nomic-embed-text")
collection_name = "company_policies"
vector_store = ElephantVectorStore(
    embedding=embeddings,
    connection_string=connection_string,
    collection_name=collection_name
)

'''
I will need to contact postgres database to see if the tables and documents exist already for the files in my project.
If they already exist, then there is nothing to do. If they do not exist, I need to:
I will need to use the embedding model to take the documents and turn them into vectors.
then do an UPDATE (I think) to the pgvector db for my document which I found not to be in the database.
'''
def RunIdempotentRagIngestion():

    # Block if we are in mock mode
    if mode == "mock":
        return True
    
    # TODO: need to take in actual docs. Loader -> chunker -> 

    raw_docs = [
        Document(
            page_content="Employees are permitted to use local scripting tools for local automation, provided no proprietary source code leaves company assets.",
            metadata={"source": "security_policy_v2.md", "category":"it_safety"}
        ),
        Document(
            page_content="Building, designing, or testingexplosive devices or physical hazards on site is strictly prohibited and results in immediate termination.",
            metadata={"source":"hr_conduct_v1.md", "category":"physical_safety"}
        )
    ]

    vector_store.add_documents(raw_docs)
    return True


#This function should have the document we want to search against in it, but as stated above in my comments,
# I have not yet thought of a way to organize and map variables to the documents
def FindSemanticlyClosestElement(incomingMessage:str, documentToSearchAgainst:str, k:int=2):

    # I think now I need to encorporate if we are in 'mock' mode
    if mode == "mock":
        return 


    # Two questions I have with this. I remember hearing that we need to block erronious retrevials, so I think we would need to set a minimum matching closeness.
    # Second question is that I am curious how we would do this outside of the LC ecosystem. I am imagining that there is a way to just talk with the pgvector itself and do the commands to get the data.
    results = vector_store.similarity_search(incomingMessage, k=k)
    return results