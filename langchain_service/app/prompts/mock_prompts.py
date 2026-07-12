MOCK_FRIENDLY_ASSISTANT = [
    "You asked a wonderful question. The capital of Oregon is Salem.",
    "Thank you for asking about how I am doing! I am doing wonderful."
]

MOCK_POLICY_VIOLATION_CHECKER = [
    "violated: Request contains restricted physical hazards.",
    "conformance: Message is completely benign."
]

MOCK_LLM_JUDGE = [
    "5: Perfect alignment with source material.",
    # Added plan 002 Step 8: a second verdict (with a colon inside the rationale)
    # so the plumbing tier exercises the parser's first-colon-only split too.
    "2: Unsupported claims present: the response invents details absent from the context.",
]

MOCK_RESPONSES = {
    "friendly_assistant": MOCK_FRIENDLY_ASSISTANT,
    "policy_violation_checker": MOCK_POLICY_VIOLATION_CHECKER,
    "llm_judge": MOCK_LLM_JUDGE
}