






#!/usr/bin/env bash
# build.sh - sustainable rebuild-and-run for LLM_Monitor

set -euo pipefail # fail fast: -e exit on error, -u undefined variables, -o pipeline fail (what is a pipeline fail??)

PROJECT="llm_monitor"

echo "Taking down previous contianers and removing orphans"
docker compose -p "$PROJECT" down --remove-orphans

#NOTE: I was unsure about what this command was actually going to do. I was hesitent to say if it was building the container or the images.
echo "Building images from current source"
docker compose -p "$PROJECT" build

echo "Taking images which we just build, and instanciating those images into actual running containers."
docker compose -p "$PROJECT" up --force-recreate -d

echo "Getting rid of those old images which no longer have any containers which are running from them."
docker image prune -f

#Do we need to also run a command to clear the layer cache???


echo "Up. Tail logs with: docker compose -p $PROJECT logs -f"