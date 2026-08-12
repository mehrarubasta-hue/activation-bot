import os
import json
import logging
import threading
import asyncio
from datetime import datetime
from flask import Flask
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand, BotCommandScopeChat, BotCommandScopeDefault
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
    return "Bot Running 24/7 - V8 Menu Button"

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

def update_activity(uid):
    ACTIVITY[str(uid)] = datetime.now().isoformat()
    save_json(ACTIVITY_FILE, ACTIVITY)

def get_online_status(uid):
    uid_str = str(uid)
    if uid_str not in ACTIVITY:
        return "⚫ OFFLINE (never active)"
    try:
        last_time = datetime.fromisoformat(ACTIVITY[uid_str])
        seconds = (datetime.now() - last_time).total_seconds()
        if seconds < 180:
            if seconds < 60:
                return f"🟢 ONLINE ({int(seconds)}s ago)"
            else:
                return f"🟢 ONLINE ({int(seconds//60)}m ago)"
        elif seconds < 3600:
            return f"🟡 {int(seconds//60)}m ago"
        elif seconds < 86400:
            return f"⚫ {int(seconds//3600)}h ago"
        else:
            return f"⚫ {int(seconds//86400)}d ago - {last_time.strftime('%d/%m %H:%M')}"
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

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = update.effective_user
    username = f"@{user.username}" if user.username else "No Username"
    name = user.first_name or "User"
    
    update_activity(uid)

    if uid == ADMIN_ID:
        online_count = sum(1 for u in ALLOWED_USERS if is_user_online(u))
        await update.message.reply_text(
            f"👑 ACTIVATION BOT - ADMIN PANEL V8\n"
            f"Photo Sharing: {'ON ✅' if SETTINGS['allow_photos'] else 'OFF ❌'}\n"
            f"Total Users: {len(ALLOWED_USERS)}/4 | Online: {online_count} | Pending: {len(PENDING_USERS)}\n"
            f"Banned Words: {len(BANNED_WORDS)}\n\n"
            f"Use Menu button below for all commands.\n"
            f"Or type commands manually:\n"
            f"/users, /online, /removeuser, /pending, /getid, /broadcast etc.\n"
        )
    elif str(uid) in ALLOWED_USERS:
        label = ALLOWED_USERS[str(uid)].upper()
        await update.message.reply_text(f"✅ WELCOME {label}! YOU ARE CONNECTED.\n🟢 You are now ONLINE")
        try:
            await context.bot.send_message(ADMIN_ID, f"🟢 {label} ({name} {username}) STARTED BOT - ONLINE\nID: {uid}")
        except:
            pass
    else:
        PENDING_USERS[str(uid)] = {"name": name, "username": username, "id": uid}
        save_json(PENDING_FILE, PENDING_USERS)
        
        await update.message.reply_text(
            f"✅ Your request has been sent to Admin.\n"
            f"Your ID: `{uid}`\n"
            f"You will receive a message once your request is approved. Please wait.",
            parse_mode="Markdown"
        )
        
        keyboard = InlineKeyboardMarkup([
            [
                InlineKeyboardButton("✅ Add User", callback_data=f"add_{uid}"),
                InlineKeyboardButton("❌ Reject", callback_data=f"reject_{uid}")
            ]
        ])
        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"🔔 NEW JOIN REQUEST\n"
                f"Name: {name}\n"
                f"{username}\n"
                f"ID: {uid}\n"
                f"Status: {get_online_status(uid)}\n\n"
                f"Click button below to add directly:",
                parse_mode="Markdown",
                reply_markup=keyboard
            )
        except:
            pass

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    update_activity(update.effective_user.id)
    await update.message.reply_text(f"YOUR TELEGRAM ID: `{update.effective_user.id}`", parse_mode="Markdown")

async def get_id_by_username(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    
    target_user = None

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
            ]
        ])
        
        await update.message.reply_text(
            f"Forwarded From:\n"
            f"Name: {target_name}\n"
            f"{target_username}\n"
            f"ID: `{target_id}`\n"
            f"Status: {get_online_status(target_id)}",
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
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅ Add User", callback_data=f"add_{target_id}")]
                ])
                await update.message.reply_text(
                    f"Found: {raw}\nName: {target_name}\nID: `{target_id}`\nStatus: {get_online_status(target_id)}",
                    parse_mode="Markdown",
                    reply_markup=keyboard
                )
            except BadRequest as e:
                await update.message.reply_text(f"❌ Username {raw} not found. Error: {e}")
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

    await update.message.reply_text(
        "HOW TO GET ID:\n"
        "1. Forward any user's message\n"
        "2. Reply with /getid\n"
        "3. /getid @username"
    )

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
        uid = clean_id(data.split("_", 1)[1])
        if not uid:
            await query.edit_message_text("❌ Invalid ID")
            return
        
        if len(ALLOWED_USERS) >= 4 and uid not in ALLOWED_USERS:
            await query.edit_message_text(f"❌ LIMIT FULL (4/4)\nCannot add {uid}\nRemove someone first.")
            return
        
        is_new = uid not in ALLOWED_USERS
        ALLOWED_USERS[uid] = f"User {len(ALLOWED_USERS)+1}" if is_new else ALLOWED_USERS[uid]
        
        if uid in PENDING_USERS:
            del PENDING_USERS[uid]
        
        save_all()
        user_label = ALLOWED_USERS[uid].upper()
        
        await query.edit_message_text(
            f"✅ USER ADDED SUCCESSFULLY!\n\n"
            f"User {user_label} has been added successfully.\n"
            f"ID: {uid}\n"
            f"Status: {get_online_status(uid)}\n\n"
            f"Notification sent to user."
        )
        
        try:
            await context.bot.send_message(int(uid), f"✅ YOU HAVE BEEN ADDED AS {user_label}!\nPlease send /start")
        except:
            pass
            
    elif data.startswith("reject_"):
        uid = clean_id(data.split("_", 1)[1])
        if uid in PENDING_USERS:
            del PENDING_USERS[uid]
            save_json(PENDING_FILE, PENDING_USERS)
        
        await query.edit_message_text(f"❌ REJECTED\nID: {uid} not added.", reply_markup=None)
        try:
            await context.bot.send_message(int(uid), "❌ Your join request was rejected by Admin.")
        except:
            pass

    elif data.startswith("remove_"):
        uid = data.split("_", 1)[1]
        if uid in ALLOWED_USERS:
            label = ALLOWED_USERS[uid]
            del ALLOWED_USERS[uid]
            if uid in ACTIVITY:
                del ACTIVITY[uid]
            save_all()
            await query.edit_message_text(f"✅ REMOVED SUCCESSFULLY!\n\nUser {label.upper()} (ID: {uid}) has been removed successfully.")
            try:
                await context.bot.send_message(
                    int(uid),
                    "❌ You have been removed from Activation Bot by Admin. You can no longer use this bot.\n\n"
                    "If you want to join again, please click /start to send a new request."
                )
            except:
                pass
        else:
            await query.edit_message_text(f"❌ User {uid} not found or already removed.")

async def add_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("USAGE: /adduser <id>\nEx: /adduser 871721883")
        return
    if len(ALLOWED_USERS) >= 4:
        await update.message.reply_text("❌ LIMIT REACHED (MAX 4).")
        return
    
    raw_input = context.args[0].strip()
    nid = clean_id(raw_input)
    
    if not nid and raw_input.startswith('@'):
        try:
            chat = await context.bot.get_chat(raw_input)
            nid = str(chat.id)
        except:
            await update.message.reply_text(f"❌ Cannot get ID from {raw_input}")
            return

    if not nid:
        await update.message.reply_text("❌ INVALID ID.")
        return

    ALLOWED_USERS[nid] = f"User {len(ALLOWED_USERS)+1}"
    if nid in PENDING_USERS:
        del PENDING_USERS[nid]
    save_all()
    await update.message.reply_text(f"✅ {ALLOWED_USERS[nid].upper()} ADDED. ID: {nid}\nUser has been added successfully.")
    try:
        await context.bot.send_message(int(nid), f"✅ YOU HAVE BEEN ADDED AS {ALLOWED_USERS[nid].upper()}. Please send /start")
    except:
        pass

async def remove_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    
    if not context.args:
        if not ALLOWED_USERS:
            await update.message.reply_text("No users added yet.")
            return
        txt = "SELECT USER TO REMOVE:\nClick button below to remove directly:\n\n"
        keyboard = []
        for k,v in ALLOWED_USERS.items():
            status = get_online_status(k)
            txt += f"{v.upper()}: {k}\n   {status}\n\n"
            keyboard.append([InlineKeyboardButton(f"Remove {v.upper()} - {k}", callback_data=f"remove_{k}")])
        
        await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(keyboard))
        return
    
    rid = clean_id(context.args[0])
    to_del = rid if rid in ALLOWED_USERS else next((k for k in ALLOWED_USERS if rid in k), None)
    if to_del:
        del ALLOWED_USERS[to_del]
        if to_del in ACTIVITY:
            del ACTIVITY[to_del]
        save_all()
        await update.message.reply_text(f"✅ REMOVED: {to_del}\nUser has been removed successfully.")
        try:
            await context.bot.send_message(
                int(to_del), 
                "❌ You have been removed from Activation Bot by Admin. You can no longer use this bot.\n\n"
                "If you want to join again, please click /start to send a new request."
            )
        except:
            pass
    else:
        await update.message.reply_text(f"❌ ID {rid} NOT FOUND.")

async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not ALLOWED_USERS:
        await update.message.reply_text("NO USERS ADDED YET.")
        return
    txt = "ADDED USERS - ONLINE STATUS (3 min):\n\n"
    keyboard = []
    online_count = 0
    for k,v in ALLOWED_USERS.items():
        status = get_online_status(k)
        if "ONLINE" in status:
            online_count += 1
        txt += f"{v.upper()}: {k}\n   {status}\n\n"
        keyboard.append([InlineKeyboardButton(f"Remove {v.upper()}", callback_data=f"remove_{k}")])
    
    txt += f"---\nOnline Now: {online_count}/{len(ALLOWED_USERS)}"
    await update.message.reply_text(txt, reply_markup=InlineKeyboardMarkup(keyboard) if keyboard else None)

async def online_status_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID and str(update.effective_user.id) not in ALLOWED_USERS:
        return
    update_activity(update.effective_user.id)
    txt = "LIVE ONLINE STATUS (3 min):\n\n"
    txt += f"ADMIN ({ADMIN_ID}): {get_online_status(ADMIN_ID)}\n\n"
    for k,v in ALLOWED_USERS.items():
        txt += f"{v.upper()}: {get_online_status(k)}\n"
    txt += "\nUser is ONLINE for 3 min after message"
    await update.message.reply_text(txt)

async def list_pending(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not PENDING_USERS:
        await update.message.reply_text("No pending requests.")
        return
    for k,v in list(PENDING_USERS.items())[:10]:
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Add", callback_data=f"add_{k}"), InlineKeyboardButton("❌ Reject", callback_data=f"reject_{k}")]
        ])
        await update.message.reply_text(
            f"PENDING REQUEST:\nName: {v['name']}\n{v['username']}\nID: {k}\nStatus: {get_online_status(k)}",
            reply_markup=keyboard
        )

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
        msg = f"BANNED WORDS ADDED ({len(added)}):\n" + "\n".join([f"- {w.upper()}" for w in added])
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("All words already banned.")

async def remove_word(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("USAGE: /removeword word")
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
        msg = f"REMOVED ({len(removed)}):\n" + "\n".join([f"- {w.upper()}" for w in removed])
        await update.message.reply_text(msg)
    else:
        await update.message.reply_text("Words not found.")

async def clear_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    BANNED_WORDS.clear()
    save_all()
    await update.message.reply_text("ALL BANNED WORDS CLEARED.")

async def list_words(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not BANNED_WORDS:
        txt = "NO BANNED WORDS"
    else:
        txt = "\n".join([f"- {w.upper()}" for w in BANNED_WORDS])
    await update.message.reply_text(f"BANNED WORDS ({len(BANNED_WORDS)}):\n{txt}")

async def toggle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    SETTINGS["allow_photos"] = not SETTINGS["allow_photos"]
    save_all()
    await update.message.reply_text(f"PHOTO SHARING: {'ON' if SETTINGS['allow_photos'] else 'OFF'}")

async def broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    update_activity(update.effective_user.id)
    if not context.args:
        await update.message.reply_text("USAGE: /broadcast <message>")
        return
    msg = " ".join(context.args)
    count = 0
    for uid in list(ALLOWED_USERS.keys()):
        try:
            await context.bot.send_message(int(uid), f"ADMIN BROADCAST:\n\n{msg}")
            count += 1
        except:
            pass
    await update.message.reply_text(f"Broadcast sent to {count} users.")

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
            await update.message.reply_text(f"WARNING MESSAGE BLOCKED - BANNED WORD: '{bw.upper()}'")
            try:
                await context.bot.send_message(ADMIN_ID, f"{ALLOWED_USERS.get(sid, sid).upper()} TRIED BANNED WORD '{bw.upper()}': {text_content[:200]}")
            except:
                pass
            return
    if not is_admin and update.message.photo and not SETTINGS["allow_photos"]:
        await update.message.reply_text("PHOTO SHARING IS OFF BY ADMIN.")
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
        badge = "🟢" if is_user_online(uid) else "⚫"
    else:
        raw_label = ALLOWED_USERS.get(sid, sid).upper()
        icon = USER_ICONS.get(raw_label, "👤")
        badge = "🟢" if is_user_online(sid) else "⚫"
    formatted_text = f"{icon} <b>{raw_label}</b> {badge}: {text_content}" if text_content else f"{icon} <b>{raw_label}</b> {badge} SENT A PHOTO"
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
    
    # ===== MENU BUTTON SETUP - NEW FEATURE =====
    # Default menu for all users - only /start
    default_commands = [
        BotCommand("start", "Start bot / Request access")
    ]
    
    # Admin menu - all admin commands
    admin_commands = [
        BotCommand("start", "Admin panel / Start"),
        BotCommand("users", "List users with online status"),
        BotCommand("online", "Live online check"),
        BotCommand("removeuser", "Remove user - with buttons"),
        BotCommand("adduser", "Add user by ID"),
        BotCommand("pending", "Pending join requests"),
        BotCommand("getid", "Get ID via forward/reply"),
        BotCommand("broadcast", "Broadcast message to all"),
        BotCommand("words", "List banned words"),
        BotCommand("addword", "Add banned words"),
        BotCommand("removeword", "Remove banned word"),
        BotCommand("clearwords", "Clear all banned words"),
        BotCommand("togglephoto", "Toggle photo sharing"),
        BotCommand("myid", "Get your own ID"),
    ]
    
    try:
        # Set default commands for everyone (only /start)
        await app.bot.set_my_commands(default_commands, scope=BotCommandScopeDefault())
        logging.info("Default menu set: /start only")
        
        # Set admin commands only for admin chat
        await app.bot.set_my_commands(admin_commands, scope=BotCommandScopeChat(chat_id=ADMIN_ID))
        logging.info(f"Admin menu set for {ADMIN_ID}")
    except Exception as e:
        logging.error(f"Failed to set menu commands: {e}")
    
    await asyncio.sleep(1)
    try:
        await app.bot.send_message(ADMIN_ID, "🔄 BOT RESTARTED V8\n✅ Menu Button Added!\nAdmin sees all commands, users see only /start\nBot is online!")
    except:
        pass
    for uid in list(ALLOWED_USERS.keys()):
        try:
            await app.bot.send_message(int(uid), "🔄 BOT RESTARTED\n✅ V8 Menu Update!\nBot is online again!")
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
    
    print("Bot Started V8 - Menu Button Feature")
    app.run_polling(stop_signals=None, allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
