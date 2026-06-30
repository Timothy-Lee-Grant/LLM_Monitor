# AI Suggestions: Developing & Testing on Low Compute — Mocks, Seams, and Config-Driven Environments

> **How to use this document (per `CLAUDE.md`):** I give you the assessment, the design, and step-by-step instructions with illustrative code — but **I do not change your code.** You implement each step yourself so you learn it. Snippets are patterns to adapt, not drop-in patches.

This is one of the most professionally valuable problems you could be solving, because the technique that fixes "I can't run the LLM locally" is the *same* technique that makes a codebase testable, fast, and CI-friendly at any company. You're not working around weak hardware — you're learning **test seams, dependency inversion, and environment configuration**, which are core senior-engineer skills.

---

## 1. Assessment — what you're really asking for

You described three goals; here's how a professional frames each:

| Your words | The professional name | What it unlocks |
|------------|----------------------|-----------------|
| "trust the LLM will give what I expect while developing" | **Test doubles / mocking at a seam** | build & test your *logic* (graph, RAG flow, injection-judge) deterministically, with zero inference |
| "easily switch to actual live LLM calls" | **Dependency inversion + configuration** | one flag flips mock ↔ live; no code change |
| "startup scripts pass params for different hardware" | **Environment configuration (profiles/overrides)** | dev-on-laptop, burst-to-good-hardware, prod — same code, different config |

The unifying principle, and the one sentence to remember:

> **Put a seam (an interface) in front of every expensive/external thing — the LLM, the embeddings, the vector DB — so you can swap a fast deterministic fake for the real thing by configuration, not by editing code.**

Once that seam exists, "low compute" stops being a blocker: you develop against fakes 95% of the time (instant, free, deterministic), and flip to real models only for the occasional live test or eval.

Your project already has the seeds of this: `FakeListChatModel` in `lang.py` *is* a fake LLM, and `OLLAMA_BASE_URL` is already config. This document is about doing that deliberately and everywhere.

---

## 2. The core design — a swappable "model provider" seam

### 2a. The principle (dependency inversion)
Today your code calls `ChatOllama(...)` directly inside functions. That **hardcodes** the real, expensive dependency. The fix: code against an *abstraction* ("give me a chat model") and let a **factory** decide — based on config — whether to hand back a real client or a fake.

```
   your logic (graph, RAG, judge)
          │  asks for "a model"
          ▼
   get_chat_model()  ──reads LLM_MODE──▶  "mock" → FakeChatModel
                                          "live" → ChatOllama / ChatOpenAI
```
Your logic never knows or cares which it got. That indifference *is* the seam.

### 2b. Python implementation (your LangChain service)
Create a small factory module (you write it; shape shown):
```python
# app/models/factory.py
import os
from langchain_core.language_models import FakeListChatModel

def get_chat_model(scenario: str = "default"):
    mode = os.getenv("LLM_MODE", "mock")           # default to mock = safe/cheap
    if mode == "live":
        from langchain_ollama import ChatOllama
        return ChatOllama(model=os.getenv("LLM_MODEL", "qwen2.5:1.5b"),
                          base_url=os.getenv("OLLAMA_BASE_URL"), temperature=0)
    # mock: deterministic, instant, no inference
    return FakeListChatModel(responses=_canned_for(scenario))
```
Now everywhere you currently write `ChatOllama(...)`, call `get_chat_model()` instead. Flip the whole system with one env var: `LLM_MODE=mock` (dev) or `LLM_MODE=live` (real test). Same for embeddings (`FakeEmbeddings` ↔ `OllamaEmbeddings`) and the retriever.

> This also fixes a real bug from your code review: it centralizes model creation in one place (the singleton/`Init()` concern), instead of scattering `ChatOllama` constructions across functions.

### 2c. C# implementation (your .NET server)
Same idea, idiomatic to .NET — an interface + DI registration chosen by config:
```csharp
public interface ILlmGateway { Task<string> AskAsync(string prompt); }

public class LiveLlmGateway : ILlmGateway { /* calls Flask via HttpClient */ }
public class MockLlmGateway : ILlmGateway {                     // instant, deterministic
    public Task<string> AskAsync(string p) => Task.FromResult("[mock] canned answer");
}
```
```csharp
// Program.cs — pick implementation by config
if (builder.Configuration["LLM_MODE"] == "live")
    builder.Services.AddScoped<ILlmGateway, LiveLlmGateway>();
else
    builder.Services.AddScoped<ILlmGateway, MockLlmGateway>();
```
Your controller depends on `ILlmGateway` (the abstraction), never on the concrete class. This is exactly the DI lesson from your earlier lectures, now used to make the system testable. (It also lets you test the .NET edge without Flask or Ollama even running.)

---

## 3. Make the fakes *smart* — scenario-based, structure-matching doubles

A dumb fake that always returns the same string only tests the happy path. To develop your injection-judge or LangGraph branching, the fake must return **the shape your code branches on**, and **different shapes for different inputs.**

### 3a. Match the contract, especially for structured output
If your policy/injection check uses `with_structured_output(PolicyResult)`, the fake must return a `PolicyResult`, not a string. Build a fake that returns canned *objects*:
```python
class FakePolicyJudge:
    def invoke(self, msg):
        violated = "bomb" in msg.lower() or "ignore previous" in msg.lower()
        return PolicyResult(violated=violated, reason="mock rule")
```
Now you can develop and unit-test your LangGraph conditional edge ("if violated → END") **deterministically**: feed "how to build a bomb" → expect blocked; feed "hello" → expect allowed. No LLM, instant, repeatable. This is precisely your "trust the LLM gives what I expect" — except you *control* what it gives, so your tests are reliable.

### 3b. Scenario fakes for the agent/tool loop
For tool-calling, a fake model can return a scripted sequence of `tool_calls` then a final answer, so you can test the loop's mechanics (does it execute the tool? loop? stop?) without a real model deciding. Drive it by a `scenario` argument.

> **Test taxonomy (worth knowing the words):** a **stub** returns canned data; a **mock** also asserts it was called correctly; a **fake** is a working lightweight implementation (e.g., `FakeListChatModel`, or an in-memory vector store). You'll mostly use fakes and stubs.

---

## 4. Configuration-driven startup — one system, many modes

Now wire the seam to your startup so you flip modes without editing code. Three layers, from simplest to most powerful.

### 4a. Environment variables + `.env` files (the values)
Keep one `.env` per mode (all gitignored):
```
# .env.mock
LLM_MODE=mock
# .env.live
LLM_MODE=live
LLM_MODEL=qwen2.5:1.5b
OLLAMA_BASE_URL=http://ollama:11434
```
Your factory (§2) reads these. This alone gives you mock↔live with no code change.

### 4b. Docker Compose **profiles** (which containers even start)
This is the big compute win. In mock mode you should **not start Ollama or the model-puller at all** — they're the heavy ones. Compose *profiles* let you tag services so they only start when requested:
```yaml
  ollama:
    image: ollama/ollama:latest
    profiles: ["live"]          # only starts when the 'live' profile is active
  ollama-pull-model:
    profiles: ["live"]
  langchain_service:
    # no profile = always starts
    environment:
      - LLM_MODE=${LLM_MODE:-mock}
```
Then:
- `docker compose up` → mock mode, **no Ollama**, near-instant, tiny RAM.
- `docker compose --profile live up` → brings up Ollama + puller for real runs.

### 4c. Compose **override files** (bigger structural differences)
For hardware-specific differences (e.g., GPU flags, a bigger model, mounting a different volume), use override files that layer on top of the base:
```
docker-compose.yaml          # base (mock-friendly defaults)
docker-compose.live.yml      # adds ollama wiring, live env
docker-compose.gpu.yml       # adds GPU reservations for good hardware
```
```bash
# laptop / mock:
docker compose up
# real, on decent hardware with GPU:
docker compose -f docker-compose.yaml -f docker-compose.live.yml -f docker-compose.gpu.yml up
```
Docker merges them left-to-right. This is the professional way to express "same system, different environment."

### 4d. A startup script that takes parameters (the friendly front door)
Wrap all of the above in one script so you don't memorize flags. Shape (you write it):
```bash
#!/usr/bin/env bash
# start.sh --mode mock|live  [--gpu]  [--model qwen2.5:1.5b]
set -euo pipefail
MODE="mock"; GPU=""; MODEL="${LLM_MODEL:-qwen2.5:1.5b}"
while [[ $# -gt 0 ]]; do case "$1" in
  --mode) MODE="$2"; shift 2;;
  --gpu)  GPU="-f docker-compose.gpu.yml"; shift;;
  --model) MODEL="$2"; shift 2;;
  *) echo "unknown arg $1"; exit 1;;
esac; done

export LLM_MODE="$MODE" LLM_MODEL="$MODEL"
if [[ "$MODE" == "live" ]]; then
  docker compose --profile live -f docker-compose.yaml -f docker-compose.live.yml $GPU up -d --build
else
  docker compose -f docker-compose.yaml up -d --build      # mock: light, no ollama
fi
echo "Started in $MODE mode (model=$MODEL)."
```
Now your daily driver is `./start.sh --mode mock` (instant), and when you borrow good hardware it's `./start.sh --mode live --gpu`. Exactly the parameterized startup you wanted.

> **Argument parsing note:** that `while/case` loop is also good, low-stakes practice for the string/parsing fluency your skill-gap docs flagged — a nice place to build that muscle.

---

## 5. The testing strategy — a pyramid tuned for no-compute development

Organize tests in layers; run the cheap ones constantly, the expensive ones rarely. This is how pros keep a fast feedback loop.

```
        ▲  fewer, slower, real LLM
        │   ┌─────────────────────────────┐
        │   │ EVAL / LIVE (real models)    │  run manually / nightly / on good HW
        │   ├─────────────────────────────┤
        │   │ END-TO-END (containers up)   │  mock LLM, real HTTP between services
        │   ├─────────────────────────────┤
        │   │ INTEGRATION / CONTRACT       │  .NET↔Flask shape; mock LLM
        │   ├─────────────────────────────┤
        │   │ UNIT (everything mocked)     │  milliseconds, run on every save
        ▼   └─────────────────────────────┘
           more, faster, no compute
```

### 5a. Unit tests (the bulk — no compute, run constantly)
With the seam in place, test your *logic* against fakes: the LangGraph routing, the tool-dispatch dict, the RAG prompt assembly, the response shaping. **Python:** `pytest` + the fake factory (or `monkeypatch` to force `LLM_MODE=mock`). **C#:** `xUnit` + the `MockLlmGateway`. These run in milliseconds and need zero models.

### 5b. Contract tests (the .NET↔Flask boundary)
Your two services agree on a JSON shape. Test that the .NET side sends `{userId, chatMessage}` and parses `{llmMessageResponse}` correctly — **without running Flask** — by mocking the HTTP boundary:
- **C#:** inject a fake `HttpMessageHandler` (or use **WireMock.Net**) that returns a canned Flask response; assert your controller handles it. This is how you'd have caught the contract-mismatch bugs from earlier reviews automatically.
- **Python:** test the Flask route with Flask's test client and a mocked `get_chat_model()`.

### 5c. End-to-end tests (containers up, but LLM mocked)
Bring the stack up in **mock mode** (no Ollama) and curl a real request through .NET → Flask → mock model → back. This proves the *wiring* (networking, serialization, routing) end to end, fast, on your laptop. **C#:** `WebApplicationFactory` spins your API in-memory for this.

### 5d. Eval / live tests (real models — rare, gated)
Only these need real inference. Run them **manually or on a schedule**, ideally when you have good hardware, against your golden dataset (the eval harness from prior docs). They answer "is the *model's* output actually good?" — a different question from "is my *code* correct?" Keep them out of the fast loop.

> **The key separation:** layers 5a–5c test *your code* (deterministic, no compute). Layer 5d tests *the model* (probabilistic, needs compute). Most bugs are in your code, so most testing needs no LLM at all. That realization is what frees you from the hardware constraint.

---

## 6. Cutting the compute you *do* use

For the times you run live, shrink the cost:

1. **Tiny models for dev** — `qwen2.5:0.5b` or `qwen2.5:1.5b` for development; reserve bigger models for eval runs on good hardware. Model name is just an env var (§4a), so switching is trivial.
2. **LLM response caching** — LangChain supports a cache (SQLite or Redis): identical calls during dev return instantly instead of re-running inference. Enable it once; repeated dev iterations stop paying the inference cost twice.
3. **Record / replay (cassettes)** — capture real responses *once* (when on good hardware) and replay them in tests forever. Tools: `vcrpy` (Python) records HTTP interactions to a file; replay needs no model. This gives "realistic" responses in tests without live calls.
4. **Don't start Ollama in mock mode** — the compose profile (§4b) is the single biggest win: your laptop never loads a model when you're developing logic.
5. **Batch eval runs** — when you do go live, run the whole golden set in one session rather than ad-hoc one-offs.

---

## 7. Bursting to better hardware (when you get access)

Because everything is config (§4), "move to better hardware" is just a different launch:
- **Same machine, bigger model:** `./start.sh --mode live --model qwen2.5:7b` (and `--gpu` if available).
- **Remote Ollama:** run Ollama on the powerful machine and point your laptop's service at it — set `OLLAMA_BASE_URL=http://<that-host>:11434`. Your laptop runs only the light containers; inference happens remotely. (Secure the port / use a tunnel.)
- **Hosted API for a session:** flip the factory to a cloud provider — `LLM_MODE=live` + `LLM_PROVIDER=azure_openai` + a key from your gitignored env/Key Vault. Same code, a different `get_chat_model` branch. This is also your eventual production path (Azure OpenAI).
- **Cloud dev box:** spin up a GPU VM, `git clone`, `./start.sh --mode live --gpu`, develop there for the session, push, tear down. Nothing in your code changes.

The point: you design once for *configurability*, and every hardware scenario becomes a launch flag.

---

## 8. Organizing the project & workflow like a pro

- **Restructure toward the production layout** (from the commercial lecture): `models/` (the factory), `graph/`, `tools/`, `rag/`, `eval/`, `config/`. The factory seam belongs in `models/`.
- **A task runner** (a `Makefile` or simple scripts) for muscle memory:
  ```
  make test         # unit + contract (mock, fast, no compute)
  make up-mock      # ./start.sh --mode mock
  make up-live      # ./start.sh --mode live
  make eval         # run golden-set evals (needs live)
  ```
- **CI strategy:** on every push, CI runs **mock-mode unit + contract + e2e tests** (fast, no GPU, free) — this is the gate. **Live evals** run on a schedule or manual trigger (they need compute and cost money). This mirrors exactly how commercial teams keep CI fast while still validating model quality periodically.
- **Branch/feature flow:** build one capability at a time behind the seam (e.g., the injection-judge) with mock-mode tests proving the *logic*, then validate with one live run. Commit the green mock tests as your safety net before moving on.

---

## 9. Step-by-step implementation roadmap

Do these in order; each is independently verifiable.

**Phase 1 — the seam (highest leverage):**
1. Create `get_chat_model()` factory in Python reading `LLM_MODE`. Replace every direct `ChatOllama(...)` with it. *Verify:* `LLM_MODE=mock` runs your endpoints instantly with canned output; `LLM_MODE=live` still calls Ollama.
2. Do the same for embeddings and the retriever (fake vs real).
3. Add `ILlmGateway` + Mock/Live implementations in C#, chosen by config in `Program.cs`. *Verify:* the .NET API answers in mock mode with Ollama/Flask down.

**Phase 2 — config-driven startup:**
4. Add `.env.mock` / `.env.live` (gitignored). *Verify:* switching files flips behavior.
5. Add `profiles: ["live"]` to `ollama` + puller in compose. *Verify:* `docker compose up` starts WITHOUT Ollama; `--profile live up` includes it.
6. Write `start.sh` with `--mode/--gpu/--model` flags. *Verify:* `./start.sh --mode mock` is fast and light.

**Phase 3 — tests:**
7. Add `pytest` unit tests for your LangGraph routing and tool dispatch using smart fakes (§3). *Verify:* they pass in milliseconds, no model.
8. Add a contract test for the .NET↔Flask shape (WireMock/fake handler). *Verify:* it catches a deliberately broken DTO.
9. Add one mock-mode e2e test (stack up, curl through). *Verify:* green on your laptop.

**Phase 4 — compute reduction & burst:**
10. Enable LangChain LLM caching for dev. *Verify:* a repeated live call returns instantly the second time.
11. Document the burst commands (remote `OLLAMA_BASE_URL`, `--gpu`, hosted API). *Verify:* one live eval run when you next get hardware.

**Phase 5 — workflow:**
12. Add a `Makefile`; wire CI to run mock-mode tests on push. *Verify:* CI is green and fast without any GPU.

---

## 10. Definition of done

You're "done" with this when:
- `./start.sh --mode mock` brings up a working system **with no model loaded**, and you can develop the LangGraph/injection-judge/RAG *logic* end to end against deterministic fakes.
- Flipping `--mode live` (or pointing at remote/better hardware) runs the *same code* against real models with **zero source changes**.
- A fast test suite (no compute) runs on every save and in CI, and catches contract/logic regressions.
- A separate, gated eval suite runs real models only when you choose.

When that's true, weak hardware is no longer a development constraint — it only limits how often you do *live* runs, which are the small minority of what development actually needs.

---

## 11. Why this is the professional approach (and a career signal)

Everything above — seams/dependency inversion, test doubles, the test pyramid, config-driven environments, fast CI with gated expensive tests — is **standard senior-engineer practice**, not a hack for weak hardware. Commercial LLM teams mock the model in unit/integration tests for exactly your reasons (speed, determinism, cost) and reserve live calls for evals. So by solving your hardware problem the right way, you're building the precise skills (testability, DI, environment config, CI design) that interviews and real teams care about. The constraint is doing you a favor: it's forcing you to learn the discipline that separates a script from a system.

*No source files were modified. This document only describes changes for you to implement.*
