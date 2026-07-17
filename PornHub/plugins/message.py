from datetime import datetime
from pyrogram import Client, filters
from pyrogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
)
from ..config import prefixs, sub_chat, sudoers

sudofilter = filters.user(sudoers)

button_a2 = InlineKeyboardMarkup(
    [
        [InlineKeyboardButton("🔍 Search karo", switch_inline_query_current_chat="")],
        [InlineKeyboardButton("📤 Link bhejo", switch_inline_query="")],
    ]
)


@Client.on_message(filters.command(["start", "restart"], prefixs) & filters.private)
async def intro_msg(_, update: Message):
    match = str(update.chat.id)
    with open("users.txt", "a+") as file:
        file.seek(0)
        line = file.read().splitlines()
        if match not in line:
            file.write(match + "\n")

    channel_btn = []
    if sub_chat:
        channel_btn = [[InlineKeyboardButton("• Channel •", url=f"https://t.me/{sub_chat}")]]

    button = InlineKeyboardMarkup(
        channel_btn + [[InlineKeyboardButton("Terms of use & Privacy", callback_data="terms")]]
    )

    text = (
        f"👋 Hi {update.from_user.first_name}!\n\n"
        "Is bot se kisi bhi supported website ka video download kar sakte ho.\n\n"
        "📌 <b>Kaise use karein:</b>\n"
        "• Seedha video ka link bhejo\n"
        "• Ya inline mode se search karo\n\n"
        "⚠️ Sirf adult 18+ content hai."
    )
    await update.reply_text(text, reply_markup=button)


@Client.on_callback_query(filters.regex("^terms$"))
async def terms_panel(_, q: CallbackQuery):
    await q.answer("Read the terms!")
    text = (
        "⚠️ <b>Terms of Use</b>\n\n"
        "• Yeh bot sirf 18+ users ke liye hai\n"
        "• Aap apni marzi se yeh bot use kar rahe ho\n"
        "• Bot staff aapka data safe rakhta hai\n\n"
        "👉 <b>Green button dabao agree karne ke liye</b>"
    )
    await q.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("✅ Agree & Continue", callback_data="final_page")],
                [InlineKeyboardButton("❌ Cancel", callback_data="home_intro")],
            ]
        ),
    )


@Client.on_callback_query(filters.regex("^home_intro$"))
async def home_page(_, update: CallbackQuery):
    await update.answer("Accept the policy to continue!")
    channel_btn = []
    if sub_chat:
        channel_btn = [[InlineKeyboardButton("• Channel •", url=f"https://t.me/{sub_chat}")]]
    button = InlineKeyboardMarkup(
        channel_btn + [[InlineKeyboardButton("Terms of use & Privacy", callback_data="terms")]]
    )
    text = (
        f"👋 Hi {update.from_user.first_name}!\n\n"
        "Is bot se kisi bhi supported website ka video download kar sakte ho.\n\n"
        "📌 <b>Kaise use karein:</b>\n"
        "• Seedha video ka link bhejo\n"
        "• Ya inline mode se search karo"
    )
    await update.edit_message_text(text, reply_markup=button)


@Client.on_callback_query(filters.regex("^final_page$"))
async def greets(_, q: CallbackQuery):
    await q.answer("Thanks for agreeing!")
    await q.edit_message_text(
        f"✅ Hi {q.from_user.first_name}!\n\nAb link bhejo aur bot download karega!",
        reply_markup=button_a2,
    )


@Client.on_message(filters.command("stats", prefixs) & sudofilter)
async def bot_statistic(c: Client, u: Message):
    try:
        users = open("users.txt").readlines()
        total = len(users)
        await c.send_document(u.chat.id, "users.txt", caption=f"Total users: {total}")
    except FileNotFoundError:
        await u.reply_text("Abhi koi user nahi hai.")


@Client.on_message(filters.command(["gcast", "broadcast"], prefixs) & sudofilter)
async def broadcast(_, update: Message):
    if not update.reply_to_message:
        await update.reply_text("Kisi message ko reply karo broadcast ke liye!")
        return
    if update.reply_to_message.text:
        await update.reply_text("✅ Broadcast shuru ho gaya!")
        query = open("users.txt").readlines()
        for row in query:
            try:
                await update.reply_to_message.copy(row.strip())
            except Exception:
                pass
    else:
        await update.reply_text("Sirf text messages broadcast ho sakte hain!")


@Client.on_message(filters.command("help", prefixs))
async def command_list(_, update: Message):
    text_1 = (
        "🛠 <b>Commands:</b>\n"
        "» /start - Bot shuru karo\n"
        "» /help  - Yeh message\n"
        "» /ping  - Bot ki speed check karo\n\n"
        "📌 <b>Download karna:</b>\n"
        "Koi bhi video link bhejo, bot download kar dega!"
    )
    text_2 = text_1 + (
        "\n\n👑 <b>Admin Commands:</b>\n"
        "» /stats - Users dekho\n"
        "» /gcast - Broadcast karo"
    )
    if update.from_user.id in sudoers:
        await update.reply_text(text_2)
    else:
        await update.reply_text(text_1)


@Client.on_message(filters.command("ping", prefixs))
async def ping(c: Client, u: Message):
    first = datetime.now()
    sent = await u.reply_text("<b>Checking...</b>")
    second = datetime.now()
    await sent.edit_text(
        f"🏓 <b>PONG!</b>\n⚡ <code>{(second - first).microseconds / 1000}</code> ms"
    )
