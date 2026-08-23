2026_08_23_14_03-Post_Break_Catchup_And_MCP_Dependency_Drift

# Catching Back Up After the Break, and a Dependency Drift Bug Found on First Boot

You've been away from `LLM_Monitor` for about a month (last commit `228a498`, "lecture doc", 2026-07-26; today is 2026-08-23). This doc does two things: (1) a fast re-orientation to where the project stands, and (2) a writeup of a real bug I hit trying to boot the stack for the first time since your break, with step-by-step instructions to fix it yourself.

## 1. Where the project stands

You don't need to re-read the whole repo to get back up to speed — three documents already carry the context, in order of how much detail you want:

| Doc | What it gives you |
|---|---|
| `README.md` | Architecture diagram, how to run it, how to talk to it |
| `persona.md` | Your own living profile — goals, skills demonstrated, strategic direction |
| `Documentation/Project_Captures/001-Project_State_Captures.md` (Capture 001, 2026-07-24) | The deepest snapshot: full architecture, engineering decisions worth citing in interviews, debugging war stories, honest "what's done vs. not started" |

**One-paragraph recap:** a C#/.NET gateway (telemetry middleware → YARP) fronts a Python/Flask service that owns a **pipeline registry** of 7 chat/RAG/agentic pipelines, running against Azure OpenAI (or Groq via `openai_compat`, or local Ollama) with pgvector for RAG and an MCP toolbox (a separate repo, `Tool_Box`) for agentic tool-calling — including a live-updating voxel-world viewer. Full four-pillar observability (logs/traces/metrics/Langfuse) and a CI-gated eval harness exist behind the `--obs` flag. Two-phase build process: hand-written scaffolding, then AI-collaborative development through staged, reviewed implementation plans (`Documentation/AI_Implementation_Plans/`).

**What's next, per your own plan documents:** `Documentation/AI_Implementation_Plans/005-Memory_And_Voxel_World_Continuity.md` is fully designed through **Stage 3** (implementation plan agreed, decisions D1–D3 made: Postgres checkpointer reusing `pgvector-service`'s own instance in a new schema, rolled out to `graph-tools`/`graph-free` first, short-term/thread-scoped memory only for now). **Stage 4 (actual implementation) has not been started.** That's almost certainly where you want to resume — 8 concrete steps are already laid out (activate `thread_id` on the wire contract → confirm OpenWebUI's real thread-id source → Postgres checkpointer → wire into the two graphs → bound message growth → voxel re-grounding fix → tests → acceptance).

## 2. What I did this session

You asked me to run the program and monitor it. Two real issues turned up — one environmental, one a genuine code/dependency bug.

### Issue A — Docker Desktop was wedged (environmental, not a code problem)

`docker info` and even `docker ps` hung indefinitely. `uptime` showed the Mac hadn't rebooted in 35 days — it slept through your whole break, and Docker Desktop's Linux VM came out of that in a state where it accepted connections but never responded, including to a graceful `osascript quit`. I force-killed the Docker processes (`pkill -f com.docker.backend`, `com.docker.virtualization`) and relaunched via `open -a Docker`. It came back clean. **No project files or containers were touched by this** — just an OS-level service restart. Worth knowing for next time you come back from a long break: if `docker` commands hang forever with no error, don't wait it out — kill and relaunch Docker Desktop first.

### Issue B — `langchain_service` fails to boot: unpinned `mcp` package drifted to a breaking major version

Once Docker was healthy, `./build.sh --mode mock` built and started containers in the documented health-check order (pgvector → toolbox → langchain_service → gateway → openwebui). `pgvector_service` and `toolbox` came up healthy. **`langchain_service` crashed on import** before Flask even started, which — correctly, by design — blocked `dotnet_server` and `openwebui` from starting at all (they depend on it being healthy).

The crash:

```
File "/service/app/tools/toolbox_client.py", line 32, in <module>
    from langchain_mcp_adapters.client import MultiServerMCPClient
File ".../langchain_mcp_adapters/callbacks.py", line 8, in <module>
    from mcp.shared.context import RequestContext as MCPRequestContext
ImportError: cannot import name 'RequestContext' from 'mcp.shared.context'
```

**Root cause, confirmed:** `langchain_service/requirements.txt` pins `langchain-mcp-adapters==0.3.0` — but not the `mcp` package itself, which `langchain-mcp-adapters` depends on transitively. The file even already flags this exact risk in a comment on that line: *"the rest of this file is unpinned (pre-existing debt, flagged in plan 003 Stage 4 Step 2 notes)."* That debt matured into a real outage: rebuilding today (a month later) resolved `mcp` fresh and got **`mcp==2.0.0`**, a new major version that restructured its module layout (it now also depends on a separate `mcp-types` package) and no longer exposes `RequestContext` from `mcp.shared.context` — an API `langchain-mcp-adapters==0.3.0` was written against.

I verified this diagnosis without touching any repo files, per your rule against me changing code — I ran an ephemeral, throwaway container from the already-built image and tested the fix hypothesis live:

```bash
docker run --rm --entrypoint bash llm_monitor-langchain_service -c \
  "pip install -q 'mcp<2.0.0' && python3 -c 'from mcp.shared.context import RequestContext; print(\"IMPORT OK\")' && pip show mcp | grep Version"
# -> IMPORT OK
# -> Version: 1.29.0
```

Confirmed: pinning `mcp` below 2.0.0 (resolves to `1.29.0`) restores the import. **This is the same failure mode as `Documentation/AI_Suggestions/001` (the Langfuse/`langchain` version-branch issue)** — an unpinned transitive dependency of a pinned package moved out from under it. That doc is worth a re-read for the pattern; this is the second time it's bitten this project.

**Current state I left the stack in:** `pgvector_service` and `toolbox` are up and healthy; `langchain_service` is `Exited (1)`; `dotnet_server` and `openwebui` are `Created` but never started (correct behavior — their `depends_on: condition: service_healthy` never resolved). Nothing was torn down, so you can inspect it directly if you want (`docker compose -p llm_monitor logs langchain_service`), or just apply the fix below and rebuild.

#### Step-by-step fix

**Applied 2026-08-23, with your explicit go-ahead** (you said "fix it" after I flagged the tension with CLAUDE.md's no-code-edits rule and you confirmed the exception). What was done:

1. Added `mcp==1.29.0` to `langchain_service/requirements.txt`, right after `langchain-mcp-adapters==0.3.0`, with a comment explaining why (dated, links back to this doc) — same "pin what we verified" convention already used for `langchain-openai==1.3.5`.
2. Rebuilt with `./build.sh --mode live --obs` (the mode you were actually trying). `langchain_service` booted clean — RAG ingestion ran, gunicorn came up, `/healthz` returned `{"mode":"live","status":"ok"}`, no `ImportError`.
3. Confirmed `dotnet_server` and `openwebui` then started too (they were blocked purely by `langchain_service`'s health-check dependency). `localhost:5000/v1/models` returned all 7 registered pipelines. `localhost:3000` (OpenWebUI) came up `healthy` and returned `HTTP 200` — the original complaint is resolved.

**Still worth doing yourself, not done here:** double-check `mcp==1.29.0` against `langchain-mcp-adapters==0.3.0`'s own declared compatibility (not just "the number that happened to work"), and decide whether the *other* unpinned lines in that file (`flask`, `langchain-core`, `langgraph`, `langchain-postgres`, `langchain-ollama`, etc.) deserve the same treatment — this exact gap (pin the direct dependency, leave its transitive dependency unpinned) is what caused this outage, and it still exists on several other lines.

## 3. New finding while verifying the fix: `--obs` mode OOM-kills Langfuse on this machine

While confirming the full `--mode live --obs` stack, `langfuse_web` was silently killed (`docker inspect` confirms `OOMKilled: true`, exit 137) a few minutes after startup. **Root cause: this Mac has 8GB of total RAM, and Docker Desktop's Linux VM is currently capped at 3072 MiB.** Running the full `--obs` profile means 15 containers at once — the core app stack (5) plus Jaeger, Prometheus, Grafana, otel-collector, and Langfuse's *entire* self-hosted stack (web, worker, its own Postgres, ClickHouse, Redis, MinIO — 6 containers by itself). That doesn't fit in 3GB, and Langfuse's Next.js web process is what lost the OOM lottery this time; a different container could next time.

This isn't a code bug — nothing to fix in the repo — but it's a real operational constraint worth knowing before you rely on `--obs` for a demo or a work session:

- **Cheapest mitigation:** bump Docker Desktop's memory allocation (Docker Desktop → Settings → Resources → Memory) from 3072 MiB to something higher — but with only 8GB total and macOS itself needing headroom, there's not a lot of slack to give it on this machine.
- **Cheaper still, for day-to-day work:** don't run `--obs` unless you're actually working on/demoing observability. `./build.sh --mode mock` or `--mode live` (no `--obs`) is 5 containers instead of 15 and won't come close to this ceiling.
- **Longer-term, worth a real decision rather than me picking for you:** self-hosted Langfuse is the single heaviest piece of the whole `--obs` profile (6 of the 15 containers). Given this machine's RAM ceiling is a recurring theme (it's also why live mode moved off local Ollama in plan 003), it may be worth weighing self-hosted Langfuse against Langfuse Cloud's free tier the next time you're touching the observability stack — that would cut `--obs` from 15 containers to 10.

## 4. Suggested order of operations from here

1. ~~Apply the `mcp` pin and confirm the full stack boots clean~~ — done above; stack is currently up and verified in `--mode live --obs`.
2. If you plan to keep `--obs` running for a while, watch for OOM kills (`docker compose -p llm_monitor ps -a` — any core-path container showing `Exited (137)` is worth an `docker inspect <name> --format '{{.State.OOMKilled}}'` check) or just switch to `--mode live` without `--obs` for regular work.
3. Resume `Documentation/AI_Implementation_Plans/005-Memory_And_Voxel_World_Continuity.md` at **Stage 4, Step 1** (activate `thread_id` on the wire contract) — the plan is fully negotiated and ready to implement one step at a time, per your usual staged-permission process.
