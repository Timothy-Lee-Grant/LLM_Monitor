

'''
I will need to contact postgres database to see if the tables and documents exist already for the files in my project.
If they already exist, then there is nothing to do. If they do not exist, I need to:
I will need to use the embedding model to take the documents and turn them into vectors.
then do an UPDATE (I think) to the pgvector db for my document which I found not to be in the database.
'''
def RunIdempotentRagIngestion():
    #
    pass