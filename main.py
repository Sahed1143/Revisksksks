import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import pymongo
import time

# ================== কনফিগারেশন ==================
API_TOKEN = '8605665089:AAG0N4NlwlbuKUp_lPA_R-kM1eHe7E24y2k'
ADMIN_IDS = [8262679678, 8915096050]  # এডমিন আইডি

# চ্যানেল কনফিগারেশন
CHANNELS = [
    {"id": -1003730354126, "link": "https://t.me/incomebd0190", "name": "Income BD Channel"},
    {"id": -1002183552076, "link": "https://t.me/winfanti", "name": "Winfanti Channel"}
]

# MongoDB URI (Render Environment Variable থেকে নিবে)
MONGO_URI = os.getenv("MONGO_URI", "")
DATA_FILE = 'bot_config.json'

bot = telebot.TeleBot(API_TOKEN)

# ================== ডাটাবেজ সেটআপ (MongoDB / JSON) ==================
use_mongo = False
db_collection = None

if MONGO_URI:
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client['telegram_bot']
        db_collection = db['config']
        use_mongo = True
        print(" Connected to MongoDB successfully!")
    except Exception as e:
        print(f" MongoDB Connection Error: {e}")

default_data = {
    "_id": "bot_settings",
    "welcome_text": "বটে আপনাকে স্বাগতম! নিচের বাটন থেকে অপশন বেছে নিন।",
    "buttons": [
        {
            "id": 1,
            "title": "বাটন ১",
            "content_type": "text",
            "text": "এটি বাটন ১ এর তথ্য।",
            "file_id": None
        }
    ],
    "users": [] # ব্রডকাস্টের জন্য ইউজার লিস্ট
}

def load_data():
    if use_mongo:
        try:
            data = db_collection.find_one({"_id": "bot_settings"})
            if not data:
                db_collection.insert_one(default_data)
                return default_data
            if "users" not in data:
                data["users"] = []
                save_data(data)
            return data
        except Exception as e:
            print(f"Error loading Mongo data: {e}")
            return default_data
    else:
        if not os.path.exists(DATA_FILE):
            save_data(default_data)
            return default_data
        try:
            with open(DATA_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                if "users" not in data:
                    data["users"] = []
                return data
        except Exception:
            return default_data

def save_data(data):
    if use_mongo:
        try:
            db_collection.replace_one({"_id": "bot_settings"}, data, upsert=True)
        except Exception as e:
            print(f"Error saving to Mongo: {e}")
    else:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    sync_telegram_menu_commands()

def register_user(user_id):
    """ইউজারদের আইডি ডাটাবেজে সেভ রাখার জন্য ফাংশন"""
    data = load_data()
    users = data.get("users", [])
    if user_id not in users:
        users.append(user_id)
        data["users"] = users
        save_data(data)

# ================== টেলিগ্রাম মেনু বার আপডেট ==================
def sync_telegram_menu_commands():
    try:
        data = load_data()
        commands = [
            types.BotCommand("start", "🚀 স্টার্ট করুন"),
            types.BotCommand("admin", "⚙️ এডমিন ড্যাশবোর্ড")
        ]
        for btn in data.get("buttons", []):
            cmd_name = f"btn_{btn['id']}"
            cmd_desc = btn['title'][:25]
            commands.append(types.BotCommand(cmd_name, cmd_desc))
            
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Error updating commands menu: {e}")

# ================== Web Server (Render 24/7 এর জন্য) ==================
app = Flask('')

@app.route('/')
def home():
    return "Bot is Running Live 24/7!"

def run_flask():
    port = int(os.environ.get("PORT", 8080))
    app.run(host='0.0.0.0', port=port)

def keep_alive():
    t = Thread(target=run_flask)
    t.start()

# ================== চ্যানেল সাবস্ক্রিপশন চেক ==================
def is_user_subscribed(user_id):
    if user_id in ADMIN_IDS:
        return True
    for ch in CHANNELS:
        try:
            member = bot.get_chat_member(ch["id"], user_id)
            if member.status in ['left', 'kicked']:
                return False
        except Exception:
            return False
    return True

def send_force_join_msg(chat_id):
    markup = types.InlineKeyboardMarkup()
    for ch in CHANNELS:
        markup.add(types.InlineKeyboardButton(f"📢 Join {ch['name']}", url=ch["link"]))
    markup.add(types.InlineKeyboardButton("🔄 চেক করুন", callback_data="check_subscription"))
    
    bot.send_message(
        chat_id,
        "❌ **বটটি ব্যবহার করতে আপনাকে অবশ্যই আমাদের চ্যানেলগুলোতে জয়েন করতে হবে!**\n\nনিচের বাটনগুলো থেকে জয়েন করে '🔄 চেক করুন' বাটনে চাপ দিন।",
        reply_markup=markup,
        parse_mode="Markdown"
    )

# ================== মেনু কিবোর্ড ==================
def get_main_keyboard(user_id):
    data = load_data()
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [types.KeyboardButton(b["title"]) for b in data.get("buttons", [])]
    markup.add(*buttons)
    
    if user_id in ADMIN_IDS:
        markup.add(types.KeyboardButton("⚙️ এডমিন ড্যাশবোর্ড"))
        
    return markup

def send_button_content(chat_id, btn):
    c_type = btn.get("content_type", "text")
    f_id = btn.get("file_id")
    text = btn.get("text", "") or ""

    try:
        if c_type == "text":
            bot.send_message(chat_id, text, parse_mode="HTML")
        elif c_type == "voice":
            bot.send_voice(chat_id, f_id, caption=text, parse_mode="HTML")
        elif c_type == "audio":
            bot.send_audio(chat_id, f_id, caption=text, parse_mode="HTML")
        elif c_type == "video":
            bot.send_video(chat_id, f_id, caption=text, parse_mode="HTML")
        elif c_type == "photo":
            bot.send_photo(chat_id, f_id, caption=text, parse_mode="HTML")
        elif c_type == "document":
            bot.send_document(chat_id, f_id, caption=text, parse_mode="HTML")
    except Exception:
        if c_type == "text":
            bot.send_message(chat_id, text)
        elif c_type == "voice":
            bot.send_voice(chat_id, f_id, caption=text)
        elif c_type == "audio":
            bot.send_audio(chat_id, f_id, caption=text)
        elif c_type == "video":
            bot.send_video(chat_id, f_id, caption=text)
        elif c_type == "photo":
            bot.send_photo(chat_id, f_id, caption=text)
        elif c_type == "document":
            bot.send_document(chat_id, f_id, caption=text)

# ================== হ্যান্ডলারস ==================

# Start Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    register_user(message.from_user.id)
    
    if not is_user_subscribed(message.from_user.id):
        send_force_join_msg(message.chat.id)
        return

    data = load_data()
    bot.send_message(
        message.chat.id, 
        data.get("welcome_text", "বটে আপনাকে স্বাগতম!"), 
        reply_markup=get_main_keyboard(message.from_user.id)
    )

# এডমিন ড্যাশবোর্ড
@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda m: m.text == "⚙️ এডমিন ড্যাশবোর্ড")
def open_dashboard(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ আপনি এই বোটের এডমিন নন।")
        return
    show_dashboard_menu(message.chat.id)

def show_dashboard_menu(chat_id):
    data = load_data()
    total_users = len(data.get("users", []))
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ নতুন বাটন যোগ করুন", callback_data="add_btn"))
    markup.add(types.InlineKeyboardButton("📝 ওয়েলকাম মেসেজ পরিবর্তন", callback_data="edit_welcome"))
    markup.add(types.InlineKeyboardButton("📢 ব্রডকাস্ট (মেসেজ পাঠান)", callback_data="broadcast_msg"))
    markup.add(types.InlineKeyboardButton(f"👥 মোট ইউজার: {total_users}", callback_data="user_count"))
    markup.add(types.InlineKeyboardButton("🔄 মেনু বার আপডেট করুন", callback_data="sync_menu"))
    
    for btn in data.get("buttons", []):
        markup.add(types.InlineKeyboardButton(f"⚙️ {btn['title']}", callback_data=f"manage_btn_{btn['id']}"))
        
    bot.send_message(
        chat_id, 
        "📊 **এডমিন ড্যাশবোর্ড**\n\nনিচের বাটনগুলোতে ক্লিক করে বোট কাস্টমাইজ করুন:", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

# ইনলাইন কলব্যাক হ্যান্ডলার
@bot.callback_query_handler(func=lambda call: True)
def handle_dashboard_callbacks(call):
    chat_id = call.message.chat.id

    if call.data == "check_subscription":
        register_user(call.from_user.id)
        if is_user_subscribed(call.from_user.id):
            bot.answer_callback_query(call.id, "✅ ধন্যবাদ! আপনি সফলভাবে জয়েন করেছেন।")
            try:
                bot.delete_message(chat_id, call.message.message_id)
            except Exception:
                pass
            data = load_data()
            bot.send_message(chat_id, data.get("welcome_text", "স্বাগতম!"), reply_markup=get_main_keyboard(call.from_user.id))
        else:
            bot.answer_callback_query(call.id, "❌ আপনি এখনও সব চ্যানেলে জয়েন করেননি!", show_alert=True)
        return

    if call.from_user.id not in ADMIN_IDS:
        bot.answer_callback_query(call.id, "❌ অনুমতি নেই।")
        return

    data = load_data()

    if call.data == "add_btn":
        msg = bot.send_message(chat_id, "✏️ নতুন বাটনের **নাম (Title)** টি লিখে পাঠান:")
        bot.register_next_step_handler(msg, process_add_btn_title)

    elif call.data == "edit_welcome":
        msg = bot.send_message(chat_id, "✏️ নতুন **ওয়েলকাম টেক্সট** লিখে পাঠান:")
        bot.register_next_step_handler(msg, process_edit_welcome)

    elif call.data == "broadcast_msg":
        msg = bot.send_message(
            chat_id, 
            "📢 **ব্রডকাস্ট মেসেজ পাঠাতে চান?**\n\n"
            "এখন যে মেসেজ, ছবি, ভিডিও, ফাইল বা ভয়েস পাঠাবেন তা বোটের সকল ইউজার পেয়ে যাবে।"
        )
        bot.register_next_step_handler(msg, process_broadcast)

    elif call.data == "user_count":
        total = len(data.get("users", []))
        bot.answer_callback_query(call.id, f"👥 মোট নিবন্ধিত ইউজার: {total}", show_alert=True)

    elif call.data == "sync_menu":
        sync_telegram_menu_commands()
        bot.answer_callback_query(call.id, "✅ মেনু বার সফলভাবে আপডেট করা হয়েছে!", show_alert=True)

    elif call.data == "back_to_dashboard":
        show_dashboard_menu(chat_id)

    elif call.data.startswith("manage_btn_"):
        btn_id = int(call.data.split("_")[2])
        show_btn_options(chat_id, btn_id)

    elif call.data.startswith("edit_title_"):
        btn_id = int(call.data.split("_")[2])
        msg = bot.send_message(chat_id, "✏️ এই বাটনের নতুন **নাম (Title)** লিখে পাঠান:")
        bot.register_next_step_handler(msg, process_edit_btn_title, btn_id)

    elif call.data.startswith("edit_content_"):
        btn_id = int(call.data.split("_")[2])
        msg = bot.send_message(
            chat_id, 
            "🎙️📹🖼️📝📁 **বাটনের কনটেন্ট সেট করুন:**\n\n"
            "আপনার কাঙ্ক্ষিত **ভয়েস নোট**, **ভিডিও**, **অডিও**, **ছবি**, **ফাইল** অথবা **মেসেজ** পাঠিয়ে দিন।"
        )
        bot.register_next_step_handler(msg, process_edit_btn_content, btn_id)

    elif call.data.startswith("delete_btn_"):
        btn_id = int(call.data.split("_")[2])
        data["buttons"] = [b for b in data["buttons"] if b["id"] != btn_id]
        save_data(data)
        bot.send_message(chat_id, "🗑️ বাটনটি সফলভাবে ডিলিট করা হয়েছে!", reply_markup=get_main_keyboard(chat_id))
        show_dashboard_menu(chat_id)

def show_btn_options(chat_id, btn_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("✏️ বাটনের নাম পরিবর্তন", callback_data=f"edit_title_{btn_id}"))
    markup.add(types.InlineKeyboardButton("🎙️/📹/📝/📁 কনটেন্ট সেট করুন", callback_data=f"edit_content_{btn_id}"))
    markup.add(types.InlineKeyboardButton("🗑️ বাটন ডিলিট করুন", callback_data=f"delete_btn_{btn_id}"))
    markup.add(types.InlineKeyboardButton("🔙 ড্যাশবোর্ডে ফিরুন", callback_data="back_to_dashboard"))
    
    bot.send_message(chat_id, f"⚙️ **বাটন কাস্টমাইজেশন (ID: {btn_id})**", reply_markup=markup, parse_mode="Markdown")

def process_add_btn_title(message):
    if not message.text:
        bot.send_message(message.chat.id, "❌ বাটনের নাম সঠিক ছিল না। আবার চেষ্টা করুন।")
        return
    title = message.text
    data = load_data()
    new_id = max([b["id"] for b in data.get("buttons", [])], default=0) + 1
    data["buttons"].append({
        "id": new_id,
        "title": title,
        "content_type": "text",
        "text": "নতুন বাটন যুক্ত করা হয়েছে।",
        "file_id": None
    })
    save_data(data)
    bot.send_message(message.chat.id, f"✅ '{title}' বাটন তৈরি করা হয়েছে!", reply_markup=get_main_keyboard(message.chat.id))
    show_dashboard_menu(message.chat.id)

def process_edit_welcome(message):
    if not message.text:
        bot.send_message(message.chat.id, "❌ সঠিক ওয়েলকাম টেক্সট দিন।")
        return
    data = load_data()
    data["welcome_text"] = message.text
    save_data(data)
    bot.send_message(message.chat.id, "✅ ওয়েলকাম টেক্সট পরিবর্তন সফল হয়েছে!")
    show_dashboard_menu(message.chat.id)

def process_edit_btn_title(message, btn_id):
    if not message.text:
        bot.send_message(message.chat.id, "❌ বাটনের নাম সঠিক ছিল না।")
        return
    data = load_data()
    for b in data.get("buttons", []):
        if b["id"] == btn_id:
            b["title"] = message.text
            break
    save_data(data)
    bot.send_message(message.chat.id, "✅ বাটনের নাম পরিবর্তন করা হয়েছে!", reply_markup=get_main_keyboard(message.chat.id))
    show_dashboard_menu(message.chat.id)

def process_edit_btn_content(message, btn_id):
    data = load_data()
    content_type = "text"
    file_id = None
    text = message.caption if message.caption else ""

    if message.content_type == 'text':
        content_type = "text"
        text = message.text
    elif message.content_type == 'voice':
        content_type = "voice"
        file_id = message.voice.file_id
    elif message.content_type == 'audio':
        content_type = "audio"
        file_id = message.audio.file_id
    elif message.content_type == 'video':
        content_type = "video"
        file_id = message.video.file_id
    elif message.content_type == 'photo':
        content_type = "photo"
        file_id = message.photo[-1].file_id
    elif message.content_type == 'document':
        content_type = "document"
        file_id = message.document.file_id

    for b in data.get("buttons", []):
        if b["id"] == btn_id:
            b["content_type"] = content_type
            b["file_id"] = file_id
            b["text"] = text
            break

    save_data(data)
    bot.send_message(message.chat.id, "✅ এই বাটনের কনটেন্ট সফলভাবে সেভ হয়েছে!")
    show_dashboard_menu(message.chat.id)

# ================== ব্রডকাস্টিং প্রসেসর ==================
def process_broadcast(message):
    data = load_data()
    users = data.get("users", [])
    
    if not users:
        bot.send_message(message.chat.id, "❌ কোনো ব্রডকাস্ট করার মতো ইউজার ডাটাবেজে পাওয়া যায়নি।")
        return

    bot.send_message(message.chat.id, f"⏳ ব্রডকাস্টিং শুরু করা হয়েছে... (মোট ইউজার: {len(users)})")
    
    success = 0
    failed = 0

    for user_id in users:
        try:
            bot.copy_message(chat_id=user_id, from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            time.sleep(0.05)  # Telegram API limit এড়ানোর জন্য ক্ষুদ্র বিরতি
        except Exception:
            failed += 1

    bot.send_message(
        message.chat.id, 
        f"✅ **ব্রডকাস্ট সম্পন্ন হয়েছে!**\n\n"
        f"🚀 সফলভাবে পাঠানো হয়েছে: **{success}** জন\n"
        f"❌ ব্যর্থ/ব্লক করেছে: **{failed}** জন", 
        parse_mode="Markdown"
    )

# ================== মেনু বার (Command Menu) রেসপন্স ==================
@bot.message_handler(func=lambda m: m.text and m.text.startswith('/btn_'))
def handle_menu_command_clicks(message):
    register_user(message.from_user.id)
    if not is_user_subscribed(message.from_user.id):
        send_force_join_msg(message.chat.id)
        return
    
    try:
        btn_id = int(message.text.replace('/btn_', ''))
        data = load_data()
        for btn in data.get("buttons", []):
            if btn["id"] == btn_id:
                send_button_content(message.chat.id, btn)
                return
    except Exception as e:
        print(f"Error handling menu command: {e}")

# ================== সাধারণ ইউজার ক্লিকের হ্যান্ডলার ==================
@bot.message_handler(content_types=['text', 'voice', 'audio', 'video', 'photo', 'document'])
def handle_user_clicks(message):
    register_user(message.from_user.id)
    
    if not is_user_subscribed(message.from_user.id):
        send_force_join_msg(message.chat.id)
        return

    if message.text == "⚙️ এডমিন ড্যাশবোর্ড":
        return

    data = load_data()
    user_text = message.text

    for btn in data.get("buttons", []):
        if btn["title"] == user_text:
            send_button_content(message.chat.id, btn)
            return

# ================== মেইন স্টার্ট প্রসেস ==================
if __name__ == '__main__':
    keep_alive()  # Web server চালু
    sync_telegram_menu_commands()  # টেলিগ্রামের মূল মেনু বার আপডেট
    print("Bot is starting successfully...")
    
    # অটোমেটিক রিস্টার্ট ও কানেকশন ধরে রাখার প্রসেস
    while True:
        try:
            bot.infinity_polling(timeout=60, long_polling_timeout=30)
        except Exception as e:
            print(f"Bot Polling Error: {e}")
            time.sleep(5)
