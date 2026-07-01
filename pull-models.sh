#!/bin/sh

#TODO: I copy/pasted this file for now because I am trying to get things working. I will need to come back to this to fully understand what is going on.

# Set the Ollama host URL (fallback to localhost if not specified via env)
OLLAMA_URL="${OLLAMA_BASE_URL:-http://ollama:11434}"

echo "Waiting for Ollama service to wake up at ${OLLAMA_URL}..."

# Loop until the /api/tags endpoint returns an HTTP 200 status code
until curl -s -o /dev/null -w "%{http_code}" "${OLLAMA_URL}/api/tags" | grep -q "200"; do
  printf "."
  sleep 1
done

echo -e "\nOllama is up and responsive! Initiating model initialization pipeline..."

# 1. Pull the text generation model
echo "Pulling text generation model (qwen2.5:1.5b)..."
curl -X POST "${OLLAMA_URL}/api/pull" \
     -H "Content-Type: application/json" \
     -d '{"name": "qwen2.5:1.5b"}'

# 2. Pull the embedding engine model
echo -e "\nPulling context embedding engine (nomic-embed-text)..."
curl -X POST "${OLLAMA_URL}/api/pull" \
     -H "Content-Type: application/json" \
     -d '{"name": "nomic-embed-text"}'

echo -e "\nModel initialization tasks completed successfully."