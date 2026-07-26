#!/usr/bin/env bash
# Acceptance pass for plan 001 (Step 10).
#
# Usage:
#   ./build.sh --mode mock && bash scripts/acceptance_check.sh mock
#   ./build.sh --mode live && bash scripts/acceptance_check.sh live
#
# Covers criteria 1, 2, 3 (live), and 4 automatically; prints manual steps for
# 5 (OpenWebUI) and 6 (pytest/CI). Prints a PASS/FAIL line per check and a
# summary; paste the output into Stage 5 of plan 001.
#
# Deliberately NO `set -e`: an acceptance pass should run EVERY check and
# report, not die on the first failure.
set -uo pipefail

MODE="${1:-mock}"
GATEWAY="http://localhost:5000"
SERVICE="http://localhost:5001"
PASS=0; FAIL=0

result() {  # $1 = exit code, $2 = description
  if [ "$1" -eq 0 ]; then echo "  PASS: $2"; PASS=$((PASS+1));
  else echo "  FAIL: $2"; FAIL=$((FAIL+1)); fi
}

post() { curl -s -m 120 -X POST "$1" -H "Content-Type: application/json" -d "$2"; }

# assert_json <json> <python-expression over d>
assert_json() {
  echo "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); assert ($2), d" 2>/dev/null
}

wait_healthy() {  # $1 = base url, waits up to 90s
  for _ in $(seq 1 45); do
    curl -sf "$1/healthz" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

count_rows() {
  docker exec pgvector_service psql -U "${POSTGRES_USER:-admin}" -d "${POSTGRES_DB:-vectordb}" -tAc \
    "SELECT count(*) FROM langchain_pg_embedding e
     JOIN langchain_pg_collection c ON e.collection_id = c.uuid
     WHERE c.name = 'company_policies_${MODE}';" 2>/dev/null | tr -d '[:space:]'
}

echo "=== Acceptance pass: mode=${MODE} ==="

echo "--- Health ---"
wait_healthy "$SERVICE";                       result $? "langchain_service /healthz reachable"
wait_healthy "$GATEWAY";                       result $? "gateway /healthz reachable"
assert_json "$(curl -s $SERVICE/healthz)" "d['mode'] == '${MODE}'"
result $? "service reports mode=${MODE}"

echo "--- Criterion 1: four pipeline endpoints, direct (dev path :5001) ---"
QUESTION='{"user_message":"Am I allowed to use local scripting tools for automation?"}'
for p in chat-basic chat-rag graph-basic graph-rag; do
  route="${p/-//}"   # chat-basic -> chat/basic
  body=$(post "$SERVICE/$route" "$QUESTION")
  assert_json "$body" "d['status']=='success' and d['metadata']['pipeline_id']=='$p' and isinstance(d['response'],str) and d['response']"
  result $? "direct /$route returns contract success"
done

echo "--- Criterion 2: same endpoints via gateway (real path :5000/api/llm) ---"
for p in chat-basic chat-rag graph-basic graph-rag; do
  route="${p/-//}"
  body=$(post "$GATEWAY/api/llm/$route" "$QUESTION")
  assert_json "$body" "d['status']=='success' and d['metadata']['pipeline_id']=='$p'"
  result $? "gateway /api/llm/$route returns contract success"
done
# Plan 003: the registry grew three toolbox-conditional pipelines; compose
# always sets TOOLBOX_URL, so a compose deployment lists all seven.
assert_json "$(curl -s $GATEWAY/v1/models)" "{m['id'] for m in d['data']} == {'llm-monitor.chat-basic','llm-monitor.chat-rag','llm-monitor.graph-basic','llm-monitor.graph-rag','llm-monitor.graph-tools','llm-monitor.graph-premium','llm-monitor.graph-free'}"
result $? "gateway /v1/models lists exactly the 7 registry pipelines"

echo "--- Contract error paths (CONTRACTS.md §3) ---"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$SERVICE/chat/basic" -H "Content-Type: application/json" -d '{}')
[ "$code" = "400" ]; result $? "missing user_message -> 400"
code=$(curl -s -o /dev/null -w "%{http_code}" -X POST "$GATEWAY/v1/chat/completions" -H "Content-Type: application/json" \
  -d '{"model":"llm-monitor.nope","messages":[{"role":"user","content":"hi"}]}')
[ "$code" = "404" ]; result $? "unknown model id -> 404"

echo "--- Criterion 3: RAG demonstrably uses ingested content ---"
rag_body=$(post "$SERVICE/chat/rag" "$QUESTION")
assert_json "$rag_body" "'security_policy_v2.md' in d['metadata']['retrieved_sources']"
result $? "chat/rag retrieved_sources includes security_policy_v2.md"
basic_body=$(post "$SERVICE/chat/basic" "$QUESTION")
assert_json "$basic_body" "d['metadata']['retrieved_sources'] == []"
result $? "chat/basic retrieved_sources is empty"
if [ "$MODE" = "live" ]; then
  # Human judgment: the live model's RAG answer should visibly draw on the policy text.
  echo "  [manual] Compare answers below — RAG should cite/paraphrase the scripting policy, basic should not:"
  echo "    RAG:   $(echo "$rag_body"   | python3 -c "import sys,json; print(json.load(sys.stdin)['response'][:300])")"
  echo "    BASIC: $(echo "$basic_body" | python3 -c "import sys,json; print(json.load(sys.stdin)['response'][:300])")"
fi

echo "--- Plan 003: ToolBox + tiered pipelines (mock-mode assertions) ---"
# Toolbox is internal-only; probe it from INSIDE the network. The langchain
# image has no curl (python:slim), so the probe is stdlib python — same idiom
# as its own healthcheck.
docker exec langchain_service python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://toolbox:8080/health').status==200 else 1)" 2>/dev/null
result $? "toolbox /health answers 200 from inside the compose network"
curl -sf http://localhost:8080/health >/dev/null 2>&1
[ $? -ne 0 ]; result $? "toolbox is NOT reachable from the host (lockdown posture holds)"

TOOLQ='{"user_message":"TOOLCALL ping {\"message\": \"acceptance\"}"}'
body=$(post "$SERVICE/graph/tools" "$TOOLQ")
assert_json "$body" "d['status']=='success' and 'pong: acceptance' in d['response'] and d['metadata']['retrieved_sources']==[]"
result $? "graph/tools executes a real MCP tool; lean tier does not retrieve"
body=$(post "$SERVICE/graph/premium" "$TOOLQ")
assert_json "$body" "d['status']=='success' and 'pong: acceptance' in d['response'] and d['metadata']['retrieved_sources']"
result $? "graph/premium executes the tool AND retrieves (tier difference visible)"
body=$(post "$SERVICE/graph/premium" '{"user_message":"BLOCKME forbidden request"}')
assert_json "$body" "d['status']=='success' and \"can't help\" in d['response'] and d['metadata']['retrieved_sources']==[]"
result $? "graph/premium policy gate blocks; retrieval never runs on blocked requests"
body=$(post "$SERVICE/graph/free" "$TOOLQ")
assert_json "$body" "d['status']=='success' and 'pong: acceptance' in d['response']"
result $? "graph/free (routing tier) executes the tool"

echo "--- Criterion 4: ingestion idempotency (restart -> row count unchanged) ---"
c1=$(count_rows)
echo "  rows before restart: ${c1}"
docker restart langchain_service >/dev/null
wait_healthy "$SERVICE"
c2=$(count_rows)
echo "  rows after restart:  ${c2}"
[ -n "$c1" ] && [ "$c1" = "$c2" ] && [ "$c1" = "2" ]
result $? "row count is 2 before and after restart (collection company_policies_${MODE})"

echo "--- Manual criteria ---"
echo "  [5] OpenWebUI: open http://localhost:3000, pick an llm-monitor.* model, send a message,"
echo "      then confirm: docker logs dotnet_server | grep telemetry"
echo "  [6] Tests/CI:   cd langchain_service && python -m pytest -v   (and CI green on push)"

echo "=== Summary (${MODE}): ${PASS} passed, ${FAIL} failed ==="
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
