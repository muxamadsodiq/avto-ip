import asyncio
import subprocess
import random
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes, ConversationHandler, MessageHandler, filters

TOKEN = ""
OWNER_ID = 
INTERFACE = "enp0s6"
SUBNET = "IPv6 location subnet"

rotation_task = None
saved_ips = []
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

def owner_only(func):
    async def wrapper(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        if update.effective_user.id != OWNER_ID:
            await update.message.reply_text("⛔ Ruxsat yo'q!")
            return ConversationHandler.END
        return await func(update, ctx)
    return wrapper

async def rotate_loop(interval, chat_id, app):
    global saved_ips
    while True:
        old_ip = saved_ips[-1] if saved_ips else None
        new_ip = random_ipv6()
        set_ipv6(new_ip)
        saved_ips.append(new_ip)

        if old_ip:
            msg = f"🔄 Eski IP o'chirildi: `{old_ip}`\n✅ Yangi IP: `{new_ip}`"
        else:
            msg = f"✅ Birinchi IP: `{new_ip}`"

        await app.bot.send_message(chat_id, msg, parse_mode="Markdown")
        await asyncio.sleep(interval)

@owner_only
async def start_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏱ Necha soniyada bir IP o'zgarsin? (minimum 5):")
    return ASKING_INTERVAL

async def get_interval(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != OWNER_ID:
        return ConversationHandler.END
    global rotation_task
    try:
        interval = int(update.message.text)
        if interval < 5:
            await update.message.reply_text("⚠️ Minimum 5 soniya kiriting!")
            return ASKING_INTERVAL
    except:
        await update.message.reply_text("⚠️ Faqat raqam kiriting!")
        return ASKING_INTERVAL

    if rotation_task and not rotation_task.done():
        rotation_task.cancel()

    rotation_task = asyncio.create_task(
        rotate_loop(interval, update.message.chat_id, ctx.application)
    )
    await update.message.reply_text(f"✅ Boshlandi! Har {interval} soniyada IP o'zgaradi.")
    return ConversationHandler.END

@owner_only
async def stop_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global rotation_task
    if rotation_task and not rotation_task.done():
        rotation_task.cancel()
        await update.message.reply_text("🛑 Rotation to'xtatildi!")
    else:
        await update.message.reply_text("⚠️ Rotation hozir ishlamayapti.")

@owner_only
async def ips_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    if not saved_ips:
        await update.message.reply_text("📭 Hali IP saqlanmagan.")
        return
    text = "📋 Saqlangan IP lar:\n\n"
    for i, ip in enumerate(saved_ips, 1):
        text += f"`{i}. {ip}`\n"
    await update.message.reply_text(text, parse_mode="Markdown")

@owner_only
async def status_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    running = "✅ Ishlayapti" if rotation_task and not rotation_task.done() else "🛑 To'xtatilgan"
    current = saved_ips[-1] if saved_ips else "Yo'q"
    await update.message.reply_text(
        f"📊 Status: {running}\n"
        f"🌐 Hozirgi IP: `{current}`\n"
        f"🔢 Jami o'zgarish: {len(saved_ips)} ta",
        parse_mode="Markdown"
    )

@owner_only
async def clear_cmd(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    global saved_ips
    saved_ips = []
    await update.message.reply_text("🗑 IP tarix tozalandi!")

async def cancel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Bekor qilindi.")
    return ConversationHandler.END

# App
app = ApplicationBuilder().token(TOKEN).build()

conv = ConversationHandler(
    entry_points=[CommandHandler("start", start_cmd)],
    states={ASKING_INTERVAL: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_interval)]},
    fallbacks=[CommandHandler("cancel", cancel)]
)

app.add_handler(conv)
app.add_handler(CommandHandler("stop", stop_cmd))
app.add_handler(CommandHandler("ips", ips_cmd))
app.add_handler(CommandHandler("status", status_cmd))
app.add_handler(CommandHandler("clear", clear_cmd))

print("Bot ishga tushdi...")
app.run_polling()