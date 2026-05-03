import os
# Telegram Bot Configuration
API_ID = int(os.getenv("api_id",0))  # Your API ID from my.telegram.org
API_HASH = os.getenv("api_hash","")  # Your API Hash from my.telegram.org
BOT_TOKEN = os.getenv("bot_token","")  # Your bot token from @BotFather

# Download Settings
MAX_FILE_SIZE = 1.9 * 1024 * 1024 * 1024  # 1.9 GB in bytes
DOWNLOAD_DIR = "downloads"
TEMP_DIR = "temp"

# Quality Options (format: resolution, max_size_mb)
QUALITY_OPTIONS = [
    ("144p", 20),
    ("240p", 30),
    ("360p", 50),
    ("480p", 100),
    ("720p", 200),
    ("1080p", 500),
    ("best", 2000),  # Best quality, up to 2GB
]
