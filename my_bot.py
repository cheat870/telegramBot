import os
import sys
import re
import json
import uuid
import subprocess
import telebot
import requests
import imageio_ffmpeg
from yt_dlp import YoutubeDL
from typing import Any
from dotenv import load_dotenv
from datetime import datetime

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

ENV_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
load_dotenv(dotenv_path=ENV_PATH)

API_TOKEN       = os.getenv("BOT_TOKEN") or os.getenv("\ufeffBOT_TOKEN")
LOG_CHANNEL_ID  = os.getenv("LOG_CHANNEL_ID") or os.getenv("\ufeffLOG_CHANNEL_ID")
ADMIN_ID        = os.getenv("ADMIN_USER_ID", "1667275809")

HAPPYHUB_API_URL = os.getenv("HAPPYHUB_API_URL", "https://happy-hub-1tzq.onrender.com/api").rstrip("/")
HAPPYHUB_EMAIL   = os.getenv("HAPPYHUB_EMAIL", "sopheapsocheat4@gmail.com")
HAPPYHUB_PASSWORD= os.getenv("HAPPYHUB_PASSWORD", "Password123!")
BOT_SECRET       = os.getenv("BOT_SECRET", "happyhub_telegram_secret_2026")

if not API_TOKEN:
    raise ValueError("BOT_TOKEN not found!")
if not LOG_CHANNEL_ID:
    raise ValueError("LOG_CHANNEL_ID not found!")
if not ADMIN_ID:
    raise ValueError("ADMIN_USER_ID not found!")

try:
    LOG_CHANNEL_ID = int(LOG_CHANNEL_ID)
except ValueError:
    pass

try:
    ADMIN_ID = int(ADMIN_ID) if ADMIN_ID else None
except ValueError:
    ADMIN_ID = None

bot = telebot.TeleBot(API_TOKEN)
telebot.apihelper.READ_TIMEOUT = 600
telebot.apihelper.CONNECT_TIMEOUT = 120

DOWNLOAD_FOLDER = "downloads"
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

COOKIES = {
    "tiktok":    "tiktok_cookies.txt",
    "facebook":  "fb_cookies.txt",
    "instagram": "ig_cookies.txt",
    "pornhub":   "ph_cookies.txt",
}

USERS_FILE = "users.json"


# ═════════════════════════════════════════════
#  PERSISTENT USER STORAGE
# ═════════════════════════════════════════════

def load_users() -> dict[int, dict]:
    """Load users from JSON file. Returns {user_id: {name, username, joined}}"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            return {int(k): v for k, v in raw.items()}
        except Exception as e:
            print(f"[USERS LOAD ERROR] {e}")
    return {}


def save_users(users: dict[int, dict]) -> None:
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"[USERS SAVE ERROR] {e}")


all_users: dict[int, dict] = load_users()
notified_users: set[int] = set(all_users.keys())


# ═════════════════════════════════════════════
#  USER JOIN NOTIFICATION
# ═════════════════════════════════════════════

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

    full_name = user.first_name
    if user.last_name:
        full_name += f" {user.last_name}"

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
            bot.send_photo(
                LOG_CHANNEL_ID,
                photo_file_id,
                caption=caption,
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                LOG_CHANNEL_ID,
                f"🖼️ _(No profile photo)_\n\n{caption}",
                parse_mode="Markdown"
            )
    except Exception as e:
        print(f"[JOIN LOG ERROR] {e}")
        print("[LOG HINT] ប្រាកដថា Bot ជា Admin ក្នុង Channel + ID ចាប់ផ្ដើម -100...")


# ═════════════════════════════════════════════
#  DOWNLOAD LOG
# ═════════════════════════════════════════════

def log_download(user, url: str, status: str, platform: str = "?", size_mb: float = 0.0, watch_url: str = ""):
    now      = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    username = f"@{user.username}" if user.username else "គ្មាន username"
    emoji    = "✅" if "success" in status else "❌"

    extra = f"\n🎬 HappyHub: {watch_url}" if watch_url else ""
    log_msg = (
        f"{emoji} *Download Log*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👤 User: {user.first_name} ({username})\n"
        f"🆔 Chat ID: `{user.id}`\n"
        f"🌐 Platform: {platform.upper()}\n"
        f"🔗 URL: {url}\n"
        f"📦 Size: {size_mb:.2f} MB\n"
        f"📊 Status: {status}{extra}\n"
        f"🕐 Time: {now}\n"
        f"━━━━━━━━━━━━━━━━"
    )

    try:
        bot.send_message(LOG_CHANNEL_ID, log_msg, parse_mode="Markdown")
    except Exception as e:
        print(f"[LOG ERROR] {e}")


# ═════════════════════════════════════════════
#  HAPPYHUB AUTO-POST SERVICE
# ═════════════════════════════════════════════

def extract_thumbnail_from_video(video_path: str) -> str | None:
    """Extracts a JPEG snapshot at 00:00:02 using imageio_ffmpeg."""
    thumb_path = os.path.splitext(video_path)[0] + "_thumb.jpg"
    try:
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_bin, "-y",
            "-ss", "00:00:02",
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            thumb_path
        ]
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            return thumb_path
        # Fallback to second 0 if second 2 failed
        cmd[3] = "00:00:00"
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=20)
        if os.path.exists(thumb_path) and os.path.getsize(thumb_path) > 0:
            return thumb_path
    except Exception as e:
        print(f"[THUMB ERROR] {e}")
    return None


def post_to_happyhub(file_path: str, title: str, platform: str, description: str = "") -> str | None:
    """Uploads downloaded video directly to Cloudflare R2 and posts it to HappyHub with thumbnail and duration."""
    try:
        session = requests.Session()
        # 1. Login to HappyHub
        login_res = session.post(
            f"{HAPPYHUB_API_URL}/auth/login",
            json={"email": HAPPYHUB_EMAIL, "password": HAPPYHUB_PASSWORD},
            headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
            timeout=20,
        )
        if login_res.status_code != 200:
            print(f"[HAPPYHUB] Login failed ({login_res.status_code}): {login_res.text}")
            return None

        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        clean_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", file_name)[-80:] or "video.mp4"

        # 2. Extract & Upload thumbnail directly to Cloudflare R2
        thumbnail_url = None
        thumb_path = extract_thumbnail_from_video(file_path)
        if thumb_path and os.path.exists(thumb_path):
            try:
                thumb_size = os.path.getsize(thumb_path)
                thumb_name = os.path.basename(thumb_path)
                clean_thumb_name = re.sub(r"[^a-zA-Z0-9._-]+", "_", thumb_name)[-80:] or "thumb.jpg"
                presign_thumb_res = session.post(
                    f"{HAPPYHUB_API_URL}/upload/presigned-url",
                    json={
                        "kind": "thumbnail",
                        "fileName": clean_thumb_name,
                        "fileType": "image/jpeg",
                        "fileSize": thumb_size,
                    },
                    headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
                    timeout=20,
                )
                if presign_thumb_res.status_code == 200:
                    thumb_data = presign_thumb_res.json()
                    thumb_upload_url = thumb_data.get("uploadUrl")
                    thumb_public_url = thumb_data.get("publicUrl")
                    if thumb_upload_url and thumb_public_url:
                        with open(thumb_path, "rb") as tf:
                            up_t = requests.put(
                                thumb_upload_url,
                                data=tf,
                                headers={"Content-Type": "image/jpeg"},
                                timeout=60,
                            )
                        if up_t.status_code in (200, 201):
                            thumbnail_url = thumb_public_url
                            print(f"[HAPPYHUB] Thumbnail uploaded: {thumbnail_url}")
            except Exception as te:
                print(f"[HAPPYHUB THUMB UPLOAD ERROR] {te}")
            finally:
                if os.path.exists(thumb_path):
                    try:
                        os.remove(thumb_path)
                    except OSError:
                        pass

        # 3. Request presigned upload URL from HappyHub backend
        presign_res = session.post(
            f"{HAPPYHUB_API_URL}/upload/presigned-url",
            json={
                "kind": "video",
                "fileName": clean_name,
                "fileType": "video/mp4",
                "fileSize": file_size,
            },
            headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
            timeout=20,
        )
        if presign_res.status_code != 200:
            print(f"[HAPPYHUB] Presigned URL failed ({presign_res.status_code}): {presign_res.text}")
            return None

        presign_data = presign_res.json()
        upload_url = presign_data.get("uploadUrl")
        storage_key = presign_data.get("storageKey")

        if not upload_url or not storage_key:
            return None

        # 4. Stream video file directly to Cloudflare R2
        with open(file_path, "rb") as f:
            upload_res = requests.put(
                upload_url,
                data=f,
                headers={"Content-Type": "video/mp4"},
                timeout=300,
            )
        if upload_res.status_code not in (200, 201):
            print(f"[HAPPYHUB] R2 stream upload failed with status {upload_res.status_code}")
            return None

        # 5. Finalize post registration on HappyHub
        final_title = (title or "Telegram Downloaded Video").strip()[:100]
        final_desc = description or f"Auto-downloaded from {platform.upper()} via Telegram Bot"
        tags = [platform.lower(), "telegram", "viral", "happyhub"]
        duration = get_video_duration(file_path)

        payload = {
            "storageKey": storage_key,
            "title": final_title,
            "description": final_desc,
            "tags": tags,
        }
        if thumbnail_url:
            payload["thumbnailUrl"] = thumbnail_url
        if duration and duration > 0:
            payload["duration"] = int(duration)
        if file_size and file_size > 0:
            payload["fileSize"] = int(file_size)

        complete_res = session.post(
            f"{HAPPYHUB_API_URL}/upload/complete",
            json=payload,
            headers={"Content-Type": "application/json", "X-Requested-With": "XMLHttpRequest"},
            timeout=20,
        )
        if complete_res.status_code in (200, 201):
            video_id = complete_res.json().get("video", {}).get("id")
            watch_url = f"https://happyhub-video.netlify.app/watch/{video_id}"
            print(f"[HAPPYHUB] Published successfully: {watch_url}")
            return watch_url
        else:
            print(f"[HAPPYHUB] Complete API failed ({complete_res.status_code}): {complete_res.text}")
            return None
    except Exception as ex:
        print(f"[HAPPYHUB EXCEPTION] {ex}")
        return None


# ═════════════════════════════════════════════
#  PLATFORM DETECTION
# ═════════════════════════════════════════════

def detect_platform(url: str) -> str:
    patterns = {
        "youtube":     r"(youtube\.com|youtu\.be)",
        "tiktok":      r"(tiktok\.com|vm\.tiktok\.com|vt\.tiktok\.com)",
        "facebook":    r"(facebook\.com|fb\.watch|fb\.com)",
        "instagram":   r"(instagram\.com)",
        "pornhub":     r"(pornhub\.com|phncdn\.com)",
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


# ═════════════════════════════════════════════
#  YT-DLP OPTIONS
# ═════════════════════════════════════════════

def build_ydl_opts(url: str, output_template: str, mobile_ua: bool = False) -> dict[str, Any]:
    platform = detect_platform(url)

    desktop_ua = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    )
    mobile_user_agent = (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) "
        "Version/17.0 Mobile/15E148 Safari/604.1"
    )
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
        opts["format"] = "best[ext=mp4]/best"
        opts["extractor_args"] = {"youtube": {"player_client": ["android", "ios", "web"]}}
    elif platform == "tiktok":
        opts["format"] = "best[ext=mp4]/best"
        opts["http_headers"]["Referer"] = "https://www.tiktok.com/"
        cookie_file = COOKIES.get("tiktok")
        if cookie_file and os.path.exists(cookie_file):
            opts["cookiefile"] = cookie_file
    elif platform == "facebook":
        opts["format"] = "best[ext=mp4]/best"
        opts["http_headers"]["Referer"] = "https://www.facebook.com/"
        cookie_file = COOKIES.get("facebook")
        if cookie_file and os.path.exists(cookie_file):
            opts["cookiefile"] = cookie_file
    elif platform == "instagram":
        opts["format"] = "best[ext=mp4]/best"
        opts["http_headers"]["Referer"] = "https://www.instagram.com/"
        cookie_file = COOKIES.get("instagram")
        if cookie_file and os.path.exists(cookie_file):
            opts["cookiefile"] = cookie_file
    elif platform == "pornhub":
        opts["format"] = "bestvideo*+bestaudio/best"
        opts["http_headers"]["Referer"] = "https://www.pornhub.com/"
        cookie_file = COOKIES.get("pornhub")
        if cookie_file and os.path.exists(cookie_file):
            opts["cookiefile"] = cookie_file
    else:
        opts["format"] = "best[ext=mp4]/best"

    return opts


def resolve_file_path(ydl: YoutubeDL, info_dict: dict) -> str | None:
    path = ydl.prepare_filename(info_dict)
    if os.path.exists(path):
        return path
    mp4 = os.path.splitext(path)[0] + ".mp4"
    if os.path.exists(mp4):
        return mp4
    try:
        files = [
            os.path.join(DOWNLOAD_FOLDER, f)
            for f in os.listdir(DOWNLOAD_FOLDER)
            if os.path.isfile(os.path.join(DOWNLOAD_FOLDER, f))
        ]
        if files:
            return max(files, key=os.path.getctime)
    except Exception:
        pass
    return None


def attempt_download(url: str, output_template: str) -> tuple[str | None, str | None, str]:
    last_error = "Unknown error"
    video_title = "Downloaded Video"

    for mobile_ua in [False, True]:
        label = "Mobile UA" if mobile_ua else "Desktop UA"
        print(f"[ATTEMPT] {label}")
        try:
            opts = build_ydl_opts(url, output_template, mobile_ua=mobile_ua)
            with YoutubeDL(opts) as ydl:  # type: ignore[arg-type]
                info = ydl.extract_info(url, download=True)
                if info and isinstance(info, dict):
                    video_title = info.get("title") or video_title
                path = resolve_file_path(ydl, info)
                if path:
                    return path, None, video_title
        except Exception as e:
            last_error = str(e)
            print(f"[FAILED] {label} → {last_error[:120]}")

    print("[ATTEMPT] Ultra-bare fallback")
    try:
        platform = detect_platform(url)
        bare: dict[str, Any] = {
            "outtmpl":    output_template,
            "format":     "best[ext=mp4]/best",
            "noplaylist": True,
            "retries":    5,
            "geo_bypass": True,
            "http_headers": {
                "User-Agent": (
                    "Mozilla/5.0 (Linux; Android 13; Pixel 7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.6367.82 Mobile Safari/537.36"
                ),
            },
        }
        if platform in COOKIES and os.path.exists(COOKIES[platform]):
            bare["cookiefile"] = COOKIES[platform]
        with YoutubeDL(bare) as ydl:  # type: ignore[arg-type]
            info = ydl.extract_info(url, download=True)
            if info and isinstance(info, dict):
                video_title = info.get("title") or video_title
            path = resolve_file_path(ydl, info)
            if path:
                return path, None, video_title
    except Exception as e:
        last_error = str(e)
        print(f"[FAILED] Ultra-bare → {last_error[:120]}")

    return None, last_error, video_title


def get_video_duration(file_path: str) -> float:
    """Extract video duration in seconds using imageio_ffmpeg."""
    try:
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        res = subprocess.run(
            [ffmpeg_bin, "-i", file_path],
            stderr=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            timeout=15
        )
        match = re.search(r"Duration:\s*(\d+):(\d+):(\d+\.?\d*)", res.stderr)
        if match:
            hours, minutes, seconds = match.groups()
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
    except Exception as e:
        print(f"[DURATION ERROR] {e}")
    return 0.0


def compress_video_for_telegram(input_path: str, target_mb: float = 28.0) -> str | None:
    """
    Smart compressor: compresses video with H.264 so it stays under Telegram's 50MB limit (~28MB)
    while preserving high visual clarity.
    Returns the path to the compressed file if successful, or None.
    """
    if not os.path.exists(input_path):
        return None

    file_size = os.path.getsize(input_path)
    if file_size <= 49 * 1024 * 1024:
        return input_path

    duration = get_video_duration(input_path)
    # If video is > 15 minutes (900 seconds), compressing down to 28MB will hurt quality too much.
    if duration > 900:
        print(f"[COMPRESS SKIP] Video duration {duration:.0f}s > 900s. Better to watch on HappyHub.")
        return None

    duration_sec = duration if duration > 5 else 60.0
    total_kb = target_mb * 8192
    audio_kbps = 96
    total_kbps = total_kb / duration_sec
    video_kbps = max(250, int(total_kbps - audio_kbps))

    compressed_path = os.path.splitext(input_path)[0] + "_compressed.mp4"
    try:
        ffmpeg_bin = imageio_ffmpeg.get_ffmpeg_exe()
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i", input_path,
            "-c:v", "libx264",
            "-preset", "faster",
            "-b:v", f"{video_kbps}k",
            "-maxrate", f"{int(video_kbps * 1.3)}k",
            "-bufsize", f"{int(video_kbps * 2)}k",
            "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2",
            "-c:a", "aac",
            "-b:a", f"{audio_kbps}k",
            "-movflags", "+faststart",
            compressed_path
        ]
        print(f"[COMPRESS] Running Smart Compression: target ~{target_mb}MB (video {video_kbps}k, scale 720p max)")
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=300)
        if proc.returncode == 0 and os.path.exists(compressed_path):
            comp_size = os.path.getsize(compressed_path)
            print(f"[COMPRESS OK] {file_size/(1024*1024):.1f}MB -> {comp_size/(1024*1024):.1f}MB")
            if comp_size <= 49.5 * 1024 * 1024:
                return compressed_path
    except Exception as ex:
        print(f"[COMPRESS ERROR] {ex}")

    if os.path.exists(compressed_path):
        try:
            os.remove(compressed_path)
        except Exception:
            pass
    return None


def friendly_error(err: str, platform: str) -> str:
    e = err.lower()
    if "unsupported url" in e:
        return "❌ Platform នេះមិន Support ទេ។"
    if "private" in e:
        return "❌ វីដេអូនេះជា Private — មើលមិនបាន។"
    if "login" in e or "sign in" in e:
        return "❌ វីដេអូនេះត្រូវ Login មើល។\n💡 Export cookies ពី Browser ហើយដាក់ក្នុង Folder Bot។"
    if "unavailable" in e or "removed" in e or "deleted" in e:
        return "❌ វីដេអូនេះត្រូវបានលុប ឬមិនមានទៀតហើយ។"
    if "timed out" in e or "timeout" in e:
        return "❌ Connection timeout — សូមព្យាយាមម្ដងទៀត។"
    if "403" in e:
        return (
            f"❌ Access ត្រូវបានបដិសេធ (403)。\n"
            f"💡 ត្រូវការ cookies file: {COOKIES.get(platform, 'cookies.txt')}"
        )
    return f"❌ Error: {err[:200]}"


# ═════════════════════════════════════════════
#  BOT HANDLERS
# ═════════════════════════════════════════════

@bot.message_handler(commands=["start"])
def send_welcome(message):
    user = message.from_user

    if user.id not in notified_users:
        notified_users.add(user.id)
        all_users[user.id] = {
            "name":     f"{user.first_name}{' ' + user.last_name if user.last_name else ''}",
            "username": user.username or "",
            "joined":   datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        save_users(all_users)
        log_user_join(user)

    bot.reply_to(
        message,
        "👋 *សួស្ដី! សូមស្វាគមន៍មកកាន់ Video Downloader & HappyHub Auto-Poster Bot!*\n\n"
        "✨ *Platform ដែល Support:*\n"
        "• TikTok (No Watermark)\n"
        "• YouTube Shorts & Videos\n"
        "• Facebook Reels & Videos\n"
        "• Instagram Reels\n"
        "• Pornhub / Twitter / X\n\n"
        "🚀 វីដេអូដែល Download នឹងត្រូវ Auto-Post ចូល HappyHub ដោយស្វ័យប្រវត្តិ!\n"
        "💡 ផ្ញើ link វីដេអូមកទីនេះដើម្បីចាប់ផ្ដើម!",
        parse_mode="Markdown"
    )


@bot.message_handler(commands=["help"])
def send_help(message):
    bot.reply_to(
        message,
        "👋 *Video Downloader & HappyHub Auto-Poster Bot*\n\n"
        "✅ *Platform ដែល Support:*\n"
        "• TikTok, YouTube, Facebook, Instagram, Pornhub, Twitter/X\n\n"
        "📽️ Format: MP4  |  Telegram Max: 50 MB\n"
        "🌐 HappyHub: វីដេអូធំជាង 50MB ក៏អាចមើលបានលើ HappyHub!\n\n"
        "💡 គ្រាន់តែ paste link វីដេអូមក!",
        parse_mode="Markdown"
    )


# ═════════════════════════════════════════════
#  ADMIN: BROADCAST & STATS
# ═════════════════════════════════════════════

@bot.message_handler(commands=["broadcast"])
def broadcast(message):
    if ADMIN_ID is None or message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ អ្នកមិនមានសិទ្ធិប្រើ command នេះទេ។")
        return

    text = message.text.partition(" ")[2].strip()
    if not text:
        bot.reply_to(
            message,
            "⚠️ *របៀបប្រើ:*\n`/broadcast សារដែលចង់ផ្ញើ`\n\n"
            "ឧទាហរណ៍:\n`/broadcast Bot នឹង Maintenance ម៉ោង 10 យប់!`",
            parse_mode="Markdown"
        )
        return

    user_ids = list(all_users.keys())
    total    = len(user_ids)

    if total == 0:
        bot.reply_to(message, "⚠️ មិនមានអ្នកប្រើណាម្នាក់ទេនៅឡើយ។")
        return

    status_msg = bot.reply_to(message, f"📤 កំពុងផ្ញើទៅ 0 / {total} នាក់...")

    sent    = 0
    failed  = 0
    blocked = 0

    broadcast_text = (
        f"📢 *សារពី Admin*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"{text}\n"
        f"━━━━━━━━━━━━━━━━"
    )

    for uid in user_ids:
        try:
            bot.send_message(uid, broadcast_text, parse_mode="Markdown")
            sent += 1
        except Exception as e:
            err = str(e).lower()
            if "blocked" in err or "deactivated" in err or "not found" in err or "403" in err:
                blocked += 1
            else:
                failed += 1
        if (sent + failed + blocked) % 20 == 0:
            try:
                bot.edit_message_text(
                    f"📤 កំពុងផ្ញើ... {sent + failed + blocked} / {total} នាក់",
                    message.chat.id,
                    status_msg.message_id
                )
            except Exception:
                pass

    summary = (
        f"✅ *Broadcast រួចរាល់!*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👥 សរុប: {total} នាក់\n"
        f"✅ ផ្ញើបាន: {sent} នាក់\n"
        f"🚫 Block/លុប: {blocked} នាក់\n"
        f"❌ Error: {failed} នាក់\n"
        f"━━━━━━━━━━━━━━━━"
    )
    bot.edit_message_text(summary, message.chat.id, status_msg.message_id, parse_mode="Markdown")


@bot.message_handler(commands=["stats"])
def stats(message):
    if ADMIN_ID is None or message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "⛔ អ្នកមិនមានសិទ្ធិប្រើ command នេះទេ។")
        return

    total = len(all_users)
    bot.reply_to(
        message,
        f"📊 *Bot Statistics*\n"
        f"━━━━━━━━━━━━━━━━\n"
        f"👥 Users សរុប: *{total} នាក់*\n"
        f"━━━━━━━━━━━━━━━━",
        parse_mode="Markdown"
    )


# ═════════════════════════════════════════════
#  VIP ORDER ADMIN APPROVAL CALLBACK HANDLER
# ═════════════════════════════════════════════

def log_vip_action(text: str):
    try:
        with open("bot_vip_log.txt", "a", encoding="utf-8") as f:
            f.write(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {text}\n")
    except Exception:
        pass

@bot.callback_query_handler(func=lambda call: bool(call.data and (call.data.startswith("vip_approve:") or call.data.startswith("vip_reject:"))))
def handle_vip_approval(call):
    log_vip_action(f"Callback from user {call.from_user.id} (@{call.from_user.username}): {call.data}")

    # Only Admin can approve/reject VIP orders
    if ADMIN_ID and str(call.from_user.id) != str(ADMIN_ID):
        log_vip_action(f"Auth failed: {call.from_user.id} != {ADMIN_ID}")
        bot.answer_callback_query(call.id, f"⛔ អ្នកមិនមានសិទ្ធិអនុម័ត VIP ទេ! (Your ID: {call.from_user.id})", show_alert=True)
        return

    data = call.data
    action, _, order_id = data.partition(":")
    is_approve = (action == "vip_approve")

    endpoint = f"{HAPPYHUB_API_URL}/vip/orders/{order_id}/approve" if is_approve else f"{HAPPYHUB_API_URL}/vip/orders/{order_id}/reject"

    try:
        res = requests.post(
            endpoint,
            headers={
                "x-bot-secret": BOT_SECRET,
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/json",
            },
            timeout=20,
        )
        data_json = res.json() if res.status_code in (200, 400, 403, 404, 500) else {}

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        admin_name = f"@{call.from_user.username}" if call.from_user.username else call.from_user.first_name

        if res.status_code == 200 and data_json.get("success"):
            log_vip_action(f"Successfully processed {action} for order {order_id}")
            if is_approve:
                msg_status = f"\n\n━━━━━━━━━━━━━━━━\n👑 *APPROVED BY ADMIN ({admin_name})*\n🕐 {now_str}\n🎉 VIP Member Activated!"
                toast_text = "✅ បានអនុម័ត VIP ជោគជ័យ! User បានឡើង VIP ហើយ។"

                # 🚀 Send Telegram Notification to the User
                try:
                    order_info = data_json.get("order", {})
                    user_info = data_json.get("user", {})
                    plan_name = order_info.get("plan", "VIP")
                    trans_id = order_info.get("transactionId") or ""

                    target_chat_id = None
                    target_username = None

                    # Check if TG: @username was passed in transactionId or user info
                    if "TG:" in trans_id:
                        target_username = trans_id.split("TG:")[1].strip().split()[0].lstrip("@").lower()
                    elif user_info.get("username"):
                        target_username = user_info.get("username").lstrip("@").lower()

                    if target_username:
                        for uid, udata in all_users.items():
                            u_uname = (udata.get("username") or "").lstrip("@").lower()
                            if u_uname and u_uname == target_username:
                                target_chat_id = uid
                                break

                    if target_chat_id:
                        user_msg = (
                            f"🎉 *អបអរសាទរ! កញ្ចប់ VIP របស់អ្នកត្រូវបាន Admin អនុម័តជោគជ័យ!*\n"
                            f"━━━━━━━━━━━━━━━━\n"
                            f"👑 *កញ្ចប់ VIP:* {plan_name}\n"
                            f"✨ គណនី HappyHub របស់អ្នកត្រូវបានដំឡើងសិទ្ធិ VIP រួចរាល់ហើយ!\n"
                            f"🎬 អ្នកអាចចូលទស្សនា និង Download 1080p ដោយឥតដែនកំណត់ឥឡូវនេះ:\n"
                            f"👉 [ចូលទស្សនា HappyHub](https://happyhub-video.netlify.app)\n"
                            f"━━━━━━━━━━━━━━━━\n"
                            f"🙏 សូមអរគុណសម្រាប់ការគាំទ្រ!"
                        )
                        bot.send_message(target_chat_id, user_msg, parse_mode="Markdown")
                        log_vip_action(f"Sent VIP notification to Telegram user {target_chat_id} (@{target_username})")
                    else:
                        log_vip_action(f"User @{target_username or 'unknown'} not in all_users or has not started the bot yet")
                except Exception as notify_user_err:
                    print(f"[NOTIFY USER ERROR] {notify_user_err}")
                    log_vip_action(f"Failed to notify user: {notify_user_err}")

            else:
                msg_status = f"\n\n━━━━━━━━━━━━━━━━\n❌ *REJECTED BY ADMIN ({admin_name})*\n🕐 {now_str}\n⚠️ Order Rejected."
                toast_text = "❌ បានបដិសេធ Order VIP នេះរួចរាល់!"

                try:
                    order_info = data_json.get("order", {})
                    trans_id = order_info.get("transactionId") or ""
                    target_chat_id = None
                    target_username = None
                    if "TG:" in trans_id:
                        target_username = trans_id.split("TG:")[1].strip().split()[0].lstrip("@").lower()
                    if target_username:
                        for uid, udata in all_users.items():
                            if (udata.get("username") or "").lstrip("@").lower() == target_username:
                                target_chat_id = uid
                                break
                    if target_chat_id:
                        bot.send_message(
                            target_chat_id,
                            "❌ *ការស្នើសុំ VIP ត្រូវបានបដិសេធដោយ Admin*\n\n"
                            "Admin មិនបានរកឃើញទឹកប្រាក់ចូលក្នុងកុង ABA ឬព័ត៌មានមិនត្រឹមត្រូវ។ សូមពិនិត្យឡើងវិញ ឬទាក់ទងមក Admin។",
                            parse_mode="Markdown"
                        )
                except Exception:
                    pass

            # Try to edit caption (if photo) or edit text (if message)
            try:
                if call.message.caption:
                    new_caption = call.message.caption + msg_status
                    bot.edit_message_caption(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        caption=new_caption,
                        parse_mode="Markdown",
                        reply_markup=None,
                    )
                else:
                    new_text = call.message.text + msg_status
                    bot.edit_message_text(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        text=new_text,
                        parse_mode="Markdown",
                        reply_markup=None,
                    )
            except Exception as edit_err:
                print(f"[EDIT MSG ERROR] {edit_err}")
                try:
                    bot.edit_message_reply_markup(
                        chat_id=call.message.chat.id,
                        message_id=call.message.message_id,
                        reply_markup=None,
                    )
                except Exception:
                    pass

            bot.answer_callback_query(call.id, toast_text, show_alert=True)
        else:
            err_msg = data_json.get("message") or data_json.get("error") or f"HTTP {res.status_code}"
            log_vip_action(f"Failed API call for {order_id} ({res.status_code}): {err_msg}")
            bot.answer_callback_query(call.id, f"⚠️ បរាជ័យ: {err_msg}", show_alert=True)
    except Exception as ex:
        print(f"[VIP APPROVAL EXCEPTION] {ex}")
        log_vip_action(f"Exception for {order_id}: {ex}")
        bot.answer_callback_query(call.id, f"❌ Error: {str(ex)[:80]}", show_alert=True)


# ═════════════════════════════════════════════
#  MAIN DOWNLOAD & AUTO-POST HANDLER
# ═════════════════════════════════════════════

def is_image_url(url: str) -> bool:
    clean_url = url.split("?", 1)[0].lower()
    return clean_url.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))


@bot.message_handler(func=lambda message: True)
def download_video(message):
    url      = message.text.strip()
    user     = message.from_user
    platform = detect_platform(url)

    if not url.startswith(("http://", "https://")):
        bot.reply_to(message, "⚠️ សូមផ្ញើ URL ដែលចាប់ផ្ដើមដោយ http:// ឬ https://")
        return

    if is_image_url(url):
        bot.reply_to(
            message,
            "⚠️ Link ដែលអ្នកផ្ញើជា Thumbnail/Image (.jpg) មិនមែនជា Video link ទេ។ សូមផ្ញើ Original video link!"
        )
        return

    msg = bot.send_message(
        message.chat.id,
        f"⏳ កំពុងដំណើរការ... [{platform.upper()}]"
    )

    size_mb: float = 0.0
    safe_uid = str(uuid.uuid4())[:8]
    output_template = f"{DOWNLOAD_FOLDER}/{safe_uid}_%(title).70s.%(ext)s"

    bot.edit_message_text(
        f"⬇️ កំពុង Download... [{platform.upper()}]",
        message.chat.id, msg.message_id
    )

    file_path, err, video_title = attempt_download(url, output_template)

    if file_path is None:
        reply = friendly_error(err or "Unknown error", platform)
        bot.edit_message_text(reply, message.chat.id, msg.message_id, parse_mode="Markdown")
        log_download(user, url, f"error: {(err or '')[:100]}", platform, 0.0)
        return

    try:
        file_size = os.path.getsize(file_path)
        size_mb   = file_size / (1024 * 1024)
    except OSError:
        bot.edit_message_text("❌ File រកមិនឃើញក្រោយ Download។", message.chat.id, msg.message_id)
        log_download(user, url, "error: file missing", platform)
        return

    bot.edit_message_text(
        f"☁️ កំពុង Auto-Post ចូល HappyHub... [{size_mb:.1f} MB]",
        message.chat.id, msg.message_id
    )

    # Auto-post to HappyHub
    watch_url = post_to_happyhub(file_path, video_title, platform)

    caption_suffix = f"\n\n🎬 *មើលលើ HappyHub:* [ចុចទីនេះ]({watch_url})" if watch_url else ""

    target_send_path = file_path
    cleanup_compressed = False
    send_size_mb = size_mb

    # Check Telegram's 50MB bot upload limit
    if file_size > 50 * 1024 * 1024:
        duration = get_video_duration(file_path)
        if duration > 900:
            mins = int(duration // 60)
            if watch_url:
                bot.edit_message_text(
                    f"✅ *Auto-Post ចូល HappyHub រួចរាល់ (Full HD)!*\n\n"
                    f"ℹ️ វីដេអូវែង ({mins} នាទី / {size_mb:.1f} MB) លើសពី 50 MB របស់ Telegram។\n"
                    f"ដើម្បីរក្សាគុណភាពច្បាស់ដាច់លេខ សូមចុចទស្សនាលើ HappyHub:\n\n"
                    f"👉 [ចុចទស្សនាកម្រិត Full HD លើ HappyHub]({watch_url})",
                    message.chat.id, msg.message_id,
                    parse_mode="Markdown"
                )
                log_download(user, url, "success (happyhub only, >15m >50MB)", platform, size_mb, watch_url)
            else:
                bot.edit_message_text(
                    f"❌ វីដេអូធំពេក ({size_mb:.1f} MB) ហើយមានប្រវែងវែង ({mins} នាទី)។ Telegram ទទួលត្រឹមតែ 50 MB ប៉ុណ្ណោះ។",
                    message.chat.id, msg.message_id
                )
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            return

        bot.edit_message_text(
            f"🔄 វីដេអូមានទំហំ ({size_mb:.1f} MB > 50MB)\n"
            f"⚡ កំពុង Smart-Compress បង្រួមមក ~28MB កម្រិត 720p HD ដើម្បីផ្ញើចូល Telegram...",
            message.chat.id, msg.message_id
        )
        comp_file = compress_video_for_telegram(file_path)
        if comp_file and os.path.exists(comp_file):
            target_send_path = comp_file
            cleanup_compressed = True
            send_size_mb = os.path.getsize(comp_file) / (1024 * 1024)
        else:
            if watch_url:
                bot.edit_message_text(
                    f"✅ *Auto-Post ចូល HappyHub រួចរាល់ (Full HD)!*\n\n"
                    f"⚠️ វីដេអូមានទំហំដើម ({size_mb:.1f} MB) លើសពី 50 MB របស់ Telegram។\n"
                    f"អ្នកអាចទស្សនាវីដេអូកម្រិតច្បាស់ពេញលេញបានលើ HappyHub:\n\n"
                    f"👉 [ចុចទស្សនាលើ HappyHub]({watch_url})",
                    message.chat.id, msg.message_id,
                    parse_mode="Markdown"
                )
                log_download(user, url, "success (happyhub only, comp failed)", platform, size_mb, watch_url)
            else:
                bot.edit_message_text(
                    f"❌ វីដេអូធំពេក ({size_mb:.1f} MB) ហើយមិនអាចបង្រួមបាន។",
                    message.chat.id, msg.message_id
                )
            if file_path and os.path.exists(file_path):
                os.remove(file_path)
            return

    bot.edit_message_text("📤 កំពុងផ្ញើចូល Telegram...", message.chat.id, msg.message_id)

    upload_ok = False
    for attempt in range(3):
        try:
            with open(target_send_path, "rb") as video:
                bot.send_video(
                    message.chat.id,
                    video,
                    timeout=600,
                    supports_streaming=True,
                    caption=f"✅ {send_size_mb:.1f} MB | {platform.upper()} | MP4{caption_suffix}",
                    parse_mode="Markdown"
                )
            upload_ok = True
            break
        except Exception as upload_err:
            print(f"[UPLOAD ATTEMPT {attempt+1} ERROR] {upload_err}")
            if attempt == 2:
                msg_text = f"❌ Telegram Upload បរាជ័យ: {str(upload_err)[:100]}"
                if watch_url:
                    msg_text += f"\n\n✅ ប៉ុន្តែបាន Post ចូល HappyHub រួចរាល់: {watch_url}"
                bot.edit_message_text(
                    msg_text,
                    message.chat.id, msg.message_id
                )
                log_download(user, url, f"upload error: {str(upload_err)[:80]}", platform, size_mb, watch_url or "")
            else:
                bot.edit_message_text(
                    f"⚠️ Upload ម្ដងទៀត {attempt + 1}/3...",
                    message.chat.id, msg.message_id
                )

    if upload_ok:
        status_text = "✅ រួចរាល់!"
        if watch_url:
            status_text += f"\n🎬 Video Live on HappyHub: {watch_url}"
        bot.edit_message_text(status_text, message.chat.id, msg.message_id)
        log_download(user, url, "success", platform, size_mb, watch_url or "")

    if cleanup_compressed and os.path.exists(target_send_path):
        try:
            os.remove(target_send_path)
        except Exception:
            pass

    if file_path and os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass


if __name__ == "__main__":
    import time
    print("🤖 HappyHub Video Downloader & Auto-Poster Bot is running...")
    while True:
        try:
            bot.infinity_polling(timeout=25, long_polling_timeout=25)
        except Exception as poll_err:
            print(f"[POLL RECONNECTING] {poll_err}")
            time.sleep(3)
