import os, re, json, html
from pathlib import Path
from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters

# Carica variabili da .env o Railway
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
TARGET_CHAT_ID = int(os.getenv("TARGET_CHAT_ID", "0"))

# Legge lista canali da variabile CHANNELS
CHANNELS = [c.strip() for c in os.getenv("CHANNELS", "").split(",") if c.strip()]

# Legge parole chiave da variabile KEYWORDS
keywords_env = os.getenv("KEYWORDS", "")
KEYWORDS = [kw.strip() for kw in keywords_env.split(",") if kw.strip()]

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN non impostato")
if not CHANNELS:
    raise RuntimeError("Nessun canale configurato in CHANNELS")
if not KEYWORDS:
    raise RuntimeError("Variabile KEYWORDS non impostata o vuota")

# Compila il regex per le keywords
KEY_RE = re.compile("|".join([re.escape(k) for k in KEYWORDS]), re.IGNORECASE)

# File per memorizzare messaggi già visti
STATE_PATH = Path("gifts_state.json")
if STATE_PATH.exists():
    try:
        STATE = json.loads(STATE_PATH.read_text())
    except Exception:
        STATE = {"seen": []}
else:
    STATE = {"seen": []}

def save_state():
    try:
        STATE_PATH.write_text(json.dumps(STATE))
    except Exception:
        pass

def is_new_announcement(chat_id: int, message_id: int) -> bool:
    key = f"{chat_id}:{message_id}"
    if key in STATE["seen"]:
        return False
    STATE["seen"].append(key)
    if len(STATE["seen"]) > 500:
        STATE["seen"] = STATE["seen"][-500:]
    save_state()
    return True

async def start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        f"Bot attivo.\nMonitorando i canali:\n{', '.join(CHANNELS)}\n"
        f"Parole chiave: {', '.join(KEYWORDS)}"
    )
    if TARGET_CHAT_ID == 0:
        await update.message.reply_text(f"Il tuo chat ID è: {update.effective_user.id}")

async def on_channel_post(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    msg = update.channel_post
    text = msg.text or msg.caption or ""
    chat_username = f"@{msg.chat.username}" if msg.chat.username else str(msg.chat.id)

    # Verifica se il canale è nella lista
    if chat_username not in CHANNELS and str(msg.chat.id) not in CHANNELS:
        return

    # Controlla parole chiave
    if not text or not KEY_RE.search(text):
        return

    # Evita duplicati
    if not is_new_announcement(msg.chat.id, msg.message_id):
        return

    if TARGET_CHAT_ID == 0:
        return

    title = msg.chat.title or chat_username
    link = f"https://t.me/{msg.chat.username}/{msg.message_id}" if msg.chat.username else None

    parts = [f"Nuovo regalo su: {html.escape(title)}"]
    if link:
        parts.append(f"Link: {link}")
    caption = "\n".join(parts)

    if msg.photo:
        await ctx.bot.send_photo(TARGET_CHAT_ID, msg.photo[-1].file_id, caption=caption)
    elif msg.animation:
        await ctx.bot.send_animation(TARGET_CHAT_ID, msg.animation.file_id, caption=caption)
    else:
        await ctx.bot.send_message(TARGET_CHAT_ID, caption, parse_mode=ParseMode.HTML)

def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.UpdateType.CHANNEL_POST, on_channel_post))
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
