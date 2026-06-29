# AI Suggestions: Fix Your Slow Startup & "Frozen" Ollama Calls

> **How to use this document (per `CLAUDE.md`):** I give you the *what* and the *why* and the *exact shape* of each change as a step-by-step guide — but **I do not change your code.** You implement every step yourself so you learn it. Each fix lists: the problem, the goal, the steps, and how to verify it worked. Snippets are illustrations to type out and adapt, not drop-in patches.

This document turns the diagnosis from the Docker lecture and code review into an ordered action plan. Do them top to bottom; each one makes the next easier to test.

---

## The diagnosis in one picture

```
Your symptom:  "./test_start_up.sh runs, I curl /test, it freezes, I can't tell if it works."

Real causes, in order of impact:
  1. down -v   → deletes the model volume every run → ~1GB re-download each startup
  2. --no-cache→ re-installs all pip deps every run → +30s each startup
  3. bare depends_on → you can curl BEFORE the model finished pulling → request hangs
  4. no timeout → a slow/cold call looks identical to a broken one
  5. M1 Air    → first inference of a 1.5B model is genuinely slow (seconds+), not a bug
```

Fixes 1–4 are yours to make. #5 is hardware reality you just need to *see* (via logs/stats) so you stop wondering.

---

## Fix 1 — Stop deleting your model on every startup (highest impact)

**Problem.** `test_start_up.sh` runs `docker compose down -v`. The `-v` deletes the `ollama_data` volume where the LLM is cached, forcing a full re-download every run.

**Goal.** Keep the model between runs; only wipe it when *you* deliberately choose to.

**Steps.**
1. Open `test_start_up.sh`. Find the teardown line:
   ```bash
   docker compose -p "$PROJECT" down -v --remove-orphans
   ```
2. Remove the `-v` so it becomes:
   ```bash
   docker compose -p "$PROJECT" down --remove-orphans
   ```
3. (Optional, recommended) Create a *separate* script for the rare "nuke everything" case so the destructive command is explicit and never the default. Make a new file `clean_slate.sh`:
   ```bash
   #!/usr/bin/env bash
   set -euo pipefail
   PROJECT="llm_monitor"
   echo "WARNING: this deletes the downloaded model volume. Re-download will be required."
   docker compose -p "$PROJECT" down -v --remove-orphans
   ```
   Then `chmod +x clean_slate.sh`.

**Verify.**
- Run `./test_start_up.sh` once (model downloads), then run it again.
- On the **second** run, `docker logs ollama_pull_model` should show the model already present / pull completing near-instantly instead of a full download.
- Time both runs; the second should be dramatically faster.

---

## Fix 2 — Re-enable the build cache

**Problem.** `build --no-cache langchain_service` re-runs `pip install` (~30s) every startup.

**Goal.** Only rebuild what changed; skip `pip install` when `requirements.txt` is unchanged.

**Steps.**
1. In `test_start_up.sh`, find:
   ```bash
   docker compose -p "$PROJECT" build --no-cache langchain_service
   ```
2. Remove `--no-cache`:
   ```bash
   docker compose -p "$PROJECT" build langchain_service
   ```
3. Keep `--no-cache` in your mental toolbox only for when you suspect a *stale* dependency layer — run it by hand that one time, not in the script.

**Verify.**
- Edit a comment in `main.py` (a code-only change), then run the script.
- In the build output you should see the `pip install` layer reported as `CACHED` and only the `COPY . .` layer rebuild. Startup is seconds, not 30s+.

---

## Fix 3 — Make services wait for *readiness*, not just *start* (kills the "freeze")

**Problem.** Bare `depends_on` lets your chat request arrive before Ollama is ready and before the model finished pulling. The request then hangs with no signal.

**Goal.** (a) Ollama is marked "healthy" only when its API answers; (b) the model-pull job must *complete* before chat traffic is allowed.

**Steps.**

**3a. Add a healthcheck to the `ollama` service.** The ollama image lacks `curl`, so use its own CLI as the probe. In `docker-compose.yaml`, under the `ollama` service, add:
```yaml
  ollama:
    image: ollama/ollama:latest
    container_name: ollama_service
    ports:
      - "11434:11434"
    volumes:
      - ollama_data:/root/.ollama
    healthcheck:
      test: ["CMD", "ollama", "list"]    # succeeds only when the API is up
      interval: 5s
      timeout: 5s
      retries: 10
      start_period: 30s                  # grace period while it boots
```
- `start_period` is key: during it, failures don't count against `retries` — it gives Ollama time to come up before health is judged.

**3b. Make the puller wait for ollama to be *healthy* (not just started):**
```yaml
  ollama-pull-model:
    image: curlimages/curl:latest
    container_name: ollama_pull_model
    depends_on:
      ollama:
        condition: service_healthy
    entrypoint: ["sh","-c","curl -X POST http://ollama:11434/api/pull -d '{\"name\": \"qwen2.5:1.5b\"}'"]
```
- Because it now waits for health, you can *optionally* simplify the old `until curl ... sleep 1` loop (your hand-rolled wait) — though leaving it does no harm.

**3c. Make `langchain_service` wait for the pull to *finish*:**
```yaml
  langchain_service:
    # ...build, ports, environment as before...
    depends_on:
      ollama:
        condition: service_healthy
      ollama-pull-model:
        condition: service_completed_successfully
```
- `service_completed_successfully` means "wait until that one-shot job exits with code 0." Now Flask won't accept traffic until the model is actually present.

**Verify.**
- `docker compose -p llm_monitor up -d` then `docker compose -p llm_monitor ps`.
- `langchain_service` should only reach "running" *after* `ollama_pull_model` shows "exited (0)" and `ollama_service` shows "healthy."
- Now your `curl` to `/test` cannot arrive before the model exists — so a hang means "slow inference," not "model missing."

---

## Fix 4 — Add a timeout so "slow" and "broken" look different

**Problem.** With no timeout, a cold/slow LLM call is indistinguishable from a hung one.

**Goal.** Bound the wait; get a clear, fast error instead of an infinite hang.

**Steps (conceptual — you write it).**
1. In `lang_practice.py`'s `TestingMethod`, the `ChatOllama` client accepts timeout configuration. Add a request timeout (e.g., 120s for an M1 cold start) when constructing the model, so a stuck call eventually raises instead of blocking forever.
2. In `main.py`'s `/test` handler, you already wrap the call in `try/except` and return a 500 with the message — good. Make sure a timeout exception is caught there and returns a clear JSON error.
3. (Later, on the .NET side) when `LlmController` calls Flask, set `HttpClient.Timeout` and catch `TaskCanceledException` to return a 504/502.

**Verify.**
- Temporarily set a *very* short timeout (e.g., 2s), curl `/test`, and confirm you get a clean JSON error quickly rather than a hang. Then restore a sane value.

---

## Fix 5 — Learn to *watch* it work (so you stop guessing)

**Problem.** You can't tell if it's working. **Goal.** A repeatable "is it alive, ready, and thinking?" check.

**Steps — run these in order whenever you test:**
1. `docker compose -p llm_monitor ps` → are `langchain_service` and `ollama_service` "running" (and healthy)?
2. `docker logs ollama_pull_model` → do you see `{"status":"success"}`? If not, the model isn't ready yet — wait.
3. Open two terminals:
   - Terminal A: `docker stats` (watch CPU/RAM).
   - Terminal B: `curl -X POST http://localhost:5001/test -H "Content-Type: application/json" -d '{"userId":"dev_123","chatMessage":"Write a haiku about computers."}'`
4. Watch Terminal A: if `ollama_service` CPU spikes, **it's working — just computing.** When generation finishes, the curl returns.
5. If something errored, `docker compose -p llm_monitor logs -f langchain_service` shows the Python exception.

**Verify.** You can now state, at any moment, which of these is true: not-up / up-but-not-ready / working-but-slow / errored. That *is* troubleshooting.

---

## Fix 6 — Smaller hygiene wins (quick, do when convenient)

1. **dotnet port:** in `docker-compose.yaml`, change `dotnet_server` ports to `"5000:8080"` (matches `EXPOSE 8080`). Verify later with `curl localhost:5000/api/Test` once the server's in the stack.
2. **Add `.dockerignore`** to `server/` and `langchain_service/` listing at least:
   ```
   .env
   .git
   __pycache__/
   bin/
   obj/
   *.md
   ```
   Verify: rebuild and confirm image size drops / `.env` isn't inside (`docker run --rm <image> ls -a`).
3. **Pin Python deps** in `requirements.txt` (e.g., `flask==3.1.*`). Verify: a fresh `--no-cache` build resolves the same versions.
4. **Fix the int-as-env-var bug** in `lang_practice.py` `OpenAiInvokation` (`os.environ[...] = 7` → must be a string, and really should read from the environment). Verify: the function no longer raises `TypeError` if called.

---

## Suggested order & a "definition of done"

```
Day 1:  Fix 1 (remove -v)  →  Fix 2 (remove --no-cache)  →  re-run, feel the speedup
Day 1:  Fix 5 (logging/stats habit)  →  now you can SEE state
Day 2:  Fix 3 (healthchecks + completion dependency)  →  the freeze is gone
Day 2:  Fix 4 (timeout)  →  failures become legible
Later:  Fix 6 hygiene items as you touch each file
```

**Done = ** you run `./test_start_up.sh`, the second run is fast (model cached), `ps` shows langchain starting only after the puller exits 0, and a `/test` curl either returns a haiku in a reasonable time or a clear JSON error — and you can narrate, from logs alone, exactly what the system is doing at each step.

---

## Why these and not a rewrite

Every fix above is small and surgical because your architecture doesn't need rebuilding — it needs *tuning*. You built a correct four-service topology with a persistence volume and service discovery; the only reasons it feels broken are two over-aggressive script flags and missing readiness gating. Fixing those converts the system from "mysterious and slow" to "fast and observable," which is exactly the platform you need before adding Postgres/pgvector and the RAG pipeline. Implement them yourself, verify each with the checks given, and you'll also be closing the Docker skill gap in the most durable way: by doing it.

*No source files were modified. This document only describes changes for you to implement.*
