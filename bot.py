import os
import json
import logging
import threading
import asyncio
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ContextTypes
from telegram.error import BadRequest

BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"
ADMIN_ID = int(os.getenv("ADMIN_ID") or 0)

USERS_FILE = "users.json"
WORDS_FILE = "words.json"
SETTINGS_FILE = "settings.json"
PENDING_FILE = "pending.json"
ACTIVITY_FILE = "activity.json"

logging.basicConfig(level=logging.INFO)

flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Bot Running 24/7 - V5 With Add Button"

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
PENDING_USERS = load_json(PENDING_FILE, {})
ACTIVITY = load_json(ACTIVITY_FILE, {})

def save_all():
    save_json(USERS_FILE, ALLOWED_USERS)
    save_json(WORDS_FILE, BANNED_WORDS)
    save_json(SETTINGS_FILE, SETTINGS)
    save_json(PENDING_FILE, PENDING_USERS)
    save_json(ACTIVITY_FILE, ACTIVITY)

def clean_id(raw):
    s = raw.strip().strip('<>').strip()
    s = ''.join(filter(str.isdigit, s))
    return s

# ===== ONLINE STATUS (3 MIN) =====
def update_activity(uid):
    ACTIVITY[str(uid)] = datetime.now().isoformat()
    save_json(ACTIVITY_FILE, ACTIVITY)

def get_online_status(uid):
    uid_str = str(uid)
    if uid_str not in ACTIVITY:
        return "⚫ OFFLINE (never active)"
    try:
        last_time = datetime.fromisoformat(ACTIVITY[uid_str])
        now = datetime.now()
        diff = now - last_time
        seconds = diff.total_seconds()
        if seconds < 180:  # 3 MINUTES as requested
            if seconds < 60:
                return f"🟢 ONLINE ({int(seconds)}s ago)"
            else:
                return f"🟢 ONLINE ({int(seconds//60)}m ago)"
        elif seconds < 3600:
            mins = int(seconds // 60)
            return f"🟡 {mins}m ago"
        elif seconds < 86400:
            hours = int(seconds // 3600)
            return f"⚫ {hours}h ago"
        else:
            days = int(seconds // 86400)
            return f"⚫ {days}d ago"
    except:
        return "⚫ OFFLINE"

def is_user_online(uid):
    uid_str = str(uid)
    if uid_str not in ACTIVITY:
        return False
    try:
        last_time = datetime.fromisoformat(ACTIVITY[uid_str])
        return (datetime.now() - last_time).total_seconds() < 180
    except:
        return False

# ===== START =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user
    username = f"@{user.username}" if user.username else "No Username"
    name = user.first_name or "User"
    
    update_activity(uid)

    if uid == ADMIN_ID:
        online_count = sum(1 for u in ALLOWED_USERS if is_user_online(u))
        await update.message.reply_text(
            f"👑 ACTIVATION BOT V5\n"
            f"Photo: {'ON ✅' if SETTINGS['allow_photos'] else 'OFF ❌'}\n"
            f"Users: {len(ALLOWED_USERS)}/4 | Online: {online_count} | Pending: {len(PENDING_USERS)}\n\n"
            "/users - Users with Online status\n"
            "/online - Live online check\n"
            "/pending - Pending requests\n"
            "/getid - Forward/Reply se ID\n"
            "/broadcast <msg>\n"
            "/adduser /removeuser"
        )
    elif str(uid) in ALLOWED_USERS:
        label = ALLOWED_USERS[str(uid)].upper()
        await update.message.reply_text(f"✅ WELCOME {label}! YOU ARE CONNECTED. 🟢 ONLINE")
        try:
            await context.bot.send_message(ADMIN_ID, f"🟢 {label} ({name} {username}) START - ONLINE\nID: {uid}")
        except:
            pass
    else:
        PENDING_USERS[str(uid)] = {"name": name, "username": username, "id": uid}
        save_json(PENDING_FILE, PENDING_USERS)
        
        await update.message.reply_text(f"YOUR ID: `{uid}`\nAdmin ko bhejo.", parse_mode="Markdown")
        
        # NEW V5: Button for direct add
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Add User", callback_data=f"add_{uid}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")
            ]
        ])
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 NEW JOIN REQUEST\n👤 Name: {name}\n{username}\n🆔 ID: {uid}\n📊 {get_online_status(uid)}\n\nNeeche button se direct add karo:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except:
            pass

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_activity(update.effective_user.id)
    await update.message.reply_text(f"ID: `{update.effective_user.id}`", parse_mode="Markdown")

# ===== GET ID WITH BUTTON =====
async def get_id_by_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    
    target_user = None
    target_id = None
    target_name = None
    target_username = None

    if update.message.reply_to_message:
        replied_user = update.message.reply_to_message.from_user
        fwd = update.message.reply_to_message.forward_origin
        if fwd:
            try:
                if hasattr(fwd, 'sender_user') and fwd.sender_user:
                    replied_user = fwd.sender_user
            except:
                pass
        target_user = replied_user

    elif update.message.forward_origin:
        try:
            origin = update.message.forward_origin
            if hasattr(origin, 'sender_user') and origin.sender_user:
                target_user = origin.sender_user
        except:
            pass

    if target_user:
        target_id = str(target_user.id)
        target_name = target_user.first_name
        target_username = f"@{target_user.username}" if target_user.username else "No username"
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Add User", callback_data=f"add_{target_id}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{target_id}")
            ],
            [
                InlineKeyboardButton(f"👤 {target_name}", callback_data="noop")
            ]
        ])
        
        await update.message.reply_text(
            f"📩 Forwarded From:\n👤 {target_name}\n{target_username}\n🆔 ID: `{target_id}`\n📊 {get_online_status(target_id)}\n\nButton dabao direct add karne ke liye:",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return

    if context.args:
        raw = context.args[0].strip()
        if raw.startswith('@'):
            try:
                chat = await context.bot.get_chat(raw)
                target_id = str(chat.id)
                target_name = chat.first_name or chat.title
                target_username = raw
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Add User", callback_data=f"add_{target_id}")]
                ])
                await update.message.reply_text(
                    f"🔍 Found: {raw}\n👤 {target_name}\n🆔 ID: `{target_id}`\n📊 {get_online_status(target_id)}",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except BadRequest as e:
                await update.message.reply_text(f"❌ {raw} nahi mila: {e}")
            return
        else:
            nid = clean_id(raw)
            if nid:
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Add User", callback_data=f"add_{nid}")]
                ])
                await update.message.reply_text(
                    f"ID: {nid}\nStatus: {get_online_status(nid)}",
                    reply_markup=keyboard
                )
                return

    await update.message.reply_text("📌 ID nikalo:\n1. Kisi ka message forward karo\n2. Reply karke /getid\n3. /getid @username")

# ===== BUTTON CALLBACK - MAIN NEW FEATURE =====
async def handle_button(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.from_user.id != ADMIN_ID:
        await query.answer("Only Admin can use this!", show_alert=True)
        return
    
    data = query.data
    
    if data == "noop":
        return
    
    if data.startswith("add_"):
        uid = data.split("_", 1)[1]
        uid = clean_id(uid)
        
        if not uid:
            await query.edit_message_text("❌ Invalid ID")
            return
        
        if len(ALLOWED_USERS) >= 4 and uid not in ALLOWED_USERS:
            await query.edit_message_text(f"❌ LIMIT FULL (4/4)\nCannot add {uid}\nPehle kisi ko /removeuser se hatao.")
            return
        
        is_new = uid not in ALLOWED_USERS
        ALLOWED_USERS[uid] = f"User {len(ALLOWED_USERS)+1}" if is_new else ALLOWED_USERS[uid]
        
        if uid in PENDING_USERS:
            del PENDING_USERS[uid]
        
        save_all()
        
        user_label = ALLOWED_USERS[uid].upper()
        
        # Edit original message to show added
        await query.edit_message_text(
            f"✅ USER ADDED SUCCESSFULLY!\n\n👤 {user_label}\n🆔 ID: {uid}\n📊 {get_online_status(uid)}\n\nUser ko notification bhej diya gaya hai.",
            reply_markup=None
        )
        
        # Notify added user
        try:
            await context.bot.send_message(
                int(uid),
                f"✅ YOU HAVE BEEN ADDED AS {user_label}!\nBot me /start karo."
            )
        except:
            pass
            
    elif data.startswith("reject_"):
        uid = data.split("_", 1)[1]
        uid = clean_id(uid)
        
        if uid in PENDING_USERS:
            del PENDING_USERS[uid]
            save_json(PENDING_FILE, PENDING_USERS)
        
        await query.edit_message_text(f"❌ REJECTED\nID: {uid} ko add nahi kiya gaya.", reply_markup=None)
        
        try:
            await context.bot.send_message(int(uid), "❌ Aapki join request reject kar di gayi hai Admin dwara.")
        except:
            pass

    elif data.startswith("remove_"):
        uid = data.split("_", 1)[1]
        if uid in ALLOWED_USERS:
            del ALLOWED_USERS[uid]
            if uid in ACTIVITY:
                del ACTIVITY[uid]
            save_all()
            await query.edit_message_text(f"✅ REMOVED: {uid}")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("USAGE: /adduser <id>")
        return
    if len(ALLOWED_USERS) >= 4:
        await update.message.reply_text("❌ LIMIT 4 FULL.")
        return
    nid = clean_id(context.args[0])
    if not nid:
        # Try username
        try:
            chat = await context.bot.get_chat(context.args[0])
            nid = str(chat.id)
        except:
            await update.message.reply_text("❌ Invalid ID")
            return
    ALLOWED_USERS[nid] = f"User {len(ALLOWED_USERS)+1}"
    if nid in PENDING_USERS:
        del PENDING_USERS[nid]
    save_all()
    await update.message.reply_text(f"✅ {ALLOWED_USERS[nid].upper()} ADDED: {nid}")
    try:
        await context.bot.send_message(int(nid), f"✅ ADDED AS {ALLOWED_USERS[nid].upper()}. /start karo")
    except:
        pass

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("USAGE: /removeuser <id>")
        return
    rid = clean_id(context.args[0])
    to_del = rid if rid in ALLOWED_USERS else next((k for k in ALLOWED_USERS if rid in k), None)
    if to_del:
        del ALLOWED_USERS[to_del]
        if to_del in ACTIVITY:
            del ACTIVITY[to_del]
        save_all()
        await update.message.reply_text(f"✅ REMOVED: {to_del}")
        try:
            await context.bot.send_message(int(to_del), "❌ Aapko bot se remove kar diya gaya hai.")
        except:
            pass
    else:
        await update.message.reply_text(f"❌ ID {rid} NOT FOUND.")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not ALLOWED_USERS:
        await update.message.reply_text("NO USERS.")
        return
    txt = "📋 USERS - ONLINE STATUS (3 min):\n\n"
    keyboard = []
    online_count = 0
    for k,v in ALLOWED_USERS.items():
        status = get_online_status(k)
        if "🟢 ONLINE" in status:
            online_count += 1
        txt += f"👤 {v.upper()}: {k}\n   {status}\n\n"
        keyboard.append([InlineKeyboardButton(f"❌ Remove {v.upper()}", callback_data=f"remove_{k}")])
    
    txt += f"🟢 Online: {online_count}/{len(ALLOWED_USERS)}"
    await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

async def online_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID and str(update.effective_user.id) not in ALLOWED_USERS:
        return
    update_activity(update.effective_user.id)
    txt = "📊 LIVE STATUS (3 min):\n\n"
    txt += f"👑 ADMIN: {get_online_status(ADMIN_ID)}\n\n"
    for k,v in ALLOWED_USERS.items():
        txt += f"{v.upper()}: {get_online_status(k)}\n"
    txt += "\n💡 3 min me message bheja to ONLINE"
    await update.message.reply_text(txt)

async def list_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not PENDING_USERS:
        await update.message.reply_text("No pending.")
        return
    for k,v in list(PENDING_USERS.items())[:10]:  # Show 10 at a time
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Add", callback_data=f"add_{k}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{k}")]
        ])
        await update.message.reply_text(
            f"⏳ PENDING:\n👤 {v['name']} {v['username']}\n🆔 {k}\n{get_online_status(k)}",
            reply_markup=keyboard
        )

async def add_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("USAGE: /addword word1, word2")
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
        await update.message.reply_text(f"✅ Added {len(added)} words")
    else:
        await update.message.reply_text("Already exists")

async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    txt = "\n".join(BANNED_WORDS) or "No banned words"
    await update.message.reply_text(f"🚫 Banned ({len(BANNED_WORDS)}):\n{txt}")

async def remove_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        return
    w = " ".join(context.args).lower()
    if w in BANNED_WORDS:
        BANNED_WORDS.remove(w)
        save_all()
        await update.message.reply_text(f"Removed {w}")

async def clear_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    BANNED_WORDS.clear()
    save_all()
    await update.message.reply_text("Cleared")

async def toggle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    SETTINGS["allow_photos"] = not SETTINGS["allow_photos"]
    save_all()
    await update.message.reply_text(f"Photo: {'ON ✅' if SETTINGS['allow_photos'] else 'OFF ❌'}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    if not context.args:
        await update.message.reply_text("USAGE: /broadcast msg")
        return
    msg = " ".join(context.args)
    count = 0
    for uid in list(ALLOWED_USERS.keys()):
        try:
            await context.bot.send_message(int(uid), f"📢 BROADCAST:\n\n{msg}")
            count += 1
        except:
            pass
    await update.message.reply_text(f"Sent to {count}")

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sid = str(uid)
    is_admin = (uid == ADMIN_ID)
    if not is_admin and sid not in ALLOWED_USERS:
        return
    update_activity(uid)
    text_content = update.message.text or update.message.caption or ""
    if not text_content and not update.message.photo and not update.message.video and not update.message.document:
        return
    for bw in BANNED_WORDS:
        if bw in text_content.lower():
            await update.message.reply_text(f"⚠️ Blocked: {bw.upper()}")
            try:
                await context.bot.send_message(ADMIN_ID, f"🚨 {ALLOWED_USERS.get(sid, sid)} tried banned: {bw}")
            except:
                pass
            return
    if not is_admin and update.message.photo and not SETTINGS["allow_photos"]:
        await update.message.reply_text("❌ Photo OFF")
        return
    label = "👑 Admin" if is_admin else ALLOWED_USERS.get(sid, "User").upper()
    icon = "👑" if is_admin else "👤"
    badge = "🟢" if is_user_online(uid) else "⚫"
    formatted_text = f"{icon} <b>{label}</b> {badge}: {text_content}" if text_content else f"{icon} <b>{label}</b> {badge} 📸"
    targets = list(ALLOWED_USERS.keys()) + ([str(ADMIN_ID)] if not is_admin else [])
    for tid in targets:
        if tid == sid:
            continue
        try:
            if update.message.photo:
                await context.bot.send_photo(int(tid), update.message.photo[-1].file_id, caption=formatted_text, parse_mode="HTML")
            elif update.message.video:
                await context.bot.send_video(int(tid), update.message.video.file_id, caption=formatted_text, parse_mode="HTML")
            elif update.message.document:
                await context.bot.send_document(int(tid), update.message.document.file_id, caption=formatted_text, parse_mode="HTML")
            else:
                await context.bot.send_message(int(tid), formatted_text, parse_mode="HTML")
        except Exception as e:
            logging.error(e)

async def on_startup(app):
    if ADMIN_ID == 0:
        return
    await asyncio.sleep(2)
    try:
        await app.bot.send_message(ADMIN_ID, "🔄 BOT V5 RESTARTED\n✅ Add Button + 3 Min Online Added!")
    except:
        pass
    for uid in list(ALLOWED_USERS.keys()):
        try:
            await app.bot.send_message(int(uid), "🔄 BOT RESTARTED\n✅ V5 Online! New: Add button feature.")
        except:
            pass

def main():
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    except:
        pass
    threading.Thread(target=run_flask, daemon=True).start()
    app = ApplicationBuilder().token(BOT_TOKEN).post_init(on_startup).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("myid", get_my_id))
    app.add_handler(CommandHandler("getid", get_id_by_username))
    app.add_handler(CommandHandler("id", get_id_by_username))
    app.add_handler(CommandHandler("adduser", add_user))
    app.add_handler(CommandHandler("removeuser", remove_user))
    app.add_handler(CommandHandler("users", list_users))
    app.add_handler(CommandHandler("online", online_status_command))
    app.add_handler(CommandHandler("status", online_status_command))
    app.add_handler(CommandHandler("pending", list_pending))
    app.add_handler(CommandHandler("addword", add_word))
    app.add_handler(CommandHandler("removeword", remove_word))
    app.add_handler(CommandHandler("words", list_words))
    app.add_handler(CommandHandler("clearwords", clear_words))
    app.add_handler(CommandHandler("togglephoto", toggle_photo))
    app.add_handler(CommandHandler("broadcast", broadcast))
    app.add_handler(CallbackQueryHandler(handle_button))
    app.add_handler(MessageHandler(filters.FORWARDED & filters.User(user_id=ADMIN_ID), get_id_by_username))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_chat))
    
    print("Bot Started V5 - Add Button + 3 Min Online")
    app.run_polling(stop_signals=None, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
