#!/usr/bin/env bash
# test_start_up.sh - Isolated startup & continuous cleanup for Langchain & Ollama

set -euo pipefail

PROJECT="llm_monitor"
SERVICES=("langchain_service" "ollama" "ollama-pull-model")

echo " 1. Aggressively tearing down previous instances of target services..."
# -v removes associated anonymous volumes, --remove-orphans drops detached containers
docker compose -p "$PROJECT" down -v --remove-orphans

echo " 2. Rebuilding Langchain fresh (bypassing layer cache)..."
docker compose -p "$PROJECT" build --no-cache langchain_service

echo " 3. Spinning up isolated Langchain and Ollama network stack..."
docker compose -p "$PROJECT" up -d "${SERVICES[@]}"

echo "  4. Purging dangling or stale images to save MacBook disk space..."
docker image prune -f

echo " Up and running. View real-time logs with:"
echo "docker compose -p $PROJECT logs -f langchain_service"