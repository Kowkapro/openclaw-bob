---
name: memoryguard-agent
description: "Store and retrieve facts about user's projects, decisions, ideas and people via MemoryGuard sub-agent. HTTP API at localhost:5002."
---

# MemoryGuard Sub-Agent

You have access to MemoryGuard — a structured knowledge base for storing facts about the user's projects, decisions, technologies, and ideas.

## How to use

All requests go to `http://127.0.0.1:5002` via curl.

### Search facts

```bash
curl -s http://127.0.0.1:5002/search -H "Content-Type: application/json" -d '{"query": "polza.ai pricing", "n_results": 5}'
```

Response: `{"results": [{"text": "...", "category": "...", "confidence": 0.95}], "count": 3}`

### Add a fact

```bash
curl -s http://127.0.0.1:5002/add -H "Content-Type: application/json" -d '{"text": "User decided to use Flask for sub-agent APIs", "category": "decisions", "context": "Architecture discussion 2026-03-13", "session_id": "bob"}'
```

Categories: `ideas`, `technologies`, `decisions`, `meetings`, `notes`, `problems`, `people`

### View statistics

```bash
curl -s http://127.0.0.1:5002/stats
```

### Delete a fact

```bash
curl -s http://127.0.0.1:5002/delete -H "Content-Type: application/json" -d '{"fact_id": "bob_1710345678"}'
```

### Health check

```bash
curl -s http://127.0.0.1:5002/health
```

## When to use

- When the user mentions something important (a decision, idea, technology choice) — save it as a fact
- When the user asks "what did I decide about X?" or "remind me about Y" — search facts
- When you need context about past projects or decisions — search first, then answer
- Proactively save important facts from conversations to build the knowledge base
- Use category `decisions` for architectural or business decisions
- Use category `ideas` for project ideas and brainstorming
- Use category `problems` for bugs, issues, and their solutions
- Use category `technologies` for tools, frameworks, and APIs the user works with
