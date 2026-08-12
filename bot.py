import os
import json
import logging
import threading
import asyncio
from datetime import datetime, timedelta
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.error import BadRequest

BOT_TOKEN = os.getenv("BOT_TOKEN") or "YOUR_BOT_TOKEN_HERE"
ADMIN_ID = int(os.getenv("ADMIN_ID") or 0)

USERS_FILE = "users.json"
WORDS_FILE = "words.json"
SETTINGS_FILE = "settings.json"
PENDING_FILE = "pending.json"
ACTIVITY_FILE = "activity.json"  # NEW for online status

logging.basicConfig(level=logging.INFO)

flask_app = Flask(__name__)
@flask_app.route('/')
def home():
    return "Bot Running 24/7 - V4 Online Status"

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

# ===== ONLINE STATUS FUNCTIONS =====
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
        
        if seconds < 180:  # 3 minutes
            mins = int(seconds // 60)
            if mins == 0:
                return f"🟢 ONLINE (active {int(seconds)}s ago)"
            else:
                return f"🟢 ONLINE (active {mins}m ago)"
        elif seconds < 3600:  # less than 1 hour
            mins = int(seconds // 60)
            return f"🟡 {mins}m ago"
        elif seconds < 86400:  # less than 24 hours
            hours = int(seconds // 3600)
            return f"⚫ {hours}h ago"
        else:
            days = int(seconds // 86400)
            return f"⚫ {days}d ago - {last_time.strftime('%d/%m %H:%M')}"
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

# ===== START COMMAND =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user
    username = f"@{user.username}" if user.username else "No Username"
    name = user.first_name or "User"
    
    # Update activity for anyone who starts
    update_activity(uid)

    if uid == ADMIN_ID:
        online_count = sum(1 for u in ALLOWED_USERS if is_user_online(u))
        await update.message.reply_text(
            f"👑 ACTIVATION BOT - ADMIN PANEL V4\n"
            f"Photo Sharing: {'ON ✅' if SETTINGS['allow_photos'] else 'OFF ❌'}\n"
            f"Total Users: {len(ALLOWED_USERS)}/4 | Online: {online_count} | Pending: {len(PENDING_USERS)}\n\n"
            "Commands:\n"
            "/users - List users with Online/Offline\n"
            "/online - Check who is online now\n"
            "/adduser <id/@username> - Add user\n"
            "/removeuser <id> - Remove user\n"
            "/pending - List pending requests\n"
            "/getid - Reply/Forward se ID nikalo\n"
            "/broadcast <msg> - Sabko message bhejo\n"
            "/addword <word1, word2> - Add banned words\n"
            "/words - Show banned words\n"
            "/togglephoto - ON/OFF photo sharing\n"
            "/myid - Get your ID"
        )
    elif str(uid) in ALLOWED_USERS:
        label = ALLOWED_USERS[str(uid)].upper()
        await update.message.reply_text(f"✅ WELCOME {label}! YOU ARE CONNECTED.\n🟢 You are now ONLINE")
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🟢 {label} ({name} {username}) ne bot START kiya - ONLINE\nID: {uid}"
            )
        except:
            pass
    else:
        PENDING_USERS[str(uid)] = {
            "name": name,
            "username": username,
            "id": uid
        }
        save_json(PENDING_FILE, PENDING_USERS)
        
        await update.message.reply_text(
            f"YOUR ID: `{uid}`\nPLEASE SEND THIS ID TO ADMIN FOR ACCESS.",
            parse_mode="Markdown"
        )
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 NEW JOIN REQUEST\n👤 Name: {name}\n{username}\n🆔 ID: `{uid}`\n\nAdd karne ke liye: /adduser {uid}",
                parse_mode="Markdown"
            )
        except:
            pass

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_activity(update.effective_user.id)
    await update.message.reply_text(f"YOUR TELEGRAM ID: `{update.effective_user.id}`", parse_mode="Markdown")

# ===== GET ID =====
async def get_id_by_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    
    if update.message.reply_to_message:
        replied_user = update.message.reply_to_message.from_user
        fwd = update.message.reply_to_message.forward_origin
        if fwd:
            try:
                if hasattr(fwd, 'sender_user'):
                    replied_user = fwd.sender_user
                elif hasattr(fwd, 'chat'):
                    await update.message.reply_text(f"Forwarded Chat: {fwd.chat.title or fwd.chat.username}\nID: {fwd.chat.id}")
                    return
            except:
                pass
        
        username = f"@{replied_user.username}" if replied_user.username else "No username"
        status = get_online_status(replied_user.id)
        await update.message.reply_text(
            f"👤 Name: {replied_user.first_name}\n{username}\n🆔 ID: `{replied_user.id}`\n📊 Status: {status}\n\nAdd karne ke liye: /adduser {replied_user.id}",
            parse_mode="Markdown"
        )
        return

    if update.message.forward_origin:
        try:
            origin = update.message.forward_origin
            if hasattr(origin, 'sender_user') and origin.sender_user:
                u = origin.sender_user
                username = f"@{u.username}" if u.username else "No username"
                status = get_online_status(u.id)
                await update.message.reply_text(
                    f"📨 Forwarded From:\n👤 {u.first_name}\n{username}\n🆔 ID: `{u.id}`\n📊 {status}\n\n/adduser {u.id}",
                    parse_mode="Markdown"
                )
                return
        except Exception as e:
            logging.error(e)

    if context.args:
        raw = context.args[0].strip()
        if raw.startswith('@'):
            raw_username = raw
        else:
            nid = clean_id(raw)
            if nid:
                status = get_online_status(nid)
                await update.message.reply_text(f"ID: {nid}\nStatus: {status}\n/adduser {nid}")
                return
            raw_username = "@" + raw if not raw.startswith('@') else raw
        
        try:
            chat = await context.bot.get_chat(raw_username)
            status = get_online_status(chat.id)
            await update.message.reply_text(
                f"🔍 Found: {raw_username}\n👤 Name: {chat.first_name or chat.title}\n🆔 ID: `{chat.id}`\n📊 {status}\n\n/adduser {chat.id}",
                parse_mode="Markdown"
            )
        except BadRequest as e:
            await update.message.reply_text(f"❌ Username {raw_username} nahi mila. Error: {e}")
        return

    await update.message.reply_text(
        "📌 ID kaise nikale:\n"
        "1. Kisi user ke message ko yahan forward karo\n"
        "2. Kisi message ka reply karke /getid likho\n"
        "3. /getid @username"
    )

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("USAGE: /adduser <user_id or @username>")
        return
    if len(ALLOWED_USERS) >= 4:
        await update.message.reply_text("❌ USER LIMIT REACHED (MAX 4).")
        return
    
    raw_input = context.args[0].strip()
    nid = clean_id(raw_input)
    
    if not nid and raw_input.startswith('@'):
        try:
            chat = await context.bot.get_chat(raw_input)
            nid = str(chat.id)
        except:
            await update.message.reply_text(f"❌ Username {raw_input} se ID nahi nikal paya.")
            return
    elif not nid:
        try:
            chat = await context.bot.get_chat("@" + raw_input.lstrip('@'))
            nid = str(chat.id)
        except:
            pass

    if not nid:
        await update.message.reply_text("❌ INVALID ID/USERNAME.")
        return

    ALLOWED_USERS[nid] = f"User {len(ALLOWED_USERS)+1}"
    if nid in PENDING_USERS:
        del PENDING_USERS[nid]
    save_all()
    await update.message.reply_text(f"✅ {ALLOWED_USERS[nid].upper()} ADDED. ID: {nid}")
    try:
        await context.bot.send_message(int(nid), f"✅ YOU HAVE BEEN ADDED AS {ALLOWED_USERS[nid].upper()}. SEND /start")
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
            await context.bot.send_message(
                int(to_del),
                "❌ Aapko Activation Bot se remove kar diya gaya hai Admin dwara."
            )
        except:
            pass
    else:
        await update.message.reply_text(f"❌ ID {rid} NOT FOUND.")

# ===== UPDATED USERS LIST WITH ONLINE STATUS - MAIN FEATURE =====
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not ALLOWED_USERS:
        await update.message.reply_text("NO USERS ADDED YET.")
        return
    
    txt = "📋 ADDED USERS - ONLINE STATUS:\n\n"
    online_count = 0
    for k,v in ALLOWED_USERS.items():
        status = get_online_status(k)
        if "🟢 ONLINE" in status:
            online_count += 1
        txt += f"👤 {v.upper()}: {k}\n   {status}\n\n"
    
    txt += f"---\n🟢 Online Now: {online_count}/{len(ALLOWED_USERS)}"
    await update.message.reply_text(txt)

async def online_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID and str(update.effective_user.id) not in ALLOWED_USERS:
        return
    update_activity(update.effective_user.id)
    
    txt = "📊 LIVE ONLINE STATUS:\n\n"
    txt += f"👑 ADMIN ({ADMIN_ID}): {get_online_status(ADMIN_ID)}\n\n"
    
    if not ALLOWED_USERS:
        txt += "No users added."
    else:
        for k,v in ALLOWED_USERS.items():
            status = get_online_status(k)
            txt += f"{v.upper()}: {status}\n"
    
    txt += "\n💡 User 3 min me message bhejta hai to ONLINE dikhega"
    await update.message.reply_text(txt)

async def list_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not PENDING_USERS:
        await update.message.reply_text("No pending requests.")
        return
    txt = ""
    for k,v in PENDING_USERS.items():
        status = get_online_status(k)
        txt += f"👤 {v['name']} {v['username']} - {k}\n   {status}\n"
    await update.message.reply_text(f"⏳ PENDING REQUESTS:\n{txt}")

async def add_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("USAGE: /addword word1, word2, word3")
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
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("⚠️ ALL WORDS ALREADY IN BANNED LIST.")

async def remove_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("USAGE: /removeword word1, word2")
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
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("❌ WORDS NOT FOUND.")

async def clear_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    BANNED_WORDS.clear()
    save_all()
    await update.message.reply_text("✅ ALL BANNED WORDS CLEARED.")

async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not BANNED_WORDS:
        txt = "NO BANNED WORDS"
    else:
        txt = "\n".join(["- " + w.upper() for w in BANNED_WORDS])
    await update.message.reply_text(f"🚫 BANNED WORDS ({len(BANNED_WORDS)}):\n{txt}")

async def toggle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    SETTINGS["allow_photos"] = not SETTINGS["allow_photos"]
    save_all()
    await update.message.reply_text(f"PHOTO SHARING: {'ON ✅' if SETTINGS['allow_photos'] else 'OFF ❌'}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("USAGE: /broadcast <your message>")
        return
    msg = " ".join(context.args)
    count = 0
    for uid in list(ALLOWED_USERS.keys()):
        try:
            await context.bot.send_message(int(uid), f"📢 ADMIN BROADCAST:\n\n{msg}")
            count += 1
        except:
            pass
    await update.message.reply_text(f"✅ Broadcast sent to {count} users.")

async def handle_chat(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    sid = str(uid)
    is_admin = (uid == ADMIN_ID)
    if not is_admin and sid not in ALLOWED_USERS:
        return
    
    # Update activity on every message - KEY FOR ONLINE STATUS
    update_activity(uid)
    
    text_content = update.message.text or update.message.caption or ""
    if not text_content and not update.message.photo and not update.message.video and not update.message.document:
        return
    for bw in BANNED_WORDS:
        if bw in text_content.lower():
            await update.message.reply_text(f"⚠️ MESSAGE BLOCKED - BANNED WORD: '{bw.upper()}'")
            try:
                await context.bot.send_message(ADMIN_ID, f"🚨 {ALLOWED_USERS.get(sid, sid).upper()} TRIED TO SEND BANNED WORD '{bw.upper()}': {text_content[:200]}")
            except:
                pass
            return
    if not is_admin and update.message.photo and not SETTINGS["allow_photos"]:
        await update.message.reply_text("❌ PHOTO SHARING IS OFF BY ADMIN.")
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
        online_badge = "🟢" if is_user_online(uid) else "⚫"
    else:
        raw_label = ALLOWED_USERS.get(sid, sid).upper()
        icon = USER_ICONS.get(raw_label, "👤")
        online_badge = "🟢" if is_user_online(sid) else "⚫"
    
    # Show online status in forwarded messages
    if text_content:
        formatted_text = f"{icon} <b>{raw_label}</b> {online_badge}: {text_content}"
    else:
        formatted_text = f"{icon} <b>{raw_label}</b> {online_badge} SENT A PHOTO 📸"
    
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
        await app.bot.send_message(ADMIN_ID, "🔄 BOT RESTARTED V4\n✅ Online Status Feature Added!\nBot is online.")
    except:
        pass
    for uid in list(ALLOWED_USERS.keys()):
        try:
            await app.bot.send_message(int(uid), "🔄 BOT RESTARTED\n✅ Activation Bot V4 is online again! New: Online status feature added.")
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
    app.add_handler(MessageHandler(filters.FORWARDED & filters.User(user_id=ADMIN_ID), get_id_by_username))
    app.add_handler(MessageHandler(filters.ALL & ~filters.COMMAND, handle_chat))
    
    print("Bot Started V4 - Online Status Added")
    app.run_polling(stop_signals=None, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
