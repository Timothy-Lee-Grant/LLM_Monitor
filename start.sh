#!/usr/bin/env bash
# start.sh --mode mock|live [--gpu] [--model qwen2.5:1.5b]

set -euo pipfail
MODE="mock"; GPU=""; MODEL=${LLM_MODEL:-qwen2.5:1.5b}
while [[ $# -gt 0 ]]; do case "$1" in
  --mode) MODE="$2"; shift 2;;
  --gpu)  GPU="-f docker-compose.gpu.yml"; shift;;
  --model) MODEL="$2"; shift 2;;
  *) echo "unknown arg $1"; exit 1;;
esac; done

export LLM_MODE="$MODE" LLM_MODEL="$MODEL"
if [[ "$MODE" == "live" ]]; then
    docker compose --profile live up -d --build