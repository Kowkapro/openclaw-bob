#!/usr/bin/env python3
# =============================================================================
# DesignerBot v2 — Image generation (polza.ai) + editing (WaveSpeed Nano-Banana)
# =============================================================================

import os
import sys
import time
import requests
import sqlite3
from datetime import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler,
    ContextTypes, MessageHandler, filters,
)

# =============================================================================
# Settings
# =============================================================================

WORKSPACE = Path("/home/openclaw/.openclaw/workspace")
BOT_TOKEN = os.getenv("DESIGNER_BOT_TOKEN", "")
POLZA_API_KEY = os.getenv("POLZA_API_KEY", "pza__BQDqwgxIhZ7zegdQsExE2Vd5lnrAkM2")
WAVESPEED_API_KEY = os.getenv("WAVESPEED_API_KEY", "")

ADMIN_ID = 1039905495

POLZA_BASE_URL = "https://polza.ai/api/v1/media"
WAVESPEED_BASE_URL = "https://api.wavespeed.ai/api/v3"

# Generation models (polza.ai /api/v1/media)
MODELS = {
    "gpt-image": {"id": "openai/gpt-image-1.5", "price": "~3₽", "emoji": "🖼"},
    "gpt5": {"id": "openai/gpt-5-image-mini", "price": "~4₽", "emoji": "🎯"},
    "seedream": {"id": "bytedance/seedream-4.5", "price": "~5₽", "emoji": "🌀"},
}
DEFAULT_MODEL = "gpt-image"

# Editing models (WaveSpeed)
EDIT_MODELS = {
    "nano-banana": {"id": "google/nano-banana/edit", "price": "~3.5₽"},
    "nano-banana-fast": {"id": "google/nano-banana-2/edit/fast", "price": "~3.5₽"},
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
    # Migrate old tables missing new columns
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
    c = conn.cursor()
    c.execute(
        'INSERT INTO generations (prompt,model,output_path,image_url,mode,admin_id) VALUES (?,?,?,?,?,?)',
        (prompt, model, str(output_path), image_url, mode, str(ADMIN_ID)),
    )
    conn.commit()
    conn.close()

# =============================================================================
# Image generation (polza.ai)
# =============================================================================

def generate_image(prompt: str, model_key: str = DEFAULT_MODEL) -> tuple:
    headers = {
        "Authorization": f"Bearer {POLZA_API_KEY}",
        "Content-Type": "application/json",
    }
    model_id = MODELS.get(model_key, MODELS[DEFAULT_MODEL])["id"]
    payload = {"model": model_id, "input": {"prompt": prompt, "aspect_ratio": "1:1"}}

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

def edit_image(image_url: str, prompt: str, model_key: str = DEFAULT_EDIT_MODEL) -> tuple:
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

        # Sync mode: outputs directly in response
        if data.get("status") == "completed" and data.get("outputs"):
            url = data["outputs"][0]
        elif data.get("id"):
            # Async fallback: poll for result
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
# Keyboard helpers (callback_data max 64 bytes — store data in user_data)
# =============================================================================

def model_keyboard() -> InlineKeyboardMarkup:
    """Model selection buttons — prompt is in user_data['last_prompt']."""
    buttons = []
    for key, info in MODELS.items():
        label = f"{info['emoji']} {key} ({info['price']})"
        buttons.append(InlineKeyboardButton(label, callback_data=f"gen:{key}"))
    return InlineKeyboardMarkup([buttons])


def post_gen_keyboard(model_key: str) -> InlineKeyboardMarkup:
    """Buttons after generation — prompt/url stored in user_data."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔄 Ещё раз", callback_data=f"regen:{model_key}"),
            InlineKeyboardButton("🎨 Другая модель", callback_data="pick"),
        ],
        [
            InlineKeyboardButton("✏️ Редактировать", callback_data="editlast"),
        ],
    ])

# =============================================================================
# Telegram handlers
# =============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎨 Генерация", callback_data="mode:gen"),
         InlineKeyboardButton("✏️ Редактирование", callback_data="mode:edit")],
        [InlineKeyboardButton("📊 Статистика", callback_data="mode:stats"),
         InlineKeyboardButton("ℹ️ Модели", callback_data="mode:models")],
    ])
    await update.message.reply_text(
        "🎨 *DesignerBot v2*\n\n"
        "Генерация и редактирование изображений\n\n"
        "• Отправь *текст* — сгенерирую картинку\n"
        "• Отправь *фото + подпись* — отредактирую через Nano-Banana\n"
        "• `/gen промпт` или `/gen промпт | модель`\n"
        "• `/edit` — режим редактирования",
        parse_mode="Markdown", reply_markup=kb,
    )


async def models_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🎨 *Генерация (polza.ai):*\n"
    for key, info in MODELS.items():
        text += f"• `{key}` — {info['id']} ({info['price']})\n"
    text += "\n✏️ *Редактирование (WaveSpeed):*\n"
    for key, info in EDIT_MODELS.items():
        text += f"• `{key}` — {info['id']} ({info['price']})\n"
    ws_status = "✅" if WAVESPEED_API_KEY else "❌ нет ключа"
    text += f"\nWaveSpeed: {ws_status}"
    await update.message.reply_text(text, parse_mode="Markdown")


async def generate_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    raw = update.message.text
    for prefix in ["/gen ", "/generate "]:
        if raw.startswith(prefix):
            raw = raw[len(prefix):]
            break
    else:
        await update.message.reply_text("Использование: `/gen промпт` или `/gen промпт | модель`", parse_mode="Markdown")
        return

    if "|" in raw:
        parts = raw.rsplit("|", 1)
        prompt, model_key = parts[0].strip(), parts[1].strip().lower()
        if model_key not in MODELS:
            await update.message.reply_text(f"Модель `{model_key}` не найдена. Доступные: {', '.join(MODELS.keys())}", parse_mode="Markdown")
            return
    else:
        prompt, model_key = raw.strip(), DEFAULT_MODEL

    if not prompt:
        await update.message.reply_text("Нужен промпт!", parse_mode="Markdown")
        return

    await _do_generate(update.message, prompt, model_key, context)


async def _do_generate(message, prompt, model_key, context=None):
    """Shared generation logic."""
    emoji = MODELS.get(model_key, {}).get("emoji", "🎨")
    msg = await message.reply_text(f"{emoji} Генерирую `{model_key}`...\n_{prompt[:80]}_", parse_mode="Markdown")

    success, result, url = generate_image(prompt, model_key)

    if success:
        # Store in user_data for buttons
        if context:
            context.user_data["last_prompt"] = prompt
            context.user_data["last_url"] = url
            context.user_data["last_model"] = model_key
        kb = post_gen_keyboard(model_key)
        with open(result, "rb") as photo:
            await message.reply_photo(
                photo=photo,
                caption=f"✨ `{model_key}` | {prompt[:100]}",
                parse_mode="Markdown",
                reply_markup=kb,
            )
        await msg.delete()
    else:
        await msg.edit_text(f"❌ {result[:300]}")


async def edit_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["mode"] = "edit"
    await update.message.reply_text(
        "✏️ *Режим редактирования*\n\n"
        "Отправь фото с подписью — что изменить.\n"
        "Например: фото + _\"добавь солнечные очки\"_\n\n"
        "Для выхода: `/gen` или `/start`",
        parse_mode="Markdown",
    )


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Photo with caption → edit via Nano-Banana."""
    if not update.message or not update.message.photo:
        return

    caption = (update.message.caption or "").strip()
    if not caption:
        await update.message.reply_text("Добавь подпись к фото — что изменить?\nНапример: _\"сделай фон красным\"_", parse_mode="Markdown")
        return

    if not WAVESPEED_API_KEY:
        await update.message.reply_text("❌ WaveSpeed API ключ не настроен")
        return

    # Get photo file URL from Telegram
    photo = update.message.photo[-1]
    file = await context.bot.get_file(photo.file_id)
    tg_url = file.file_path  # Telegram CDN URL

    msg = await update.message.reply_text(f"✏️ Редактирую через Nano-Banana...\n_{caption[:80]}_", parse_mode="Markdown")

    success, result, url = edit_image(tg_url, caption)

    if success:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✏️ Ещё правка", callback_data=f"editstart:{url[:200]}")],
        ])
        with open(result, "rb") as photo_file:
            await update.message.reply_photo(
                photo=photo_file,
                caption=f"✏️ Nano-Banana | {caption[:100]}",
                parse_mode="Markdown",
                reply_markup=kb,
            )
        await msg.delete()
    else:
        await msg.edit_text(f"❌ {result[:300]}")


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Plain text → generate with default model."""
    if not update.message or not update.message.text:
        return
    prompt = update.message.text.strip()
    if not prompt:
        return
    await _do_generate(update.message, prompt, DEFAULT_MODEL, context)


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle inline button presses."""
    query = update.callback_query
    await query.answer()
    data = query.data

    if data.startswith("gen:"):
        # gen:model_key — prompt from user_data
        model_key = data.split(":", 1)[1]
        prompt = context.user_data.get("last_prompt", "")
        if prompt:
            await _do_generate(query.message, prompt, model_key, context)

    elif data.startswith("regen:"):
        # regen:model_key — same prompt, same/different model
        model_key = data.split(":", 1)[1]
        prompt = context.user_data.get("last_prompt", "")
        if prompt:
            await _do_generate(query.message, prompt, model_key, context)

    elif data == "pick":
        # Show model selection
        kb = model_keyboard()
        await query.message.reply_text("Выбери модель:", reply_markup=kb)

    elif data == "editlast":
        # Edit last generated image
        url = context.user_data.get("last_url", "")
        if url:
            context.user_data["edit_url"] = url
            context.user_data["mode"] = "edit_url"
            await query.message.reply_text(
                "✏️ Отправь текст — что изменить в этой картинке?\n"
                "Например: _\"добавь солнечные очки\"_",
                parse_mode="Markdown",
            )
        else:
            await query.message.reply_text("Отправь фото с подписью для редактирования")

    elif data == "mode:gen":
        await query.message.reply_text("Отправь текст — сгенерирую картинку!")
        context.user_data["mode"] = "gen"

    elif data == "mode:edit":
        context.user_data["mode"] = "edit"
        await query.message.reply_text(
            "✏️ Отправь фото с подписью — что изменить.",
            parse_mode="Markdown",
        )

    elif data == "mode:stats":
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT COUNT(*) FROM generations")
        total = c.fetchone()[0]
        c.execute("SELECT model, COUNT(*) FROM generations GROUP BY model")
        by_model = c.fetchall()
        c.execute("SELECT mode, COUNT(*) FROM generations GROUP BY mode")
        by_mode = c.fetchall()
        conn.close()
        text = f"📊 *Статистика*\n\n🖼 Всего: {total}\n"
        if by_model:
            text += "\n*По моделям:*\n"
            for m, cnt in by_model:
                text += f"• {m}: {cnt}\n"
        if by_mode:
            text += "\n*По режиму:*\n"
            for m, cnt in by_mode:
                text += f"• {m}: {cnt}\n"
        await query.message.reply_text(text, parse_mode="Markdown")

    elif data == "mode:models":
        text = "🎨 *Генерация:*\n"
        for key, info in MODELS.items():
            text += f"• `{key}` ({info['price']})\n"
        text += "\n✏️ *Редактирование:*\n"
        for key, info in EDIT_MODELS.items():
            text += f"• `{key}` ({info['price']})\n"
        await query.message.reply_text(text, parse_mode="Markdown")


async def handle_text_or_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route text based on current mode."""
    if not update.message or not update.message.text:
        return

    text = update.message.text.strip()
    if not text:
        return

    mode = context.user_data.get("mode", "gen")

    if mode == "edit_url":
        # User is sending edit instruction for a previously generated image
        url = context.user_data.get("edit_url", "")
        if not url:
            await update.message.reply_text("Нет картинки для редактирования. Отправь фото.")
            return
        if not WAVESPEED_API_KEY:
            await update.message.reply_text("❌ WaveSpeed API ключ не настроен")
            return

        msg = await update.message.reply_text(f"✏️ Редактирую...\n_{text[:80]}_", parse_mode="Markdown")
        success, result, new_url = edit_image(url, text)

        if success:
            context.user_data["edit_url"] = new_url  # Chain edits
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton("✏️ Ещё правка", callback_data=f"editstart:{new_url[:200]}")],
                [InlineKeyboardButton("🎨 Новая генерация", callback_data="mode:gen")],
            ])
            with open(result, "rb") as photo:
                await update.message.reply_photo(
                    photo=photo, caption=f"✏️ {text[:100]}",
                    parse_mode="Markdown", reply_markup=kb,
                )
            await msg.delete()
        else:
            await msg.edit_text(f"❌ {result[:300]}")

        context.user_data["mode"] = "gen"  # Reset after edit
    else:
        # Default: generate
        await _do_generate(update.message, text, DEFAULT_MODEL, context)


async def list_images(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not SAVE_DIR.exists():
        await update.message.reply_text("Нет изображений")
        return
    images = sorted(SAVE_DIR.glob("*.png"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not images:
        await update.message.reply_text("Нет изображений")
        return
    text = "📸 *Последние:*\n\n"
    for img in images[:10]:
        size = img.stat().st_size / 1024
        text += f"• `{img.name}` ({size:.0f} KB)\n"
    await update.message.reply_text(text, parse_mode="Markdown")


async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM generations")
    total = c.fetchone()[0]
    c.execute("SELECT model, COUNT(*) FROM generations GROUP BY model")
    by_model = c.fetchall()
    conn.close()
    text = f"📊 *Статистика*\n\n🖼 Всего: {total}\n"
    if by_model:
        for m, cnt in by_model:
            text += f"• {m}: {cnt}\n"
    await update.message.reply_text(text, parse_mode="Markdown")

# =============================================================================
# Main
# =============================================================================

def main():
    if not BOT_TOKEN:
        print("DESIGNER_BOT_TOKEN not set!")
        sys.exit(1)

    init_db()
    print(f"DesignerBot v2 | Models: {list(MODELS.keys())} | Edit: {list(EDIT_MODELS.keys())}")
    print(f"Polza: {POLZA_BASE_URL} | WaveSpeed: {'OK' if WAVESPEED_API_KEY else 'NO KEY'}")

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("gen", generate_cmd))
    app.add_handler(CommandHandler("generate", generate_cmd))
    app.add_handler(CommandHandler("edit", edit_cmd))
    app.add_handler(CommandHandler("models", models_cmd))
    app.add_handler(CommandHandler("list", list_images))
    app.add_handler(CommandHandler("stats", stats))
    app.add_handler(CallbackQueryHandler(handle_callback))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_or_edit))

    print("Starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
