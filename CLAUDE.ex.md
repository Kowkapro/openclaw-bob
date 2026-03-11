# CLAUDE.md — Project Rules

## #1 DEVELOPMENT WORKFLOW (highest priority, ALWAYS follow)
RULE: Every feature follows this EXACT sequence. NEVER skip steps.
1. Implement the feature
2. Test that it works (run it, verify output)
3. Ask user to confirm/approve the result
4. ONLY after user approval: update relevant docs (`Trade_notification.md`, `CLAUDE.md`)
5. Run `/push`

RULE: NEVER make large untested changes. One feature at a time.
RULE: NEVER run `/push` without completing steps 1-4 above.
RULE: After completing a milestone, check it off in `Trade_notification.md` section 8.
RULE: When discovering a bug/gotcha, add it to KNOWN ISSUES below.

## LANGUAGE
- RULE: Speak Russian to the user. Plans, explanations, task descriptions — always in Russian.
- RULE: Code, code comments, git commits — in English.
- RULE: ESO game terms (items, locations, guilds) — in English (TTC uses EN names).

## FOCUS
- RULE: Only implement features from the current step in `Trade_notification.md` section 8. Do NOT suggest or build anything outside the plan.

## PROJECT CONTEXT
- Server: PC North America (NA)
- Base URL: `https://us.tamrieltradecentre.com`
- Data source: TTC JSON API via Playwright (CSR — HTML parsing does NOT work)
- avg_price: SuggestedPrice from PriceCheck API (`/api/pc/Trade/PriceCheck`, intercepted via PriceCheckResult page)

## CODE
- RULE: ALWAYS read a file before modifying it.
- RULE: Do NOT create new files unless absolutely necessary.
- RULE: Follow project structure from `Trade_notification.md` section 5.
- RULE: All TTC URLs must include `lang=en-US` parameter.

## SCRAPING (hard rules)
- RULE: Use Playwright headless + API response interception. cloudscraper/BS4 do NOT work (CSR).
- RULE: Delay between requests: 3–5 seconds, randomized.
- RULE: Check interval: 5–10 minutes (not more frequent).
- RULE: One request at a time — no parallel page loads.
- RULE: Detect reCAPTCHA v2 fallback → log error + notify Telegram, do NOT crash.
- RULE: Minimum breakeven discount = 8.7% (below = loss after 8% ESO commission). NEVER alert below this.
- RULE: Always multiply by `quantity` in profit formula — `unit_price × qty`, not just `unit_price`.

## SECURITY (hard rules, NEVER override)
- NEVER put secrets (passwords, API keys, tokens) in code — use `.env`
- NEVER commit: `.env`, `*.pkl`, `*.db`, `data/`, `*.log`
- NEVER commit payment data, marketplace accounts, buyer names
- Bot actions MUST have random delays (human-like behavior)

## GIT
- Commits: short, English, descriptive
- `.gitignore` must include: `.env`, `data/`, `__pycache__/`, `*.pkl`, `*.db`, `*.log`

## KNOWN ISSUES
- TTC is CSR (Knockout.js) — all `data-bind` spans are empty in raw HTML. Only Playwright works.
- reCAPTCHA v3 required for API calls — Playwright handles it automatically via browser.
- Cookie/session lifetime unpredictable — use storage_state persistence.
- Listings "5 minutes ago" may already be sold — TTC has inherent data delay.
- Items older than 8 hours are almost certainly sold; 120-minute filter is reasonable.
- Verified Item IDs (2026-03-10): Rosin=2677, Dreugh Wax=211, Tempering Alloy=5687, Kuta=1114, Chromium Plating=27586, Dragon's Blood=20157, Dragon Rheum=21009, Columbine=3200, Heartwood=11971, Potent Nirncrux=3790, Hakeijo=4794.
- TTC API may return incomplete listings (missing fields) — parser must skip them gracefully, not crash.
- PriceCheck API requires `SearchType`, `ItemID`, `ItemNamePattern`, `SortBy`, `Order`, `lang` params.
- Old self-calculated avg_price (median of 10 listings) was 2-3x lower than real price — caused false alerts.
- config.yaml `request_delay_seconds` is not yet wired to client.py — must be connected in main.py.
- PriceCheck API SuggestedPrice is unreliable for cheap items with few listings (<100). Essence of Health: API said 268g, real price 8-10g. Only use PriceCheck for high-volume upgrade materials (1000+ listings).
- Essence of Health removed from watchlist — low liquidity (sits 10+ days), wildly inaccurate SuggestedPrice.
