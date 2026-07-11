10 July, 2026

## Stage 1 (Design Documentation)

1. Context:

**Current State**:

This is the first collaborative AI feature implementation. Previously everything had been done 100% by hand. I wrote all the code, and completely developed this project myself. But now we are changing the implemention strategy which we will be using to develop this project. Now we will be taking on a collaborative development with AI as outlined in the CLAUDE.md file for AI_Implementation_Plans. 

This project currently has many different docker components. All of them are started up within the docker compose file. A build script is able to perform the docker compose calls to build and inject environment variables into the system. The two main dynamic environment variables are 'live' and 'mock'. 'live' is for when we want to start our system up with the real LLM and Ollama service. 'mock' is when we want to start up our project, but don't want to have the heavy system of Ollama and interacting with those LLMs.

The system currently operates as follows. The langchain_service gets an HTTP request from outside the docker network. It will recieve a POST request and that POST request will have the user's message. This user's message is then sent to our internal langchain_logic. The internal logic will process the users message by getting a standardized prompt, getting a standardized model, and invoking the chain with the user's message. I then tried to implement a RAG that would allow for functionality of comparing the user's message to documents in the vector database to give extra context.

I then attempted to get langgraph operating (but this is very much not working right now).

**Current Problems**:

- The system was under active development. It was working in parts, but every day there were many new changes, logic taken out, endpoints removed, classes modified, etc. So the current state of the system is very much unstable.

- I don't think that my RAG system actually works.

- I am unsure of the architecture which this project is using. I attempted to use my best judgement to create a scalable, distributed, asyncronous system; but I am lacking in experience in this realm, so I don't know if I did it in a good way or not.

- There is no standard interface and agreements between the different docker services for how these HTTP requests will be sent.

- The system is not connected correctly. The langchain_service should not be recieving any communications from outside the docker network. (I want to have API endpoint enabled in my langchain_service which are able to be reached by outside for testing reasons, but in the actual system all requests should be going through my YARP dotnet server.)

**Direction For This Implementation**

- Refactor code within each of the docker services to be professional, scalable, and clean.
- Ensure RAG actually saves documents corrently into our vector database
- Ensure RAG successfully retrieves those documents based on user message
- Create a standardized interface and contract between all of the services in the project.
- Have multiple API endpoints inside the langchain_service such that a user can send messages to be processed in the following ways in both base langchain (no langgraph) and in langgraph (but remember that we want scalablility so the implementation you use to implement these two endpoints with langgraph should allow for easy growth of new features within the langgraph system):

A simple POST request that gets sent to the llm with that message and given response.

A POST request that has extra context injected into it from the RAG.

So in total, there will be 4 working valid (testing) API endpoints which I can hit from outside docker network, and 4 other (real) API endpoints that I can hit by routing through my dotnet YARP sever.

- Ensure Openwebui is working and compatable with our system and can call as required.

2. Interfaces & contracts

I don't know

3. Acceptance criteria

(1) `./build.sh --mode mock` responds with all containers healthy, all 4 test endpoints return 200 with valid contract JSON; 
(2) same via dotnet gateway routes; 
(3) live mode: RAG endpoint response demonstrably uses ingested document content; 
(4) re-running ingestion twice yields no duplicate rows in pgvector; 
(5) OpenWebUI chat round-trips through the real pipeline (no hardcoded stub); 
(6) pytest suite covering contract shapes passes in CI.

4. Non-goals

- We do not need to attempt to implement features and functionality which does not currently exist in the project. For example, tool usage.
- Don't need to implement policy checking and blocking


## Stage 2 (Discussion)

---

### [AI — 2026_07_10_19_50] Opening entry: current-state findings and discussion questions

Timothy, I investigated the full codebase before writing this. First, concrete facts about the current state so our discussion is grounded in reality rather than memory. Then, the decisions I need from you.

#### A. Verified breakages (why the service is unstable)

These are not opinions — the refactor of prompts into `PromptFactory` left the rest of the codebase pointing at symbols that no longer exist:

1. **`app/models/factory.py` cannot import.** Line: `from app.prompts.MyPromptTemplates import MockChatTypeDictionary, number_of_chat_types`. Neither name exists anymore (the mock data moved to `mock_prompts.py` as `MOCK_RESPONSES` etc.). Since everything imports the factory, the entire service fails at startup. This is the root "nothing works" bug.
2. **`OrchestrationLogic.py` calls `GetHappyEncouragingAssistentRagPrompt()`** — replaced by `PromptFactory.get_assistant_prompt()`. NameError at request time.
3. **`graph/nodes.py` imports `GetPolicyViolationCheckerPrompt`** — same problem. Also, it's used as `GetPolicyViolationCheckerPrompt | model` without being called (it was a function; now it needs to be `PromptFactory.get_policy_checker_prompt() | model`).
4. **`graph/build_graph.py`**: `from langgraph.prebuilt import ToolNode, tool_condition` — the real name is `tools_condition`. Also `build_graph()` is incomplete (adds 2 nodes, no edges, no compile, returns `None`); only `build_graph_old()` is complete.
5. **Prompt variable mismatch**: `get_assistant_prompt()` requires `{context}`, but the non-RAG worker invokes with only `{"user_message": ...}` → KeyError. Also the template has `("placeholder", "{message}")` but nothing ever passes `message`.
6. **`/v1/chat/completions` is a hardcoded stub** — OpenWebUI "works" only in the sense that it receives a fake canned string. It never touches the orchestration layer.
7. **Dotnet `LlmController`**: reads `OLLAMA_BASE_URL` (never set for `dotnet_server` in compose → null), posts to `/api/chat` (doesn't exist on Flask), media type is `"/application/json"` (invalid — leading slash), and returns the raw `HttpResponseMessage` object serialized instead of reading the body. Four independent bugs; this path has never worked end-to-end.
8. **There is no YARP.** The plan says "my YARP dotnet server," but `Program.cs` is a plain controller app — no YARP package, no reverse-proxy config. This matters for question 1 below.
9. **`RunIdempotentRagIngestion` is not idempotent.** `add_documents` with no IDs inserts duplicates on every startup. Your pgvector collection is accumulating copies of the same two documents. Fix: deterministic IDs (e.g., hash of content) so re-ingestion upserts.
10. Minor but worth fixing while we're in there: `ChatState.disired_model` typo (it's load-bearing — nodes read `state["disired_model"]`), `main.py` runs ingestion *after* creating the app with `debug=True` (the Flask reloader imports the module twice → double ingestion), and Flask's dev server isn't a production server (gunicorn is the standard fix).

#### B. My read on the architecture (answering your "is my architecture good?" worry)

The overall shape is sound and industry-standard: gateway → orchestration service → model runtime + vector DB, with mock/live profiles. That's genuinely the right decomposition. Your instability isn't an architecture problem — it's the absence of two things professionals lean on: **contracts** (so a rename in one file can't silently break five others) and **tests/CI that run the service** (so breakage is caught at commit time, not demo time). This implementation should prioritize those two, because they're what makes the refactor *stay* fixed.

#### C. Decisions I need from you before Stage 3

**Q1 — What is the dotnet server, really?** Two different products:
   - (a) **True YARP reverse proxy**: transparent forwarding, routes defined in `appsettings.json`, no DTOs, no controller for the chat path. Telemetry middleware still works. Less code, matches "API gateway" on a resume.
   - (b) **Controller-based orchestrator** (what exists now): receives, validates, transforms, forwards via HttpClient. More code, more control, but it duplicates the contract and is where 4 of your bugs live.
   - My recommendation: (a) for the chat routes, keeping a controller only where the gateway adds real logic later (auth, policy). But it's your call and it changes the plan significantly.

**Q2 — The contract.** I propose one canonical JSON shape at every HTTP boundary, snake_case on the wire (configure `System.Text.Json` naming policy in C# rather than renaming C# properties — this answers the comment-question in your controller about naming conventions across languages). Request: `{user_id, user_message, requested_model}`. Response: `{status, response, metadata{...}}`. Documented in one markdown file that both services link to. Agree, or do you want to design it together in more detail first?

**Q3 — Endpoint layout.** Plan says 4 test endpoints. I propose: `/test/chat/basic`, `/test/chat/rag`, `/test/graph/basic`, `/test/graph/rag`, plus the real `/v1/chat/completions` for OpenWebUI. For scalable dispatch, your own commented-out idea in `FlaskServer.py` (dict of model-id → orchestration function) is the right pattern — OpenWebUI's model picker then selects the pipeline. Confirm?

**Q4 — Mock mode and RAG.** Currently mock mode makes `FindSemanticlyClosestElement` return `[]`, so the RAG path is untestable without Ollama. Do you want a mock embedding model (deterministic fake vectors) so the *full* RAG path — pgvector included — runs in mock mode? I'd argue yes: it makes the RAG contract testable in CI. Cost: a bit more mock code.

**Q5 — LangGraph scope.** For "scalable growth," I'd structure the graph as: entry → (rag?) → agent → respond, with the policy-check node deferred (your non-goals exclude policy blocking). The graph and plain-chain paths would share the same `ModelFactory`/`PromptFactory`/retriever components. The checkpointer stays out of scope for this cleanup. Agree?

**Q6 — Acceptance criteria** (you left this open; here's a strawman): (1) `./build.sh --mode mock` → all containers healthy, all 4 test endpoints return 200 with valid contract JSON; (2) same via dotnet gateway routes; (3) live mode: RAG endpoint response demonstrably uses ingested document content; (4) re-running ingestion twice yields no duplicate rows in pgvector; (5) OpenWebUI chat round-trips through the real pipeline (no hardcoded stub); (6) pytest suite covering contract shapes passes in CI.

Answer inline or in chat and I'll fold your decisions into the next entry.

---

Yes, I read over your assessment and it sounds correct. 

**Q1** I wanted to put YARP into this project to be able to signal to Microsoft that I would be a good canditate and have experience working with their systems. I was thinking that YARP could be a rate limiter, authentication, etc. I don't know if this is the right way to think about it, but this was my logic.

**Q2** I like your idea.

**q3** Sounds good, but does this assume that all of those will be going to the langchain_service? Will we have 4 (or I guess 5) more that correspond to going to the dotnet server to be routed though the authentication and telemetry gathering in the future?

**q4** Yes, I definately want to be able to have a fully mock path, as you described and suggested.

**q5** How will we handle the situations in the future where we have multiple users attempting to connect to the same pipeline? Or we need to upgrade a pipeline to add a new feature? Or if I want to add something like photo parsing? Is your idea scalable in these dimensions?

**q6** I like it and have updated my acceptance criteria section.

---

### [AI — 2026_07_10_23_13] Reply: YARP confirmed, endpoint topology, pipeline scalability

**Q1 (YARP) — your logic is exactly right.** YARP is Microsoft's own reverse-proxy library, built as ASP.NET Core middleware, which means the gateway becomes: `request → telemetry middleware → (future: auth middleware) → (future: rate-limiter middleware) → YARP forwarder → langchain_service`. Rate limiting and auth aren't *inside* YARP — they're standard ASP.NET middleware (`AddRateLimiter`, `AddAuthentication`) that sit in front of the proxy step, which is precisely the mental model you described. This is also the honest resume story: "built an API gateway with YARP, custom telemetry middleware, with extension points for auth and rate limiting." **Decision: option (a), true YARP proxy.** Your existing `TelemetryMiddleware` survives unchanged. `LlmController` gets retired (or kept only as a non-routed reference).

**Q3 (endpoint topology) — good catch, and here's the cleaner framing: the 4 "test" and 4 "real" endpoints are the same 4 endpoints, reached via two network paths.** We do not write 8 handlers. The langchain_service defines 4 canonical routes (+ the OpenWebUI ones):

```
langchain_service (port 5000 internal):
  POST /chat/basic          POST /graph/basic
  POST /chat/rag            POST /graph/rag
  GET  /v1/models           POST /v1/chat/completions

Test path (dev only):   host:5001 → langchain_service directly
                        (works because compose maps 5001:5000)
Real path:              host:5000 → dotnet gateway → telemetry middleware
                        → YARP forwards /api/llm/{**rest} → langchain_service/{rest}
```

So `POST host:5000/api/llm/chat/rag` and `POST host:5001/chat/rag` hit the identical handler — one goes through the gateway (telemetry, future auth), one bypasses it. When you eventually want to lock the system down, you delete the `5001:5000` port mapping from compose and the "test path" ceases to exist without touching any code. This satisfies your Stage 1 requirement ("langchain_service should not receive outside communications... except for testing") as a *configuration* choice, not a code fork.

**Q5 (pipeline scalability) — three separate concerns, three separate mechanisms:**

1. *Multiple users, same pipeline.* Compiled chains and graphs are **stateless, reusable objects** — we build each pipeline once at startup, and every request is an independent `.invoke()` carrying its own state dict. Two users invoking the same graph concurrently never touch each other's data, the same way two calls to a pure function don't. Per-request concurrency is handled by the server layer (gunicorn workers). Later, when you add memory, per-user state lives in the checkpointer keyed by `thread_id` — the pipeline object itself still stays shared and stateless. This is the standard production pattern.
2. *Upgrading a pipeline.* This is what the **registry pattern** (your model-id → pipeline dict) buys us. Each pipeline has a string id (`"chat-basic"`, `"agent-rag"`). Upgrading = registering `"agent-rag-v2"` alongside v1; OpenWebUI's model list exposes both; you A/B them; you retire v1 by deleting one registry line. No endpoint changes, no client changes.
3. *New capabilities (e.g., photo parsing).* Two insertion points, both already planned: a new **node** in an existing graph (if it's a step in a flow — e.g., "if message contains image, parse it, put description in state, continue"), or a new **registry entry** (if it's a new flow entirely). The contract is the only thing that needs future-proofing: we'll define `user_message` today but keep the request shape extensible (a future `attachments` field is additive, not breaking). Designing the v1 contract so additions don't break existing clients is the real scalability discipline here — and it's a non-goal to *implement* photo parsing now.

**Where we stand:** Q1 decided (YARP proxy), Q2 agreed (snake_case contract, single doc), Q3 clarified above (confirm you're happy with "same endpoints, two paths"), Q4 decided (full mock RAG path), Q5 answered above, Q6 locked into Stage 1. If Q3's topology and Q5's answers sit right with you, I consider Stage 2 converged and I'll write the full Stage 3 implementation plan on your go.

---

## Stage 3 (Implementation Planning)

Not Gotten To Yet

### Stage 3 Discussion Subsection

Not Gotten To Yet

## Stage 4 (Implementation)

Not Gotten To Yet

## Stage 5 (Final Results, Testing, Verficiation)

Not Gotten To Yet