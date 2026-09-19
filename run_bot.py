"""
Entry point to launch the Indian Supermarket Ops Telegram Bot.
Usage: python run_bot.py
"""
import sys
import os

# Ensure UTF-8 output on Windows
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from config.settings import TELEGRAM_BOT_TOKEN
from bot.telegram_bot import create_telegram_app

def main():
    if not TELEGRAM_BOT_TOKEN or TELEGRAM_BOT_TOKEN.startswith("your_"):
        print("=" * 70)
        print("⚠️  TELEGRAM_BOT_TOKEN is not set in .env or environment!")
        print("To run the live Telegram bot:")
        print("1. Talk to @BotFather on Telegram to obtain a bot token.")
        print("2. Add TELEGRAM_BOT_TOKEN=<your_token> in .env file.")
        print("3. Re-run: python run_bot.py")
        print("\n💡 NOTE: You can run the full interactive terminal right now using:")
        print("   python run_cli.py")
        print("   or run the automated evaluation suite:")
        print("   python test_scenarios.py")
        print("=" * 70)
        sys.exit(1)

    print("=" * 70)
    print("🚀 Starting Indian Supermarket Ops Telegram Bot...")
    print("Bot is polling Telegram updates. Press Ctrl+C to stop.")
    print("=" * 70)
    app = create_telegram_app()
    app.run_polling()

if __name__ == "__main__":
    main()
