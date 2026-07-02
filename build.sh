#!/usr/bin/env bash
# build.sh --mode mock|live  [--gpu]  [--model qwen2.5:1.5b]

set -euo pipefail # fail fast: -e exit on error, -u undefined variables, -o pipeline fail
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


echo "Building images from current source"
if [[ "$MODE" == "live" ]]; then
    # Previous way (it told me to change because 'We explicitly declare the file structure parameters here to pass them cleanly')
    # docker compose -p "$PROJECT" build
    # echo "Taking images which we just build, and instanciating those images into actual running containers."
    # docker compose --profile live -p "$PROJECT" up --force-recreate -d

    # NOTE: We are now enabling secondary composition override
    # $GPU is called a dynamic string injector
    # TODO: investigate layed docker compose setups, dynamic string injectors, and composition overrides.
    docker compose -p "$PROJECT" --profile live -f docker-compose.yaml $GPU build 
    echo "Instanciating live containers (Ollama active)"
    docker compose -p "$PROJECT" --profile live -f docker-compose.yaml $GPU up --force-recreate -d
else
    docker compose -p "$PROJECT" -f docker-compose.yaml build
    echo "Instantiating mock containers (Lightweight Mode)"
    docker compose -p "$PROJECT" -f docker-compose.yaml up --force-recreate -d
fi

echo "Getting rid of those old images which no longer have any containers which are running from them."
docker image prune -f

echo "Up. Tail logs with: docker compose -p $PROJECT logs -f"