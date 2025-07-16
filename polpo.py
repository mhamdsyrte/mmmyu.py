# -*- coding: utf-8 -*-
import sqlite3
import re
from datetime import datetime
import telebot
from telebot import types

# --- إعدادات الأدمن ---
ADMIN_ID = 6874272305
bot = telebot.TeleBot("8061968121:AAGpz5LYRAXHbl1RBk8ibbwqgUutq5eQuqs", parse_mode="HTML")

# تهيئة قاعدة البيانات
conn = sqlite3.connect('tasks.db', check_same_thread=False)
cursor = conn.cursor()

# إنشاء الجداول
cursor.execute('''CREATE TABLE IF NOT EXISTS users
             (user_id INTEGER PRIMARY KEY, 
              username TEXT,
              first_name TEXT,
              balance REAL DEFAULT 0,
              tasks_completed INTEGER DEFAULT 0,
              withdrawals INTEGER DEFAULT 0,
              deposits INTEGER DEFAULT 0,
              banned INTEGER DEFAULT 0,
              reg_date TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS tasks
             (task_id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER,
              type TEXT,
              target TEXT,
              reward REAL,
              count INTEGER,
              status TEXT DEFAULT 'pending',
              creation_date TEXT)''')

cursor.execute('''CREATE TABLE IF NOT EXISTS transactions
             (trans_id INTEGER PRIMARY KEY AUTOINCREMENT,
              user_id INTEGER,
              amount REAL,
              type TEXT,
              method TEXT,
              admin_id INTEGER,
              date TEXT)''')

conn.commit()

# متغيرات مؤقتة
pending_ads = {}
admin_pending = {}

# تحقق من صلاحية الأدمن
def is_admin(user_id):
    return user_id == ADMIN_ID

# تحقق من رابط صحيح
def is_valid_url(url):
    regex = re.compile(
        r'^(https?://)?'  # http:// or https://
        r'(?:(?:[A-Z0-9](?:[A-Z0-9-]{0,61}[A-Z0-9])?\.)+[A-Z]{2,6}\.?|'  # domain...
        r'localhost|'  # localhost...
        r'\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3})'  # ...or ip
        r'(?::\d+)?'  # optional port
        r'(?:/?|[/?]\S+)$', re.IGNORECASE)
    return re.match(regex, url) is not None

# تحقق من رابط بوت
def is_bot_link(url):
    return url.startswith('https://t.me/') or url.startswith('@')

# تحقق من رابط قناة
def is_channel_link(url):
    return url.startswith('https://t.me/') or url.startswith('@')

# --- واجهة المستخدم العادي ---
@bot.message_handler(commands=['start'])
def start(message):
    user_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name
    reg_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # إضافة المستخدم إذا لم يكن موجوداً
    cursor.execute("INSERT OR IGNORE INTO users (user_id, username, first_name, reg_date) VALUES (?, ?, ?, ?)",
                  (user_id, username, first_name, reg_date))
    conn.commit()
    
    welcome = """
مرحباً بك في بوت المهام 🏆

اختر أحد الخيارات:
- المهام ⚡
- رصيدك 💰
- الإعلان 📢
- المساعدة ❓
    """
    keyboard = types.ReplyKeyboardMarkup(resize_keyboard=True)
    keyboard.row("⚡ المهام", "💰 الرصيد")
    keyboard.row("📢 اعلن", "❓ المساعدة")
    
    bot.send_message(message.chat.id, welcome, reply_markup=keyboard)

@bot.message_handler(func=lambda m: m.text == "⚡ المهام")
def tasks_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🤖 بوتات", callback_data="tasks_bots"))
    markup.add(types.InlineKeyboardButton("📣 قنوات", callback_data="tasks_channels"))
    markup.add(types.InlineKeyboardButton("🔗 روابط", callback_data="tasks_links"))
    markup.add(types.InlineKeyboardButton("📝 مهام فردية", callback_data="tasks_custom"))
    
    bot.send_message(message.chat.id, "اختر نوع المهام:", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "💰 الرصيد")
def balance_menu(message):
    cursor.execute("SELECT balance FROM users WHERE user_id=?", (message.from_user.id,))
    balance = cursor.fetchone()
    balance_amount = balance[0] if balance else 0.0
    
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ إضافة رصيد", callback_data="add_balance"))
    markup.add(types.InlineKeyboardButton("➖ سحب رصيد", callback_data="withdraw"))
    
    bot.send_message(message.chat.id, f"رصيدك: {balance_amount:.3f}$", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "withdraw")
def withdraw_methods(call):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("💳 Payeer", callback_data="withdraw_payeer"))
    markup.add(types.InlineKeyboardButton("💰 Cwallet", callback_data="withdraw_cwallet"))
    markup.add(types.InlineKeyboardButton("🔐 Tonkeeper", callback_data="withdraw_ton"))
    markup.add(types.InlineKeyboardButton("🏦 Binance", callback_data="withdraw_binance"))
    
    bot.edit_message_text(
        "اختر طريقة السحب (الحد الأدنى 0.50$):",
        call.message.chat.id,
        call.message.message_id,
        reply_markup=markup
    )

@bot.message_handler(func=lambda m: m.text == "📢 اعلن")
def ad_menu(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🤖 بوت", callback_data="ad_bot"))
    markup.add(types.InlineKeyboardButton("📣 قناة", callback_data="ad_channel"))
    markup.add(types.InlineKeyboardButton("🔗 رابط", callback_data="ad_link"))
    markup.add(types.InlineKeyboardButton("📝 مهمة فردية", callback_data="ad_custom"))
    
    bot.send_message(message.chat.id, "اختر نوع الإعلان:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith('ad_'))
def handle_ad_type(call):
    ad_type = call.data.split('_')[1]
    user_id = call.from_user.id
    
    if ad_type == 'bot':
        msg = bot.send_message(call.message.chat.id, "📌 أرسل رابط البوت (يجب أن يبدأ ب https://t.me/ أو @):")
        bot.register_next_step_handler(msg, process_bot_link, user_id)
    elif ad_type == 'channel':
        msg = bot.send_message(call.message.chat.id, "📢 رفع البوت مشرف في القناة مع الصلاحيات المطلوبة ثم أرسل رابط القناة (يجب أن يبدأ ب https://t.me/ أو @):")
        bot.register_next_step_handler(msg, process_channel_link, user_id)
    elif ad_type == 'link':
        msg = bot.send_message(call.message.chat.id, "🔗 أرسل الرابط الذي تريد الترويج له:")
        bot.register_next_step_handler(msg, process_link, user_id)
    elif ad_type == 'custom':
        msg = bot.send_message(call.message.chat.id, "📝 أرسل وصف المهمة الفردية:")
        bot.register_next_step_handler(msg, process_custom_task, user_id)

def process_bot_link(message, user_id):
    if not is_bot_link(message.text):
        msg = bot.send_message(message.chat.id, "❌ الرابط غير صالح. يجب أن يبدأ ب https://t.me/ أو @")
        bot.register_next_step_handler(msg, process_bot_link, user_id)
        return
        
    pending_ads[user_id] = {'type': 'bot', 'target': message.text}
    msg = bot.send_message(message.chat.id, "🔢 أرسل عدد الحسابات المطلوبة (الحد الأدنى 100 حساب):")
    bot.register_next_step_handler(msg, process_bot_count, user_id)

def process_bot_count(message, user_id):
    try:
        count = int(message.text)
        if count < 100:
            msg = bot.send_message(message.chat.id, "❌ الحد الأدنى هو 100 حساب")
            bot.register_next_step_handler(msg, process_bot_count, user_id)
            return
            
        pending_ads[user_id]['count'] = count
        msg = bot.send_message(message.chat.id, "💰 أرسل السعر لكل حساب (الحد الأدنى 0.003$):")
        bot.register_next_step_handler(msg, process_bot_price, user_id)
    except:
        msg = bot.send_message(message.chat.id, "❌ الرجاء إدخال رقم صحيح")
        bot.register_next_step_handler(msg, process_bot_count, user_id)

def process_bot_price(message, user_id):
    try:
        price = float(message.text)
        if price < 0.003:
            msg = bot.send_message(message.chat.id, "❌ الحد الأدنى هو 0.003$ لكل حساب")
            bot.register_next_step_handler(msg, process_bot_price, user_id)
            return
            
        pending_ads[user_id]['price'] = price
        total_cost = price * pending_ads[user_id]['count']
        
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = cursor.fetchone()
        balance_amount = balance[0] if balance else 0.0
        
        if balance_amount < total_cost:
            bot.send_message(message.chat.id, f"❌ رصيدك غير كافي. تحتاج إلى {total_cost:.3f}$ بينما رصيدك هو {balance_amount:.3f}$")
            return
            
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ تأكيد", callback_data="confirm_ad"))
        markup.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_ad"))
        
        bot.send_message(
            message.chat.id,
            f"""📋 تفاصيل الإعلان:
            
نوع الإعلان: بوت 🤖
الرابط: {pending_ads[user_id]['target']}
عدد الحسابات: {pending_ads[user_id]['count']}
السعر لكل حساب: {price:.3f}$
التكلفة الإجمالية: {total_cost:.3f}$

رصيدك الحالي: {balance_amount:.3f}$
الرصيد بعد الخصم: {(balance_amount - total_cost):.3f}$""",
            reply_markup=markup
        )
    except:
        msg = bot.send_message(message.chat.id, "❌ الرجاء إدخال سعر صحيح")
        bot.register_next_step_handler(msg, process_bot_price, user_id)

def process_channel_link(message, user_id):
    if not is_channel_link(message.text):
        msg = bot.send_message(message.chat.id, "❌ الرابط غير صالح. يجب أن يبدأ ب https://t.me/ أو @")
        bot.register_next_step_handler(msg, process_channel_link, user_id)
        return
        
    pending_ads[user_id] = {'type': 'channel', 'target': message.text}
    msg = bot.send_message(message.chat.id, "🔢 أرسل عدد المشتركين المطلوب (الحد الأدنى 500 مشترك):")
    bot.register_next_step_handler(msg, process_channel_count, user_id)

def process_channel_count(message, user_id):
    try:
        count = int(message.text)
        if count < 500:
            msg = bot.send_message(message.chat.id, "❌ الحد الأدنى هو 500 مشترك")
            bot.register_next_step_handler(msg, process_channel_count, user_id)
            return
            
        pending_ads[user_id]['count'] = count
        msg = bot.send_message(message.chat.id, "💰 أرسل السعر لكل مشترك (الحد الأدنى 0.003$):")
        bot.register_next_step_handler(msg, process_channel_price, user_id)
    except:
        msg = bot.send_message(message.chat.id, "❌ الرجاء إدخال رقم صحيح")
        bot.register_next_step_handler(msg, process_channel_count, user_id)

def process_channel_price(message, user_id):
    try:
        price = float(message.text)
        if price < 0.003:
            msg = bot.send_message(message.chat.id, "❌ الحد الأدنى هو 0.003$ لكل مشترك")
            bot.register_next_step_handler(msg, process_channel_price, user_id)
            return
            
        pending_ads[user_id]['price'] = price
        total_cost = price * pending_ads[user_id]['count']
        
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = cursor.fetchone()
        balance_amount = balance[0] if balance else 0.0
        
        if balance_amount < total_cost:
            bot.send_message(message.chat.id, f"❌ رصيدك غير كافي. تحتاج إلى {total_cost:.3f}$ بينما رصيدك هو {balance_amount:.3f}$")
            return
            
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✅ تأكيد", callback_data="confirm_ad"))
        markup.add(types.InlineKeyboardButton("❌ إلغاء", callback_data="cancel_ad"))
        
        bot.send_message(
            message.chat.id,
            f"""📋 تفاصيل الإعلان:
            
نوع الإعلان: قناة 📣
الرابط: {pending_ads[user_id]['target']}
عدد المشتركين: {pending_ads[user_id]['count']}
السعر لكل مشترك: {price:.3f}$
التكلفة الإجمالية: {total_cost:.3f}$

رصيدك الحالي: {balance_amount:.3f}$
الرصيد بعد الخصم: {(balance_amount - total_cost):.3f}$""",
            reply_markup=markup
        )
    except:
        msg = bot.send_message(message.chat.id, "❌ الرجاء إدخال سعر صحيح")
        bot.register_next_step_handler(msg, process_channel_price, user_id)

@bot.callback_query_handler(func=lambda c: c.data == "confirm_ad")
def confirm_ad(call):
    user_id = call.from_user.id
    if user_id not in pending_ads:
        bot.answer_callback_query(call.id, "❌ انتهت صلاحية الطلب")
        return
        
    ad_data = pending_ads[user_id]
    total_cost = ad_data['price'] * ad_data['count']
    
    cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (total_cost, user_id))
    
    creation_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("INSERT INTO tasks (user_id, type, target, reward, count, creation_date) VALUES (?, ?, ?, ?, ?, ?)",
                  (user_id, ad_data['type'], ad_data['target'], ad_data['price'], ad_data['count'], creation_date))
    conn.commit()
    
    bot.edit_message_text(
        "✅ تم نشر إعلانك بنجاح وسيتم مراجعته من قبل الإدارة",
        call.message.chat.id,
        call.message.message_id
    )
    
    task_id = cursor.lastrowid
    bot.send_message(
        ADMIN_ID,
        f"""📢 طلب إعلان جديد:
        
معرف المهمة: {task_id}
نوع الإعلان: {ad_data['type']}
الرابط: {ad_data['target']}
العدد: {ad_data['count']}
السعر: {ad_data['price']}$
التكلفة: {total_cost:.3f}$
        
من المستخدم: @{call.from_user.username} ({call.from_user.id})"""
    )
    
    del pending_ads[user_id]

@bot.callback_query_handler(func=lambda c: c.data == "cancel_ad")
def cancel_ad(call):
    user_id = call.from_user.id
    if user_id in pending_ads:
        del pending_ads[user_id]
    
    bot.edit_message_text(
        "❌ تم إلغاء الطلب",
        call.message.chat.id,
        call.message.message_id
    )

@bot.message_handler(func=lambda m: m.text == "❓ المساعدة")
def help_menu(message):
    help_text = """
⚡ بوت المهام البسيط ⚡

- اختر "المهام" لرؤية المهام المتاحة
- اختر "الرصيد" لإدارة رصيدك
- اختر "اعلن" لنشر إعلان جديد

للتواصل: @username
    """
    bot.send_message(message.chat.id, help_text)

# --- واجهة الأدمن ---
@bot.message_handler(commands=['admin'])
def admin_panel(message):
    if not is_admin(message.from_user.id):
        bot.reply_to(message, "⛔ ليس لديك صلاحية الدخول هنا")
        return
    
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    markup.add("👥 إدارة المستخدمين", "📊 إحصائيات البوت")
    markup.add("💼 إدارة الرصيد", "📋 المهام المعلقة")
    markup.add("📢 إرسال إشعار عام", "🔙 القائمة الرئيسية")
    
    bot.send_message(message.chat.id, "👨‍💼 لوحة تحكم الإدمن", reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👥 إدارة المستخدمين" and is_admin(m.from_user.id))
def manage_users(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔍 عرض معلومات مستخدم", callback_data="admin_view_user"))
    markup.add(types.InlineKeyboardButton("⛔ حظر مستخدم", callback_data="admin_ban_user"))
    markup.add(types.InlineKeyboardButton("✅ فك حظر مستخدم", callback_data="admin_unban_user"))
    markup.add(types.InlineKeyboardButton("📜 قائمة المحظورين", callback_data="admin_banned_list"))
    
    bot.send_message(message.chat.id, "اختر إجراء:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_view_user" and is_admin(c.from_user.id))
def admin_view_user(call):
    msg = bot.send_message(call.message.chat.id, "أرسل معرف المستخدم (ID):")
    bot.register_next_step_handler(msg, process_admin_view_user)

def process_admin_view_user(message):
    try:
        user_id = int(message.text)
        cursor.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        user = cursor.fetchone()
        
        if user:
            cursor.execute("SELECT COUNT(*) FROM tasks WHERE user_id=?", (user_id,))
            tasks_count = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id=? AND type='withdrawal'", (user_id,))
            withdrawals = cursor.fetchone()[0]
            
            cursor.execute("SELECT COUNT(*) FROM transactions WHERE user_id=? AND type='deposit'", (user_id,))
            deposits = cursor.fetchone()[0]
            
            info = f"""
📋 معلومات المستخدم:
            
🆔 المعرف: {user[0]}
👤 الاسم: {user[2]}
📛 اليوزر: @{user[1]}
💰 الرصيد: {user[3]:.3f}$
📅 تاريخ التسجيل: {user[8]}
            
📊 الإحصائيات:
📌 المهام المنجزة: {user[4]}
🔄 السحوبات: {withdrawals}
➕ الإيداعات: {deposits}
⛔ الحالة: {"محظور" if user[7] else "نشط"}
            """
            bot.send_message(message.chat.id, info)
        else:
            bot.send_message(message.chat.id, "❌ المستخدم غير موجود")
    except:
        bot.send_message(message.chat.id, "❌ يجب إدخال معرف صحيح")

@bot.callback_query_handler(func=lambda c: c.data == "admin_ban_user" and is_admin(c.from_user.id))
def admin_ban_user(call):
    msg = bot.send_message(call.message.chat.id, "أرسل معرف المستخدم (ID) للحظر:")
    bot.register_next_step_handler(msg, process_admin_ban_user)

def process_admin_ban_user(message):
    try:
        user_id = int(message.text)
        cursor.execute("UPDATE users SET banned=1 WHERE user_id=?", (user_id,))
        conn.commit()
        
        cursor.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
        username = cursor.fetchone()
        
        if username:
            bot.send_message(message.chat.id, f"✅ تم حظر المستخدم @{username[0]} بنجاح")
        else:
            bot.send_message(message.chat.id, "✅ تم حظر المستخدم بنجاح")
    except:
        bot.send_message(message.chat.id, "❌ حدث خطأ أثناء الحظر")

@bot.callback_query_handler(func=lambda c: c.data == "admin_unban_user" and is_admin(c.from_user.id))
def admin_unban_user(call):
    msg = bot.send_message(call.message.chat.id, "أرسل معرف المستخدم (ID) لفك الحظر:")
    bot.register_next_step_handler(msg, process_admin_unban_user)

def process_admin_unban_user(message):
    try:
        user_id = int(message.text)
        cursor.execute("UPDATE users SET banned=0 WHERE user_id=?", (user_id,))
        conn.commit()
        
        cursor.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
        username = cursor.fetchone()
        
        if username:
            bot.send_message(message.chat.id, f"✅ تم فك حظر المستخدم @{username[0]} بنجاح")
        else:
            bot.send_message(message.chat.id, "✅ تم فك حظر المستخدم بنجاح")
    except:
        bot.send_message(message.chat.id, "❌ حدث خطأ أثناء فك الحظر")

@bot.message_handler(func=lambda m: m.text == "💼 إدارة الرصيد" and is_admin(m.from_user.id))
def manage_balance(message):
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("➕ إضافة رصيد", callback_data="admin_add_balance"))
    markup.add(types.InlineKeyboardButton("➖ خصم رصيد", callback_data="admin_sub_balance"))
    markup.add(types.InlineKeyboardButton("📜 جميع الأرصدة", callback_data="admin_all_balances"))
    
    bot.send_message(message.chat.id, "اختر إجراء:", reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data == "admin_add_balance" and is_admin(c.from_user.id))
def admin_add_balance(call):
    msg = bot.send_message(call.message.chat.id, "أرسل معرف المستخدم (ID) والمبلغ بهذا الشكل:\n12345 10.5")
    bot.register_next_step_handler(msg, process_admin_add_balance)

def process_admin_add_balance(message):
    try:
        user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = float(amount)
        
        cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (amount, user_id))
        
        trans_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO transactions (user_id, amount, type, admin_id, date) VALUES (?, ?, ?, ?, ?)",
                      (user_id, amount, 'deposit', message.from_user.id, trans_date))
        
        conn.commit()
        
        cursor.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
        username = cursor.fetchone()
        
        if username:
            bot.send_message(message.chat.id, f"✅ تم إضافة {amount:.3f}$ لرصيد @{username[0]} بنجاح")
        else:
            bot.send_message(message.chat.id, f"✅ تم إضافة {amount:.3f}$ لرصيد المستخدم بنجاح")
    except:
        bot.send_message(message.chat.id, "❌ صيغة غير صحيحة. استخدم: ID المبلغ")

@bot.callback_query_handler(func=lambda c: c.data == "admin_sub_balance" and is_admin(c.from_user.id))
def admin_sub_balance(call):
    msg = bot.send_message(call.message.chat.id, "أرسل معرف المستخدم (ID) والمبلغ بهذا الشكل:\n12345 10.5")
    bot.register_next_step_handler(msg, process_admin_sub_balance)

def process_admin_sub_balance(message):
    try:
        user_id, amount = message.text.split()
        user_id = int(user_id)
        amount = float(amount)
        
        cursor.execute("SELECT balance FROM users WHERE user_id=?", (user_id,))
        balance = cursor.fetchone()[0]
        
        if balance < amount:
            bot.send_message(message.chat.id, "❌ رصيد المستخدم لا يكفي")
            return
            
        cursor.execute("UPDATE users SET balance = balance - ? WHERE user_id=?", (amount, user_id))
        
        trans_date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cursor.execute("INSERT INTO transactions (user_id, amount, type, admin_id, date) VALUES (?, ?, ?, ?, ?)",
                      (user_id, amount, 'withdrawal', message.from_user.id, trans_date))
        
        conn.commit()
        
        cursor.execute("SELECT username FROM users WHERE user_id=?", (user_id,))
        username = cursor.fetchone()
        
        if username:
            bot.send_message(message.chat.id, f"✅ تم خصم {amount:.3f}$ من رصيد @{username[0]} بنجاح")
        else:
            bot.send_message(message.chat.id, f"✅ تم خصم {amount:.3f}$ من رصيد المستخدم بنجاح")
    except:
        bot.send_message(message.chat.id, "❌ صيغة غير صحيحة. استخدم: ID المبلغ")

@bot.message_handler(func=lambda m: m.text == "📊 إحصائيات البوت" and is_admin(m.from_user.id))
def bot_stats(message):
    cursor.execute("SELECT COUNT(*) FROM users")
    total_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM users WHERE banned=1")
    banned_users = cursor.fetchone()[0]
    
    cursor.execute("SELECT SUM(balance) FROM users")
    total_balance = cursor.fetchone()[0] or 0
    
    cursor.execute("SELECT COUNT(*) FROM tasks")
    total_tasks = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tasks WHERE status='completed'")
    completed_tasks = cursor.fetchone()[0]
    
    stats = f"""
📊 إحصائيات البوت:

👥 إجمالي المستخدمين: {total_users}
⛔ المستخدمين المحظورين: {banned_users}
💰 إجمالي الأرصدة: {total_balance:.3f}$
📌 إجمالي المهام: {total_tasks}
✅ المهام المكتملة: {completed_tasks}
    """
    
    bot.send_message(message.chat.id, stats)

@bot.message_handler(func=lambda m: m.text == "📋 المهام المعلقة" and is_admin(m.from_user.id))
def pending_tasks(message):
    cursor.execute("SELECT * FROM tasks WHERE status='pending' ORDER BY creation_date DESC")
    tasks = cursor.fetchall()
    
    if not tasks:
        bot.send_message(message.chat.id, "لا توجد مهام معلقة حالياً")
        return
    
    for task in tasks:
        task_info = f"""
📌 مهمة #{task[0]}
👤 مقدم الطلب: {task[1]}
📝 النوع: {task[2]}
🔗 الرابط: {task[3]}
💰 السعر: {task[4]:.3f}$
🔢 العدد: {task[5]}
📅 التاريخ: {task[7]}
        """
        
        markup = types.InlineKeyboardMarkup()
        markup.add(
            types.InlineKeyboardButton("✅ قبول", callback_data=f"approve_task_{task[0]}"),
            types.InlineKeyboardButton("❌ رفض", callback_data=f"reject_task_{task[0]}")
        )
        
        bot.send_message(message.chat.id, task_info, reply_markup=markup)

@bot.callback_query_handler(func=lambda c: c.data.startswith(('approve_task_', 'reject_task_')) and is_admin(c.from_user.id))
def handle_task_decision(call):
    task_id = int(call.data.split('_')[2])
    action = call.data.split('_')[0]
    
    if action == 'approve':
        cursor.execute("UPDATE tasks SET status='active' WHERE task_id=?", (task_id,))
        conn.commit()
        
        cursor.execute("SELECT user_id FROM tasks WHERE task_id=?", (task_id,))
        user_id = cursor.fetchone()[0]
        
        bot.edit_message_text(f"✅ تم قبول المهمة #{task_id}", call.message.chat.id, call.message.message_id)
        bot.send_message(user_id, f"تم قبول طلبك للمهمة #{task_id} وتم تفعيلها")
    else:
        cursor.execute("SELECT user_id, reward, count FROM tasks WHERE task_id=?", (task_id,))
        task = cursor.fetchone()
        
        if task:
            total = task[1] * task[2]
            cursor.execute("UPDATE users SET balance = balance + ? WHERE user_id=?", (total, task[0]))
            cursor.execute("DELETE FROM tasks WHERE task_id=?", (task_id,))
            conn.commit()
            
            bot.edit_message_text(f"❌ تم رفض المهمة #{task_id}", call.message.chat.id, call.message.message_id)
            bot.send_message(task[0], f"تم رفض طلبك للمهمة #{task_id} وتم إعادة الرصيد ({total:.3f}$)")

@bot.message_handler(func=lambda m: m.text == "📢 إرسال إشعار عام" and is_admin(m.from_user.id))
def broadcast_message(message):
    msg = bot.send_message(message.chat.id, "أرسل الرسالة التي تريد نشرها لجميع المستخدمين:")
    bot.register_next_step_handler(msg, process_broadcast)

def process_broadcast(message):
    cursor.execute("SELECT user_id FROM users WHERE banned=0")
    users = cursor.fetchall()
    
    success = 0
    failed = 0
    
    for user in users:
        try:
            bot.send_message(user[0], f"📢 إشعار عام من الإدارة:\n\n{message.text}")
            success += 1
        except:
            failed += 1
    
    bot.send_message(message.chat.id, f"✅ تم إرسال الإشعار لـ {success} مستخدم\n❌ فشل الإرسال لـ {failed} مستخدم")

@bot.message_handler(func=lambda m: m.text == "🔙 القائمة الرئيسية" and is_admin(m.from_user.id))
def back_to_main(message):
    start(message)

print(f"Bot is running...\nAdmin ID: {ADMIN_ID}")
bot.infinity_polling()