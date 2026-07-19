#!/usr/bin/env bash
# Acceptance pass for plan 002 (Step 9b). Prereq: ./build.sh --mode mock --obs (or live).
#
#   bash scripts/observability_check.sh
#
# Automates criteria (a), (b-partial), (c-partial), (d-plumbing); prints manual
# steps for the rest. Same conventions as acceptance_check.sh: no `set -e`,
# run everything, report at the end, paste output into Stage 5 of plan 002.
set -uo pipefail

GATEWAY="http://localhost:5000"
JAEGER="http://localhost:16686"
PROM="http://localhost:9090"
LANGFUSE="http://localhost:3002"
LF_KEYS="pk-lf-local-llm-monitor:sk-lf-local-llm-monitor"
PASS=0; FAIL=0

result() { if [ "$1" -eq 0 ]; then echo "  PASS: $2"; PASS=$((PASS+1)); else echo "  FAIL: $2"; FAIL=$((FAIL+1)); fi }
assert_json() { echo "$1" | python3 -c "import sys,json; d=json.load(sys.stdin); assert ($2), d" 2>/dev/null; }

# wait_for <url> <tries>: poll every 2s. Found the hard way (Stage 5 finding 1):
# one-shot checks race container startup — the gateway doesn't START until
# langchain is healthy, and Langfuse migrates on first boot. An acceptance
# script must wait for readiness the same way compose depends_on does.
wait_for() {
  for _ in $(seq 1 "$2"); do
    curl -sf "$1" >/dev/null 2>&1 && return 0
    sleep 2
  done
  return 1
}

echo "=== Observability acceptance pass (plan 002) ==="

echo "--- Stack reachable (waiting for readiness, up to ~3 min on first boot) ---"
wait_for "$GATEWAY/healthz" 60;                                  result $? "gateway /healthz (waits for langchain healthy + dotnet start)"
wait_for "$JAEGER/" 15;                                          result $? "Jaeger UI"
wait_for "$PROM/-/ready" 15;                                     result $? "Prometheus ready"
wait_for "$LANGFUSE/api/public/health" 90;                       result $? "Langfuse health (first boot runs migrations)"

echo "--- Generate traffic (8 requests through the gateway) ---"
for i in 1 2; do for p in chat/basic chat/rag graph/basic graph/rag; do
  curl -s -o /dev/null -X POST "$GATEWAY/api/llm/$p" -H "Content-Type: application/json" \
    -d '{"user_message":"observability acceptance probe"}'
done; done
echo "  sent; waiting 10s for batch exporters and scrape interval..."
sleep 10

echo "--- Criterion (a): one trace, both services ---"
traces=$(curl -s "$JAEGER/api/traces?service=gateway&limit=5&lookback=10m" 2>/dev/null || echo '{}')
assert_json "$traces" "any({p['serviceName'] for p in t.get('processes',{}).values()} >= {'gateway','langchain_service'} for t in d.get('data',[]))"
result $? "Jaeger has a trace containing spans from BOTH gateway and langchain_service"

echo "--- Criterion (b): metrics flowing ---"
up=$(curl -s "$PROM/api/v1/query?query=up" 2>/dev/null)
assert_json "$up" "sum(1 for r in d['data']['result'] if r['value'][1]=='1') >= 2"
result $? "Prometheus: both scrape targets up"
reqs=$(curl -s "$PROM/api/v1/query?query=llm_requests_total" 2>/dev/null)
assert_json "$reqs" "len({r['metric'].get('pipeline_id') for r in d['data']['result']}) >= 4"
result $? "Prometheus: llm_requests_total present for all 4 pipelines"

echo "--- Criterion (c): Langfuse captured generations ---"
lf=$(curl -s -u "$LF_KEYS" "$LANGFUSE/api/public/traces?limit=1" 2>/dev/null || echo '{}')
assert_json "$lf" "len(d.get('data',[])) >= 1"
result $? "Langfuse API returns at least one trace (verify prompt/chunks visually in UI)"

echo "--- Criterion (d): eval plumbing tiers (inside the container) ---"
docker exec langchain_service python -m eval.eval_retrieval --tier plumbing >/dev/null 2>&1
result $? "retrieval eval plumbing tier runs green"
docker exec langchain_service python -m eval.eval_judge --tier plumbing >/dev/null 2>&1
result $? "judge eval plumbing tier runs green"

echo "--- Manual criteria ---"
echo "  [b] Grafana http://localhost:3001 — RED panels populated for 4 pipelines after the traffic above"
echo "  [c] Langfuse http://localhost:3002 — open newest trace: rendered prompt, nested graph nodes, tags"
echo "  [d-quality] live baselines:  docker exec langchain_service python -m eval.eval_retrieval --tier quality --save-baseline"
echo "  [e]         docker exec langchain_service python -m eval.eval_judge --tier quality --calibration"
echo "  [f] fire-alarm: corrupt a golden expected_doc_id -> retrieval --gate must exit 1 -> revert"
echo "  [g] ./build.sh --mode mock (no --obs) -> container set identical to plan-001 baseline, 39 tests green"

echo "=== Summary: ${PASS} passed, ${FAIL} failed ==="
exit $([ "$FAIL" -eq 0 ] && echo 0 || echo 1)
