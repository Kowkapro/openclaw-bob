#!/bin/bash
# Usage: /home/openclaw/search_memory.sh "query text"
QUERY="$1"
if [ -z "$QUERY" ]; then
    echo "Error: query is required"
    echo "Usage: /home/openclaw/search_memory.sh 'what did I decide about APIs'"
    exit 1
fi
curl -s http://127.0.0.1:5002/search \
  -H 'Content-Type: application/json' \
  -d "{\"query\": \"$QUERY\", \"n_results\": 5}"
