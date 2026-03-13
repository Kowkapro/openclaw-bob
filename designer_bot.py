#!/usr/bin/env python3
# =============================================================================
# DesignerBot v2 — Telegram bot + HTTP API (Flask)
# =============================================================================
# Telegram: user-facing interface (generate/edit images)
# HTTP API (localhost:5001): internal API for Bob (OpenClaw) to delegate tasks
# =============================================================================

import os
import sys
import time
import requests
import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)
from flask import Flask, request as flask_request, jsonify, send_file

# =============================================================================
# Settings
# =============================================================================

WORKSPACE = Path("/home/openclaw/.openclaw/workspace")
BOT_TOKEN = os.getenv("DESIGNER_BOT_TOKEN", "")
POLZA_API_KEY = os.getenv("POLZA_API_KEY", "pza__BQDqwgxIhZ7zegdQsExE2Vd5lnrAkM2")
WAVESPEED_API_KEY = os.getenv("WAVESPEED_API_KEY", "")

ADMIN_ID = 1039905495
API_PORT = 5001

POLZA_BASE_URL = "https://polza.ai/api/v1/media"
WAVESPEED_BASE_URL = "https://api.wavespeed.ai/api/v3"

# Generation models (polza.ai /api/v1/media)
MODELS = {
    "gpt-image": {"id": "openai/gpt-image-1.5", "price": "~3r", "emoji": "\U0001f5bc"},
    "gpt5": {"id": "openai/gpt-5-image-mini", "price": "~4r", "emoji": "\U0001f3af"},
    "seedream": {"id": "bytedance/seedream-4.5", "price": "~5r", "emoji": "\U0001f300"},
}
DEFAULT_MODEL = "gpt-image"

# Editing models (WaveSpeed)
EDIT_MODELS = {
    "nano-banana": {"id": "google/nano-banana/edit", "price": "~3.5r"},
    "nano-banana-fast": {"id": "google/nano-banana-2/edit/fast", "price": "~3.5r"},
}
DEFAULT_EDIT_MODEL = "nano-banana"

DB_PATH = WORKSPACE / "bots" / "designer_bot.db"
SAVE_DIR = WORKSPACE / "bots" / "generated"

# =============================================================================
# Database
# =============================================================================

def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS generations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        prompt TEXT, model TEXT, output_path TEXT, image_url TEXT,
        mode TEXT DEFAULT 'generate',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        admin_id TEXT
    )''')
    try:
        c.execute("ALTER TABLE generations ADD COLUMN image_url TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        c.execute("ALTER TABLE generations ADD COLUMN mode TEXT DEFAULT 'generate'")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    conn.close()


def log_gen(prompt, model, output_path, image_url="", mode="generate"):
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        'INSERT INTO generations (prompt,model,output_path,image_url,mode,admin_id) VALUES (?,?,?,?,?,?)',
        (prompt, model, str(output_path), image_url, mode, str(ADMIN_ID)),
    )
    conn.commit()
    conn.close()

# =============================================================================
# Image generation (polza.ai)
# =============================================================================

def generate_image(prompt, model_key=DEFAULT_MODEL, aspect_ratio="1:1"):
    headers = {
        "Authorization": f"Bearer {POLZA_API_KEY}",
        "Content-Type": "application/json",
    }
    model_id = MODELS.get(model_key, MODELS[DEFAULT_MODEL])["id"]
    payload = {"model": model_id, "input": {"prompt": prompt, "aspect_ratio": aspect_ratio}}

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = SAVE_DIR / f"gen_{ts}.png"

    try:
        r = requests.post(POLZA_BASE_URL, headers=headers, json=payload, timeout=180)
        if r.status_code != 200:
            return False, f"API {r.status_code}: {r.text[:200]}", ""

        data = r.json()
        if "data" not in data or not data["data"]:
            return False, f"No data: {list(data.keys())}", ""

        url = data["data"][0].get("url", "")
        if not url:
            return False, "No URL in response", ""

        img = requests.get(url, timeout=60)
        if img.status_code != 200:
            return False, f"Download failed: {img.status_code}", ""

        with open(out, "wb") as f:
            f.write(img.content)

        log_gen(prompt, model_key, str(out), url)
        return True, str(out), url

    except Exception as e:
        return False, str(e), ""

# =============================================================================
# Image editing (WaveSpeed Nano-Banana)
# =============================================================================

def edit_image(image_url, prompt, model_key=DEFAULT_EDIT_MODEL):
    if not WAVESPEED_API_KEY:
        return False, "WAVESPEED_API_KEY not set", ""

    headers = {
        "Authorization": f"Bearer {WAVESPEED_API_KEY}",
        "Content-Type": "application/json",
    }
    model_path = EDIT_MODELS.get(model_key, EDIT_MODELS[DEFAULT_EDIT_MODEL])["id"]
    payload = {
        "images": [image_url],
        "prompt": prompt,
        "output_format": "png",
        "enable_sync_mode": True,
    }

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = SAVE_DIR / f"edit_{ts}.png"

    try:
        r = requests.post(
            f"{WAVESPEED_BASE_URL}/{model_path}",
            headers=headers, json=payload, timeout=120,
        )
        if r.status_code != 200:
            return False, f"WaveSpeed {r.status_code}: {r.text[:200]}", ""

        data = r.json()
        url = ""

        if data.get("status") == "completed" and data.get("outputs"):
            url = data["outputs"][0]
        elif data.get("id"):
            pred_id = data["id"]
            for _ in range(30):
                time.sleep(3)
                check = requests.get(
                    f"{WAVESPEED_BASE_URL}/predictions/{pred_id}/result",
                    headers=headers, timeout=15,
                )
                if check.status_code == 200:
                    cr = check.json()
                    if cr.get("status") == "completed" and cr.get("outputs"):
                        url = cr["outputs"][0]
                        break
                    if cr.get("status") == "failed":
                        return False, "Edit failed", ""
            else:
                return False, "Edit timeout", ""
        else:
            return False, f"Unexpected: {list(data.keys())}", ""

        img = requests.get(url, timeout=60)
        if img.status_code != 200:
            return False, f"Download failed: {img.status_code}", ""

        with open(out, "wb") as f:
            f.write(img.content)

        log_gen(prompt, model_key, str(out), url, mode="edit")
        return True, str(out), url

    except Exception as e:
        return False, str(e), ""

# =============================================================================
# FLASK HTTP API (for Bob / OpenClaw)
# =============================================================================

flask_api = Flask(__name__)


@flask_api.route("/health", methods=["GET"])
def api_health():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
    conn.close()
    return jsonify({
        "status": "ok",
        "service": "designer",
        "models": list(MODELS.keys()),
        "edit_models": list(EDIT_MODELS.keys()),
        "total_generations": total,
    })


@flask_api.route("/generate", methods=["POST"])
def api_generate():
    data = flask_request.get_json(force=True)
    prompt = data.get("prompt", "")
    model = data.get("model", DEFAULT_MODEL)
    aspect = data.get("aspect_ratio", "1:1")
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    if model not in MODELS:
        return jsonify({"error": f"Unknown model. Available: {list(MODELS.keys())}"}), 400

    success, result, url = generate_image(prompt, model, aspect)
    if success:
        return jsonify({"status": "ok", "file_path": result, "image_url": url, "model": model})
    else:
        return jsonify({"status": "error", "error": result}), 500


@flask_api.route("/edit", methods=["POST"])
def api_edit():
    data = flask_request.get_json(force=True)
    image_url = data.get("image_url", "")
    prompt = data.get("prompt", "")
    model = data.get("model", DEFAULT_EDIT_MODEL)
    if not image_url or not prompt:
        return jsonify({"error": "image_url and prompt are required"}), 400

    success, result, url = edit_image(image_url, prompt, model)
    if success:
        return jsonify({"status": "ok", "file_path": result, "image_url": url})
    else:
        return jsonify({"status": "error", "error": result}), 500


@flask_api.route("/models", methods=["GET"])
def api_models():
    return jsonify({
        "generation": {k: v["id"] for k, v in MODELS.items()},
        "editing": {k: v["id"] for k, v in EDIT_MODELS.items()},
    })


@flask_api.route("/stats", methods=["GET"])
def api_stats():
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
    by_model = dict(conn.execute("SELECT model, COUNT(*) FROM generations GROUP BY model").fetchall())
    by_mode = dict(conn.execute("SELECT mode, COUNT(*) FROM generations GROUP BY mode").fetchall())
    conn.close()
    return jsonify({"total": total, "by_model": by_model, "by_mode": by_mode})


@flask_api.route("/generate_and_send", methods=["POST"])
def api_generate_and_send():
    """Async: immediately returns OK, generates image in background, sends via Telegram."""
    data = flask_request.get_json(force=True)
    prompt = data.get("prompt", "")
    model = data.get("model", DEFAULT_MODEL)
    aspect = data.get("aspect_ratio", "1:1")
    chat_id = data.get("chat_id", ADMIN_ID)
    if not prompt:
        return jsonify({"error": "prompt is required"}), 400
    if model not in MODELS:
        return jsonify({"error": f"Unknown model. Available: {list(MODELS.keys())}"}), 400

    def background_generate():
        try:
            success, result, url = generate_image(prompt, model, aspect)
            bot = Bot(token=BOT_TOKEN)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if success:
                with open(result, "rb") as photo:
                    loop.run_until_complete(
                        bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=f"\U0001f3a8 `{model}` | {prompt[:150]}",
                            parse_mode="Markdown",
                        )
                    )
            else:
                loop.run_until_complete(
                    bot.send_message(chat_id=chat_id, text=f"\u274c Generation failed: {result[:300]}")
                )
            loop.close()
        except Exception as e:
            try:
                bot = Bot(token=BOT_TOKEN)
                import asyncio
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(
                    bot.send_message(chat_id=chat_id, text=f"\u274c Error: {str(e)[:300]}")
                )
                loop.close()
            except Exception:
                pass

    t = threading.Thread(target=background_generate, daemon=True)
    t.start()

    return jsonify({
        "status": "queued",
        "message": f"Image generation started. Result will be sent to @BobDesignAgentbot (chat {chat_id})",
        "model": model,
        "prompt": prompt[:100],
    })


@flask_api.route("/edit_and_send", methods=["POST"])
def api_edit_and_send():
    """Async: immediately returns OK, edits image in background, sends via Telegram."""
    data = flask_request.get_json(force=True)
    image_url = data.get("image_url", "")
    prompt = data.get("prompt", "")
    model = data.get("model", DEFAULT_EDIT_MODEL)
    chat_id = data.get("chat_id", ADMIN_ID)
    if not image_url or not prompt:
        return jsonify({"error": "image_url and prompt are required"}), 400

    def background_edit():
        try:
            success, result, url = edit_image(image_url, prompt, model)
            bot = Bot(token=BOT_TOKEN)
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            if success:
                with open(result, "rb") as photo:
                    loop.run_until_complete(
                        bot.send_photo(
                            chat_id=chat_id,
                            photo=photo,
                            caption=f"\u270f\ufe0f Edit | {prompt[:150]}",
                            parse_mode="Markdown",
                        )
                    )
            else:
                loop.run_until_complete(
                    bot.send_message(chat_id=chat_id, text=f"\u274c Edit failed: {result[:300]}")
                )
            loop.close()
        except Exception as e:
            pass

    t = threading.Thread(target=background_edit, daemon=True)
    t.start()

    return jsonify({
        "status": "queued",
        "message": f"Edit started. Result will be sent to @BobDesignAgentbot (chat {chat_id})",
    })


def run_flask_api():
    flask_api.run(host="127.0.0.1", port=API_PORT, debug=False, use_reloader=False)

# =============================================================================
# Telegram keyboard helpers
# =============================================================================

def model_keyboard():
    buttons = []
    for key, info in MODELS.items():
        label = f"{info['emoji']} {key} ({info['price']})"
        buttons.append(InlineKeyboardButton(label, callback_data=f"gen:{key}"))
    return InlineKeyboardMarkup([buttons])


def post_gen_keyboard(model_key):
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("\U0001f504 Again", callback_data=f"regen:{model_key}"),
            InlineKeyboardButton("\U0001f3a8 Other model", callback_data="pick"),
        ],
        [
            InlineKeyboardButton("\u270f\ufe0f Edit", callback_data="editlast"),
        ],
    ])

# =============================================================================
# Telegram handlers
# =============================================================================

async def tg_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("\U0001f3a8 Generate", callback_data="mode:gen"),
         InlineKeyboardButton("\u270f\ufe0f Edit", callback_data="mode:edit")],
        [InlineKeyboardButton("\U0001f4ca Stats", callback_data="mode:stats"),
         InlineKeyboardButton("\u2139\ufe0f Models", callback_data="mode:models")],
    ])
    await update.message.reply_text(
        "\U0001f3a8 *DesignerBot v2*\n\n"
        "Image generation & editing\n\n"
        "Send *text* to generate\n"
        "Send *photo + caption* to edit\n"
        "`/gen prompt` or `/gen prompt | model`",
        parse_mode="Markdown", reply_markup=kb,
    )


async def tg_models(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "\U0001f3a8 *Generation (polza.ai):*\n"
    for key, info in MODELS.items():
        text += f"- `{key}` — {info['id']} ({info['price']})\n"
    text += "\n\u270f\ufe0f *Editing (WaveSpeed):*\n"
    for key, info in EDIT_MODELS.items():
        text += f"- `{key}` — {info['id']} ({info['price']})\n"
    ws = "ok" if WAVESPEED_API_KEY else "no key"
    text += f"\nWaveSpeed: {ws}"
    await update.message.reply_text(text, parse_mode="Markdown")


async def tg_generate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return
    raw = update.message.text
    for prefix in ["/gen ", "/generate "]:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    else:
        await update.message.reply_text("Usage: `/gen prompt` or `/gen prompt | model`", parse_mode="Markdown")
        return

    if "|" in raw:
        parts = raw.rsplit("|", 1)
        prompt, model_key = parts[0].strip(), parts[1].strip().lower()
        if model_key not in MODELS:
            await update.message.reply_text(f"Unknown model `{model_key}`. Available: {', '.join(MODELS.keys())}", parse_mode="Markdown")
            return
    else:
        prompt, model_key = raw.strip(), DEFAULT_MODEL

    if not prompt:
        return
    await _do_generate(update.message, prompt, model_key, context)


async def _do_generate(message, prompt, model_key, context=None):
    emoji = MODELS.get(model_key, {}).get("emoji", "\U0001f3a8")
    msg = await message.reply_text(f"{emoji} Generating `{model_key}`...\n_{prompt[:80]}_", parse_mode="Markdown")

    success, result, url = generate_image(prompt, model_key)

    if success:
        if context:
            context.user_data["last_prompt"] = prompt
            context.user_data["last_url"] = url
            context.user_data["last_model"] = model_key
        kb = post_gen_keyboard(model_key)
        with open(result, "rb") as photo:
            await message.reply_photo(photo=photo, caption=f"`{model_key}` | {prompt[:100]}", parse_mode="Markdown", reply_markup=kb)
        await msg.delete()
    else:
        await msg.edit_text(f"Error: {result[:300]}")


async def tg_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "edit"
    await update.message.reply_text(
        "\u270f\ufe0f *Edit mode*\n\nSend photo with caption.\nExit: `/gen` or `/start`",
        parse_mode="Markdown",
    )


async def tg_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.photo:
        return
    caption = (update.message.caption or "").strip()
    if not caption:
        await update.message.reply_text("Add a caption describing what to change.")
        return
    if not WAVESPEED_API_KEY:
        await update.message.reply_text("WaveSpeed API key not set.")
        return

    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    tg_url = file.file_path

    msg = await update.message.reply_text(f"\u270f\ufe0f Editing...\n_{caption[:80]}_", parse_mode="Markdown")
    success, result, url = edit_image(tg_url, caption)

    if success:
        with open(result, "rb") as pf:
            await update.message.reply_photo(pf, caption=f"\u270f\ufe0f {caption[:100]}", parse_mode="Markdown")
        await msg.delete()
    else:
        await msg.edit_text(f"Error: {result[:300]}")


async def tg_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("gen:") or data.startswith("regen:"):
        model_key = data.split(":", 1)[1]
        prompt = context.user_data.get("last_prompt", "")
        if prompt:
            await _do_generate(query.message, prompt, model_key, context)

    elif data == "pick":
        await query.message.reply_text("Choose model:", reply_markup=model_keyboard())

    elif data == "editlast":
        url = context.user_data.get("last_url", "")
        if url:
            context.user_data["edit_url"] = url
            context.user_data["mode"] = "edit_url"
            await query.message.reply_text("Send text describing what to change.", parse_mode="Markdown")

    elif data == "mode:gen":
        context.user_data["mode"] = "gen"
        await query.message.reply_text("Send text to generate!")

    elif data == "mode:edit":
        context.user_data["mode"] = "edit"
        await query.message.reply_text("Send photo with caption.")

    elif data == "mode:stats":
        conn = sqlite3.connect(DB_PATH)
        total = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
        by_model = conn.execute("SELECT model, COUNT(*) FROM generations GROUP BY model").fetchall()
        conn.close()
        text = f"\U0001f4ca *Stats* — {total} total\n"
        for m, cnt in by_model:
            text += f"- {m}: {cnt}\n"
        await query.message.reply_text(text, parse_mode="Markdown")

    elif data == "mode:models":
        text = "\U0001f3a8 *Generation:*\n"
        for key, info in MODELS.items():
            text += f"- `{key}` ({info['price']})\n"
        await query.message.reply_text(text, parse_mode="Markdown")


async def tg_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message or not update.message.text:
        return
    text = update.message.text.strip()
    if not text:
        return

    mode = context.user_data.get("mode", "gen")

    if mode == "edit_url":
        url = context.user_data.get("edit_url", "")
        if not url or not WAVESPEED_API_KEY:
            await update.message.reply_text("No image to edit or no API key.")
            return
        msg = await update.message.reply_text(f"\u270f\ufe0f Editing...\n_{text[:80]}_", parse_mode="Markdown")
        success, result, new_url = edit_image(url, text)
        if success:
            context.user_data["edit_url"] = new_url
            with open(result, "rb") as photo:
                await update.message.reply_photo(photo, caption=f"\u270f\ufe0f {text[:100]}", parse_mode="Markdown")
            await msg.delete()
        else:
            await msg.edit_text(f"Error: {result[:300]}")
        context.user_data["mode"] = "gen"
    else:
        await _do_generate(update.message, text, DEFAULT_MODEL, context)


async def tg_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    total = conn.execute("SELECT COUNT(*) FROM generations").fetchone()[0]
    by_model = conn.execute("SELECT model, COUNT(*) FROM generations GROUP BY model").fetchall()
    conn.close()
    text = f"\U0001f4ca *Stats* — {total} total\n"
    for m, cnt in by_model:
        text += f"- {m}: {cnt}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# =============================================================================
# Main
# =============================================================================

def main():
    if not BOT_TOKEN:
        print("DESIGNER_BOT_TOKEN not set!")
        sys.exit(1)

    init_db()

    # Start Flask API in background thread
    api_thread = threading.Thread(target=run_flask_api, daemon=True)
    api_thread.start()
    print(f"HTTP API running on http://127.0.0.1:{API_PORT}")

    # Start Telegram bot
    print(f"DesignerBot v2 | Models: {list(MODELS.keys())} | Edit: {list(EDIT_MODELS.keys())}")
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", tg_start))
    app.add_handler(CommandHandler("gen", tg_generate))
    app.add_handler(CommandHandler("generate", tg_generate))
    app.add_handler(CommandHandler("edit", tg_edit))
    app.add_handler(CommandHandler("models", tg_models))
    app.add_handler(CommandHandler("stats", tg_stats))
    app.add_handler(CallbackQueryHandler(tg_callback))
    app.add_handler(MessageHandler(filters.PHOTO, tg_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, tg_text))

    print("DesignerBot v2 started (Telegram + HTTP API)")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
