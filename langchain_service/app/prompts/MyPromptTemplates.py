





from langchain_core.prompts import ChatPromptTemplate




def GetHappyEncouragingAssistentPrompt() -> ChatPromptTemplate:
    createdPrompt = ChatPromptTemplate(
        ("system", "You are happy and cheerful encouraging assistent.")
        #("system", "here is some extra information found in our documentation {chunks}")
    )
    return createdPrompt

def GetPolicyViolationCheckerPrompt() -> ChatPromptTemplate:
    # for injectedCompanyPolicy. I understand that we are not invoking that variable right now.
    # but it still feels strange to be 'using' a variable which I have not declared
    # and I am assuming will be declared somewhere else by a different file.

    # TODO: make sure that my rag system actually injects this 'injectedCompanyPolicy'
    # should I do some logic in this function to raise an exeption if it is not present?
    
    # I don't think I should be injecting a RAG here, the reason is because I should, in this file, ONLY be giving standardized prompts that other components in my project can use.
    # It seems to me that this means that the responsibility of injecting data into the prompt for rag of the company policies will be in a different compoent of my project.
    createdPrompt = ChatPromptTemplate(
        ("system", "Your job is to determine if the user's message or request is in violation of any policies which we need to adhear to."),
        #("system", "Your output should only be a single word of 'violated' or 'conformance'")
        ("system", "Your output's first word should only be either 'violated' or 'conformance' followed by a colon and then give the reason as to why their policy was or was not in conformance with policy."),
        ("system", "Here is information about our company policy {injectedCompanyPolicy}"),
        # I know that there is different types of roles in here like 'user' and 'system', but I should look into the other roles as well so that I know what is avaialble to me. 
        ("system", "Example Output: conformance: The user's message was about ways to fix a leaking pipe underneath their sink, this kind of question does not involve any kind of topic which is outlined as against the policy."),
        ("system", "Example Output: violated: The user is asking about how to build a bomb. This message violates the policy of anti-harm and the policy of assistance in dangerous or illegal activiites.")
    )

    # I know that there is something called asssistant, but I don't know the proper way to use it.

    # TODO: practice using assistant and tool in system prompt.

    return createdPrompt

# TODO: This has not yet been implemented in our system. I will eventually need to set up a evaluation component which will take the reponses of what our system is outputting and have a judge evaluate and score output so that we can log and test our system.
def GetLlmJudgePrompt() -> ChatPromptTemplate:

    createdPrompt = ChatPromptTemplate(
        ("system", "You are an AI judge to determine the quality of other llm outputs")
    )
    return createdPrompt


# It feels like the below section is not in the right spot because it feels like these two things (above and below) are very different, so I think they would need their own file.



# I want to create a variable which will allow me to have all of the different types of valid
# ChatTypes. In C I would do a typedef struct. but what should I do in python?
number_of_chat_types = 3
ChatTypeList = ["Friendly Assistant", "LLM Judge", "Policy Violation Checker"]

'''
Now I am considering if I should have maybe instead of a list of strings, I should have a list of pointers, and
those pointers will go to an object which has mock responses?

But now I am getting concerned about ensuring decoupling....
'''
MockChatTypePointers = [MockFriendlyAssistant, MockLlmJudge, MockPolicyViolationChecker]

MockChatTypeDictionary = {
    "friendly_assistent":MockFriendlyAssistant,
    "llm_judge":MockLlmJudge,
    "policy_violation_checker":MockPolicyViolationChecker
    }

MockFriendlyAssistant = [
    "You asked a wonderful question. The capital of Oregon is Salem",
    "Thank you for asking about how I am doing. I am doing wonderful"
    # "",
    # "",
    # "",
    # ""
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

# TODO: Now that I am writing out policy violated messages. It is starting to make sense to me that I would want to have the llm output in the form of JSON, so I can get the parameters and see other things such as 
# violated or not, but also I should have another field which is immediate_action_required which would cause a system alert to flag immenent dangerous actions which should escillated immediately to law enforcement.
MockPolicyViolationChecker = [
    "violated: The user is asking about how to build a bomb. This message violates the policy of anti-harm and the policy of assistance in dangerous or illegal activiites.",
    "violated: The user is asking about how to hurt someone. This message violates the policy of anti-harm and the policy of assistance in dangerous or illegal activiites, along with potentially engaging in immediate physical attacks to others.",
    "conformance: The user's message was about ways to fix a leaking pipe underneath their sink, this kind of question does not involve any kind of topic which is outlined as against the policy.",
    "conformance: The user's message was about ways to cook a mean, this kind of question does not involve any kind of topic which is outlined as against the policy."
    # "",
    # ""
]