import os

OLLAMA_MODEL = "llama3"
OLLAMA_VISION_MODEL = "llava"
# Portable tool locations (D:). Set FFMPEG_LOCATION / TESSERACT_CMD env vars to override.
FFMPEG_LOCATION = os.environ.get("FFMPEG_LOCATION") or (
    r"D:\tools\ffmpeg\bin" if os.path.isdir(r"D:\tools\ffmpeg\bin") else "")
TESSERACT_CMD = os.environ.get("TESSERACT_CMD") or (
    r"D:\tools\tesseract\tesseract.exe" if os.path.exists(r"D:\tools\tesseract\tesseract.exe")
    else (r"C:\Program Files\Tesseract-OCR\tesseract.exe"
          if os.path.exists(r"C:\Program Files\Tesseract-OCR\tesseract.exe") else "tesseract"))
YT_DLP_PATH = os.environ.get("YT_DLP_PATH") or (
    r"D:\python_3.12\Scripts\yt-dlp.exe" if os.path.exists(r"D:\python_3.12\Scripts\yt-dlp.exe") else "yt-dlp")
WAKE_WORD_THRESHOLD = 0.5
USE_SPEECH_FILTER = True
WHATSAPP_SESSION_PATH = "./whatsapp_session"
GMAIL_CREDENTIALS_PATH = "./credentials.json"
YT_MUSIC_QUALITY = "bestaudio"
ALLOWED_ROOTS = ["D:/projects", "C:/Users/Samarth"]
WINDOWS_USER = "Samarth"
BLACKLISTED_PATHS = ["/etc", "/System", "C:/Windows"]
MAX_READ_CHARS = 50000
REQUIRE_CONFIRM_ON_DELETE = True
REQUIRE_CONFIRM_ON_WRITE = True
CHROMA_DB_PATH = "./friday_memory"
MAX_MEMORY_RESULTS = 5
WEATHER_CITY = "Bengaluru"
USER_NAME = "Boss"
