# CLAUDE.md — OpenClaw Project Rules

## #1 DEVELOPMENT WORKFLOW (highest priority, ALWAYS follow)
RULE: Every step follows this EXACT sequence. NEVER skip steps.
1. Implement the change (config, script, command)
2. Test that it works (run it, verify output)
3. Ask user to confirm/approve the result
4. ONLY after user approval: update relevant docs (`openclaw-setup.md`, `CLAUDE.md`)
5. Run `/push`

RULE: NEVER make large untested changes. One step at a time.
RULE: NEVER run `/push` without completing steps 1-4 above.
RULE: After completing a setup block, check it off in `openclaw-setup.md` section "Статус".
RULE: When discovering a bug/gotcha, add it to KNOWN ISSUES below.

## LANGUAGE
- RULE: Speak Russian to the user. Plans, explanations, task descriptions — always in Russian.
- RULE: Code, config files, git commits — in English.

## FOCUS
- RULE: Only work on the current uncompleted block in `openclaw-setup.md`. Do NOT suggest or build anything outside the plan.

## PROJECT CONTEXT
- Project: OpenClaw — personal AI assistant in Telegram (bot name: "Боб")
- Hosting: Beget VPS, Moscow, Ubuntu 24.04 LTS, 2GB RAM, 10GB SSD
- LLM: DeepSeek V3.2 Exp via polza.ai (OpenAI-compatible), model `deepseek/deepseek-v3.2-exp`
- API Base URL: `https://polza.ai/api/v1`
- Channel: Telegram (primary), bot: @botclawAi_BOT
- Runtime: Node.js v22.22.1
- OpenClaw: v2026.3.8
- Process manager: nohup (systemd user services unavailable on this server)
- Firewall: UFW (ports: 22, 80, 443)

## SERVER PATHS
- OpenClaw binary: `/home/openclaw/.npm-global/bin/openclaw`
- Config: `/home/openclaw/.openclaw/openclaw.json`
- SOUL.md: `/home/openclaw/.openclaw/SOUL.md`
- MEMORY.md: `/home/openclaw/.openclaw/workspace/MEMORY.md`
- Workspace: `/home/openclaw/.openclaw/workspace/`
- Logs: `/tmp/openclaw.log`

## GATEWAY MANAGEMENT
- Start: `nohup su - openclaw -c "/home/openclaw/.npm-global/bin/openclaw gateway" > /tmp/openclaw.log 2>&1 &`
- Stop: `pkill -9 -f "openclaw gateway"`
- Status: `pgrep -a -f "openclaw gateway"`
- After any config change: stop + start gateway

## CODE & CONFIG
- RULE: ALWAYS read a file before modifying it.
- RULE: Do NOT create new files unless absolutely necessary.
- RULE: NEVER put secrets (API keys, bot tokens, passwords) in code or git — use .env locally, config on server only.

## SECURITY (hard rules, NEVER override)
- NEVER commit: `.env`, API keys, bot tokens, Telegram user IDs, VPS passwords
- NEVER put any secrets in any file tracked by git
- Secrets live in `.env` locally (gitignored) and in openclaw.json on server only

## GIT
- Commits: short, English, descriptive
- `.gitignore` must include: `.env`, `*.log`, `.claude/`, any file with secrets

## KNOWN ISSUES
- systemd user services unavailable — gateway must be started with nohup as root
- After SSH disconnect, gateway survives only if started with nohup (not with `&` alone)
- Telegram channel NOT configured via `openclaw onboard` — token added manually to `channels` in openclaw.json
- `dmPolicy: "pairing"` requires manual pairing on first connect (enter code in Telegram)
- `allowFrom` requires numeric Telegram User ID `"tg:123456789"` — NOT username
- After any config change, restart gateway manually (see GATEWAY MANAGEMENT above)
- Node.js must be v22.x
