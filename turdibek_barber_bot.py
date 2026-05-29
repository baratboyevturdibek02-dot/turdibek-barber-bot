import json, os
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, CallbackQueryHandler, ConversationHandler, filters, ContextTypes

TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "0"))
LOCATION_LAT = 40,5130926
LOCATION_LON = 68,7694332
LOCATION_ADDRESS = " Gulistan, Sirdaryo Region,Firdavs Salon,Qurilish ko'chasi"
DATA_FILE = "navbatlar.json"
CHOOSING_DATE, CHOOSING_TIME, ENTERING_NAME, ENTERING_PHONE, CONFIRMING = range(5)

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def is_slot_taken(date, time):
    return f"{date}_{time}" in load_data()

def save_appointment(date, time, user_id, name, phone, username):
    data = load_data()
    data[f"{date}_{time}"] = {"date": date, "time": time, "user_id": user_id, "name": name, "phone": phone, "username": username or "-"}
    save_data(data)

def cancel_appointment(date, time):
    data = load_data()
    key = f"{date}_{time}"
    if key in data:
        del data[key]
        save_data(data)
        return True
    return False

def get_next_days():
    days = []
    today = datetime.now()
    for i in range(7):
        day = today + timedelta(days=i)
        if day.weekday() < 6:
            days.append(day)
    return days

def fmt(dt):
    w = {0:"Dush",1:"Sesh",2:"Chor",3:"Pay",4:"Juma",5:"Shan",6:"Yak"}
    return f"{w[dt.weekday()]} {dt.strftime('%d.%m')}"

def get_slots():
    slots = []
    t = datetime.strptime("09:00", "%H:%M")
    e = datetime.strptime("22:00", "%H:%M")
    while t <= e:
        slots.append(t.strftime("%H:%M"))
        t += timedelta(minutes=30)
    return slots

def menu(is_admin=False):
    if is_admin:
        kb = [[KeyboardButton("📅 Navbat olish")],[KeyboardButton("📋 Bugungi mijozlar")],[KeyboardButton("📊 Barcha navbatlar")],[KeyboardButton("🕐 Bo'sh vaqtlar"), KeyboardButton("📍 Lokatsiya")],[KeyboardButton("ℹ️ Ma'lumot")]]
    else:
        kb = [[KeyboardButton("📅 Navbat olish")],[KeyboardButton("🕐 Bo'sh vaqtlar"), KeyboardButton("📍 Lokatsiya")],[KeyboardButton("ℹ️ Ma'lumot"), KeyboardButton("❌ Navbatni bekor qilish")]]
    return ReplyKeyboardMarkup(kb, resize_keyboard=True)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = user.id == ADMIN_ID
    text = f"✂️ *Turdibek_Barber* ga xush kelibsiz!\n\nSalom, {user.first_name}! 👋\n{'🔑 *Admin paneli*\n' if is_admin else ''}Tugmani tanlang:"
    await update.message.reply_text(text, parse_mode="Markdown", reply_markup=menu(is_admin))

async def navbat_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    days = get_next_days()
    btns = []
    row = []
    for d in days:
        row.append(InlineKeyboardButton(fmt(d), callback_data=f"date_{d.strftime('%Y-%m-%d')}"))
        if len(row) == 3:
            btns.append(row); row = []
    if row: btns.append(row)
    btns.append([InlineKeyboardButton("❌ Bekor", callback_data="cancel")])
    await update.message.reply_text("📅 *Kun tanlang:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return CHOOSING_DATE

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "cancel":
        await q.edit_message_text("❌ Bekor qilindi.")
        return ConversationHandler.END
    date = q.data.replace("date_", "")
    context.user_data["date"] = date
    slots = get_slots()
    btns = []
    row = []
    for s in slots:
        taken = is_slot_taken(date, s)
        row.append(InlineKeyboardButton(f"🔴 {s}" if taken else f"✅ {s}", callback_data="taken" if taken else f"time_{s}"))
        if len(row) == 4:
            btns.append(row); row = []
    if row: btns.append(row)
    btns.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back")])
    dt = datetime.strptime(date, "%Y-%m-%d")
    await q.edit_message_text(f"🕐 *{fmt(dt)} — vaqt tanlang:*\n✅ bo'sh  🔴 band", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return CHOOSING_TIME

async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "taken":
        await q.answer("❌ Bu vaqt band!", show_alert=True)
        return CHOOSING_TIME
    if q.data == "back":
        days = get_next_days()
        btns = []
        row = []
        for d in days:
            row.append(InlineKeyboardButton(fmt(d), callback_data=f"date_{d.strftime('%Y-%m-%d')}"))
            if len(row) == 3:
                btns.append(row); row = []
        if row: btns.append(row)
        btns.append([InlineKeyboardButton("❌ Bekor", callback_data="cancel")])
        await q.edit_message_text("📅 *Kun tanlang:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
        return CHOOSING_DATE
    context.user_data["time"] = q.data.replace("time_", "")
    await q.edit_message_text(f"✅ *{context.user_data['date']} soat {context.user_data['time']}*\n\n📝 Ismingizni kiriting:")
    return ENTERING_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("⚠️ Kamida 3 harf kiriting.")
        return ENTERING_NAME
    context.user_data["name"] = name
    await update.message.reply_text(f"👤 *{name}*\n\n📞 Telefon raqamingiz:\n_(+998901234567)_", parse_mode="Markdown")
    return ENTERING_PHONE

async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not (phone.startswith("+") and len(phone) >= 12):
        await update.message.reply_text("⚠️ Format: +998901234567")
        return ENTERING_PHONE
    context.user_data["phone"] = phone
    d = context.user_data["date"]
    t = context.user_data["time"]
    n = context.user_data["name"]
    dt = datetime.strptime(d, "%Y-%m-%d")
    btns = [[InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm"), InlineKeyboardButton("❌ Bekor", callback_data="cancel_b")]]
    await update.message.reply_text(
        f"📋 *Navbat:*\n\n📅 {fmt(dt)} ({d})\n🕐 {t}\n👤 {n}\n📞 {phone}\n\nTasdiqlaysizmi?",
        parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))
    return CONFIRMING

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "cancel_b":
        await q.edit_message_text("❌ Bekor qilindi.")
        return ConversationHandler.END
    user = update.effective_user
    d = context.user_data["date"]
    t = context.user_data["time"]
    n = context.user_data["name"]
    p = context.user_data["phone"]
    if is_slot_taken(d, t):
        await q.edit_message_text("⚠️ Bu vaqt band bo'ldi. Qaytadan urinib ko'ring.")
        return ConversationHandler.END
    save_appointment(d, t, user.id, n, p, user.username)
    dt = datetime.strptime(d, "%Y-%m-%d")
    await q.edit_message_text(
        f"🎉 *Navbat olindi!*\n\n📅 {fmt(dt)} ({d})\n🕐 {t}\n👤 {n}\n📞 {p}\n\n📍 {LOCATION_ADDRESS}\n\n_Vaqtida keling!_ ✂️",
        parse_mode="Markdown")
    try:
        await context.bot.send_message(ADMIN_ID, f"🔔 *Yangi navbat!*\n📅 {fmt(dt)} {t}\n👤 {n}\n📞 {p}", parse_mode="Markdown")
    except:
        pass
    return ConversationHandler.END

async def cancel_conv(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor.", reply_markup=menu())
    return ConversationHandler.END

async def bosh_vaqtlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = "🕐 *Bo'sh vaqtlar:*\n\n"
    for day in get_next_days():
        ds = day.strftime("%Y-%m-%d")
        free = [s for s in get_slots() if not is_slot_taken(ds, s)]
        text += f"📅 *{fmt(day)}*\n  " + ("  ".join(free[:10]) if free else "🔴 Band") + "\n\n"
    await update.message.reply_text(text, parse_mode="Markdown")

async def lokatsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📍 *Manzil:*\n{LOCATION_ADDRESS}", parse_mode="Markdown")
    await update.message.reply_location(latitude=LOCATION_LAT, longitude=LOCATION_LON)

async def malumot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✂️ *Turdibek Barber*\n\n💈 Xizmatlar:\n• Soch — 60.000\n• Soqol — 20.000\n• Soch+Soqol — 90.000\n• Bolalar — 40.000\n\n⏰ Dush-Shan 09:00-22:00\n📞 +998 94 971 04 05",
        parse_mode="Markdown")

async def bekor_qilish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    appts = [v for v in data.values() if v["user_id"] == user.id]
    if not appts:
        await update.message.reply_text("📭 Navbat yo'q.")
        return
    btns = [[InlineKeyboardButton(f"🗑 {a['date']} {a['time']}", callback_data=f"del_{a['date']}_{a['time']}")] for a in appts]
    btns.append([InlineKeyboardButton("❌ Yopish", callback_data="close")])
    await update.message.reply_text("📋 *Navbatlaringiz:*", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(btns))

async def del_cb(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()
    if q.data == "close":
        await q.edit_message_text("✅ Yopildi.")
        return
    if q.data.startswith("del_"):
        parts = q.data[4:].rsplit("_", 1)
        cancel_appointment(parts[0], parts[1])
        await q.edit_message_text(f"✅ Bekor qilindi.")

async def bugungi(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    today = datetime.now().strftime("%Y-%m-%d")
    appts = sorted([v for v in load_data().values() if v["date"] == today], key=lambda x: x["time"])
    if not appts:
        await update.message.reply_text(f"📭 Bugun navbat yo'q.")
        return
    text = f"📋 *Bugun ({today}):*\n\n"
    for i, a in enumerate(appts, 1):
        text += f"*{i}. {a['time']}* — {a['name']} | {a['phone']}\n"
    await update.message.reply_text(text + f"\n📊 Jami: {len(appts)}", parse_mode="Markdown")

async def barcha(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return
    data = load_data()
    if not data:
        await update.message.reply_text("📭 Navbat yo'q.")
        return
    appts = sorted(data.values(), key=lambda x: (x["date"], x["time"]))
    cur = None
    text = "📊 *Barcha navbatlar:*\n"
    for a in appts:
        if a["date"] != cur:
            cur = a["date"]
            dt = datetime.strptime(cur, "%Y-%m-%d")
            text += f"\n📅 *{fmt(dt)}:*\n"
        text += f"  🕐 {a['time']} — {a['name']} | {a['phone']}\n"
    await update.message.reply_text(text + f"\n📊 Jami: {len(appts)}", parse_mode="Markdown")

async def handle(update: Update, context: ContextTypes.DEFAULT_TYPE):
    t = update.message.text
    if t == "🕐 Bo'sh vaqtlar": await bosh_vaqtlar(update, context)
    elif t == "📍 Lokatsiya": await lokatsiya(update, context)
    elif t == "ℹ️ Ma'lumot": await malumot(update, context)
    elif t == "❌ Navbatni bekor qilish": await bekor_qilish(update, context)
    elif t == "📋 Bugungi mijozlar": await bugungi(update, context)
    elif t == "📊 Barcha navbatlar": await barcha(update, context)

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^📅 Navbat olish$"), navbat_start)],
        states={
            CHOOSING_DATE: [CallbackQueryHandler(choose_date)],
            CHOOSING_TIME: [CallbackQueryHandler(choose_time)],
            ENTERING_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTERING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone)],
            CONFIRMING: [CallbackQueryHandler(confirm)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conv)],
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv)
    app.add_handler(CallbackQueryHandler(del_cb, pattern="^(del_|close)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    print("Bot ishga tushdi!")
    app.run_polling()

if __name__ == "__main__":
    main()
