#!/bin/bash
# Usage: /home/openclaw/save_memory.sh "fact text" [category]
# Categories: ideas, technologies, decisions, meetings, notes, problems, people
TEXT="$1"
CATEGORY="${2:-notes}"
if [ -z "$TEXT" ]; then
    echo "Error: text is required"
    echo "Usage: /home/openclaw/save_memory.sh 'decided to use Flask for APIs' decisions"
    exit 1
fi
curl -s http://127.0.0.1:5002/add \
  -H 'Content-Type: application/json' \
  -d "{\"text\": \"$TEXT\", \"category\": \"$CATEGORY\", \"session_id\": \"bob\"}"
