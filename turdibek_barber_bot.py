"""
Turdibek_Barber - Sartaroshxona Telegram Boti
O'zbek tilida navbat olish, bo'sh vaqtlar, lokatsiya va mijozlar ro'yxati
"""

import json
import os
from datetime import datetime, timedelta
from telegram import (
    Update, ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton
)
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, ConversationHandler, filters,
    ContextTypes
)

# ========================
# SOZLAMALAR
# ========================
TOKEN = os.environ.get("TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_ID"))

# Sartaroshxona lokatsiyasi
LOCATION_LAT = 40,5130926
LOCATION_LON = 68,7694332
LOCATION_ADDRESS = "Firdavs salon, Gulistan, Sirdaryo Region,Quruvchilar ko'chasi"

# Fayl — navbatlar saqlanadigan joy
DATA_FILE = "navbatlar.json"

# Conversation holatlari
(
    CHOOSING_DATE,
    CHOOSING_TIME,
    ENTERING_NAME,
    ENTERING_PHONE,
    CONFIRMING,
) = range(5)

# ========================
# MA'LUMOTLAR BOSHQARUVI
# ========================

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def get_appointments():
    return load_data()

def save_appointment(date, time, user_id, name, phone, username):
    data = load_data()
    key = f"{date}_{time}"
    data[key] = {
        "date": date,
        "time": time,
        "user_id": user_id,
        "name": name,
        "phone": phone,
        "username": username or "—",
        "booked_at": datetime.now().strftime("%d.%m.%Y %H:%M")
    }
    save_data(data)

def is_slot_taken(date, time):
    data = load_data()
    return f"{date}_{time}" in data

def cancel_appointment(date, time):
    data = load_data()
    key = f"{date}_{time}"
    if key in data:
        del data[key]
        save_data(data)
        return True
    return False

# ========================
# YORDAMCHI FUNKSIYALAR
# ========================

def get_next_days(n=7):
    """Keyingi N kun (dushanba-shanba)"""
    days = []
    today = datetime.now()
    for i in range(n):
        day = today + timedelta(days=i)
        if day.weekday() < 6:  # 0-5: Dush-Shanba (Yakshanba dam olish)
            days.append(day)
    return days

def format_date(dt):
    weekdays = {
        0: "Dush", 1: "Sesh", 2: "Chor",
        3: "Pay",  4: "Juma", 5: "Shan"
    }
    return f"{weekdays[dt.weekday()]} {dt.strftime('%d.%m')}"

def get_time_slots():
    """09:00 dan 19:00 gacha, har 30 daqiqa"""
    slots = []
    start = datetime.strptime("09:00", "%H:%M")
    end   = datetime.strptime("19:00", "%H:%M")
    while start <= end:
        slots.append(start.strftime("%H:%M"))
        start += timedelta(minutes=30)
    return slots

def main_menu_keyboard():
    keyboard = [
        [KeyboardButton("📅 Navbat olish")],
        [KeyboardButton("🕐 Bo'sh vaqtlar"), KeyboardButton("📍 Lokatsiya")],
        [KeyboardButton("ℹ️ Ma'lumot"), KeyboardButton("❌ Navbatni bekor qilish")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def admin_menu_keyboard():
    keyboard = [
        [KeyboardButton("📋 Bugungi mijozlar")],
        [KeyboardButton("📊 Barcha navbatlar")],
        [KeyboardButton("🗑 Navbat o'chirish")],
        [KeyboardButton("📅 Navbat olish")],
        [KeyboardButton("📍 Lokatsiya"), KeyboardButton("ℹ️ Ma'lumot")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ========================
# START
# ========================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = (user.id == ADMIN_ID)

    welcome = (
        f"✂️ *Turdibek_Barber* ga xush kelibsiz!\n\n"
        f"Salom, {user.first_name}! 👋\n"
        f"Men sizga qulay navbat olishda yordam beraman.\n\n"
        f"{'🔑 *Admin paneli ulandi*\n' if is_admin else ''}"
        f"Quyidagi tugmalardan birini tanlang:"
    )

    kb = admin_menu_keyboard() if is_admin else main_menu_keyboard()
    await update.message.reply_text(welcome, parse_mode="Markdown", reply_markup=kb)

# ========================
# NAVBAT OLISH — ConversationHandler
# ========================

async def navbat_olish_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    days = get_next_days(7)
    buttons = []
    row = []
    for i, day in enumerate(days):
        row.append(InlineKeyboardButton(format_date(day), callback_data=f"date_{day.strftime('%Y-%m-%d')}"))
        if len(row) == 3:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")])

    await update.message.reply_text(
        "📅 *Kun tanlang:*\n_(Yakshanba dam olish kuni)_",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return CHOOSING_DATE

async def choose_date(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel":
        await query.edit_message_text("❌ Bekor qilindi.")
        return ConversationHandler.END

    selected_date = query.data.replace("date_", "")
    context.user_data["selected_date"] = selected_date

    slots = get_time_slots()
    buttons = []
    row = []
    for slot in slots:
        taken = is_slot_taken(selected_date, slot)
        label = f"🔴 {slot}" if taken else f"✅ {slot}"
        cb = "taken" if taken else f"time_{slot}"
        row.append(InlineKeyboardButton(label, callback_data=cb))
        if len(row) == 4:
            buttons.append(row)
            row = []
    if row:
        buttons.append(row)
    buttons.append([InlineKeyboardButton("⬅️ Orqaga", callback_data="back_date")])

    dt = datetime.strptime(selected_date, "%Y-%m-%d")
    await query.edit_message_text(
        f"🕐 *{format_date(dt)} uchun vaqt tanlang:*\n\n"
        f"✅ — bo'sh  🔴 — band",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return CHOOSING_TIME

async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "taken":
        await query.answer("❌ Bu vaqt allaqachon band!", show_alert=True)
        return CHOOSING_TIME

    if query.data == "back_date":
        days = get_next_days(7)
        buttons = []
        row = []
        for day in days:
            row.append(InlineKeyboardButton(format_date(day), callback_data=f"date_{day.strftime('%Y-%m-%d')}"))
            if len(row) == 3:
                buttons.append(row)
                row = []
        if row:
            buttons.append(row)
        buttons.append([InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel")])
        await query.edit_message_text(
            "📅 *Kun tanlang:*",
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup(buttons)
        )
        return CHOOSING_DATE

    selected_time = query.data.replace("time_", "")
    context.user_data["selected_time"] = selected_time
    await query.edit_message_text(
        f"✅ *{context.user_data['selected_date']} soat {selected_time}* tanlandi.\n\n"
        f"📝 Ism va familiyangizni kiriting:"
    )
    return ENTERING_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    if len(name) < 3:
        await update.message.reply_text("⚠️ Iltimos, to'liq ism kiriting (kamida 3 harf).")
        return ENTERING_NAME

    context.user_data["name"] = name
    await update.message.reply_text(
        f"👤 *{name}*\n\n📞 Telefon raqamingizni kiriting:\n_(Masalan: +998901234567)_",
        parse_mode="Markdown"
    )
    return ENTERING_PHONE

async def enter_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    if not (phone.startswith("+") and len(phone) >= 12):
        await update.message.reply_text("⚠️ Noto'g'ri format. Masalan: +998901234567")
        return ENTERING_PHONE

    context.user_data["phone"] = phone
    date = context.user_data["selected_date"]
    time = context.user_data["selected_time"]
    name = context.user_data["name"]
    dt = datetime.strptime(date, "%Y-%m-%d")

    buttons = [
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data="confirm"),
            InlineKeyboardButton("❌ Bekor", callback_data="cancel_booking")
        ]
    ]

    await update.message.reply_text(
        f"📋 *Navbat ma'lumotlari:*\n\n"
        f"📅 Sana: *{format_date(dt)} ({date})*\n"
        f"🕐 Vaqt: *{time}*\n"
        f"👤 Ism: *{name}*\n"
        f"📞 Tel: *{phone}*\n\n"
        f"Tasdiqlaysizmi?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )
    return CONFIRMING

async def confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "cancel_booking":
        await query.edit_message_text("❌ Navbat bekor qilindi.")
        return ConversationHandler.END

    user = update.effective_user
    date = context.user_data["selected_date"]
    time = context.user_data["selected_time"]
    name = context.user_data["name"]
    phone = context.user_data["phone"]

    if is_slot_taken(date, time):
        await query.edit_message_text("⚠️ Kechirasiz, bu vaqt hozirgina band bo'ldi. Qaytadan urinib ko'ring.")
        return ConversationHandler.END

    save_appointment(date, time, user.id, name, phone, user.username)

    dt = datetime.strptime(date, "%Y-%m-%d")
    await query.edit_message_text(
        f"🎉 *Navbat muvaffaqiyatli olindi!*\n\n"
        f"📅 {format_date(dt)} ({date})\n"
        f"🕐 Soat {time}\n"
        f"👤 {name}\n"
        f"📞 {phone}\n\n"
        f"📍 Manzil: {LOCATION_ADDRESS}\n\n"
        f"_Iltimos, vaqtida keling!_ ✂️",
        parse_mode="Markdown"
    )

    # Admin ga xabar
    try:
        await context.bot.send_message(
            ADMIN_ID,
            f"🔔 *Yangi navbat!*\n\n"
            f"📅 {format_date(dt)} soat {time}\n"
            f"👤 {name}\n"
            f"📞 {phone}\n"
            f"🆔 @{user.username or user.first_name}",
            parse_mode="Markdown"
        )
    except Exception:
        pass

    return ConversationHandler.END

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Amal bekor qilindi.", reply_markup=main_menu_keyboard())
    return ConversationHandler.END

# ========================
# BO'SH VAQTLAR
# ========================

async def bosh_vaqtlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    days = get_next_days(7)
    text = "🕐 *Bo'sh vaqtlar (bugundan 7 kun):*\n\n"

    for day in days:
        date_str = day.strftime("%Y-%m-%d")
        dt_label = format_date(day)
        slots = get_time_slots()
        free_slots = [s for s in slots if not is_slot_taken(date_str, s)]

        if free_slots:
            text += f"📅 *{dt_label}* ({date_str})\n"
            text += "  " + "  ".join(free_slots[:10])
            if len(free_slots) > 10:
                text += f"\n  ...va yana {len(free_slots)-10} ta"
            text += "\n\n"
        else:
            text += f"📅 *{dt_label}* — 🔴 Barcha vaqtlar band\n\n"

    await update.message.reply_text(text, parse_mode="Markdown")

# ========================
# LOKATSIYA
# ========================

async def lokatsiya(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"📍 *Turdibek Barber manzili:*\n{LOCATION_ADDRESS}",
        parse_mode="Markdown"
    )
    await update.message.reply_location(
        latitude=LOCATION_LAT,
        longitude=LOCATION_LON
    )

# ========================
# MA'LUMOT
# ========================

async def malumot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "✂️ *Turdibek Barber*\n\n"
        "💈 Xizmatlar:\n"
        "  • Soch olish — 30.000 so'm\n"
        "  • Soqol olish — 20.000 so'm\n"
        "  • Soch + Soqol — 45.000 so'm\n"
        "  • Bolalar soch olish — 20.000 so'm\n\n"
        "⏰ Ish vaqti: Dush-Shan 09:00-19:00\n"
        "  (Yakshanba — dam olish kuni)\n\n"
        "📞 Telefon: +998 90 123 45 67\n"
        f"📍 {LOCATION_ADDRESS}",
        parse_mode="Markdown"
    )

# ========================
# NAVBATNI BEKOR QILISH (MIJOZ)
# ========================

async def bekor_qilish(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    user_appointments = [v for v in data.values() if v["user_id"] == user.id]

    if not user_appointments:
        await update.message.reply_text("📭 Sizda faol navbat mavjud emas.")
        return

    buttons = []
    for appt in sorted(user_appointments, key=lambda x: x["date"]):
        label = f"🗑 {appt['date']} {appt['time']}"
        cb = f"del_{appt['date']}_{appt['time']}"
        buttons.append([InlineKeyboardButton(label, callback_data=cb)])
    buttons.append([InlineKeyboardButton("❌ Yopish", callback_data="close")])

    await update.message.reply_text(
        "📋 *Sizning navbatlaringiz:*\nBekor qilmoqchi bo'lganingizni tanlang:",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(buttons)
    )

async def del_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    if query.data == "close":
        await query.edit_message_text("✅ Yopildi.")
        return

    if query.data.startswith("del_"):
        parts = query.data.replace("del_", "").rsplit("_", 1)
        date, time = parts[0], parts[1]
        cancel_appointment(date, time)
        await query.edit_message_text(f"✅ *{date} {time}* navbati bekor qilindi.", parse_mode="Markdown")

        try:
            await context.bot.send_message(
                ADMIN_ID,
                f"❌ *Navbat bekor qilindi!*\n📅 {date} soat {time}",
                parse_mode="Markdown"
            )
        except Exception:
            pass

# ========================
# ADMIN — MIJOZLAR RO'YXATI
# ========================

async def bugungi_mijozlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return

    today = datetime.now().strftime("%Y-%m-%d")
    data = load_data()
    today_list = sorted(
        [v for v in data.values() if v["date"] == today],
        key=lambda x: x["time"]
    )

    if not today_list:
        await update.message.reply_text(f"📭 Bugun ({today}) uchun navbat yo'q.")
        return

    text = f"📋 *Bugungi mijozlar ({today}):*\n{'─'*30}\n"
    for i, appt in enumerate(today_list, 1):
        text += (
            f"\n*{i}. {appt['time']}* — {appt['name']}\n"
            f"   📞 {appt['phone']}\n"
            f"   👤 @{appt['username']}\n"
        )
    text += f"\n{'─'*30}\n📊 Jami: {len(today_list)} ta navbat"
    await update.message.reply_text(text, parse_mode="Markdown")

async def barcha_navbatlar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("⛔ Ruxsat yo'q.")
        return

    data = load_data()
    if not data:
        await update.message.reply_text("📭 Hozircha navbat mavjud emas.")
        return

    sorted_appts = sorted(data.values(), key=lambda x: (x["date"], x["time"]))
    current_date = None
    text = "📊 *Barcha navbatlar:*\n"

    for appt in sorted_appts:
        if appt["date"] != current_date:
            current_date = appt["date"]
            dt = datetime.strptime(current_date, "%Y-%m-%d")
            text += f"\n📅 *{format_date(dt)} ({current_date}):*\n"
        text += f"  🕐 {appt['time']} — {appt['name']} | {appt['phone']}\n"

    text += f"\n📊 Jami: {len(sorted_appts)} ta navbat"
    await update.message.reply_text(text, parse_mode="Markdown")

# ========================
# ASOSIY HANDLER
# ========================

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text

    if text == "🕐 Bo'sh vaqtlar":
        await bosh_vaqtlar(update, context)
    elif text == "📍 Lokatsiya":
        await lokatsiya(update, context)
    elif text == "ℹ️ Ma'lumot":
        await malumot(update, context)
    elif text == "❌ Navbatni bekor qilish":
        await bekor_qilish(update, context)
    elif text == "📋 Bugungi mijozlar":
        await bugungi_mijozlar(update, context)
    elif text == "📊 Barcha navbatlar":
        await barcha_navbatlar(update, context)

# ========================
# BOTNI ISHGA TUSHIRISH
# ========================

def main():
    app = ApplicationBuilder().token(TOKEN).build()

    # Navbat olish conversation
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^📅 Navbat olish$"), navbat_olish_start)
        ],
        states={
            CHOOSING_DATE:  [CallbackQueryHandler(choose_date)],
            CHOOSING_TIME:  [CallbackQueryHandler(choose_time)],
            ENTERING_NAME:  [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
            ENTERING_PHONE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_phone)],
            CONFIRMING:     [CallbackQueryHandler(confirm_booking)],
        },
        fallbacks=[CommandHandler("cancel", cancel_conversation)],
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(del_callback, pattern="^(del_|close)"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    print("✂️ Turdibek_Barber boti ishga tushdi...")
    app.run_polling()

if __name__ == "__main__":
    main()
