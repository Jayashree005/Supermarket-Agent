"""
Global Configuration & Settings for Indian Supermarket Ops Agent
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Base paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "output"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Load environment variables
load_dotenv(BASE_DIR / ".env")

# API Keys & Credentials
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")

# LLM Model Configuration (gemini-3.6-flash offers high RPM free-tier quota & fast function calling)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")

# Database Path
DB_PATH = DATA_DIR / "kirana_store.db"

# Store Defaults (can be customized via persistent preferences)
DEFAULT_SHOP_NAME = "ABC Super Market"
DEFAULT_SHOP_ADDRESS = "ABC Super Market, Coimbatore, Tamil Nadu"
DEFAULT_SHOP_GSTIN = "XXX"
DEFAULT_STATE = "Tamil Nadu"
DEFAULT_STATE_CODE = "33"
DEFAULT_CURRENCY = "₹"
