# LLM_Monitor

A self-hosted LLM serving platform: a C# / .NET gateway routes traffic through telemetry middleware and YARP to a Python LangChain/LangGraph service, which runs chat and RAG pipelines against local Ollama models with a pgvector database for retrieval. OpenWebUI sits on top as the chat frontend, talking to the system through an OpenAI-compatible API that I implemented.

I built this to go deep on AI orchestration and to have a real system where I could practice the engineering discipline I want to bring to a production team: contract-first API design, honest CI, health-checked container orchestration, and a documented review process for every change.

# Architecture

Request flow:

OpenWebUI -> dotnet gateway (telemetry middleware -> YARP reverse proxy) -> langchain_service (Flask) -> pipeline registry -> Ollama / pgvector

The services, each in its own container:

- **dotnet_server** — C# gateway. Custom telemetry middleware logs method, path, status, and latency for every request on the way out, then YARP forwards to the inner network. Auth and rate limiting are designed as future middleware in front of the same forwarder.
- **langchain_service** — Python/Flask. Owns a pipeline registry with four pipelines: chat-basic and chat-rag (LangChain chains), graph-basic and graph-rag (LangGraph). Also exposes an OpenAI-compatible surface (/v1/models, /v1/chat/completions) where the model id selects the pipeline, so adding a registry entry automatically exposes a new "model" to any OpenAI client.
- **pgvector-service** — Postgres with the pgvector extension for RAG retrieval. Ingestion is idempotent: documents are hashed and only vectorized once, not re-embedded on every startup.
- **ollama** — local model serving, only started under the live compose profile.
- **openwebui** — chat frontend. Configured to enter through the gateway, so every chat transits the telemetry middleware.

# Running It

```
./build.sh --mode mock        # lightweight, stubbed model provider
./build.sh --mode live        # real Ollama models (add --gpu for the GPU compose override)
./build.sh --mode mock --obs  # either mode + the observability stack (Jaeger, Prometheus, Grafana, Langfuse)
bash scripts/acceptance_check.sh mock   # PASS/FAIL check against the running system
bash scripts/observability_check.sh     # PASS/FAIL check of the observability stack (requires --obs)
```

The mock mode exists because my development machine can't run heavy models. The entire pipeline (gateway, registry, RAG retrieval, contracts) executes identically in both modes; only the model provider is stubbed. Chat at http://localhost:3000, gateway at http://localhost:5000.

# Observability

With `--obs`, every request leaves a story: a distributed trace across the C# gateway and Python service (one `traceparent` header stitching both into a single Jaeger tree), RED + token metrics per pipeline in Grafana, the fully rendered prompt and retrieved chunks in Langfuse, and gateway log lines carrying the trace id so logs join to traces. A golden-dataset eval harness (hit@k / MRR plus an LLM-as-judge faithfulness score) runs its deterministic tier in CI behind a self-arming regression gate. Everything is profile-gated: without the flag, none of it runs.

**Startup steps and a guided tour of the telemetry (one request traced through all four pillars): [observability/README.md](observability/README.md).**

# Engineering Decisions

**Contract-first API design.** Every HTTP boundary is defined in CONTRACTS.md before it is implemented. Wire shapes are snake_case everywhere, changes must be additive within a version, and both the C# and Python sides implement the shapes exactly. C# maps PascalCase to the wire via JsonNamingPolicy rather than hand-renaming fields.

**Production lockdown is a config change, not a code change.** The langchain_service is directly reachable on port 5001 for development and testing. Deleting that one port mapping in docker-compose is the lockdown switch; the gateway path is the only path that remains.

**Startup ordering through health checks, not sleeps.** The gateway waits on the langchain service being healthy, which waits on postgres being healthy. The langchain healthcheck is stdlib Python because the slim base image ships neither curl nor wget, and its start_period budgets for one-time RAG ingestion.

**Honest CI.** The original GitHub Actions workflow "passed" by installing nothing and running a test that imported no application code. I rebuilt it so the Python job installs the real requirements and runs the real pytest suite, and a separate job builds and tests the C# solution. A green build now means something.

# Testing

- Python: pytest suites covering the API contract, the pipeline registry, the model factory, and idempotent ingestion ids.
- C#: xUnit project for the gateway.
- System level: scripts/acceptance_check.sh runs an end-to-end PASS/FAIL pass against the live containers, deliberately without set -e so every check reports instead of dying on the first failure.

# How This Was Built

This project was developed in two stages, and the process is documented in the repo because I think the process is part of the work.

**Stage 1: hand-written scaffolding.** I built every component myself — the Docker system, the C# gateway, the langchain service — and got the full path working end to end, so that I understood every piece before any AI touched the code.

**Stage 2: AI-collaborative development with review gates.** Larger features go through a staged process (Documentation/AI_Implementation_Plans): I write the design goals, the AI and I discuss architecture and tradeoffs, it produces a step-by-step implementation plan, and then it implements one step at a time with my explicit permission per step. I review every change like a PR — the git history includes rounds of my review feedback and the resulting fixes. Separately, Claude acts as a mentor that writes code reviews and lecture-style documents on concepts it finds I am weak on (Documentation folder).

I did this deliberately: AI-assisted development is how software gets built now, and I wanted to practice doing it with the same rigor as human code review rather than accepting generated code blind.

# Roadmap

- Observability and metrics collection (in progress on the ai_dev branch): structured telemetry beyond the current middleware logging.
- Evals (in progress on the ai_dev branch): retrieval evaluation and LLM-as-judge evaluation against a golden dataset, wired into CI.
- Streaming responses on the OpenAI surface, auth and rate limiting middleware at the gateway, and conversation memory via LangGraph checkpointing (thread_id is already reserved in the contract).

# Milestones

- June 23, 2026 — project start.
- July 2, 2026 — Docker system: build script, compose file, all five services spinning up with environment injection.
- July 8, 2026 — full langchain pipeline connected end to end.
- July 10, 2026 — OpenWebUI talking to my service through the gateway; switched from pure hand development to the staged AI-collaborative process.
- July 11, 2026 — first implementation plan merged (PR #2): pipeline registry, LangGraph pipelines, real YARP proxy, OpenAI-compatible surface, honest CI, idempotent ingestion.
