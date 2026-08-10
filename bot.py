import os
import json
import logging
import threading
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN") or "APNA_BOT_TOKEN_YAHAN_DALO"
ADMIN_ID = int(os.getenv("ADMIN_ID") or 0)

USERS_FILE = "users.json"
WORDS_FILE = "words.json"
SETTINGS_FILE = "settings.json"

logging.basicConfig(level=logging.INFO)

# --- Flask for Render/Koyeb 24/7 ---
flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "✅ Activation Bot is Running 24/7 - Photo Sharing ON"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    flask_app.run(host='0.0.0.0', port=port)

# --- JSON Storage ---
def load_json(file, default):
    if os.path.exists(file):
        try:
            with open(file, "r") as f: return json.load(f)
        except: return default
    return default

def save_json(file, data):
    with open(file, "w") as f: json.dump(data, f, indent=2)

ALLOWED_USERS = load_json(USERS_FILE, {})
BANNED_WORDS = load_json(WORDS_FILE, ["spam", "gaali"])
SETTINGS = load_json(SETTINGS_FILE, {"allow_photos": True, "allow_videos": True})

def save_all():
    save_json(USERS_FILE, ALLOWED_USERS)
    save_json(WORDS_FILE, BANNED_WORDS)
    save_json(SETTINGS_FILE, SETTINGS)

# --- Commands (same as V2) ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if uid == ADMIN_ID:
        await update.message.reply_text(f"👑 Activation Bot Admin\nPhoto: {'ON ✅' if SETTINGS['allow_photos'] else 'OFF ❌'}\n/adduser <id> /removeuser /users /addword /removeword /words /togglephoto /broadcast")
    elif str(uid) in ALLOWED_USERS:
        await update.message.reply_text(f"✅ Welcome {ALLOWED_USERS[str(uid)]}! Text + Photo bhej sakte ho. ID hidden rahegi.")
    else:
        await update.message.reply_text(f"ID: `{uid}` - Admin ko bhejo", parse_mode="Markdown")

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"ID: `{update.effective_user.id}`", parse_mode="Markdown")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if not context.args or len(ALLOWED_USERS) >= 4:
        await update.message.reply_text("Use: /adduser <id> or Limit Full (4)")
        return
    nid = context.args[0].strip()
    ALLOWED_USERS[nid] = f"User {len(ALLOWED_USERS)+1}"
    save_all()
    await update.message.reply_text(f"✅ {ALLOWED_USERS[nid]} added: {nid}")
    try: await context.bot.send_message(int(nid), f"✅ Aap {ALLOWED_USERS[nid]} ke roop me add ho gaye.")
    except: pass

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if context.args and context.args[0] in ALLOWED_USERS:
        del ALLOWED_USERS[context.args[0]]; save_all()
        await update.message.reply_text("✅ Removed")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    txt = "\n".join([f"{v}: {k}" for k,v in ALLOWED_USERS.items()]) or "Empty"
    await update.message.reply_text(f"Users:\n{txt}")

async def add_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if context.args:
        w = " ".join(context.args).lower()
        if w not in BANNED_WORDS: BANNED_WORDS.append(w); save_all()
        await update.message.reply_text(f"✅ Banned: {w}")

async def remove_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    if context.args:
        w = " ".join(context.args).lower()
        if w in BANNED_WORDS: BANNED_WORDS.remove(w); save_all()
        await update.message.reply_text(f"✅ Removed: {w}")

async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    await update.message.reply_text("Banned:\n" + "\n".join(BANNED_WORDS))

async def toggle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID: return
    SETTINGS["allow_photos"] = not SETTINGS["allow_photos"]; save_all()
    await update.message.reply_text(f"Photo: {'ON ✅' if SETTINGS['allow_photos'] else 'OFF ❌'}")

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id; sid = str(uid)
    is_admin = (uid == ADMIN_ID)
    if not is_admin and sid not in ALLOWED_USERS: return
    text_content = update.message.text or update.message.caption or ""
    # Banned check
    for bw in BANNED_WORDS:
        if bw in text_content.lower():
            await update.message.reply_text(f"⚠️ Blocked - banned word '{bw}'")
            try: await context.bot.send_message(ADMIN_ID, f"🚨 {ALLOWED_USERS.get(sid, sid)} ne '{bw}' bheja: {text_content[:200]}")
            except: pass
            return
    if not is_admin and update.message.photo and not SETTINGS["allow_photos"]:
        await update.message.reply_text("❌ Photo OFF hai"); return

    label = "👑 Admin" if is_admin else ALLOWED_USERS.get(sid, sid)
    caption = f"{label}: {text_content}" if text_content else f"{label} ne photo bheji 📸"
    targets = list(ALLOWED_USERS.keys()) + ([str(ADMIN_ID)] if not is_admin else [])
    for tid in targets:
        if tid == sid: continue
        try:
            if update.message.photo:
                await context.bot.send_photo(int(tid), update.message.photo[-1].file_id, caption=caption)
            elif update.message.video:
                await context.bot.send_video(int(tid), update.message.video.file_id, caption=caption)
            elif update.message.document:
                await context.bot.send_document(int(tid), update.message.document.file_id, caption=caption)
            else:
                await context.bot.send_message(int(tid), f"{label}: {text_content}")
        except Exception as e: logging.error(e)

def main():
    threading.Thread(target=run_flask, daemon=True).start()
    if "APNA_BOT" in BOT_TOKEN or ADMIN_ID == 0:
        print("WARNING: Set BOT_TOKEN and ADMIN_ID in ENV")
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", get_my_id))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("users", list_users))
    app.add_handler(CommandHandler("addword", add_word))
    app.add_handler(CommandHandler("removeword", remove_word))
    app.add_handler(CommandHandler("words", list_words))
    app.add_handler(CommandHandler("togglephoto", toggle_photo))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_chat))
    print("Bot + Flask Started for 24/7 hosting")
    app.run_polling()

if __name__ == "__main__":
    main()
