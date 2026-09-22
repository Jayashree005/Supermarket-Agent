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

import html
import re
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
from config.seed_data import seed_database, reset_database
from core.agent_loop import KiranaOpsAgent

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger("KiranaTelegramBot")

# Initialize agent singleton
agent = KiranaOpsAgent()

def markdown_to_telegram_html(text: str) -> str:
    """Converts LLM markdown formatting into safe, valid Telegram HTML."""
    if not text:
        return ""

    # Protect code blocks
    code_blocks = []
    def save_cb(m):
        code_blocks.append(m.group(1))
        return f"___CODE_BLOCK_{len(code_blocks)-1}___"
    text = re.sub(r"```(.*?)```", save_cb, text, flags=re.DOTALL)

    # Protect inline code
    inline_codes = []
    def save_ic(m):
        inline_codes.append(m.group(1))
        return f"___INLINE_CODE_{len(inline_codes)-1}___"
    text = re.sub(r"`([^`\n]+)`", save_ic, text)

    # HTML-escape raw text
    text = html.escape(text)

    # Convert bold **text** to <b>text</b>
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text, flags=re.DOTALL)

    # Convert italic *text* (excluding bullet star lists)
    text = re.sub(r"(?<![\w\*])\*([^\*\n]+?)\*(?![\w\*])", r"<i>\1</i>", text)

    # Restore inline code safely
    for i, code in enumerate(inline_codes):
        text = text.replace(f"___INLINE_CODE_{i}___", f"<code>{html.escape(code)}</code>")

    # Restore code blocks safely
    for i, cb in enumerate(code_blocks):
        text = text.replace(f"___CODE_BLOCK_{i}___", f"<pre>{html.escape(cb.strip())}</pre>")

    return text

async def send_formatted_reply(message, text: str):
    """Sends a reply with Telegram HTML formatting, falling back to plain text if needed."""
    html_text = markdown_to_telegram_html(text)
    try:
        await message.reply_text(html_text, parse_mode="HTML")
    except Exception as e:
        logger.warning(f"HTML parse failed ({e}), falling back to plain text.")
        await message.reply_text(text)

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Greets the store owner and outlines capabilities."""
    welcome_text = (
        "🏪 <b>Welcome to your Supermarket Ops Agent!</b>\n\n"
        "Run your entire shop in plain shopkeeper language:\n\n"
        "📦 <b>Inventory:</b>\n"
        "• <i>'50 packets of Maggi came in, cost ₹12, MRP ₹14'</i>\n"
        "• <i>'how much sugar is left?'</i>\n"
        "• <i>'what's running out?'</i>\n\n"
        "🧾 <b>Billing & POS:</b>\n"
        "• <i>'make a bill: 2kg sugar, 1 Aashirvaad atta 5kg, 4 Maggi, 1 Amul butter, UPI'</i>\n"
        "• <i>'drop the butter, make it 6 Maggi'</i>\n"
        "• <i>'finalize the bill'</i>\n\n"
        "💳 <b>Khata (Credit Ledger):</b>\n"
        "• <i>'put ₹500 on Ramesh's credit'</i>\n"
        "• <i>'what is Ramesh's balance?'</i>\n"
        "• <i>'Ramesh paid ₹300'</i>\n\n"
        "📊 <b>Close & Documents:</b>\n"
        "• <i>'today's sales?' / 'close the day'</i>\n"
        "• <i>'send me that bill as a PDF'</i>\n"
        "• <i>'make this week's sales analysis deck'</i>\n\n"
        "⚙️ <b>Preferences:</b>\n"
        "• <i>'always assume UPI unless I say cash'</i>\n"
        "• <i>'default atta = Aashirvaad 5kg'</i>\n\n"
        "Use <code>/new</code> anytime to start a fresh transaction (store memory persists).\n"
        "Use <code>/reset_db</code> to restore initial stock levels and catalog."
    )
    await update.message.reply_text(welcome_text, parse_mode="HTML")

async def new_chat_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Resets active draft and conversation context; durable preferences remain."""
    chat_id = str(update.effective_chat.id)
    msg = agent.reset_chat(chat_id)
    await update.message.reply_text(f"🔄 {msg}")

async def reset_store_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Wipes transactions and restores original stock and Khata balances."""
    chat_id = str(update.effective_chat.id)
    reset_database()
    agent.reset_chat(chat_id)
    await update.message.reply_text("🔄 Store inventory, stock quantities, and Khata balances have been reset to pristine initial state!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Displays command cheatsheet."""
    help_text = (
        "📖 <b>Shopkeeper Quick Guide:</b>\n\n"
        "• <b>Receive Stock:</b> <code>50 packets of Maggi came in, cost ₹12, MRP ₹14</code>\n"
        "• <b>Add Item:</b> <code>new item: Amul Butter 100g, GST 12%, MRP ₹62, cost ₹50</code>\n"
        "• <b>Cut Bill:</b> <code>make a bill: 2kg sugar, 4 Maggi, UPI</code>\n"
        "• <b>Edit Bill:</b> <code>drop the sugar, make it 6 Maggi</code>\n"
        "• <b>Stock Query:</b> <code>how much sugar is left?</code>\n"
        "• <b>Khata:</b> <code>put ₹500 on Ramesh's credit</code> | <code>Ramesh paid ₹300</code>\n"
        "• <b>Daily Close:</b> <code>today's sales?</code>\n"
        "• <b>PDF Invoice:</b> <code>send me that bill as a PDF</code>\n"
        "• <b>Analysis Deck:</b> <code>make this week's sales analysis deck</code>\n"
        "• <b>Reset Chat:</b> <code>/new</code>\n"
        "• <b>Reset Store/Stock:</b> <code>/reset_db</code>"
    )
    await update.message.reply_text(help_text, parse_mode="HTML")

async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Processes shopkeeper natural language input and delivers answers + artifacts."""
    if not update.message or not update.message.text:
        return

    chat_id = str(update.effective_chat.id)
    user_text = update.message.text.strip()

    # Send typing action indicator
    await context.bot.send_chat_action(chat_id=update.effective_chat.id, action="typing")

    turn = agent.process_message(chat_id, user_text)

    # Reply with agent's text response using HTML formatting
    await send_formatted_reply(update.message, turn.text)

    # Deliver any generated document artifacts directly
    for artifact_path in turn.artifacts:
        if os.path.exists(artifact_path):
            file_name = os.path.basename(artifact_path)
            caption = f"📄 {file_name}"
            if file_name.endswith(".pdf"):
                caption = "🧾 <b>GST Tax Invoice</b>"
            elif file_name.endswith(".pptx"):
                caption = "📊 <b>Store Operations Analysis Deck</b>"

            with open(artifact_path, "rb") as doc_file:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=doc_file,
                    filename=file_name,
                    caption=caption,
                    parse_mode="HTML"
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
    app.add_handler(CommandHandler("reset_db", reset_store_command))
    app.add_handler(CommandHandler("reset_store", reset_store_command))
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
