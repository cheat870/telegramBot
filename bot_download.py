import os
import re
import telebot
from yt_dlp import YoutubeDL
from typing import Any
from dotenv import load_dotenv
from datetime import datetime
import json

load_dotenv()

API_TOKEN      = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
LOG_CHANNEL_ID = os.getenv("LOG_CHANNEL_ID", "LOG_CHANNEL_ID")
DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

COOKIES = {
    "tiktok":    "tiktok_cookies.txt",
    "facebook":  "fb_cookies.txt",
    "instagram": "ig_cookies.txt",
}

# ------------------- USERS -------------------
USERS_FILE = "users.json"
if os.path.exists(USERS_FILE):
    with open(USERS_FILE, "r") as f:
        all_users = set(json.load(f))
else:
    all_users = set()

notified_users: set[int] = set()

def save_users(users: set[int]):
    with open(USERS_FILE, "w") as f:
        json.dump(list(users), f)

# ------------------- BOT INIT -------------------
bot = telebot.TeleBot(API_TOKEN)

# ------------------- LOGGING -------------------
def get_user_profile_photo(user_id: int):
    try:
        photos = bot.get_user_profile_photos(user_id, limit=1)
        if photos.total_count > 0:
            return photos.photos[0][0].file_id
    except Exception as e:
        print(f"[PHOTO ERROR] {e}")
    return None

def log_user_join(user):
    now      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = f"@{user.username}" if user.username else "គ្មាន username"
    lang     = user.language_code.upper() if user.language_code else "?"
    full_name = user.first_name + (f" {user.last_name}" if user.last_name else "")
    caption = (
        f"👤 *New User*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"📛 Name: {full_name}\n"
        f"🔖 Username: {username}\n"
        f"🆔 User ID: `{user.id}`\n"
        f"🌐 Language: {lang}\n"
        f"🕐 Time: {now}\n"
        f"━━━━━━━━━━━━━━━━"
    )
    try:
        photo_file_id = get_user_profile_photo(user.id)
        if photo_file_id:
            bot.send_photo(LOG_CHANNEL_ID, photo_file_id, caption=caption, parse_mode="Markdown")
        else:
            bot.send_message(LOG_CHANNEL_ID, f"🖼️ _(No profile photo)_\n\n{caption}", parse_mode="Markdown")
    except Exception as e:
        print(f"[JOIN LOG ERROR] {e}")
        print("[LOG HINT] Bot must be admin in channel")

def log_download(user, url: str, status: str, platform: str = "?", size_mb: float = 0.0):
    now      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = f"@{user.username}" if user.username else "គ្មាន username"
    emoji    = "✅" if status == "success" else "❌"
    log_msg = (
        f"{emoji} *Download Log*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 User: {user.first_name} ({username})\n"
        f"🆔 Chat ID: `{user.id}`\n"
        f"🌐 Platform: {platform.upper()}\n"
        f"🔗 URL: {url}\n"
        f"📦 Size: {size_mb:.2f} MB\n"
        f"📊 Status: {status}\n"
        f"🕐 Time: {now}\n"
        f"━━━━━━━━━━━━━━━━"
    )
    try:
        bot.send_message(LOG_CHANNEL_ID, log_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"[LOG ERROR] {e}")

# ------------------- PLATFORM DETECTION -------------------
def detect_platform(url: str) -> str:
    patterns = {
        "youtube":     r"(youtube\.com|youtu\.be)",
        "tiktok":      r"(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)",
        "facebook":    r"(facebook\.com|fb\.watch|fb\.com)",
        "instagram":   r"(instagram\.com)",
        "twitter":     r"(twitter\.com|x\.com|t\.co)",
        "reddit":      r"(reddit\.com|redd\.it)",
        "vimeo":       r"(vimeo\.com)",
        "dailymotion": r"(dailymotion\.com|dai\.ly)",
        "twitch":      r"(twitch\.tv|clips\.twitch\.tv)",
        "pinterest":   r"(pinterest\.com|pin\.it)",
        "threads":     r"(threads\.net)",
        "bilibili":    r"(bilibili\.com|b23\.tv)",
        "streamable":  r"(streamable\.com)",
        "rumble":      r"(rumble\.com)",
        "odysee":      r"(odysee\.com)",
        "soundcloud":  r"(soundcloud\.com)",
    }
    for platform, pattern in patterns.items():
        if re.search(pattern, url, re.IGNORECASE):
            return platform
    return "generic"

# ------------------- YT-DLP -------------------
def build_ydl_opts(url: str, output_template: str, mobile_ua: bool = False) -> dict[str, Any]:
    platform = detect_platform(url)
    desktop_ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36")
    mobile_user_agent = ("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1")
    ua = mobile_user_agent if mobile_ua else desktop_ua
    opts: dict[str, Any] = {
        "outtmpl":             output_template,
        "merge_output_format": "mp4",
        "noplaylist":          True,
        "retries":             10,
        "fragment_retries":    10,
        "geo_bypass":          True,
        "socket_timeout":      30,
        "http_headers": {
            "User-Agent":      ua,
            "Accept-Language": "en-US,en;q=0.9",
            "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        },
        "postprocessors": [{
            "key":            "FFmpegVideoConvertor",
            "preferedformat": "mp4",
        }],
        "postprocessor_args": [
            "-movflags", "faststart",
            "-c:v", "copy",
            "-c:a", "aac",
            "-strict", "experimental",
        ],
    }
    if platform == "youtube":
        opts["format"] = "bestvideo[height<=720][ext=mp4]+bestaudio[ext=m4a]/best[height<=720]/best"
    elif platform == "tiktok":
        opts["format"] = "best"
        opts["http_headers"]["Referer"] = "https://www.tiktok.com/"
        if os.path.exists(COOKIES["tiktok"]):
            opts["cookiefile"] = COOKIES["tiktok"]
    elif platform == "facebook":
        opts["format"] = "best[ext=mp4]/best"
        opts["http_headers"]["Referer"] = "https://www.facebook.com/"
        if os.path.exists(COOKIES["facebook"]):
            opts["cookiefile"] = COOKIES["facebook"]
    elif platform == "instagram":
        opts["format"] = "best[ext=mp4]/best"
        opts["http_headers"]["Referer"] = "https://www.instagram.com/"
        if os.path.exists(COOKIES["instagram"]):
            opts["cookiefile"] = COOKIES["instagram"]
    else:
        opts["format"] = "best[height<=720]/best"
    return opts

def resolve_file_path(ydl: YoutubeDL, info_dict: dict) -> str | None:
    path = ydl.prepare_filename(info_dict)
    if os.path.exists(path):
        return path
    mp4 = os.path.splitext(path)[0] + ".mp4"
    if os.path.exists(mp4):
        return mp4
    return None

def attempt_download(url: str, output_template: str) -> tuple[str | None, str | None]:
    last_error = "Unknown error"
    for mobile_ua in [False, True]:
        try:
            opts = build_ydl_opts(url, output_template, mobile_ua=mobile_ua)
            with YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
                info = ydl.extract_info(url, download=True)
                path = resolve_file_path(ydl, info)
                if path:
                    return path, None
        except Exception as e:
            last_error = str(e)
    return None, last_error

# ------------------- FRIENDLY ERROR -------------------
def friendly_error(err: str, platform: str) -> str:
    e = err.lower()
    if "unsupported url" in e:
        return "❌ Platform នេះ​មិន​ Support ទេ។"
    return f"❌ Error: {err[:200]}"

# ------------------- BOT HANDLERS -------------------
@bot.message_handler(commands=["start"])
def start_handler(message):
    user = message.from_user
    if user.id not in notified_users:
        notified_users.add(user.id)
        log_user_join(user)
    if user.id not in all_users:
        all_users.add(user.id)
        save_users(all_users)

    welcome_text = (
        "👋 *សួស្ដី!* ផ្ញើ link វីដេអូ ខ្ញុំ​នឹង Download ជូន!\n\n"
        "✅ *Platforms ដែល Support:*\n• YouTube • TikTok • Facebook\n• Instagram • Twitter/X • Reddit\n• Vimeo • Dailymotion • Twitch\n• Bilibili • Streamable • Rumble\n• Pinterest • Threads • និងច្រើន​ទៀត!\n\n📽️ Format: MP4  |  Max: 50 MB"
    )
    image_path = "start_image.jpg"
    try:
        with open(image_path, "rb") as photo:
            bot.send_photo(message.chat.id, photo, caption=welcome_text, parse_mode="Markdown")
    except FileNotFoundError:
        bot.send_message(message.chat.id, welcome_text, parse_mode="Markdown")

@bot.message_handler(func=lambda message: True)
def download_video(message):
    url = message.text.strip()
    user = message.from_user
    platform = detect_platform(url)

    if not url.startswith("http"):
        bot.reply_to(message, "⚠️ សូម​ផ្ញើ URL ត្រឹម​ត្រូវ (ចាប់ផ្ដើម​ដោយ http/https)")
        return

    msg = bot.send_message(message.chat.id, f"⏳ កំពុង​ដំណើរការ... [{platform.upper()}]")
    output_template = f"{DOWNLOAD_FOLDER}/%(title).80s.%(ext)s"
    file_path, err = attempt_download(url, output_template)

    if file_path is None:
        reply = friendly_error(err or "Unknown error", platform)
        bot.edit_message_text(reply, message.chat.id, msg.message_id, parse_mode="Markdown")
        log_download(user, url, f"error: {err}", platform, 0.0)
        return

    file_size = os.path.getsize(file_path)
    size_mb = file_size / (1024*1024)

    if file_size > 50*1024*1024:
        bot.edit_message_text(f"❌ វីដេអូ​ធំ​ពេក ({size_mb:.1f} MB)\nTelegram ទទួល​បាន​តែ 50 MB ប៉ុណ្ណោះ។", message.chat.id, msg.message_id)
        log_download(user, url, f"too large ({size_mb:.1f}MB)", platform, size_mb)
        os.remove(file_path)
        return

    bot.edit_message_text("📤 កំពុង Upload...", message.chat.id, msg.message_id)
    try:
        with open(file_path, "rb") as video:
            bot.send_video(message.chat.id, video, timeout=120, supports_streaming=True, caption=f"✅ {size_mb:.1f} MB | {platform.upper()} | MP4")
        bot.edit_message_text("✅ រួច​រាល់!", message.chat.id, msg.message_id)
        log_download(user, url, "success", platform, size_mb)
    except Exception as upload_err:
        bot.edit_message_text(f"❌ Upload បរាជ័យ: {str(upload_err)[:150]}", message.chat.id, msg.message_id)
        log_download(user, url, f"upload error: {str(upload_err)[:80]}", platform, size_mb)

    if file_path and os.path.exists(file_path):
        os.remove(file_path)

print("Bot is running...")
bot.infinity_polling()