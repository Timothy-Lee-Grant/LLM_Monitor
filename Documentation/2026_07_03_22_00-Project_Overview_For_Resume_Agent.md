# Project Overview: LLM_Monitor

> **Document purpose:** A structured, machine-readable summary of the `LLM_Monitor` project, written for ingestion by an AI agent that maintains a portfolio/resume knowledge base. It describes what the project is, its architecture, the technologies used, the concrete skills it demonstrates, and its honest current status. Optimized for parsing and reuse, not for human marketing prose.

---

## 1. Structured metadata (quick-parse block)

```yaml
project_name: LLM_Monitor
owner: Timothy Grant
type: personal_learning_project
domain: [backend_engineering, ai_engineering, distributed_systems, observability, devops]
status: in_progress            # active development; not production-deployed
maturity: early_mid            # architecture established; core pipeline being wired
started: 2026-06 (approx)
primary_languages: [Python, C#]
architecture_style: microservices (multi-container)
one_line: >
  A multi-service system that routes user chat requests through a .NET API gateway
  to a Python/LangChain orchestration service which performs policy/safety checks,
  retrieval-augmented generation, tool use, and conversation memory against local
  LLMs (Ollama) and a pgvector vector database, with an emphasis on observability.
learning_goal: >
  Build the backend, distributed-systems, and AI-integration skills required for a
  software engineering role at a large technology company (target: Microsoft).
```

---

## 2. One-paragraph description

LLM_Monitor is a self-directed engineering project that implements an **LLM observability and orchestration platform** as a set of containerized microservices. A **C#/.NET server** acts as the edge/API gateway (request validation, telemetry, response shaping) and forwards user messages to a **Python service built on LangChain/LangGraph** that orchestrates the AI workflow: a policy/prompt-injection safety gate, retrieval-augmented generation (RAG) over company-policy documents, tool invocation, conversation memory, and a final grounded response. Supporting containers include **Ollama** (local LLM inference), **pgvector/PostgreSQL** (vector + relational storage), and a model-provisioning job. The project deliberately mirrors a commercial LLM-application architecture (edge gateway + orchestration service + data/observability plane) at reduced scale, and is built with professional practices in mind: dependency injection, a mock/live configuration seam for development on low-compute hardware, idempotent startup routines, and structured telemetry.

---

## 3. Architecture

```
 user ─▶ [C#/.NET API gateway] ─HTTP─▶ [Python LangChain/LangGraph orchestrator]
              (validation,                    │  policy/injection check (guardrails)
               telemetry,                      │  RAG retrieval (pgvector)
               response shaping)               │  tool invocation (bounded agent loop)
                                               │  conversation memory (checkpointer)
                                               │  grounded response
                                               ▼
                          [Ollama: local LLM + embeddings]   [pgvector/Postgres: vectors, telemetry, history]
        (all services run as Docker containers on a private network, orchestrated via docker-compose)
```

**Service inventory:**

| Service | Tech | Responsibility |
|---------|------|----------------|
| `dotnet_server` | C# / ASP.NET Core | Edge gateway: receives user HTTP requests, middleware-based telemetry, forwards to orchestrator |
| `langchain_service` | Python / Flask / LangChain / LangGraph | Orchestrates the AI pipeline (guardrails → RAG → tools → memory → response) |
| `ollama` | Ollama | Serves local LLMs and embedding models (e.g., qwen2.5, nomic-embed-text) |
| `pgvector-service` | PostgreSQL + pgvector | Vector store for RAG; relational store for telemetry/history |
| model-provisioning | container job | Ensures required models are pulled before serving |

---

## 4. Technology stack (for skill-tagging)

```yaml
languages: [Python, C#, Bash, SQL]
backend_frameworks: [ASP.NET Core, Flask]
ai_frameworks: [LangChain, LangGraph, Ollama]
ai_concepts: [RAG, embeddings, semantic_search, vector_databases, tool_calling,
              prompt_engineering, structured_output, guardrails, prompt_injection_defense,
              agent_orchestration, evaluation, conversation_memory]
data: [PostgreSQL, pgvector, psycopg, connection_pooling]
infrastructure: [Docker, docker-compose, containers, volumes, healthchecks, service_discovery]
patterns: [microservices, api_gateway, dependency_injection, factory_pattern,
           registry_pattern, mock_seam, idempotent_initialization, stateless_service_external_state]
practices: [observability, structured_logging, telemetry, configuration_management,
            test_seams, separation_of_concerns]
cloud_alignment: [Azure_OpenAI, Azure_AI_Search, AKS, Azure_Container_Apps, Azure_Key_Vault]  # target-stack familiarity, not yet used
```

---

## 5. Skills demonstrated (mapped, honest)

Grouped so a resume agent can select relevant items per job description. Each is backed by concrete work in the repo.

**Backend engineering**
- Designed a multi-service HTTP architecture with an API gateway forwarding to a downstream orchestration service.
- Built ASP.NET Core endpoints with dependency injection, middleware, model validation, and `IHttpClientFactory`-based inter-service calls.
- Designed cross-service JSON request/response contracts (DTOs).

**AI engineering / LLM integration**
- Implemented (in progress) a RAG pipeline: document ingestion, embeddings, pgvector storage, and semantic retrieval.
- Designed an orchestration flow with layered guardrails (policy + prompt-injection checks), tool invocation, and structured-output classification.
- Built a provider/model factory abstraction with a mock-vs-live configuration seam.

**Distributed systems / infrastructure**
- Containerized all services; orchestrated with docker-compose using private networking, named volumes, healthchecks, and service-name discovery.
- Applied stateless-service + external-state design for conversation memory (checkpointer + thread isolation).
- Authored parameterized startup/build scripts (mock vs live, compute-tier flags).

**Databases**
- Provisioned PostgreSQL + pgvector; designed vector and relational schemas; connection pooling; idempotent ingestion.

**Software engineering practice**
- Separation of concerns via a package layout (api / models / orchestration / prompts / rag / tools / memory / telemetry / eval / config).
- Test-seam design for development without heavy compute (deterministic mocks).
- Structured logging and per-node telemetry as a cross-cutting concern.

**Observability (the project's thesis)**
- Middleware- and node-level telemetry capture (latency, tokens, model, decisions), correlation-id propagation across services, designed toward OpenTelemetry/dashboards.

---

## 6. Notable engineering decisions (signal for depth)

- **Mock/live seam via a model factory + env config** — enables full pipeline development on low-compute hardware (an M1 laptop) with a one-flag switch to real inference. Demonstrates test-double / dependency-inversion thinking.
- **LangGraph state-machine orchestration** — modeling the request pipeline as nodes + conditional edges + shared state rather than a monolithic function; supports branching (block on policy violation), a bounded tool loop, and checkpointer-based memory.
- **pgvector over a standalone vector DB** — keeps vectors and relational telemetry in one engine, enabling joins and simpler operations at this scale.
- **Idempotent startup ingestion + healthcheck-gated dependencies** — services wait for readiness, and re-running setup does not duplicate data.
- **Commercial-architecture mirroring** — the edge-gateway/orchestrator/data-plane split intentionally reflects production LLM systems.

---

## 7. Current status (accurate, for honest representation)

```yaml
completed:
  - Multi-container docker-compose environment (dotnet, langchain, ollama, pgvector)
  - Local LLM inference reachable end-to-end (curl -> flask -> ollama) proven in earlier iterations
  - Professional package restructure of the Python service
  - Dependency and configuration groundwork for RAG (pgvector, psycopg, embeddings)
  - Model factory with mock/live seam (in progress)
in_progress:
  - Wiring the orchestration pipeline as a LangGraph state machine
  - RAG retrieval integration into the request flow
  - Conversation memory (checkpointer + thread_id)
  - Telemetry persistence and structured logging
not_started:
  - Evaluation harness (golden dataset + LLM-as-judge in CI)
  - Automated test suite
  - Production/cloud deployment
honest_note: >
  This is a learning project in active development. Its value for a resume is the
  breadth and correctness of the ARCHITECTURE and the range of modern backend + AI
  concepts engaged, rather than a finished, deployed product. Several components are
  scaffolded or partially wired at time of writing.
```

---

## 8. Resume-agent usage hints

- **Best framed as:** a backend/AI-infrastructure project demonstrating microservices, LLM integration (RAG/agents/guardrails), Docker orchestration, and observability — aligned to cloud/AI software-engineering roles.
- **Strongest talking points:** the edge-gateway + orchestrator architecture, the mock/live test seam for constrained-hardware development, pgvector-based RAG, and the observability-first design.
- **Avoid overstating:** do not describe it as production-deployed or fully complete; describe capabilities as designed/implemented/in-progress per section 7.
- **Keywords for matching:** microservices, API gateway, ASP.NET Core, LangChain, LangGraph, RAG, pgvector, PostgreSQL, embeddings, vector database, tool calling, prompt injection, guardrails, Docker, docker-compose, observability, telemetry, dependency injection, Ollama, LLM orchestration.
- **Related detail available:** the project's `Documentation/` folder contains code reviews, concept lectures, skill-gap analyses, and research docs that can supply deeper evidence for any specific skill claim.

*This document is a summary artifact. No project source code is included or modified here.*
