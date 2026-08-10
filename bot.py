import os
import json
import logging
import threading
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"
ADMIN_ID = int(os.getenv("ADMIN_ID") or 0)

USERS_FILE = "users.json"
WORDS_FILE = "words.json"
SETTINGS_FILE = "settings.json"

logging.basicConfig(level=logging.INFO)

flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Bot Running 24/7"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, "r") as f:
                return json.load(f)
        except:
            return default
    return default

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=2)

ALLOWED_USERS = load_json(USERS_FILE, {})
BANNED_WORDS = load_json(WORDS_FILE, ["spam", "abuse"])
SETTINGS = load_json(SETTINGS_FILE, {"allow_photos": True, "allow_videos": True})

def save_all():
    save_json(USERS_FILE, ALLOWED_USERS)
    save_json(WORDS_FILE, BANNED_WORDS)
    save_json(SETTINGS_FILE, SETTINGS)

def clean_id(raw):
    s = raw.strip().strip('<>').strip()
    s = ''.join(filter(str.isdigit, s))
    return s

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        await update.message.reply_text(
            "👑 ACTIVATION BOT - ADMIN PANEL\n"
            f"Photo Sharing: {'ON ✅' if SETTINGS['allow_photos'] else 'OFF ❌'}\n\n"
            "Commands:\n"
            "/adduser <id> - Add user (Ex: /adduser 871721883)\n"
            "/removeuser <id> - Remove user\n"
            "/users - List users\n"
            "/addword <word> - Add banned (comma for multiple)\n"
            "/removeword <word> - Remove banned\n"
            "/words - Show banned words\n"
            "/clearwords - Clear all banned words\n"
            "/togglephoto - ON/OFF photo sharing\n"
            "/myid - Get your ID",
            protect_content=True
        )
    elif str(uid) in ALLOWED_USERS:
        label = ALLOWED_USERS[str(uid)].upper()
        await update.message.reply_text(
            f"✅ WELCOME {label}! YOU ARE CONNECTED.",
            protect_content=True
        )
    else:
        await update.message.reply_text(
            f"YOUR ID: `{uid}`\nPLEASE SEND THIS ID TO ADMIN FOR ACCESS.",
            parse_mode="Markdown",
            protect_content=True
        )

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"YOUR TELEGRAM ID: `{update.effective_user.id}`", parse_mode="Markdown", protect_content=True)

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("USAGE: /adduser <user_id> EXAMPLE: /adduser 871721883", protect_content=True)
        return
    if len(ALLOWED_USERS) >= 4:
        await update.message.reply_text("❌ USER LIMIT REACHED (MAX 4).", protect_content=True)
        return
    nid = clean_id(context.args[0])
    if not nid:
        await update.message.reply_text("❌ INVALID ID.", protect_content=True)
        return
    ALLOWED_USERS[nid] = f"User {len(ALLOWED_USERS)+1}"
    save_all()
    await update.message.reply_text(f"✅ {ALLOWED_USERS[nid].upper()} ADDED. ID: {nid}", protect_content=True)
    try:
        await context.bot.send_message(int(nid), f"✅ YOU HAVE BEEN ADDED AS {ALLOWED_USERS[nid].upper()}. SEND /start", protect_content=True)
    except:
        pass

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("USAGE: /removeuser <id>", protect_content=True)
        return
    rid = clean_id(context.args[0])
    to_del = rid if rid in ALLOWED_USERS else next((k for k in ALLOWED_USERS if rid in k), None)
    if to_del:
        del ALLOWED_USERS[to_del]
        save_all()
        await update.message.reply_text(f"✅ REMOVED: {to_del}", protect_content=True)
    else:
        await update.message.reply_text(f"❌ ID {rid} NOT FOUND.", protect_content=True)

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not ALLOWED_USERS:
        await update.message.reply_text("NO USERS ADDED YET.", protect_content=True)
        return
    txt = "\n".join([f"👤 {v.upper()}: {k}" for k,v in ALLOWED_USERS.items()])
    await update.message.reply_text(f"📋 ADDED USERS:\n{txt}", protect_content=True)

async def add_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("USAGE: /addword word1, word2, word3 EXAMPLE: /addword spam, whatsapp, user id", protect_content=True)
        return
    full_text = " ".join(context.args)
    words = [w.strip().lower() for w in full_text.split(',') if w.strip()]
    added = []
    for w in words:
        if w not in BANNED_WORDS:
            BANNED_WORDS.append(w)
            added.append(w)
    if added:
        save_all()
        msg = "✅ BANNED WORDS ADDED (%d):\n" % len(added) + "\n".join(["- " + w.upper() for w in added])
        await update.message.reply_text(msg, protect_content=True)
    else:
        await update.message.reply_text("⚠️ ALL WORDS ALREADY IN BANNED LIST.", protect_content=True)

async def remove_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("USAGE: /removeword word1, word2", protect_content=True)
        return
    full_text = " ".join(context.args)
    words = [w.strip().lower() for w in full_text.split(',') if w.strip()]
    removed = []
    for w in words:
        if w in BANNED_WORDS:
            BANNED_WORDS.remove(w)
            removed.append(w)
    if removed:
        save_all()
        msg = "✅ REMOVED (%d):\n" % len(removed) + "\n".join(["- " + w.upper() for w in removed])
        await update.message.reply_text(msg, protect_content=True)
    else:
        await update.message.reply_text("❌ WORDS NOT FOUND.", protect_content=True)

async def clear_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    BANNED_WORDS.clear()
    save_all()
    await update.message.reply_text("✅ ALL BANNED WORDS CLEARED.", protect_content=True)

async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not BANNED_WORDS:
        txt = "NO BANNED WORDS"
    else:
        txt = "\n".join(["- " + w.upper() for w in BANNED_WORDS])
    await update.message.reply_text(f"🚫 BANNED WORDS ({len(BANNED_WORDS)}):\n{txt}", protect_content=True)

async def toggle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    SETTINGS["allow_photos"] = not SETTINGS["allow_photos"]
    save_all()
    await update.message.reply_text(f"PHOTO SHARING: {'ON ✅' if SETTINGS['allow_photos'] else 'OFF ❌'}", protect_content=True)

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sid = str(uid)
    is_admin = (uid == ADMIN_ID)
    if not is_admin and sid not in ALLOWED_USERS:
        return
    text_content = update.message.text or update.message.caption or ""
    if not text_content and not update.message.photo and not update.message.video and not update.message.document:
        return
    for bw in BANNED_WORDS:
        if bw in text_content.lower():
            await update.message.reply_text(f"⚠️ MESSAGE BLOCKED - BANNED WORD: '{bw.upper()}'", protect_content=True)
            try:
                await context.bot.send_message(ADMIN_ID, f"🚨 {ALLOWED_USERS.get(sid, sid).upper()} TRIED TO SEND BANNED WORD '{bw.upper()}': {text_content[:200]}", protect_content=True)
            except:
                pass
            return
    if not is_admin and update.message.photo and not SETTINGS["allow_photos"]:
        await update.message.reply_text("❌ PHOTO SHARING IS OFF BY ADMIN.", protect_content=True)
        return
    USER_ICONS = {
        "USER 1": "👤",
        "USER 2": "👨‍💼",
        "USER 3": "🧑‍🔧",
        "USER 4": "👨‍💻"
    }
    if is_admin:
        raw_label = "ADMIN"
        icon = "👑"
    else:
        raw_label = ALLOWED_USERS.get(sid, sid).upper()
        icon = USER_ICONS.get(raw_label, "👤")
    if text_content:
        formatted_text = f"{icon} <b>{raw_label}</b>: {text_content}"
    else:
        formatted_text = f"{icon} <b>{raw_label}</b> SENT A PHOTO 📸"
    targets = list(ALLOWED_USERS.keys()) + ([str(ADMIN_ID)] if not is_admin else [])
    for tid in targets:
        if tid == sid:
            continue
        try:
            if update.message.photo:
                await context.bot.send_photo(int(tid), update.message.photo[-1].file_id, caption=formatted_text, parse_mode="HTML", protect_content=True)
            elif update.message.video:
                await context.bot.send_video(int(tid), update.message.video.file_id, caption=formatted_text, parse_mode="HTML", protect_content=True)
            elif update.message.document:
                await context.bot.send_document(int(tid), update.message.document.file_id, caption=formatted_text, parse_mode="HTML", protect_content=True)
            else:
                await context.bot.send_message(int(tid), formatted_text, parse_mode="HTML", protect_content=True)
        except Exception as e:
            logging.error(e)

def main():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except:
        pass
    threading.Thread(target=run_flask, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", get_my_id))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("users", list_users))
    app.add_handler(CommandHandler("addword", add_word))
    app.add_handler(CommandHandler("removeword", remove_word))
    app.add_handler(CommandHandler("words", list_words))
    app.add_handler(CommandHandler("clearwords", clear_words))
    app.add_handler(CommandHandler("togglephoto", toggle_photo))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_chat))
    print("Bot Started - Fixed SyntaxError + Bold Only Label + Multi Banned Words")
    app.run_polling(stop_signals=None, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
