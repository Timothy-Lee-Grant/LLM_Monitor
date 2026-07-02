





from langchain_core.prompts import ChatPromptTemplate


def GetHappyEncouragingAssistentPrompt() -> ChatPromptTemplate:
    createdPrompt = ChatPromptTemplate(
        ("system", "You are happy and cheerful encouraging assistent.")
        #("system", "here is some extra information found in our documentation {chunks}")
    )
    return createdPrompt

# TODO: This has not yet been implemented in our system. I will eventually need to set up a evaluation component which will take the reponses of what our system is outputting and have a judge evaluate and score output so that we can log and test our system.
def GetLlmJudgePrompt() -> ChatPromptTemplate:

    createdPrompt = ChatPromptTemplate(
        ("system", "You are an AI judge to determine the quality of other llm outputs")
    )
    return createdPrompt