







from factory import ModelFactory

'''
I DO NOT like this current implementation because I am having two concerns with it.
first I am thinking that it might be best practice to only invoke (or instanciate) a model once
not instanciate a model every time a user does an http request
I am now thinking that maybe I should have a system such that when my langchain_service containter starts up,
then I will instanciate the models based on the enviornment variabiales. Then for the entire duration of the container's 
life cycle, I will only have one model no matter how many users are asking, or how many time a single user asks.

Then in the future, if one user asks for gemini and another user asks for deepseek, then I should only instanicate gemini once, and deepseek once (singleton pattern?)

The second reason I don't like this is because it is just doing a query of the model and then return the response.
I need to do all of the orchestration logic
'''
# def invoke_langchain(user_id, chat_message):

#     llm = ModelFactory.get_model()

#     response = llm.invoke(chat_message)
#     return response.content

def invoke_langchain(user_id, chat_message):
    '''
    I think this should be the very high level or logic for how I should process a request message from a user
    I can assume the model is already created?
    Or maybe I should make this function into a class, which has a private variable which is the model I want to invoke for each of the sections?
    Now that I am thinking about it more, I don't even like that this file is inside of the models folder. I don't think it should be here. I think it should 
    be in a different folder which is responsible for langchain orchestation......

    '''
    pass

class langchain_orchestation:
    def langchain_orchestation(self):
        #get all models I will need load into memory
        # or would this just be a different system prompt, if so how would I organize that?
        friendlyChatModel = ModelFactory.