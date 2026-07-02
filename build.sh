#!/usr/bin/env bash
# build.sh --mode mock|live  [--gpu]  [--model qwen2.5:1.5b]

set -euo pipefail # fail fast: -e exit on error, -u undefined variables, -o pipeline fail (what is a pipeline fail??)
MODE="mock"; GPU=""; MODEL="${LLM_MODEL:-qwen2.5:1.5b}"
while [[ $# -gt 0 ]]; do case "$1" in
  --mode) MODE="$2"; shift 2;;
  --gpu)  GPU="-f docker-compose.gpu.yml"; shift;;
  --model) MODEL="$2"; shift 2;;
  *) echo "unknown arg $1"; exit 1;;
esac; done

PROJECT="llm_monitor"

export LLM_MODE="$MODE" LLM_MODEL="$MODEL"

echo "Taking down previous contianers and removing orphans"
docker compose -p "$PROJECT" down --remove-orphans

if [[ "$MODE" == "live" ]]; then
    echo "Building images from current source"
    docker compose -p "$PROJECT" build

    echo "Taking images which we just build, and instanciating those images into actual running containers."
    docker compose --profile live -p "$PROJECT" up --force-recreate -d
else
    echo "Building images from current source"
    docker compose -p "$PROJECT" build

    echo "Taking images which we just build, and instanciating those images into actual running containers."
    docker compose -p "$PROJECT" up --force-recreate -d  
fi

echo "Getting rid of those old images which no longer have any containers which are running from them."
docker image prune -f

#Do we need to also run a command to clear the layer cache???


echo "Up. Tail logs with: docker compose -p $PROJECT logs -f"