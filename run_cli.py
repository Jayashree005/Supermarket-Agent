"""
Interactive Shopkeeper Terminal CLI for Indian Supermarket Ops Agent.
Allows testing all agent capabilities, multi-turn drafting, Khata queries,
and artifact generation directly in the console without needing a Telegram token.
Usage: python run_cli.py
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

from database.db import init_db
from config.seed_data import seed_database
from core.agent_loop import KiranaOpsAgent

def main():
    print("=" * 75)
    print("🏪  INDIAN SUPERMARKET / KIRANA OPS AGENT - INTERACTIVE TERMINAL")
    print("=" * 75)
    print("Initializing database and catalog...")
    init_db()
    seed_database()

    agent = KiranaOpsAgent()
    session_id = "cli_shopkeeper_session"

    print("\n✓ Ready! The chat is the product. Speak in terse shopkeeper English.")
    print("Commands:")
    print("  /new        - Reset conversation context & active draft (keeps stock & preferences)")
    print("  /reset-db   - Wipe transactions & restore original stock, Khata & catalog")
    print("  /exit       - Quit interactive terminal")
    print("-" * 75)

    while True:
        try:
            user_input = input("\nShopkeeper > ").strip()
            if not user_input:
                continue

            if user_input.lower() in ["/exit", "exit", "quit"]:
                print("Exiting. Namaste!")
                break

            if user_input.lower() in ["/new", "/reset"]:
                msg = agent.reset_chat(session_id)
                print(f"\n🔄 {msg}")
                continue

            if user_input.lower() in ["/reset-db", "/reset-stock", "/reset-store"]:
                from config.seed_data import reset_database
                reset_database()
                agent.reset_chat(session_id)
                print("\n🔄 Store database reset! Stock quantities, Khata balances, and catalog restored to original state.")
                continue

            print("\nThinking and executing tools...")
            turn = agent.process_message(session_id, user_input)

            if turn.tools_executed:
                print(f"[Tools Invoked: {', '.join(turn.tools_executed)}]")

            print(f"\nAgent > {turn.text}")

            if turn.artifacts:
                for art in turn.artifacts:
                    print(f"\n[Generated Artifact]: {art}")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting. Namaste!")
            break
        except Exception as e:
            print(f"\n[Error]: {e}")

if __name__ == "__main__":
    main()
