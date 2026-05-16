import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Anomali eşikleri
Z_SCORE_THRESHOLD = float(os.getenv("Z_SCORE_THRESHOLD", "2.5"))
DAILY_RETURN_THRESHOLD = float(os.getenv("DAILY_RETURN_THRESHOLD", "5.0"))
MARKET_CAP_CHANGE_THRESHOLD = float(os.getenv("MARKET_CAP_CHANGE_THRESHOLD", "10.0"))

# Zamanlama
FETCH_TIME = os.getenv("FETCH_TIME", "10:30")

# Fon türü
FUND_TYPE = os.getenv("FUND_TYPE", "YAT")

# Veritabanı
DB_PATH = os.path.join(os.path.dirname(__file__), "data", "tefas.db")
