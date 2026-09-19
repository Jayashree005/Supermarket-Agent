"""
Telegram Bot Interface for Indian Kirana & Supermarket Ops Agent.
Supports plain shopkeeper language, multi-turn drafting, document delivery (PDF/PPTX),
voice notes, receipt images, and /new session resets.
"""
import os
import sys
import logging
from pathlib import Path

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters
)

from config.settings import TELEGRAM_BOT_TOKEN
from database.db import init_db
from config.seed_data import seed_database
from core.agent_loop import KiranaOpsAgent

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("KiranaTelegramBot")

# Initialize agent singleton
agent = KiranaOpsAgent()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the store owner and outlines capabilities."""
    welcome_text = (
        "🏪 **Welcome to your Kirana Supermarket Ops Agent!**\n\n"
        "Run your entire shop in plain shopkeeper language:\n\n"
        "📦 **Inventory:**\n"
        "• *'50 packets of Maggi came in, cost ₹12, MRP ₹14'*\n"
        "• *'how much sugar is left?'*\n"
        "• *'what's running out?'*\n\n"
        "🧾 **Billing & POS:**\n"
        "• *'make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI'*\n"
        "• *'drop the butter, make it 6 Maggi'*\n"
        "• *'finalize the bill'*\n\n"
        "💳 **Khata (Credit Ledger):**\n"
        "• *'put ₹500 on Ramesh\\'s credit'*\n"
        "• *'what\\'s Ramesh\\'s balance?'*\n"
        "• *'Ramesh paid ₹300'*\n\n"
        "📊 **Close & Documents:**\n"
        "• *'today\\'s sales?' / 'close the day'*\n"
        "• *'send me that bill as a PDF'*\n"
        "• *'make this week\\'s sales analysis deck'*\n\n"
        "⚙️ **Preferences:**\n"
        "• *'always assume UPI unless I say cash'*\n"
        "• *'default atta = Aashirvaad 5kg'*\n\n"
        "Use `/new` anytime to start a fresh transaction (store memory persists)."
    )
    await update.message.reply_text(welcome_text, parse_mode="Markdown")

async def new_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resets active draft and conversation context; durable preferences remain."""
    chat_id = str(update.effective_chat.id)
    msg = agent.reset_chat(chat_id)
    await update.message.reply_text(f"🔄 {msg}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays command cheatsheet."""
    help_text = (
        "📖 **Shopkeeper Quick Guide:**\n\n"
        "• **Receive Stock:** `50 packets of Maggi came in, cost ₹12, MRP ₹14`\n"
        "• **Add Item:** `new item: Amul Butter 100g, GST 12%, MRP ₹62, cost ₹50`\n"
        "• **Cut Bill:** `make a bill: 2kg sugar, 4 Maggi, UPI`\n"
        "• **Edit Bill:** `drop the sugar, make it 6 Maggi`\n"
        "• **Stock Query:** `how much sugar is left?`\n"
        "• **Khata:** `put ₹500 on Ramesh's credit` | `Ramesh paid ₹300`\n"
        "• **Daily Close:** `today's sales?`\n"
        "• **PDF Invoice:** `send me that bill as a PDF`\n"
        "• **Analysis Deck:** `make this week's sales analysis deck`\n"
        "• **Reset Chat:** `/new`"
    )
    await update.message.reply_text(help_text, parse_mode="Markdown")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes shopkeeper natural language input and delivers answers + artifacts."""
    if not update.message or not update.message.text:
        return

    chat_id = str(update.effective_chat.id)
    user_text = update.message.text.strip()

    # Send typing action indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    turn = agent.process_message(chat_id, user_text)

    # Reply with agent's text response
    await update.message.reply_text(turn.text)

    # Deliver any generated document artifacts directly
    for artifact_path in turn.artifacts:
        if os.path.exists(artifact_path):
            file_name = os.path.basename(artifact_path)
            caption = f"📄 {file_name}"
            if file_name.endswith(".pdf"):
                caption = "🧾 **GST Tax Invoice**"
            elif file_name.endswith(".pptx"):
                caption = "📊 **Store Operations Analysis Deck**"

            with open(artifact_path, "rb") as doc_file:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=doc_file,
                    filename=file_name,
                    caption=caption,
                    parse_mode="Markdown"
                )

def create_telegram_app():
    """Builds and initializes the Telegram Application instance."""
    init_db()
    seed_database()

    if not TELEGRAM_BOT_TOKEN:
        logger.warning("TELEGRAM_BOT_TOKEN is not set in environment or .env file.")

    app = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    # Command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("new", new_chat_command))
    app.add_handler(CommandHandler("reset", new_chat_command))
    app.add_handler(CommandHandler("help", help_command))

    # Message handlers
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    return app

if __name__ == "__main__":
    if not TELEGRAM_BOT_TOKEN:
        print("Error: TELEGRAM_BOT_TOKEN is not configured.")
        sys.exit(1)
    print("Starting Indian Kirana Ops Telegram Bot...")
    app = create_telegram_app()
    app.run_polling()
