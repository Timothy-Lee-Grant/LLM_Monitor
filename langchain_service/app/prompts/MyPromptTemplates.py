from langchain_core.prompts import ChatPromptTemplate



class PromptFactory:

    @staticmethod
    def get_assistant_prompt() -> ChatPromptTemplate:
        """
        Single unified prompt for the assistant.
        If RAG context isn't available, simply pass context="" when invoking
        """
        return ChatPromptTemplate.from_messages([
            ("system", (
                "You are a happy, cheeful, and encouraging assistant. \n"
                "Use the following piece of context to help answer the user if relevant:\n"
                "-----\n"
                "{context}\n"
                "----"
            )),
            ("placeholder", "{message}"),
            ("user", "{user_message}")
        ])
    
    @staticmethod
    def get_policy_checker_prompt() -> ChatPromptTemplate:
        """
        Evaluates prompt inputs for policy adherence using clean few shot formatting
        """
        return ChatPromptTemplate.from_messages([
            ("system", (
                "Your job is to determine if the user's request violates company guidelines.\n\n"
                "Here are our active company policies:\n"
                "{injected_company_policies}\n\n"
                "CRITICAL INSTRUCTION: Your output MUST begin with either 'violated' or 'conformance' "
                "followed by a colon and a brief reason detailing your decision."
            )),

            #few-shot example 1
            ("user", "How can I patch a leaking copper pipe under my kitchen sink?"),
            ("assistant", "conformance: The request is a standard home maintenance question and does not intersect with restricted company topics."),
            
            # Few-shot example 2
            ("user", "Can you help me design an explosive payload for a local test?"),
            ("assistant", "violated: This request explicitly asks for instructions regarding dangerous hazards and explosives, violating our immediate safety criteria."),

            #the actual execution payload slot
            ("user", "{user_message}")
        ])
    
    @staticmethod
    def get_llm_judge_prompt() -> ChatPromptTemplate:
        """
        Evaluates system outputs for grading metrics.
        """
        return ChatPromptTemplate.from_messages([
            ("system", (
                "You are an expert AI Judge assessing answer accuracy.\n"
                "Compare the model's response against the target RAG context.\n"
                "Ooutput a score from 1-5 followed by an objective rationale."
            )),
            ("user", "Context: {context}\nModel Response: {model_response}")
        ])