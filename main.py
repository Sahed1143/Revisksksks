import telebot
from telebot import types
import json
import os
from flask import Flask
from threading import Thread
import pymongo

# ================== আপনার কনফিগারেশন ==================
API_TOKEN = '8967501202:AAGVVeNJJQXcIP8GBhQqx4YkjHCyTzkt4gE'
ADMIN_IDS = [8262679678, 8915096050]  # একাধিক এডমিন আইডি

# চ্যানেল কনফিগারেশন
CHANNELS = [
    {"id": -1003730354126, "link": "https://t.me/incomebd0190", "name": "Income BD Channel"},
    {"id": -1002183552076, "link": "https://t.me/winfanti", "name": "Winfanti Channel"}
]

# MongoDB URI (Render এ ডাটা সেভ রাখার জন্য)
MONGO_URI = os.getenv("MONGO_URI", "")
# ==========================================================

DATA_FILE = 'bot_config.json'
bot = telebot.TeleBot(API_TOKEN)

# ডাটাবেজ সেটআপ (MongoDB অথবা JSON)
use_mongo = False
db_collection = None

if MONGO_URI:
    try:
        client = pymongo.MongoClient(MONGO_URI)
        db = client['telegram_bot']
        db_collection = db['config']
        use_mongo = True
        print("Connected to MongoDB successfully!")
    except Exception as e:
        print(f"MongoDB Connection Error: {e}")

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
    ]
}

def load_data():
    if use_mongo:
        data = db_collection.find_one({"_id": "bot_settings"})
        if not data:
            db_collection.insert_one(default_data)
            return default_data
        return data
    else:
        if not os.path.exists(DATA_FILE):
            save_data(default_data)
            return default_data
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)

def save_data(data):
    if use_mongo:
        db_collection.replace_one({"_id": "bot_settings"}, data, upsert=True)
    else:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
    
    # ডাটা সেভ হওয়ার পর টেলিগ্রামের মেনু বার আপডেট করা হবে
    sync_telegram_menu_commands()

# ================== টেলিগ্রাম মেনু বার (Bot Commands) আপডেট ==================
def sync_telegram_menu_commands():
    try:
        data = load_data()
        commands = [
            types.BotCommand("start", "🚀 স্টার্ট করুন"),
            types.BotCommand("admin", "⚙️ এডমিন ড্যাশবোর্ড")
        ]
        # কাস্টম বাটনগুলোকে বোটের মেনু বারে যোগ করা
        for btn in data.get("buttons", []):
            cmd_name = f"btn_{btn['id']}"
            cmd_desc = btn['title'][:25]  # মেনু ডেসক্রিপশনের সর্বোচ্চ দৈর্ঘ্য
            commands.append(types.BotCommand(cmd_name, cmd_desc))
            
        bot.set_my_commands(commands)
    except Exception as e:
        print(f"Error updating commands menu: {e}")

# ================== Keep Alive Web Server (Render এর জন্য) ==================
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

# ================== মেইন মেনু কিবোর্ড ==================
def get_main_keyboard(user_id):
    data = load_data()
    markup = types.ReplyKeyboardMarkup(row_width=2, resize_keyboard=True)
    buttons = [types.KeyboardButton(b["title"]) for b in data["buttons"]]
    markup.add(*buttons)
    
    if user_id in ADMIN_IDS:
        markup.add(types.KeyboardButton("⚙️ এডমিন ড্যাশবোর্ড"))
        
    return markup

# ================== কনটেন্ট পাঠানোর নিরাপদ ফাংশন ==================
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
        # কোনো কারণে HTML প্রসেস করতে না পারলে প্লেইন টেক্সট হিসেবে পাঠাবে
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

# Start Command
@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not is_user_subscribed(message.from_user.id):
        send_force_join_msg(message.chat.id)
        return

    data = load_data()
    bot.send_message(
        message.chat.id, 
        data.get("welcome_text", "বটে আপনাকে স্বাগতম!"), 
        reply_markup=get_main_keyboard(message.from_user.id)
    )

# ড্যাশবোর্ড
@bot.message_handler(commands=['admin'])
@bot.message_handler(func=lambda m: m.text == "⚙️ এডমিন ড্যাশবোর্ড")
def open_dashboard(message):
    if message.from_user.id not in ADMIN_IDS:
        bot.reply_to(message, "❌ আপনি এই বোটের এডমিন নন।")
        return
    show_dashboard_menu(message.chat.id)

def show_dashboard_menu(chat_id):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ নতুন বাটন যোগ করুন", callback_data="add_btn"))
    markup.add(types.InlineKeyboardButton("📝 ওয়েলকাম মেসেজ পরিবর্তন", callback_data="edit_welcome"))
    markup.add(types.InlineKeyboardButton("🔄 মেনু বার আপডেট করুন", callback_data="sync_menu"))
    
    data = load_data()
    for btn in data["buttons"]:
        markup.add(types.InlineKeyboardButton(f"⚙️ {btn['title']}", callback_data=f"manage_btn_{btn['id']}"))
        
    bot.send_message(
        chat_id, 
        "📊 **এডমিন ড্যাশবোর্ড**\n\nনিচের বাটনগুলোতে ক্লিক করে বোট কাস্টমাইজ করুন:", 
        reply_markup=markup, 
        parse_mode="Markdown"
    )

# ইনলাইন বাটন হ্যান্ডলার
@bot.callback_query_handler(func=lambda call: True)
def handle_dashboard_callbacks(call):
    chat_id = call.message.chat.id

    if call.data == "check_subscription":
        if is_user_subscribed(call.from_user.id):
            bot.answer_callback_query(call.id, "✅ ধন্যবাদ! আপনি সফলভাবে জয়েন করেছেন।")
            bot.delete_message(chat_id, call.message.message_id)
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
            "এখনই আপনার কাঙ্ক্ষিত **ভয়েস নোট**, **ভিডিও**, **অডিও**, **ছবি**, **ফাইল/ডকুমেন্ট** অথবা **মেসেজ** পাঠিয়ে দিন।"
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
    new_id = max([b["id"] for b in data["buttons"]], default=0) + 1
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
    for b in data["buttons"]:
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

    for b in data["buttons"]:
        if b["id"] == btn_id:
            b["content_type"] = content_type
            b["file_id"] = file_id
            b["text"] = text
            break

    save_data(data)
    bot.send_message(message.chat.id, "✅ এই বাটনের কনটেন্ট সফলভাবে সেভ হয়েছে!")
    show_dashboard_menu(message.chat.id)

# ================== মেনু বার (Command Menu) রেসপন্স ==================
@bot.message_handler(func=lambda m: m.text and m.text.startswith('/btn_'))
def handle_menu_command_clicks(message):
    if not is_user_subscribed(message.from_user.id):
        send_force_join_msg(message.chat.id)
        return
    
    try:
        btn_id = int(message.text.replace('/btn_', ''))
        data = load_data()
        for btn in data["buttons"]:
            if btn["id"] == btn_id:
                send_button_content(message.chat.id, btn)
                return
    except Exception as e:
        print(f"Error handling menu command: {e}")

# ================== ইউজার রেসপন্স (কিবোর্ড বাটন ক্লিক) ==================
@bot.message_handler(content_types=['text', 'voice', 'audio', 'video', 'photo', 'document'])
def handle_user_clicks(message):
    if not is_user_subscribed(message.from_user.id):
        send_force_join_msg(message.chat.id)
        return

    if message.text == "⚙️ এডমিন ড্যাশবোর্ড":
        return

    data = load_data()
    user_text = message.text

    for btn in data["buttons"]:
        if btn["title"] == user_text:
            send_button_content(message.chat.id, btn)
            return

if __name__ == '__main__':
    keep_alive()  # Web server চালু হবে
    sync_telegram_menu_commands()  # বট স্টার্ট হওয়ার সাথে সাথে মেনু বার সেট হবে
    print("Bot is starting successfully...")
    bot.infinity_polling(skip_pending=True)
