import asyncio
import os
from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from yt_dlp import YoutubeDL
import uuid
import shutil

# Initialize the bot
app = Client(
    "youtube_downloader_bot",
    api_id=os.getenv("API_ID"),
    api_hash=os.getenv("API_HASH"),
    bot_token=os.getenv("BOT_TOKEN")
)

# Store user states and video info
user_states = {}
video_info = {}

# Start command
@app.on_message(filters.command("start"))
async def start(client, message):
    await message.reply_text(
        "Welcome to YouTube Downloader Bot!\nSend a YouTube link to download as video or MP3.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("Help", callback_data="help")]
        ])
    )

# Handle YouTube URL
@app.on_message(filters.regex(r"^(https?://)?(www\.)?(youtube\.com|youtu\.be)/"))
async def handle_youtube_url(client, message):
    user_id = message.from_user.id
    url = message.text

    # Fetch video info using yt-dlp
    ydl_opts = {'quiet': True, 'noplaylist': True}
    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_info[user_id] = info
            formats = info.get('formats', [])
            
            # Prepare format selection buttons
            video_buttons = []
            audio_buttons = []
            for fmt in formats:
                if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                    resolution = f"{fmt.get('resolution', 'Unknown')} ({fmt.get('ext')})"
                    video_buttons.append(
                        InlineKeyboardButton(
                            resolution,
                            callback_data=f"video_{fmt['format_id']}"
                        )
                    )
                elif fmt.get('acodec') != 'none':
                    audio_quality = f"{fmt.get('abr', 0)}kbps ({fmt.get('ext')})"
                    audio_buttons.append(
                        InlineKeyboardButton(
                            audio_quality,
                            callback_data=f"audio_{fmt['format_id']}"
                        )
                    )

            # Create keyboard
            buttons = []
            if video_buttons:
                buttons.append([InlineKeyboardButton("Download Video", callback_data="select_video")])
                if len(video_buttons) > 0:
                    buttons.extend([video_buttons[i:i+2] for i in range(0, len(video_buttons), 2)])
            if audio_buttons:
                buttons.append([InlineKeyboardButton("Download Audio", callback_data="select_audio")])
                if len(audio_buttons) > 0:
                    buttons.extend([audio_buttons[i:i+2] for i in range(0, len(audio_buttons), 2)])

            user_states[user_id] = {'url': url, 'stage': 'select_type'}
            await message.reply_text(
                f"Video: {info.get('title')}\nChoose download type:",
                reply_markup=InlineKeyboardMarkup(buttons)
            )
    except Exception as e:
        await message.reply_text(f"Error: {str(e)}")

# Handle callback queries
@app.on_callback_query()
async def handle_callback(client, callback_query):
    user_id = callback_query.from_user.id
    data = callback_query.data

    if user_id not in user_states:
        await callback_query.message.reply_text("Please send a YouTube link first.")
        return

    state = user_states[user_id]

    if data == "select_video":
        user_states[user_id]['stage'] = 'select_video_resolution'
        formats = video_info[user_id].get('formats', [])
        video_buttons = []
        for fmt in formats:
            if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                resolution = f"{fmt.get('resolution', 'Unknown')} ({fmt.get('ext')})"
                video_buttons.append(
                    [InlineKeyboardButton(resolution, callback_data=f"video_{fmt['format_id']}")]
                )
        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(video_buttons)
        )
    elif data == "select_audio":
        user_states[user_id]['stage'] = 'select_audio_resolution'
        formats = video_info[user_id].get('formats', [])
        audio_buttons = []
        for fmt in formats:
            if fmt.get('acodec') != 'none':
                audio_quality = f"{fmt.get('abr', 0)}kbps ({fmt.get('ext')})"
                audio_buttons.append(
                    [InlineKeyboardButton(audio_quality, callback_data=f"audio_{fmt['format_id']}")]
                )
        await callback_query.message.edit_reply_markup(
            reply_markup=InlineKeyboardMarkup(audio_buttons)
        )
    elif data.startswith("video_") or data.startswith("audio_"):
        format_id = data.split("_")[1]
        url = state['url']
        output_path = f"downloads/{uuid.uuid4()}"
        
        if data.startswith("video_"):
            ydl_opts = {
                'format': format_id,
                'outtmpl': f"{output_path}.%(ext)s",
                'merge_output_format': 'mp4'
            }
        else:
            ydl_opts = {
                'format': format_id,
                'outtmpl': f"{output_path}.mp3",
                'postprocessors': [{
                    'key': 'FFmpegExtractAudio',
                    'preferredcodec': 'mp3',
                    'preferredquality': '192',
                }]
            }

        try:
            await callback_query.message.reply_text("Downloading... Please wait.")
            with YoutubeDL(ydl_opts) as ydl:
                ydl.download([url])
            
            # Find the downloaded file
            for file in os.listdir("downloads"):
                if file.startswith(os.path.basename(output_path)):
                    file_path = os.path.join("downloads", file)
                    break
            else:
                await callback_query.message.reply_text("Error: File not found after download.")
                return

            # Send file
            if data.startswith("video_"):
                await callback_query.message.reply_video(
                    video=file_path,
                    caption=video_info[user_id].get('title')
                )
            else:
                await callback_query.message.reply_audio(
                    audio=file_path,
                    caption=video_info[user_id].get('title')
                )

            # Clean up
            shutil.rmtree("downloads", ignore_errors=True)
            os.makedirs("downloads", exist_ok=True)
            del user_states[user_id]
            del video_info[user_id]
        except Exception as e:
            await callback_query.message.reply_text(f"Error: {str(e)}")
            shutil.rmtree("downloads", ignore_errors=True)
            os.makedirs("downloads", exist_ok=True)

# Help command
@app.on_message(filters.command("help"))
async def help_command(client, message):
    await message.reply_text(
        "Send a YouTube link to download.\n"
        "1. Choose Video or Audio.\n"
        "2. Select resolution/quality.\n"
        "3. Wait for the download to complete."
    )

async def main():
    os.makedirs("downloads", exist_ok=True)
    await app.start()
    await app.idle()

if __name__ == "__main__":
    asyncio.run(main())
