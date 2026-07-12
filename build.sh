#!/usr/bin/env bash
# build.sh --mode mock|live  [--obs]  [--gpu]  [--model qwen2.5:1.5b]
#
#   --obs   also start the observability stack (otel-collector, Jaeger,
#           Prometheus, Grafana) via the compose "obs" profile, and set
#           OBSERVABILITY_ENABLED=true for the app services.
#           Without it the system is exactly as light as before plan 002.

set -euo pipefail # fail fast: -e exit on error, -u undefined variables, -o pipeline fail
MODE="mock"; GPU=""; OBS=""; MODEL="${LLM_MODEL:-qwen2.5:1.5b}"
while [[ $# -gt 0 ]]; do case "$1" in
  --mode) MODE="$2"; shift 2;;
  --gpu)  GPU="-f docker-compose.gpu.yml"; shift;;
  --obs)  OBS="--profile obs"; shift;;
  --model) MODEL="$2"; shift 2;;
  *) echo "unknown arg $1"; exit 1;;
esac; done

PROJECT="llm_monitor"

export LLM_MODE="$MODE" LLM_MODEL="$MODEL"
if [[ -n "$OBS" ]]; then export OBSERVABILITY_ENABLED="true"; else export OBSERVABILITY_ENABLED="false"; fi

echo "Taking down previous contianers and removing orphans"
docker compose -p "$PROJECT" --profile "*" down --remove-orphans


echo "Building images from current source"
if [[ "$MODE" == "live" ]]; then
    # Previous way (it told me to change because 'We explicitly declare the file structure parameters here to pass them cleanly')
    # docker compose -p "$PROJECT" build
    # echo "Taking images which we just build, and instanciating those images into actual running containers."
    # docker compose --profile live -p "$PROJECT" up --force-recreate -d

    # NOTE: We are now enabling secondary composition override
    # $GPU is called a dynamic string injector
    # TODO: investigate layed docker compose setups, dynamic string injectors, and composition overrides.
    docker compose -p "$PROJECT" --profile live ${OBS} -f docker-compose.yaml ${GPU:-} build
    echo "Instanciating live containers (Ollama active)${OBS:+ + observability stack}"
    docker compose -p "$PROJECT" --profile live ${OBS} -f docker-compose.yaml ${GPU:-} up --force-recreate -d
else
    docker compose -p "$PROJECT" ${OBS} -f docker-compose.yaml build
    echo "Instantiating mock containers (Lightweight Mode)${OBS:+ + observability stack}"
    docker compose -p "$PROJECT" ${OBS} -f docker-compose.yaml up --force-recreate -d
fi

echo "Getting rid of those old images which no longer have any containers which are running from them."
docker image prune -f

echo "Up. Tail logs with: docker compose -p $PROJECT logs -f"
if [[ -n "$OBS" ]]; then
  echo "Observability UIs:  Jaeger http://localhost:16686  |  Prometheus http://localhost:9090  |  Grafana http://localhost:3001"
fi

# WARNING: This resets Docker Desktop to a fresh install state.
# It will delete your local container layers, but it destroys the bloat instantly.
#rm -rf ~/Library/Containers/com.docker.docker
