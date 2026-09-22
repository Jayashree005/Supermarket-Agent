"""
Utility script to reset the Indian Supermarket database, stock levels,
Khata accounts, and preferences back to their pristine original seed state.
Usage: python reset_db.py
"""
import sys

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

from database.db import init_db
from config.seed_data import reset_database

def main():
    print("=" * 65)
    print("🏪  Resetting Store Database & Stock Levels...")
    print("=" * 65)
    init_db()
    reset_database()
    print("✓ Successfully restored catalog, stock quantities, and Khata balances")
    print("  to pristine initial state!")
    print("=" * 65)

if __name__ == "__main__":
    main()
