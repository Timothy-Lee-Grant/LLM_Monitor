





from langchain_core.prompts import ChatPromptTemplate


def GetHappyEncouragingAssistentPrompt() -> ChatPromptTemplate:
    createdPrompt = ChatPromptTemplate(
        ("system", "You are happy and cheerful encouraging assistent.")
        #("system", "here is some extra information found in our documentation {chunks}")
    )
    return createdPrompt

def GetPolicyViolationCheckerPrompt() -> ChatPromptTemplate:
    # I don't think I should be injecting a RAG here, the reason is because I should, in this file, ONLY be giving standardized prompts that other components in my project can use.
    # It seems to me that this means that the responsibility of injecting data into the prompt for rag of the company policies will be in a different compoent of my project.
    createdPrompt = ChatPromptTemplate(
        ("system", "Your job is to determine if the user's message or request is in violation of any policies which we need to adhear to."),
        #("system", "Your output should only be a single word of 'violated' or 'conformance'")
        ("system", "Your output's first word should only be either 'violated' or 'conformance' followed by a colon and then give the reason as to why their policy was or was not in conformance with policy."),
        # I know that there is different types of roles in here like 'user' and 'system', but I should look into the other roles as well so that I know what is avaialble to me. 
        ("system", "Example Output: conformance: The user's message was about ways to fix a leaking pipe underneath their sink, this kind of question does not involve any kind of topic which is outlined as against the policy."),
        ("system", "Example Output: violated: The user is asking about how to build a bomb. This message violates the policy of anti-harm and the policy of assistance in dangerous or illegal activiites.")
    )

    return createdPrompt

# TODO: This has not yet been implemented in our system. I will eventually need to set up a evaluation component which will take the reponses of what our system is outputting and have a judge evaluate and score output so that we can log and test our system.
def GetLlmJudgePrompt() -> ChatPromptTemplate:

    createdPrompt = ChatPromptTemplate(
        ("system", "You are an AI judge to determine the quality of other llm outputs")
    )
    return createdPrompt