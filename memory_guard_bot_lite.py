#!/usr/bin/env python3
# =============================================================================
# MemoryGuard Lite — Telegram bot + HTTP API (Flask)
# =============================================================================
# Telegram: user-facing interface
# HTTP API (localhost:5002): internal API for Bob (OpenClaw) to delegate tasks
# =============================================================================

import os
import sys
import json
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import List, Dict

WORKSPACE = Path("/home/openclaw/.openclaw/workspace")

try:
    from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
    from telegram.ext import Application, CommandHandler, ContextTypes
except ImportError:
    print("pip install python-telegram-bot==20.7")
    sys.exit(1)

try:
    from flask import Flask, request, jsonify
except ImportError:
    print("pip install flask")
    sys.exit(1)

# =============================================================================
# CONFIG
# =============================================================================

BOT_TOKEN = os.getenv("MEMORYGUARD_BOT_TOKEN", "")
ADMINS = [1039905495]
API_PORT = 5002

CATEGORIES = {
    "ideas": "Project ideas",
    "technologies": "Technologies & tools",
    "decisions": "Decisions made",
    "meetings": "Meetings",
    "notes": "Notes",
    "problems": "Problems & solutions",
    "people": "People",
}

DB_PATH = WORKSPACE / "memory_rag" / "memory.db"

# =============================================================================
# DATABASE
# =============================================================================

def get_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS facts (
        id TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        category TEXT NOT NULL,
        context TEXT,
        timestamp TEXT,
        session_id TEXT,
        updated_at TEXT
    )""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_category ON facts(category)")
    c.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON facts(timestamp)")
    conn.commit()
    conn.close()

# =============================================================================
# MEMORY GUARD CORE
# =============================================================================

class MemoryGuardLite:
    def __init__(self):
        init_db()

    def add_fact(self, text, category="ideas", context="", session_id=""):
        conn = get_db()
        fact_id = f"{session_id}_{int(datetime.now().timestamp())}"
        now = datetime.now().isoformat()
        conn.execute(
            "INSERT OR REPLACE INTO facts (id,text,category,context,timestamp,session_id,updated_at) VALUES (?,?,?,?,?,?,?)",
            (fact_id, text, category.lower(), context, now, session_id, now),
        )
        conn.commit()
        conn.close()
        return {"fact_id": fact_id, "category": category.lower()}

    def search_facts(self, query, n_results=10):
        conn = get_db()
        facts = [dict(r) for r in conn.execute("SELECT * FROM facts ORDER BY updated_at DESC").fetchall()]
        conn.close()
        if not query:
            return facts[:n_results]
        q = query.lower()
        results = []
        for f in facts:
            if q in f["text"].lower():
                results.append({**f, "confidence": 1.0})
            else:
                qw = set(q.split())
                tw = set(f["text"].lower().split())
                common = qw & tw
                if common:
                    results.append({**f, "confidence": len(common) / max(len(qw), len(tw))})
        results.sort(key=lambda x: x["confidence"], reverse=True)
        return results[:n_results]

    def get_stats(self):
        conn = get_db()
        rows = conn.execute("SELECT category, COUNT(*) as count FROM facts GROUP BY category ORDER BY count DESC").fetchall()
        conn.close()
        return {r["category"]: r["count"] for r in rows}

    def get_total(self):
        conn = get_db()
        total = conn.execute("SELECT COUNT(*) FROM facts").fetchone()[0]
        conn.close()
        return total

    def delete_fact(self, fact_id):
        conn = get_db()
        conn.execute("DELETE FROM facts WHERE id = ?", (fact_id,))
        conn.commit()
        conn.close()
        return True


mg = MemoryGuardLite()

# =============================================================================
# FLASK HTTP API (for Bob / OpenClaw)
# =============================================================================

api = Flask(__name__)


@api.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok", "service": "memoryguard", "total_facts": mg.get_total()})


@api.route("/search", methods=["POST"])
def api_search():
    data = request.get_json(force=True)
    query = data.get("query", "")
    n = data.get("n_results", 10)
    results = mg.search_facts(query, n_results=n)
    return jsonify({"results": results, "count": len(results)})


@api.route("/add", methods=["POST"])
def api_add():
    data = request.get_json(force=True)
    text = data.get("text", "")
    category = data.get("category", "notes")
    context = data.get("context", "")
    session_id = data.get("session_id", "bob")
    if not text:
        return jsonify({"error": "text is required"}), 400
    result = mg.add_fact(text, category, context, session_id)
    return jsonify({"status": "ok", **result})


@api.route("/stats", methods=["GET"])
def api_stats():
    stats = mg.get_stats()
    return jsonify({"total": mg.get_total(), "by_category": stats})


@api.route("/delete", methods=["POST"])
def api_delete():
    data = request.get_json(force=True)
    fact_id = data.get("fact_id", "")
    if not fact_id:
        return jsonify({"error": "fact_id is required"}), 400
    mg.delete_fact(fact_id)
    return jsonify({"status": "ok", "deleted": fact_id})


def run_api():
    api.run(host="127.0.0.1", port=API_PORT, debug=False, use_reloader=False)

# =============================================================================
# TELEGRAM HANDLERS
# =============================================================================

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    admin = " (Admin)" if update.effective_user.id in ADMINS else ""
    total = mg.get_total()
    await update.message.reply_text(
        f"\U0001f6e1 *MemoryGuard*{admin}\n\n"
        f"Knowledge base for your projects.\n"
        f"\U0001f4ca Facts: {total}\nHelp: /help",
        parse_mode="Markdown",
    )


async def help_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    total = mg.get_total()
    await update.message.reply_text(
        f"\U0001f6e1 *MemoryGuard* ({total} facts)\n\n"
        "/query <text> — search\n/stats — statistics\n/categories — list\n"
        "/list <cat> — show category\n/add <text> — add fact\n"
        "/delete <id> — delete\n/export — export JSON",
        parse_mode="Markdown",
    )


async def query_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /query <question>")
        return
    q = " ".join(ctx.args)
    results = mg.search_facts(q, 10)
    if not results:
        await update.message.reply_text("Nothing found.")
        return
    text = f"\U0001f50d *Found {len(results)}*:\n\n"
    for i, f in enumerate(results, 1):
        text += f"{i}. *{f['category']}*: {f['text']}\n"
    await update.message.reply_text(text[:4000], parse_mode="Markdown")


async def stats_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    stats = mg.get_stats()
    total = mg.get_total()
    text = f"\U0001f4ca *Stats* — {total} facts\n\n"
    for cat, cnt in stats.items():
        pct = (cnt / total * 100) if total > 0 else 0
        text += f"{cat}: {cnt} ({pct:.0f}%)\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def categories_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    text = "\U0001f4c2 *Categories*:\n\n"
    for k, v in CATEGORIES.items():
        text += f"- `{k}` — {v}\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def list_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not ctx.args:
        await update.message.reply_text("Usage: /list <category>")
        return
    cat = ctx.args[0].lower()
    all_facts = mg.search_facts("", 100)
    results = [f for f in all_facts if f["category"] == cat]
    if not results:
        await update.message.reply_text(f"Category `{cat}` is empty.")
        return
    text = f"\U0001f4c2 *{cat}* ({len(results)}):\n\n"
    for i, f in enumerate(results, 1):
        text += f"{i}. {f['text']}\n"
    await update.message.reply_text(text[:4000], parse_mode="Markdown")


async def add_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        await update.message.reply_text("Admin only.")
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /add <text> [category]")
        return
    args = " ".join(ctx.args)
    category = "ideas"
    parts = args.rsplit(" ", 1)
    if len(parts) == 2 and parts[1].lower() in CATEGORIES:
        category = parts[1].lower()
        text = parts[0]
    else:
        text = args
    mg.add_fact(text, category, "Added via Telegram", f"tg_{update.effective_user.id}")
    await update.message.reply_text(f"Added to `{category}`: {text}", parse_mode="Markdown")


async def delete_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMINS:
        return
    if not ctx.args:
        await update.message.reply_text("Usage: /delete <id>")
        return
    mg.delete_fact(ctx.args[0])
    await update.message.reply_text(f"Deleted `{ctx.args[0]}`")


async def export_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    facts = mg.search_facts("", 1000)
    path = WORKSPACE / "memory_rag" / "export.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(facts, f, ensure_ascii=False, indent=2)
    with open(path, "rb") as f:
        await update.message.reply_document(f, filename="memory_export.json", caption=f"{len(facts)} facts")
    path.unlink()

# =============================================================================
# MAIN
# =============================================================================

def main():
    if not BOT_TOKEN:
        print("Set MEMORYGUARD_BOT_TOKEN!")
        sys.exit(1)

    # Start Flask API in background thread
    api_thread = threading.Thread(target=run_api, daemon=True)
    api_thread.start()
    print(f"HTTP API running on http://127.0.0.1:{API_PORT}")

    # Start Telegram bot
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("query", query_cmd))
    app.add_handler(CommandHandler("stats", stats_cmd))
    app.add_handler(CommandHandler("categories", categories_cmd))
    app.add_handler(CommandHandler("list", list_cmd))
    app.add_handler(CommandHandler("add", add_cmd))
    app.add_handler(CommandHandler("delete", delete_cmd))
    app.add_handler(CommandHandler("export", export_cmd))

    print("MemoryGuard Lite started (Telegram + HTTP API)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
