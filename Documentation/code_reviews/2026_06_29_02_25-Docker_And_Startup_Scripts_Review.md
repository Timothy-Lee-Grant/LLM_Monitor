# Code Review — Docker Topology, Startup Scripts & the Ollama Integration

| | |
|---|---|
| **Date** | 29-06-2026 (02:25) |
| **Reviewer** | Senior Engineer (review pass) |
| **Scope** | `docker-compose.yaml`, `test_start_up.sh`, `build.sh`, `server/dockerfile`, `langchain_service/dockerfile`, `langchain_service/main.py`, `lang_practice.py`, `.env` handling, `README.md` |
| **Verdict** | 🟡 **Approve with required changes** — the multi-container architecture is genuinely good and it *runs*; but the startup script actively fights your own caching (re-downloads the model every run), startup ordering is race-prone, and there are a few latent code defects. |

---

## 1. Summary

This is a big step up in ambition: you now orchestrate four services (dotnet, Flask/LangChain, Ollama, and a one-shot model-puller) with a real volume, a private network, and environment-based service discovery. The fact that you got Ollama pulling a model and a Flask service standing up on an M1 Air is a real accomplishment, and a couple of your choices are genuinely clever (the separate `curlimages/curl` puller that hand-rolls a readiness wait is a neat workaround for Ollama's missing-`curl` problem).

The issues are concentrated in **operational efficiency and startup correctness**, not architecture. Your `test_start_up.sh` does two expensive things on every run — wipes the model volume (`down -v`) and disables the build cache (`--no-cache`) — which together explain the painful, minutes-long startups you're experiencing on weak hardware. Startup ordering relies on bare `depends_on`, which only waits for containers to *start*, not to be *ready* — the root of your "I curl it and it freezes" symptom. And there are a handful of code-level defects (mostly in unused practice functions, plus the lingering dotnet port mismatch).

None of this is a redesign. It's tuning an already-sound system. The companion **AI_Suggestions** document gives step-by-step fixes; this review enumerates and prioritizes the findings.

**Severity:** 🔴 Blocking-for-usability · 🟠 Major · 🟡 Minor · 🟢 Nit · ✅ Positive

---

## 2. Operational correctness (the issues you're actually feeling)

### 🔴 O1 — `test_start_up.sh` deletes the model volume on every run
**File:** `test_start_up.sh`
```bash
docker compose -p "$PROJECT" down -v --remove-orphans
```
`-v` removes named volumes, including `ollama_data` — the *only* place `qwen2.5:1.5b` is cached. Every startup therefore re-downloads ~1 GB and re-loads the model. On an M1 Air this is the dominant cost and the main reason startups feel broken/frozen. The `ollama_data` volume exists precisely to prevent this.
**Direction:** use plain `down` for normal runs; reserve `-v` for a deliberate, separate "clean everything" script.

### 🟠 O2 — `--no-cache` on every build re-installs all Python deps each run
**File:** `test_start_up.sh`
```bash
docker compose -p "$PROJECT" build --no-cache langchain_service
```
This discards the build cache, so the ~30-second `pip install` (flask, langchain, numpy, …) you watched scroll by runs *every* startup, even when only `main.py` changed. `--no-cache` is a debugging tool, not a default.
**Direction:** drop `--no-cache`; let layer caching skip `pip install` when `requirements.txt` is unchanged. Your Dockerfile's layer order already supports this.

### 🟠 O3 — Startup ordering is a readiness race
**File:** `docker-compose.yaml`
```yaml
langchain_service:
  depends_on: [ollama]            # waits for container start, not readiness
ollama-pull-model:
  depends_on: [ollama]
```
Bare `depends_on` only guarantees the ollama *container* has started, not that its API is listening or that the model is pulled. So a chat request can arrive before the model exists → it hangs or errors, with no signal to you. **This is the mechanism behind your "freeze."** Nothing makes `langchain_service` wait for `ollama-pull-model` to *finish*.
**Direction:** add a `healthcheck` to ollama and use `depends_on: { ollama: { condition: service_healthy } }`; make `langchain_service` wait for the puller via `condition: service_completed_successfully`. (Details in AI_Suggestions.)

### 🟡 O4 — No request timeout anywhere in the chain
A slow/cold LLM call has no timeout in Flask or the (future) .NET caller, so a hung dependency looks identical to a slow one. Adding a timeout converts "frozen forever" into a clear, fast failure you can act on.

---

## 3. Configuration & Dockerfile findings

### 🟠 C1 — dotnet port mapping still mismatched
**File:** `docker-compose.yaml`
```yaml
dotnet_server:
  ports: ["5000:80"]     # container listens on 8080 (EXPOSE 8080)
```
Carried over from the last review and still wrong; host 5000 → container 80 hits nothing (the app is on 8080). Not exercised by `test_start_up.sh` (dotnet isn't in its `SERVICES` list), but it'll block you the moment you bring the server into the stack.
**Direction:** `"5000:8080"`.

### 🟡 C2 — EOL base image for the Flask service
**File:** `langchain_service/dockerfile` → `FROM python:3.9.13-slim-buster`. Debian Buster is end-of-life and Python 3.9 is near EOL; unpatched OS packages and shrinking wheel compatibility. Move toward `python:3.12-slim-bookworm` eventually.

### 🟡 C3 — `debug=True` in the containerized Flask app
**File:** `main.py` → `app.run(..., debug=True)`. Fine for local learning, but it's the dev server + auto-reloader (slow, and an RCE vector). Flag it now so it doesn't ship later; production would use gunicorn.

### 🟢 C4 — Unpinned Python dependencies
`requirements.txt` lists `flask`, `langchain-core`, etc. with no versions → non-reproducible builds (a future `pip install` may pull a breaking major). Pin them (`flask==3.*`) when you stabilize.

### 🟢 C5 — `build.sh` and `test_start_up.sh` have diverged
You now have two startup scripts with different semantics (`build.sh` keeps volumes + cache; `test_start_up.sh` destroys both). That's fine intentionally, but document the difference at the top of each so future-you knows which to run. `build.sh` still carries open-question comments ("what is a pipeline fail?") — answered in the prior concepts doc.

---

## 4. Code defects (mostly in `lang_practice.py`)

These are in practice/experimental code and won't all run today, but they're real bugs worth catching:

- 🟠 **D1 — `os.environ["OPENAI_API_KEY"] = 7`** (`OpenAiInvokation`): environment variables must be **strings**; assigning an `int` raises `TypeError`. Also the value `7` is a placeholder, not a key. (And keys should come from the environment/secret store, never a literal.)
- 🟡 **D2 — `ChatPromptTemplate.from_message(...)`** (`OpenAiInvokation`): the method is `from_messages` (plural). Will raise `AttributeError`.
- 🟡 **D3 — `model="gpt-40-mini"`**: typo for `gpt-4o-mini` (letter o, not zero).
- 🟡 **D4 — `OllamaInvokation()` builds a model but never invokes it** and ignores `OLLAMA_BASE_URL` (hardcodes localhost) — dead/inconsistent vs. the working `TestingMethod`, which does it right.
- 🟢 **D5 — `invoke_langchain` in `lang.py` still returns `model.response`** (nonexistent attribute) instead of `response.content`. The mock path is unused now that `/test` calls `TestingMethod`, but it's still a latent bug if `/api/chat` is hit.
- 🟢 **D6 — `Init()` in `lang.py`** is an empty stub returning `None`; fine as a placeholder, but note the provider-selection logic it sketches will need real wiring.

> Positive within this: **`TestingMethod` is correct** — it reads `OLLAMA_BASE_URL` from env, builds an LCEL chain (`prompt | model | StrOutputParser()`), and invokes it. That's the right LangChain pattern, and it's the path `/test` actually uses. Good.

---

## 5. Security / hygiene

- ✅ **`.env` files are gitignored** (`.env`, `.env.*` in `.gitignore`) — good; secrets aren't committed.
- 🟡 **S1 — two `.env` files with placeholder/test keys** (`MyKeyWord`, `MyTestKeyWordTimothy`). Harmless now, but establish the discipline: real keys only ever in gitignored env files or a secret manager (Azure Key Vault later), injected at runtime, never baked into an image layer.
- 🟢 **S2 — No `.dockerignore`** in either service. Without one, `COPY . .` can ship `.env`, `.git`, `__pycache__`, and `bin/obj` into the image — bloat and potential secret leakage. Add one per service.

---

## 6. What's good (✅)

- ✅ **Real multi-service orchestration** — four services, a named volume, a private network, env-based service discovery (`OLLAMA_BASE_URL=http://ollama:11434`). This is a legitimate distributed-system topology.
- ✅ **The model-puller pattern** — a separate one-shot `curlimages/curl` container that **waits** (`until curl ... do sleep 1`) before pulling. You hand-rolled a readiness check, neatly sidestepping the well-known "ollama image has no curl" healthcheck problem.
- ✅ **Correct use of a volume for model persistence** — `ollama_data:/root/.ollama` is exactly right; the only problem is the script wiping it (O1), not the design.
- ✅ **Service-name networking** done correctly (container port 11434, not a host port).
- ✅ **`LangChain LCEL` chain in `TestingMethod`** is idiomatic and correct.
- ✅ **Self-documenting comments** in the scripts and `ConceptsINeedToReview.md` — you're tracking your own unknowns precisely, which is what makes this reviewable and teachable.

---

## 7. Required actions

**For usability (do first):**
- [ ] O1 — stop wiping `ollama_data`; plain `down` for normal runs
- [ ] O3 — healthcheck on ollama + `service_healthy` / `service_completed_successfully` dependencies

**Major:**
- [ ] O2 — remove `--no-cache` from the default startup
- [ ] O4 — add a request timeout on the LLM call
- [ ] C1 — fix dotnet port to `5000:8080`
- [ ] D1 — don't assign an int to an env var; source keys from env

**Recommended:** C2 base image, C3 debug flag, C4 pin deps, S2 `.dockerignore`, D2–D5 practice-code fixes.

---

## 8. Reviewer's note

The encouraging read: nothing here is an architecture problem. Your topology is sound and even shows real instinct (the readiness-waiting puller). What's hurting you is two flags in one script fighting the caching that the rest of your design set up correctly — so the *system* looks broken when it's mostly just re-doing expensive work every run and being tested before it's ready. Fix O1 and O3 and your startup goes from "minutes and a freeze" to "seconds and a working endpoint," at which point you can actually iterate. Read the Docker lecture for the mental model, then implement the AI_Suggestions steps. Strong, ambitious iteration.

*No source files were modified as part of this review.*
