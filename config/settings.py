import os
from pathlib import Path
from dotenv import load_dotenv

# Base Paths
RECIPIENT_EMAIL = "itsrishisaiteja@gmail.com"
BASE_DIR = Path(__file__).resolve().parent.parent
SECRETS_DIR = BASE_DIR / "secrets"

# Load .env file from secrets folder first, then fallback to root
env_path = SECRETS_DIR / ".env"
if not env_path.exists():
    env_path = BASE_DIR / ".env"
load_dotenv(dotenv_path=env_path)

# Environment Variables
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3.5-flash")
SHEET_ID = os.getenv("SHEET_ID")