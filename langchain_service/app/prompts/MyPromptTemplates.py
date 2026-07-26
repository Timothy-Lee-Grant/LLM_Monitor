from langchain_core.messages import SystemMessage
from langchain_core.prompts import ChatPromptTemplate


# Prompt versions (plan 002 Step 5c). Bump the version WHENEVER the template
# text changes — eval scores and traces are tagged with these, so a quality
# shift is attributable to the exact prompt that caused it. This is the seed
# of prompt management (Timothy's Stage 1 concern about evolving prompts).
ASSISTANT_PROMPT_VERSION = "assistant.friendly@1"
POLICY_CHECKER_PROMPT_VERSION = "policy.checker@1"
LLM_JUDGE_PROMPT_VERSION = "judge.faithfulness@2"  # @1 was the pre-rubric stub
TOOL_AGENT_PROMPT_VERSION = "agent.tools@1"  # plan 003 Step 3


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
            # ("placeholder", "{chat_history}") slot returns here when memory is added
            ("user", "{user_message}")
        ])
    
    @staticmethod
    def get_tool_agent_system() -> SystemMessage:
        """System message for the tool-loop agent (plan 003 Step 3).

        A concrete SystemMessage rather than a ChatPromptTemplate: the tool
        loop invokes the model on the RAW accumulating message list (human ->
        ai(tool_calls) -> tool -> ai...), and a template with fixed slots
        can't represent that growing history. The template returns when a
        history placeholder is added alongside memory.
        """
        return SystemMessage(content=(
            "You are a happy, cheerful, and encouraging assistant with access to tools.\n"
            "Use a tool whenever it can answer the user's question factually — for\n"
            "example current server time or server information — instead of guessing.\n"
            "After a tool returns, incorporate its result into your answer.\n"
            "If no tool is relevant, just answer directly."
        ))

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
        """Faithfulness judge (upgraded plan 002 Step 8; original stub was judge.accuracy@1).

        The rubric is INJECTED as a variable rather than hardcoded here —
        eval/rubric.md stays the single source of truth for scoring criteria,
        and rubric edits don't require code changes (they require a rubric
        version bump instead).
        """
        return ChatPromptTemplate.from_messages([
            ("system", (
                "You are an impartial evaluation judge. Apply the rubric below EXACTLY as written.\n\n"
                "{rubric}\n\n"
                "CRITICAL: respond with ONLY one line in the format:\n"
                "<score 1-5>: <one-sentence rationale citing the decisive claim>"
            )),
            ("user", "Context:\n{context}\n\nModel Response:\n{model_response}")
        ])