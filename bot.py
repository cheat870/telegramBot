import os
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes
import yt_dlp

BOT_TOKEN = "7775236984:AAEG62do6oEDZh40cg9yuqvq5tSC2vC_hKM"
DOWNLOAD_FOLDER = "downloads"
TELEGRAM_MAX_SIZE = 50 * 1024 * 1024  # 50 MB

os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

# --- Start command ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "សួស្ដី! ចម្លង link TikTok ដើម្បីទាញយកវីដេអូ។\n"
        "វីដេអូ MP4 នឹងត្រូវទាញយក និងផ្ញើដោយស្វ័យប្រវត្តិ។"
    )

# --- Progress hook with single message ---
def progress_hook(update: Update, context: ContextTypes.DEFAULT_TYPE, msg_id_container: dict):
    last_percent = {"value": 0}

    def hook(d):
        if d['status'] == 'downloading':
            percent_str = d.get('_percent_str', '0%')
            try:
                percent = int(percent_str.strip().replace('%',''))
            except:
                percent = 0

            if percent != last_percent["value"] and percent % 5 == 0:
                last_percent["value"] = percent
                # Update single message
                asyncio.create_task(update_progress(update, context, msg_id_container, percent))

    return hook

async def update_progress(update, context, msg_id_container, percent):
    if 'msg_id' in msg_id_container:
        try:
            await context.bot.edit_message_text(
                chat_id=update.effective_chat.id,
                message_id=msg_id_container['msg_id'],
                text=f"⏳ Downloading: {percent}%"
            )
        except:
            pass
    else:
        msg = await update.message.reply_text(f"⏳ Downloading: {percent}%")
        msg_id_container['msg_id'] = msg.message_id

# --- Download video function ---
async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    url = update.message.text
    msg_id_container = {}

    ydl_opts = {
        'outtmpl': os.path.join(DOWNLOAD_FOLDER, '%(title)s.%(ext)s'),
        'format': 'bestvideo+bestaudio/best',
        'noplaylist': True,
        'progress_hooks': [progress_hook(update, context, msg_id_container)],
        'quiet': True,
        'merge_output_format': 'mp4',
    }

    try:
        def download():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                info = ydl.extract_info(url, download=True)
                # New yt-dlp: get filepath from requested_downloads
                if 'requested_downloads' in info:
                    return info['requested_downloads'][0]['filepath']
                return ydl.prepare_filename(info)

        file_path = await asyncio.to_thread(download)
        file_size = os.path.getsize(file_path)

        # Update progress message to finished
        if 'msg_id' in msg_id_container:
            try:
                await context.bot.edit_message_text(
                    chat_id=update.effective_chat.id,
                    message_id=msg_id_container['msg_id'],
                    text="⏳ Download complete!"
                )
            except:
                pass

        # Send video/document
        with open(file_path, 'rb') as f:
            if file_size <= TELEGRAM_MAX_SIZE:
                await update.message.reply_video(f, caption="✅ Video Download Finished!")
            else:
                await update.message.reply_document(
                    f, caption=f"✅ Video Download Finished! (File size: {file_size / (1024*1024):.2f} MB)"
                )

        os.remove(file_path)

    except Exception as e:
        await update.message.reply_text(f"សូមរងចាំបន្តិច....")

# --- Main bot ---
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, download_video))

    print("🚀 Bot is running...")
    app.run_polling()

if __name__ == "__main__":
    main()
