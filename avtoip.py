import asyncio
import subprocess
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

TOKEN = "8744860134:AAESlXyIRF74IOy3mo60rI-1MCfdZEiNYs8"
OWNER_ID = 5724592490
INTERFACE = "enp0s6"
SUBNET = "2603:c021:5:a200"

rotation_task = None
saved_ips = []
interval_value = 20
ASKING_INTERVAL = 1

def random_ipv6():
    r = lambda: format(random.randint(0, 65535), 'x')
    return f"{SUBNET}:{r()}:{r()}:{r()}:{r()}"

def set_ipv6(ip):
    result = subprocess.run(
        f"ip -6 addr show dev {INTERFACE} | grep {SUBNET} | grep -v '63a1:cb6f:8001' | awk '{{print $2}}'",
        shell=True, capture_output=True, text=True
    )
    for addr in result.stdout.strip().split('\n'):
        if addr:
            subprocess.run(f"sudo ip -6 addr del {addr} dev {INTERFACE}", shell=True)
    subprocess.run(f"sudo ip -6 addr add {ip}/64 dev {INTERFACE}", shell=True)
    subprocess.run(f"sudo ip -6 route replace default via fe80::200:17ff:fedd:e6a4 dev {INTERFACE} src {ip}", shell=True)

def main_menu(is_running=False):
    status = "🟢 ON" if is_running else "🔴 OFF"
    keyboard = [
        [InlineKeyboardButton(f"⚡ Rotation: {status}", callback_data="toggle")],
        [InlineKeyboardButton("📺 Live", callback_data="live")],
        [InlineKeyboardButton("📋 IP lar", callback_data="ips"),
         InlineKeyboardButton("🗑 Tozala", callback_data="clear")],
    ]
    return InlineKeyboardMarkup(keyboard)

def live_menu():
    keyboard = [[InlineKeyboardButton("◀️ Orqaga", callback_data="back")]]
    return InlineKeyboardMarkup(keyboard)

async def rotate_loop(interval, chat_id, message_id, app):
    global saved_ips
    while True:
        old_ip = saved_ips[-1] if saved_ips else None
        new_ip = random_ipv6()
        set_ipv6(new_ip)
        saved_ips.append(new_ip)

        text = "📺 *Live IP o'zgarishlar:*\n\n"
        for ip in saved_ips[-10:]:
            text += f"✅ `{ip}`\n"
        text += f"\n🔄 Oxirgi: `{new_ip}`"

        try:
            await app.bot.edit_message_text(
                chat_id=chat_id,
                message_id=message_id,
                text=text,
                parse_mode="Markdown",
                reply_markup=live_menu()
            )
        except:
            pass

        await asyncio.sleep(interval)

async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("⛔ Ruxsat yo'q!")
        return
    is_running = rotation_task and not rotation_task.done()
    await update.message.reply_text(
        "🌐 *IP Rotator*\n\nBoshqaruv paneli:",
        parse_mode="Markdown",
        reply_markup=main_menu(is_running)
    )

async def button_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global rotation_task, interval_value
    query = update.callback_query
    await query.answer()

    if query.from_user.id != OWNER_ID:
        await query.answer("⛔ Ruxsat yo'q!", show_alert=True)
        return

    is_running = rotation_task and not rotation_task.done()

    if query.data == "toggle":
        if is_running:
            rotation_task.cancel()
            await query.edit_message_text(
                "🌐 *IP Rotator*\n\nBoshqaruv paneli:",
                parse_mode="Markdown",
                reply_markup=main_menu(False)
            )
        else:
            await query.edit_message_text(
                "⏱ Necha soniyada bir IP o'zgarsin? (minimum 5)\n\nRaqam yuboring:",
                parse_mode="Markdown"
            )
            ctx.user_data["waiting_interval"] = True
            ctx.user_data["menu_message_id"] = query.message.message_id

    elif query.data == "live":
        if not is_running:
            await query.answer("⚠️ Avval rotationni yoqing!", show_alert=True)
            return
        await query.edit_message_text(
            "📺 *Live IP o'zgarishlar:*\n\nKutilmoqda...",
            parse_mode="Markdown",
            reply_markup=live_menu()
        )
        ctx.user_data["live_message_id"] = query.message.message_id
        ctx.user_data["live_chat_id"] = query.message.chat_id

        if rotation_task and not rotation_task.done():
            rotation_task.cancel()

        rotation_task = asyncio.create_task(
            rotate_loop(interval_value, query.message.chat_id, query.message.message_id, ctx.application)
        )

    elif query.data == "back":
        if rotation_task and not rotation_task.done():
            rotation_task.cancel()
        is_running = False
        await query.edit_message_text(
            "🌐 *IP Rotator*\n\nBoshqaruv paneli:",
            parse_mode="Markdown",
            reply_markup=main_menu(is_running)
        )

    elif query.data == "ips":
        if not saved_ips:
            await query.answer("📭 Hali IP saqlanmagan!", show_alert=True)
            return
        text = "📋 *Saqlangan IP lar:*\n\n"
        for i, ip in enumerate(saved_ips, 1):
            text += f"`{i}. {ip}`\n"
        await query.edit_message_text(
            text,
            parse_mode="Markdown",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("◀️ Orqaga", callback_data="back")]])
        )

    elif query.data == "clear":
        saved_ips.clear()
        await query.answer("🗑 Tozalandi!", show_alert=True)

async def interval_message(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global rotation_task, interval_value
    if update.effective_user.id != OWNER_ID:
        return
    if not ctx.user_data.get("waiting_interval"):
        return

    try:
        interval = int(update.message.text)
        if interval < 5:
            await update.message.reply_text("⚠️ Minimum 5 soniya!")
            return
    except:
        await update.message.reply_text("⚠️ Faqat raqam kiriting!")
        return

    interval_value = interval
    ctx.user_data["waiting_interval"] = False

    await update.message.delete()

    msg_id = ctx.user_data.get("menu_message_id")
    rotation_task = asyncio.create_task(
        rotate_loop(interval, update.message.chat_id, msg_id, ctx.application)
    )

    await ctx.application.bot.edit_message_text(
        chat_id=update.message.chat_id,
        message_id=msg_id,
        text="🌐 *IP Rotator*\n\nBoshqaruv paneli:",
        parse_mode="Markdown",
        reply_markup=main_menu(True)
    )

app = ApplicationBuilder().token(TOKEN).build()
app.add_handler(CommandHandler("start", start_cmd))
app.add_handler(CallbackQueryHandler(button_handler))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, interval_message))

print("Bot ishga tushdi...")
app.run_polling()