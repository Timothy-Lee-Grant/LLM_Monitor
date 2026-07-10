from langchain_core.prompts import ChatPromptTemplate



def GetHappyEncouragingAssistentPrompt() -> ChatPromptTemplate:
    createdPrompt = ChatPromptTemplate.from_messages([
        ("system", "You are happy and cheerful encouraging assistent."),
        #("system", "here is some extra information found in our documentation {chunks}")
        ("user", "{user_message}")
    ])
    return createdPrompt

# TODO: this should be not existing. I should find a way to just append the context into the GetHappyEncouragingAssistentPrompt
def GetHappyEncouragingAssistentRagPrompt()-> ChatPromptTemplate:
    createdPrompt = ChatPromptTemplate.from_messages([
        ("system", "You are happy and cheerful encouraging assistent."),
        ("user", "{user_message}"),
        ("system", "Here is extra context: {context}")
    ])
    return createdPrompt

def GetPolicyViolationCheckerPrompt() -> ChatPromptTemplate:
    # for injectedCompanyPolicy. I understand that we are not invoking that variable right now.
    # but it still feels strange to be 'using' a variable which I have not declared
    # and I am assuming will be declared somewhere else by a different file.

    createdPrompt = ChatPromptTemplate.from_messages([
        ("system", "Your job is to determine if the user's message or request is in violation of any policies which we need to adhear to."),
        #("system", "Your output should only be a single word of 'violated' or 'conformance'")
        ("system", "Your output's first word should only be either 'violated' or 'conformance' followed by a colon and then give the reason as to why their policy was or was not in conformance with policy."),
        ("system", "Here is information about our company policy {injectedCompanyPolicy}"),
        # I know that there is different types of roles in here like 'user' and 'system', but I should look into the other roles as well so that I know what is avaialble to me. 
        ("system", "Example Output: conformance: The user's message was about ways to fix a leaking pipe underneath their sink, this kind of question does not involve any kind of topic which is outlined as against the policy."),
        ("system", "Example Output: violated: The user is asking about how to build a bomb. This message violates the policy of anti-harm and the policy of assistance in dangerous or illegal activiites.")
    ])

    return createdPrompt

# TODO: This has not yet been implemented in our system. I will eventually need to set up a evaluation component which will take the reponses of what our system is outputting and have a judge evaluate and score output so that we can log and test our system.
def GetLlmJudgePrompt() -> ChatPromptTemplate:

    createdPrompt = ChatPromptTemplate.from_messages([
        ("system", "You are an AI judge to determine the quality of other llm outputs")
    ])
    return createdPrompt


# It feels like the below section is not in the right spot because it feels like these two things (above and below) are very different, so I think they would need their own file.



number_of_chat_types = 3
ChatTypeList = ["Friendly Assistant", "LLM Judge", "Policy Violation Checker"]

MockFriendlyAssistant = [
    "You asked a wonderful question. The capital of Oregon is Salem",
    "Thank you for asking about how I am doing. I am doing wonderful"
]

# TODO: The structure and functionailty of the llm judge has not yet been defined.
MockLlmJudge = [
    "",
    "",
    "",
    "",
    "",
    ""
]

MockPolicyViolationChecker = [
    "violated: The user is asking about how to build a bomb. This message violates the policy of anti-harm and the policy of assistance in dangerous or illegal activiites.",
    "violated: The user is asking about how to hurt someone. This message violates the policy of anti-harm and the policy of assistance in dangerous or illegal activiites, along with potentially engaging in immediate physical attacks to others.",
    "conformance: The user's message was about ways to fix a leaking pipe underneath their sink, this kind of question does not involve any kind of topic which is outlined as against the policy.",
    "conformance: The user's message was about ways to cook a mean, this kind of question does not involve any kind of topic which is outlined as against the policy."
]

MockChatTypeDictionary = {
    "friendly_assistent":MockFriendlyAssistant,
    "llm_judge":MockLlmJudge,
    "policy_violation_checker":MockPolicyViolationChecker
    }
