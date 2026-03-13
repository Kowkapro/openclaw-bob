#!/bin/bash
# Usage: /home/openclaw/generate_image.sh "prompt in English" [model]
# Models: gpt-image (default), gpt5, seedream
# Result: image sent to @BobDesignAgentbot via Telegram
PROMPT="$1"
MODEL="${2:-gpt-image}"
if [ -z "$PROMPT" ]; then
    echo "Error: prompt is required"
    echo "Usage: /home/openclaw/generate_image.sh 'bright cartoon avatar' gpt-image"
    exit 1
fi
curl -s http://127.0.0.1:5001/generate_and_send \
  -H 'Content-Type: application/json' \
  -d "{\"prompt\": \"$PROMPT\", \"model\": \"$MODEL\", \"chat_id\": 1039905495}"
