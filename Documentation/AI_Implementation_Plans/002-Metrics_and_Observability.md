12 July, 2026

# Stage 1 (Design Documentation)

**Direction For This Implementation**

This document is an outline of Documentation/concepts_documentation/018-Observability_And_AI_Evaluation_Concepts_For_Plan_002.md which was made to overview the concepts and ideas which will be needed to be understood during implementation. Read that document to get a better understanding of this implementation plan.

## General Feel

After this implementation the system should be fully wired up in a sustainable and well architectured way to capture, log, and display all telemetry data coming from the system. The telemetry data will be both the standard traditional data (such as latency, error rate, request rate) and traditional data specific to AI systems (token per request, etc). In addition to the traditional metrics and telemetry, our system will also need to produce, collect, report, display, process AI information (LLM as judge, vector database retreival judging, etc).

All of this information will need to be collected and be able to be viewable to the users.

For LangFuse operations, we should make sure to take advantage of the registry pattern we developed in the previous 001 implementation. We should attach instrumentation at the registry boundary.

Another thing that I am now thinking about is that we have not yet added tools or memory into this system. This is going to be something that we will also want to have observability for. Therefore in this implementation plan we will need to do it in such a way that allows for easy addition and integration of tools and memory. Maybe this means adding fake stubs, or it means holding off entirely on this implementation plan and working on the tools and memory plan first, then returning to this plan.

## Retrieval 

This can be done within the CI testing regularly because it will be cheap. We will be able to deterministically test the quality of retrieval of the documents from the vector database.

With the retrieval, another thing that will need to be taken into consideration with the architecutre is that I am planning on having different tables for my vector databases. One will be for documents which contain 'acceptable ai usage', this will be used to block potentially harmful user requests, another table will be a group of documents which might be useful to suplement the user's message to give a more helpful answer.

### LLM as Judge

This will be to judge the output of the responses which the user gets back for their input. 

Because the LLM is itself a model, I (Timothy) will need to provide human examples as to what kind of responses will be expected and hoped for as responses. When creating this system, give a stub document and indicate where you want me to fill in human information. I think that we will also need a rubric (or maybe what I just described is the rubric itself). I also know that there is a standard of REGAS which we want to follow and implement in this evaluation system.

When implementing this, it will need to be considered carefully from an architectural point of view because as of now our system has a placeholder 'friendly assistant' prompt, but in the future, we will be changing this so that we can have more nuanced and better responses. We might also have different type of message prompts based on parameters. So we will need to have our system be able to plan for this.

Another interesting idea which I had was for user feedback, it is mentioned in the 018-Observability_And_AI_Evaluation_Concepts_For_Plan_002.md that we can use if the user gives us a thumbs up or thumbs down to determine if the llm's answer was good or not. An idea which I had was we could also use the user's reponse message back to the llm to determine the quality of the previous message. An example of this would be if the user got Response A and then they followed up by saying "But I still don't quite understand....." This indicates that Response A was not optimal, so the follow up can indicate information about the previous message. If we use an LLM judge to look at user's follow up messages, we can have it judge the previous llm response based on degree of positive or negative. If the user says "That's not what I mean at all!" This is a much stronger negative indicator than just saying "But I still don't quite understand....." so the llm judge would rate the stronger negative response with a larger negative number. Likewise, if the user says "Thank you, I got it now." this would be a positive indicator of the previous message.

### Errors to Fix Before Starting Implementation

- When I log onto OpenWebUI, I should only and always connect to my dotnet server. I should only be able to reach my langchain test endpoints with a curl command. (Now I am thinking that I need to look into the architecture on this because is it that we are automatically reporting all endpoint pipelines which we registered to OpenWebUI, because if that is the case then this will be more difficult to change.)

But it should be the case that we are automatically connected with the dotnet endpoints.

- When I first open up my OpenWebUI on my browser, I get spammed with messages telling me that I am connected.

## In Scope

I like the ouline which was given for this plan of:

1. OTel tracing: gateway root span → traceparent propagation → Flask/registry spans → Collector → local trace backend. (C#→Python distributed trace working = the headline.)
Metrics: RED + token/latency counters per pipeline_id, Prometheus + one Grafana dashboard.

2. LLM-layer capture: prompt/chunks/tokens per invocation at the registry boundary (Langfuse, or OTel attributes to start — a genuine Stage 2 discussion: Langfuse now vs OTel-only first).

3. Golden dataset v1 (15–30 items) + retrieval metrics (hit@k, MRR) running in CI mock mode.

4. First LLM-as-judge eval (faithfulness on the golden set), nightly/manual, using your existing judge prompt.

## Out of Scope

alerting/paging, SSE streaming, security gates beyond design notes, checkpointer/memory, RAGAS-the-library (although I am confused as to why REGAS would be out if it is part of the retreival metrics)