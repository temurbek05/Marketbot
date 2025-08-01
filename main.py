from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, KeyboardButton, ReplyKeyboardMarkup, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
import os, json, uuid, openpyxl
from openpyxl import Workbook

BOT_TOKEN = "7427242655:AAEib0vXUVsczfZ5Mlc8MOm9SOstG7Cm0W4"
ADMIN_ID = 793339530  # O'zingizning Telegram ID'ingiz bilan almashtiring

BOOKS_FILE = "books.json"
KITOB_MEDIA = "kitoblar"
CHEK_MEDIA = "cheklar"
EXCEL_FILE = "orders.xlsx"

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

def save_order_to_excel(full_name, phone, book_title, qty, location_link):
    if not os.path.exists(EXCEL_FILE):
        wb = Workbook()
        ws = wb.active
        ws.append(["Ism Familiya", "Telefon", "Kitob", "Soni", "Lokatsiya"])
    else:
        wb = openpyxl.load_workbook(EXCEL_FILE)
        ws = wb.active

    ws.append([full_name, phone, book_title, qty, location_link])
    wb.save(EXCEL_FILE)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = ReplyKeyboardMarkup([[KeyboardButton("\ud83d\udcda Kitoblar ro'yxati")]], resize_keyboard=True)
    await update.message.reply_text(
        "\ud83d\udcda Ushbu bot Gulruh Markayeva tomonidan yozilgan \u201cFEVRAL\u201d kitobi sotuviga mo\u2018ljallangan.\n\n"
        "\ud83d\udc69\u200d\ud83d\udcbc Muallif: Gulruh Markayeva\n\n"
        "\ud83d\udccc Telegram kanal: https://t.me/gulruh_markayeva\n\n"
        "\ud83d\udcb0 Kitob narxi: har bir kitob tavsifida ko\u2018rsatilgan.\n\n"
        "\ud83d\udcde Admin: +998 90 123 45 67",
        reply_markup=keyboard
    )

async def show_books(update: Update, context: ContextTypes.DEFAULT_TYPE):
    books = load_books()
    if not books:
        await update.message.reply_text("\ud83d\udcbc Kitoblar hozircha mavjud emas.")
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
            caption=f"\ud83d\udcd6 {book['title']}\n\ud83d\udcac {book['description']}\n\ud83d\udcb0 {book['price']} so'm\n\ud83d\udcb3 {book['card']}\n\ud83d\udce6 Qolgan: {book['count']} dona",
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

    await query.message.reply_text("\ud83d\udcb3 Iltimos, to\u2018lov cheki rasmni yuboring. Faqat bitta rasm yuboring!")

async def photo_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id
    if update.message.media_group_id:
        await update.message.reply_text("\u274c Faqat bitta rasm yuboring!")
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

        await update.message.reply_text("\u2705 Kitob qo\u2018shildi!")
        del admin_add_state[user_id]
        return

    if not context.user_data.get("selected_book") or not user_photo_state.get(user_id, False):
        await update.message.reply_text("\u2757 Avval kitob va miqdorni tanlang.")
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
        text=f"\ud83e\uddbe Buyurtma keldi: /confirm_{user_id} yoki /reject_{user_id}"
    )
    await context.bot.send_photo(chat_id=ADMIN_ID, photo=open(filepath, "rb"))
    await update.message.reply_text("\u2705 Chek yuborildi! Endi admin tasdiqlashini kuting.")

async def addbook_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("\u274c Sizda bu huquq yo\u2018q.")
        return
    admin_add_state[update.effective_user.id] = {"step": "waiting_title"}
    await update.message.reply_text("\ud83d\udcd6 Yangi kitob nomini kiriting:")

async def admin_text_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in admin_add_state:
        return

    step = admin_add_state[user_id]["step"]
    text = update.message.text.strip()

    if step == "waiting_title":
        admin_add_state[user_id]["title"] = text
        admin_add_state[user_id]["step"] = "waiting_description"
        await update.message.reply_text("\ud83d\udcdd Tavsifini yozing:")
    elif step == "waiting_description":
        admin_add_state[user_id]["description"] = text
        admin_add_state[user_id]["step"] = "waiting_price"
        await update.message.reply_text("\ud83d\udcb0 Narxini kiriting:")
    elif step == "waiting_price":
        admin_add_state[user_id]["price"] = text
        admin_add_state[user_id]["step"] = "waiting_card"
        await update.message.reply_text("\ud83d\udcb3 Karta raqamini kiriting:")
    elif step == "waiting_card":
        admin_add_state[user_id]["card"] = text
        admin_add_state[user_id]["step"] = "waiting_count"
        await update.message.reply_text("\ud83d\udce6 Nechta mavjud? (raqamda yozing)")
    elif step == "waiting_count":
        if not text.isdigit():
            await update.message.reply_text("\u2757 Iltimos, raqam kiriting.")
            return
        admin_add_state[user_id]["count"] = text
        admin_add_state[user_id]["step"] = "waiting_photo"
        await update.message.reply_text("\ud83d\udcf8 Endi kitob rasmni yuboring (jpg/png).")

async def confirm_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(update.message.text.split("_")[1])
        order = pending_orders.get(user_id)
        if not order:
            await update.message.reply_text("\u2757 Buyurtma topilmadi.")
            return

        new_count = update_book_count(order["book_id"], order["qty"])
        button = KeyboardButton("\ud83d\udcf1 Telefon raqamni ulashish", request_contact=True)
        markup = ReplyKeyboardMarkup([[button]], resize_keyboard=True, one_time_keyboard=True)

        user_order_info[user_id] = {
            "book_id": order["book_id"],
            "qty": order["qty"],
            "has_contact": False
        }

        await context.bot.send_message(
            user_id,
            f"\u2705 To\u2018lov tasdiqlandi.\n\ud83d\udce6 Qolgan: {new_count} dona\n\ud83d\udcde Telefon raqamingizni yuboring:",
            reply_markup=markup
        )
    except:
        await update.message.reply_text("\u274c Format: /confirm_<user_id>")

async def reject_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return
    try:
        user_id = int(update.message.text.split("_")[1])
        await context.bot.send_message(user_id, "\u274c Kechirasiz, to\u2018lov rad etildi.")
    except:
        await update.message.reply_text("\u274c Format: /reject_<user_id>")

async def contact_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    contact = update.message.contact
    user_id = update.message.from_user.id

    if user_id not in user_order_info:
        await update.message.reply_text("\u2757 Avval to\u2018lov qilishingiz kerak.")
        return

    context.user_data["full_name"] = f"{contact.first_name} {contact.last_name or ''}"
    context.user_data["phone"] = contact.phone_number
    user_order_info[user_id]["has_contact"] = True

    await update.message.reply_text("\ud83d\udccd Iltimos, manzilingizni (live location) yuboring.")

async def location_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    if user_id not in user_order_info or not user_order_info[user_id].get("has_contact", False):
        await update.message.reply_text("\u2757 Avval telefon raqamingizni yuboring.")
        return

    location = update.message.location
    info = user_order_info[user_id]
    books = load_books()
    book = next((b for b in books if b["id"] == info.get("book_id")), None)

    location_link = f"https://maps.google.com/?q={location.latitude},{location.longitude}"
    save_order_to_excel(
        full_name=context.user_data.get("full_name", "Noma'lum"),
        phone=context.user_data.get("phone", "Noma'lum"),
        book_title=book['title'] if book else "Noma'lum",
        qty=info.get("qty", 1),
        location_link=location_link
    )

    await context.bot.send_message(
        chat_id=ADMIN_ID,
        text=f"\ud83d\udce6 Buyurtmachi:\n"
             f"\ud83d\udc64 {context.user_data.get('full_name', 'Noma\'lum')}\n"
             f"\ud83d\udcde {context.user_data.get('phone', 'Noma\'lum')}\n"
             f"\ud83d\udcd6 {book['title'] if book else 'Noma\'lum'} ({info.get('qty', 1)} dona)\n"
             f"\ud83d\udccd {location_link}"
    )
    await update.message.reply_text("\u2705 Buyurtma yakunlandi!")

    del user_order_info[user_id]

async def get_orders_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        return

    if not os.path.exists(EXCEL_FILE):
        await update.message.reply_text("\ud83d\udcbc Hozircha hech qanday buyurtma mavjud emas.")
        return

    await update.message.reply_document(document=InputFile(EXCEL_FILE), filename="buyurtmalar.xlsx")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("addbook", addbook_handler))
    app.add_handler(CommandHandler("getorders", get_orders_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("Kitoblar"), show_books))
    app.add_handler(CallbackQueryHandler(handle_qty_selection, pattern="^qty_"))
    app.add_handler(MessageHandler(filters.PHOTO, photo_handler))
    app.add_handler(MessageHandler(filters.CONTACT, contact_handler))
    app.add_handler(MessageHandler(filters.LOCATION, location_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^/confirm_"), confirm_handler))
    app.add_handler(MessageHandler(filters.TEXT & filters.Regex("^/reject_"), reject_handler))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, admin_text_handler))

    print("\u2705 Bot ishga tushdi.")
    app.run_polling()

if __name__ == "__main__":
    main()
