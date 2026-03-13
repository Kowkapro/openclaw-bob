---
name: designer-agent
description: "Generate and edit images via DesignerBot sub-agent. Use HTTP API at localhost:5001 to create images (polza.ai) and edit them (WaveSpeed Nano-Banana)."
---

# DesignerBot Sub-Agent

You have access to DesignerBot — an image generation and editing service running locally.

## How to use

All requests go to `http://127.0.0.1:5001` via curl.

### Generate an image

```bash
curl -s http://127.0.0.1:5001/generate -H "Content-Type: application/json" -d '{"prompt": "a futuristic city at sunset", "model": "gpt-image", "aspect_ratio": "1:1"}'
```

Response: `{"status": "ok", "file_path": "/path/to/image.png", "image_url": "https://...", "model": "gpt-image"}`

Available models:
- `gpt-image` — OpenAI GPT Image 1.5 (~3₽) — default, best quality
- `gpt5` — OpenAI GPT-5 Image Mini (~4₽) — creative
- `seedream` — ByteDance Seedream 4.5 (~5₽) — photorealistic

### Edit an image

```bash
curl -s http://127.0.0.1:5001/edit -H "Content-Type: application/json" -d '{"image_url": "https://url-of-image", "prompt": "add sunglasses"}'
```

### Check available models

```bash
curl -s http://127.0.0.1:5001/models
```

### View statistics

```bash
curl -s http://127.0.0.1:5001/stats
```

### Health check

```bash
curl -s http://127.0.0.1:5001/health
```

## Important

- After generating, the image is saved to `/home/openclaw/.openclaw/workspace/bots/generated/`
- The response contains both `file_path` (local file) and `image_url` (remote URL)
- To show the image to the user, use the `image_url` from the response
- If the service is down, it will be restarted automatically by watchdog within 5 minutes
- When the user asks to "create an image", "draw", "generate a picture", "make a logo" etc. — use this skill
