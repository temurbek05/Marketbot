from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os, json, uuid

BOT_TOKEN = "7427242655:AAEib0vXUVsczfZ5Mlc8MOm9SOstG7Cm0W4"
ADMIN_ID = 793339530  # Sizning userinfobot’dan olingan ID

BOOKS_FILE = "books.json"
KITOB_MEDIA = "kitoblar"
CHEK_MEDIA = "cheklar"

os.makedirs(KITOB_MEDIA, exist_ok=True)
os.makedirs(CHEK_MEDIA, exist_ok=True)

admin_add_state = {}
pending_orders = {}
user_photo_state = {}
user_order_info = {}

def load_books():
    if os.path.exists(BOOKS_FILE):
        with open(BOOKS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_books(data):
    with open(BOOKS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def update_book_count(book_id, qty):
    books = load_books()
    for book in books:
        if book["id"] == book_id and book["count"] >= qty:
            book["count"] -= qty
            save_books(books)
            return book["count"]
    return None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup([[KeyboardButton("📚 Kitoblar ro'yxati")]], resize_keyboard=True)
    await update.message.reply_text(
        "📚 Ushbu bot Gulruh Markayeva tomonidan yozilgan kitoblar sotuviga mo‘ljallangan.\n\n"
        "👩‍💼 Muallif: Gulruh Markayeva – psixologik ruhdagi blog asoschisi, 5 yillik tajribaga ega ingliz tili o’qituvchisi va zamonaviy adabiyotga kirib kelayotgan istiqbolli muallif.\n\n"
        "📌 Telegram kanal: @yupiterlik\n\n"
        "💰 Kitob narxi: har bir kitob tavsifida ko‘rsatilgan.\n\n"
        "📞 Savollar bo‘yicha admin: @jupiter_ads",
        reply_markup=keyboard
    )

async def show_books(update: Update, context: ContextTypes.DEFAULT_TYPE):
    books = load_books()
    if not books:
        await update.message.reply_text("📭 Kitoblar hozircha mavjud emas.")
        return

    for book in books:
        if book.get("count", 0) <= 0:
            continue
        qty_buttons = [
            InlineKeyboardButton(str(i), callback_data=f"qty_{book['id']}_{i}") for i in range(1, min(6, book["count"]+1))
        ]
        keyboard = InlineKeyboardMarkup([qty_buttons])
        await update.message.reply_photo(
            photo=open(book["image_path"], "rb"),
            caption=f"📖 {book['title']}\n💬 {book['description']}\n💰 {book['price']} so'm\n💳 {book['card']}\n📦 Qolgan: {book['count']} dona",
            reply_markup=keyboard
        )

async def handle_qty_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    _, book_id, qty = query.data.split("_")
    qty = int(qty)
    context.user_data["selected_book"] = book_id
    context.user_data["selected_qty"] = qty
    user_photo_state[query.from_user.id] = True

    await query.message.reply_text("💳 Iltimos, to‘lov cheki rasmni yuboring. Faqat bitta rasm yuboring!")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.media_group_id:
        await update.message.reply_text("❌ Faqat bitta rasm yuboring!")
        return

    if user_id in admin_add_state and admin_add_state[user_id]["step"] == "waiting_photo":
        photo = update.message.photo[-1]
        file = await photo.get_file()
        image_path = os.path.join(KITOB_MEDIA, f"{uuid.uuid4()}.jpg")
        await file.download_to_drive(image_path)

        new_book = {
            "id": str(uuid.uuid4()),
            "title": admin_add_state[user_id]["title"],
            "description": admin_add_state[user_id]["description"],
            "price": admin_add_state[user_id]["price"],
            "card": admin_add_state[user_id]["card"],
            "count": int(admin_add_state[user_id]["count"]),
            "image_path": image_path
        }

        books = load_books()
        books.append(new_book)
        save_books(books)

        await update.message.reply_text("✅ Kitob qo‘shildi!")
        del admin_add_state[user_id]
        return

    if not context.user_data.get("selected_book") or not user_photo_state.get(user_id, False):
        await update.message.reply_text("❗ Avval kitob va miqdorni tanlang.")
        return

    photo = update.message.photo[-1]
    file = await photo.get_file()
    filepath = os.path.join(CHEK_MEDIA, f"{uuid.uuid4()}.jpg")
    await file.download_to_drive(filepath)

    pending_orders[user_id] = {
        "book_id": context.user_data["selected_book"],
        "qty": context.user_data["selected_qty"],
        "photo_path": filepath
    }

    user_photo_state[user_id] = False

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"🧾 Buyurtma keldi: /confirm_{user_id} yoki /reject_{user_id}"
    )
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=open(filepath, "rb"))
    await update.message.reply_text("✅ Chek yuborildi! Endi admin tasdiqlashini kuting.")

async def addbook_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    admin_add_state[update.effective_user.id] = {"step": "waiting_title"}
    await update.message.reply_text("📖 Kitob nomini kiriting:")

async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admin_add_state:
        return

    step = admin_add_state[user_id]["step"]
    text = update.message.text.strip()

    if step == "waiting_title":
        admin_add_state[user_id]["title"] = text
        admin_add_state[user_id]["step"] = "waiting_description"
        await update.message.reply_text("📝 Tavsif:")
    elif step == "waiting_description":
        admin_add_state[user_id]["description"] = text
        admin_add_state[user_id]["step"] = "waiting_price"
        await update.message.reply_text("💰 Narx:")
    elif step == "waiting_price":
        admin_add_state[user_id]["price"] = text
        admin_add_state[user_id]["step"] = "waiting_card"
        await update.message.reply_text("💳 Karta raqami:")
    elif step == "waiting_card":
        admin_add_state[user_id]["card"] = text
        admin_add_state[user_id]["step"] = "waiting_count"
        await update.message.reply_text("📦 Nechta bor? (raqam)")
    elif step == "waiting_count":
        if not text.isdigit():
            await update.message.reply_text("❗ Raqam kiriting.")
            return
        admin_add_state[user_id]["count"] = text
        admin_add_state[user_id]["step"] = "waiting_photo"
        await update.message.reply_text("🖼 Rasmni yuboring (jpg/png).")

async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(update.message.text.split("_")[1])
        order = pending_orders.get(user_id)
        if not order:
            await update.message.reply_text("❗ Buyurtma topilmadi.")
            return

        new_count = update_book_count(order["book_id"], order["qty"])
        button = KeyboardButton("📱 Telefon raqamni ulashish", request_contact=True)
        markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)

        user_order_info[user_id] = {
            "book_id": order["book_id"],
            "qty": order["qty"],
            "has_contact": False
        }

        await context.bot.send_message(
            user_id,
            f"✅ To‘lov tasdiqlandi.\n📦 Qolgan: {new_count} dona\n📲 Telefon raqamingizni yuboring:",
            reply_markup=markup
        )
    except:
        await update.message.reply_text("❌ Format: /confirm_<user_id>")

async def reject_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(update.message.text.split("_")[1])
        await context.bot.send_message(user_id, "❌ Kechirasiz, to‘lov rad etildi.")
    except:
        await update.message.reply_text("❌ Format: /reject_<user_id>")

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user_id = update.message.from_user.id

    if user_id not in user_order_info:
        await update.message.reply_text("❗ Avval to‘lov qilishingiz kerak.")
        return

    context.user_data["full_name"] = f"{contact.first_name} {contact.last_name or ''}"
    context.user_data["phone"] = contact.phone_number
    user_order_info[user_id]["has_contact"] = True

    await update.message.reply_text("📍 Iltimos, manzilingizni (live location) yuboring.")

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_order_info or not user_order_info[user_id].get("has_contact", False):
        await update.message.reply_text("❗ Avval telefon raqamingizni yuboring.")
        return

    location = update.message.location
    info = user_order_info[user_id]
    books = load_books()
    book = next((b for b in books if b["id"] == info.get("book_id")), None)

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"📦 Buyurtmachi:\n"
             f"👤 {context.user_data.get('full_name', 'Noma\'lum')}\n"
             f"📞 {context.user_data.get('phone', 'Noma\'lum')}\n"
             f"📚 {book['title'] if book else 'Noma\'lum'} ({info.get('qty', 1)} dona)\n"
             f"📍 https://maps.google.com/?q={location.latitude},{location.longitude}"
    )
    await update.message.reply_text("✅ Buyurtma yakunlandi!")

    del user_order_info[user_id]

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Kitoblar"), show_books))
    app.add_handler(CallbackQueryHandler(handle_qty_selection, pattern="^qty_"))
    app.add_handler(CommandHandler("addbook", addbook_handler))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^/confirm_"), confirm_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^/reject_"), reject_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler))

    print("✅ Bot ishga tushdi.")
    app.run_polling()

if __name__ == "__main__":
    main()
