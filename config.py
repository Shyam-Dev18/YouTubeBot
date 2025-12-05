import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    # Telegram API credentials
    API_ID = int(os.getenv("API_ID", 0))
    API_HASH = os.getenv("API_HASH", "")
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    
    # Video configuration
    MAX_FILE_SIZE = 850 * 1024 * 1024  # 850MB in bytes
    
    # YT-DLP formats for H.264 + AAC
    YDL_FORMATS = "bestvideo[ext=mp4][vcodec^=avc1]+bestaudio[ext=m4a]/bestvideo[ext=mp4][vcodec^=avc]+bestaudio[ext=m4a]/bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"
    
    # YT-DLP options for merging without re-encoding
    YDL_OPTS = {
        'format': YDL_FORMATS,
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'socket_timeout': 30,
        'noprogress': True,
        'merge_output_format': 'mp4',
        'postprocessor_args': {
            'ffmpeg': [
                '-c', 'copy',           # Copy without re-encoding
                '-movflags', '+faststart',
                '-max_muxing_queue_size', '9999',
            ]
        },
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
        'outtmpl': 'temp/%(id)s.%(ext)s',
        'progress_hooks': [],
    }
    
    # Bot settings
    TEMP_DIR = "temp"
    MAX_CONCURRENT_DOWNLOADS = 1
    MAX_MESSAGE_LENGTH = 4096
    
    # Health check server
    HEALTH_PORT = int(os.getenv("PORT", 8080))
    
    # Cookies for yt-dlp (REQUIRED - must be set in environment)
    #COOKIES_TXT = os.getenv("/youtubecookie.txt", "")
    COOKIES_TXT = os.getenv("YOUTUBECOOKIE_TXT", "/youtubecookie.txt")
    print("COOKIE: ", COOKIES_TXT)
    
config = Config()

