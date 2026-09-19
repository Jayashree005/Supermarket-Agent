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

# LLM Model Configuration (gemini-flash-lite-latest offers high RPM free-tier quota & fast function calling)
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")

# Database Path
DB_PATH = DATA_DIR / "kirana_store.db"

# Store Defaults (can be customized via persistent preferences)
DEFAULT_SHOP_NAME = "Sri Krishna Supermarket & Kirana"
DEFAULT_SHOP_ADDRESS = "14, 100ft Road, Indiranagar, Bengaluru, Karnataka - 560038"
DEFAULT_SHOP_GSTIN = "29ABCDE1234F1Z5"
DEFAULT_STATE = "Karnataka"
DEFAULT_STATE_CODE = "29"
DEFAULT_CURRENCY = "₹"
