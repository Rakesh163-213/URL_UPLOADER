import os
import asyncio
from pyrogram import Client, filters
from pyrogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from config import API_ID, API_HASH, BOT_TOKEN, MAX_FILE_SIZE, DOWNLOAD_DIR, TEMP_DIR, QUALITY_OPTIONS
from downloader import VideoDownloader
from uploader import VideoUploader
from progress import ProgressManager
from utils import format_size, format_time, cleanup_files


# Create directories
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_DIR, exist_ok=True)

# Initialize components
app = Client("url_uploader_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)
downloader = VideoDownloader(DOWNLOAD_DIR)
uploader = VideoUploader(app, MAX_FILE_SIZE)  # Initialize immediately
progress_manager = ProgressManager()

# Bot statistics
stats = {
    'downloads': 0,
    'uploads': 0,
    'users': set()
}

# Store URL mappings for quality selection callbacks
url_mappings = {}

# Store message references for progress updates
progress_messages = {}


@app.on_message(filters.command("start"))
async def start_command(client, message: Message):
    """Handle /start command"""
    user_id = message.from_user.id
    stats['users'].add(user_id)

    welcome_text = """🤖 **URL Uploader Bot**

Send me any video URL and I'll download it for you!

**Features:**
• 🎬 Multiple quality options
• 📊 Real-time progress tracking
• 🖼️ Auto-generated thumbnails
• 📦 Large file support (splits >1.9GB)
• ⚡ Fast downloads and uploads

**Commands:**
/start - Show this message
/help - Get help
/status - Check bot status
/stats - View statistics

**Supported URLs:**
• YouTube videos
• Direct HTTP/HTTPS links
• Many other video platforms

Just send me a URL to get started!"""

    await message.reply_text(welcome_text)


@app.on_message(filters.command("help"))
async def help_command(client, message: Message):
    """Handle /help command"""
    help_text = """📖 **Help**

**How to use:**
1. Send me a video URL
2. Choose your preferred quality
3. Wait for download and upload
4. Enjoy your video!

**Quality Options:**
• 144p - ~20MB
• 240p - ~30MB
• 360p - ~50MB
• 480p - ~100MB
• 720p - ~200MB
• 1080p - ~500MB
• Best - Up to 2GB

**Progress Tracking:**
• Real-time download/upload progress
• Speed and ETA display
• Cancel button to stop mid-way

**Large Files:**
• Files > 1.9GB are automatically split
• Each part is uploaded separately
• Parts are numbered for easy identification

**Tips:**
• Use direct links for faster downloads
• Lower quality = faster download
• Check /status for bot health

Need more help? Contact @support"""

    await message.reply_text(help_text)


@app.on_message(filters.command("status"))
async def status_command(client, message: Message):
    """Handle /status command"""
    status_text = f"""🟢 **Bot Status**

✅ Bot is running and healthy
✅ Download service active
✅ Upload service active
✅ Progress tracking enabled

**Configuration:**
• Max file size: {format_size(MAX_FILE_SIZE)}
• Download directory: {DOWNLOAD_DIR}
• Temp directory: {TEMP_DIR}

**System:**
• Active users: {len(stats['users'])}
• Total downloads: {stats['downloads']}
• Total uploads: {stats['uploads']}

Everything is working normally! 🚀"""

    await message.reply_text(status_text)


@app.on_message(filters.command("stats"))
async def stats_command(client, message: Message):
    """Handle /stats command"""
    stats_text = f"""📊 **Statistics**

**Usage:**
• Total users: {len(stats['users'])}
• Total downloads: {stats['downloads']}
• Total uploads: {stats['uploads']}

**Success Rate:**
• Downloads completed: {stats['downloads']}
• Uploads completed: {stats['uploads']}

**Performance:**
• Average download speed: Calculating...
• Average upload speed: Calculating...

Keep using the bot! 🎉"""

    await message.reply_text(stats_text)


@app.on_message(filters.text)
async def handle_url(client, message: Message):
    """Handle URL messages"""
    # Skip if it's a command
    if message.text.startswith('/'):
        return

    url = message.text.strip()

    # Basic URL validation
    if not (url.startswith('http://') or url.startswith('https://')):
        await message.reply_text("❌ Please send a valid URL (http:// or https://)")
        return

    # Get video info
    await message.reply_text("🔍 Analyzing video...")

    video_info = downloader.get_video_info(url)

    if not video_info:
        await message.reply_text("❌ Failed to get video info. Please check the URL and try again.")
        return

    # Generate quality options
    quality_options = downloader.get_quality_options(video_info, QUALITY_OPTIONS)

    if not quality_options:
        await message.reply_text("❌ No suitable quality options found for this video.")
        return

    # Store URL mapping for callback handling
    url_mapping = {}

    # Create inline keyboard
    keyboard = []
    for option in quality_options:
        quality = option['quality']
        # Use actual file size if available, otherwise use max_size
        if 'estimated_size' in option and option['estimated_size']:
            size = format_size(option['estimated_size'])
        else:
            size = format_size(option['max_size'])
        callback_data = f"quality_{option['format_id']}"
        keyboard.append([InlineKeyboardButton(f"{quality} ({size})", callback_data=callback_data)])

        # Store URL for this format_id
        url_mapping[option['format_id']] = url

    reply_markup = InlineKeyboardMarkup(keyboard)

    # Display video info
    title = video_info['title']
    duration = format_time(video_info['duration'])
    estimated_size = format_size(video_info['filesize']) if video_info['filesize'] else "Unknown"

    info_text = f"""🎬 **Video Found**

📹 **Title:** {title}
⏱️ **Duration:** {duration}
📦 **Estimated Size:** {estimated_size}

Select your preferred quality:"""

    sent_message = await message.reply_text(info_text, reply_markup=reply_markup)

    # Store URL mapping with message ID
    url_mappings[sent_message.id] = url_mapping


@app.on_callback_query()
async def handle_callback(client, callback_query: CallbackQuery):
    """Handle callback queries"""
    user_id = callback_query.from_user.id
    message_id = callback_query.message.id

    if callback_query.data == "cancel":
        # Handle cancel
        tracker = progress_manager.get_tracker(user_id, message_id)
        if tracker:
            tracker.cancel()
            await callback_query.answer("Cancelling...")
            await callback_query.message.edit_text("❌ Operation cancelled")
        else:
            await callback_query.answer("No active operation to cancel")
        return

    # Handle quality selection
    if callback_query.data.startswith("quality_"):
        format_id = callback_query.data.replace("quality_", "")

        # Get URL from stored mapping
        message_id = callback_query.message.id
        if message_id not in url_mappings:
            await callback_query.answer("❌ Error: Session expired. Please send the URL again.")
            return

        url_mapping = url_mappings[message_id]
        url = url_mapping.get(format_id)

        if not url:
            await callback_query.answer("❌ Error: URL not found for this quality option")
            return

        # Get video info again
        video_info = downloader.get_video_info(url)
        if not video_info:
            await callback_query.answer("❌ Failed to get video info")
            return

        # Find quality option
        quality_option = None
        for option in downloader.get_quality_options(video_info, QUALITY_OPTIONS):
            if option['format_id'] == format_id:
                quality_option = option
                break

        if not quality_option:
            await callback_query.answer("❌ Quality option not found")
            return

        # Start download
        await callback_query.answer(f"Starting download in {quality_option['quality']}...")

        # Create progress tracker with filename and quality
        tracker = progress_manager.create_tracker(
            user_id,
            message_id,
            filename=video_info['title'],
            quality=quality_option['quality']
        )

        # Update message with initial progress
        progress_text = f"""📥 **Starting Download...**

🎬 {video_info['title']}
⏱️ Duration: {format_time(video_info['duration'])}
📊 Quality: {quality_option['quality']}"""

        await callback_query.message.edit_text(
            progress_text,
            reply_markup=uploader.get_cancel_keyboard()
        )

        # Download in background
        asyncio.create_task(download_and_upload(
            client,
            callback_query.message,
            url,
            quality_option,
            video_info,
            tracker,
            user_id,
            message_id
        ))


async def progress_updater():
    """Background task to update progress messages every 0.5-1 second for smooth animation"""
    print("Progress updater started")
    while True:
        await asyncio.sleep(0.5)  # Update every 0.5 seconds for smooth animation
        try:
            # Get all active trackers
            trackers = progress_manager.get_all_trackers()

            for tracker in trackers:
                try:
                    # Get the message to update
                    key = (tracker.user_id, tracker.message_id)
                    if key in progress_messages:
                        message = progress_messages[key]
                        progress_text = tracker.get_progress_text()

                        # Update the message with progress
                        try:
                            await message.edit_text(
                                progress_text,
                                reply_markup=uploader.get_cancel_keyboard()
                            )
                        except Exception as e:
                            # Ignore common Telegram errors
                            if "FloodWait" not in str(e) and "MessageNotModified" not in str(e):
                                print(f"Error updating progress message: {e}")
                except Exception as e:
                    print(f"Error in progress tracker loop: {e}")
        except Exception as e:
            print(f"Error in progress updater: {e}")


async def download_and_upload(client, message, url, quality_option, video_info, tracker, user_id, message_id):
    """Download and upload video with progress tracking"""
    try:
        # Store message reference for progress updates
        progress_messages[(user_id, message_id)] = message

        # Update stats
        stats['downloads'] += 1

        # Download video in thread pool to avoid blocking async operations
        downloaded_file, error = await asyncio.to_thread(
            downloader.download_video, url, quality_option, tracker
        )

        if error:
            await message.edit_text(f"❌ Download failed: {error}")
            progress_manager.remove_tracker(user_id, message_id)
            if (user_id, message_id) in progress_messages:
                del progress_messages[(user_id, message_id)]
            return

        if not downloaded_file or not os.path.exists(downloaded_file):
            await message.edit_text("❌ Downloaded file not found")
            progress_manager.remove_tracker(user_id, message_id)
            if (user_id, message_id) in progress_messages:
                del progress_messages[(user_id, message_id)]
            return

        # Update message for upload
        file_size = os.path.getsize(downloaded_file)
        filename = os.path.basename(downloaded_file)

        # Update tracker for upload phase
        tracker.filename = filename
        tracker.reset()

        upload_text = f"""📤 **Starting Upload...**

🎬 {video_info['title']}
📦 Size: {format_size(file_size)}
📁 Filename: {filename}"""

        await message.edit_text(
            upload_text,
            reply_markup=uploader.get_cancel_keyboard()
        )

        # Upload video
        caption = filename
        result, upload_error = await uploader.upload_video(
            message.chat.id,
            downloaded_file,
            tracker,
            caption
        )

        if upload_error:
            await message.edit_text(f"❌ Upload failed: {upload_error}")
            cleanup_files([downloaded_file])
            progress_manager.remove_tracker(user_id, message_id)
            if (user_id, message_id) in progress_messages:
                del progress_messages[(user_id, message_id)]
            return

        # Update stats
        stats['uploads'] += 1

        # Success message
        success_text = f"""✅ **Upload Complete!**

🎬 {video_info['title']}
📦 Size: {format_size(file_size)}
📁 Filename: {filename}

Your video has been uploaded successfully!"""

        await message.edit_text(success_text)

        # Cleanup downloaded file
        cleanup_files([downloaded_file])

        # Remove tracker and message reference
        progress_manager.remove_tracker(user_id, message_id)
        if (user_id, message_id) in progress_messages:
            del progress_messages[(user_id, message_id)]

    except Exception as e:
        await message.edit_text(f"❌ Error: {str(e)}")
        progress_manager.remove_tracker(user_id, message_id)
        if (user_id, message_id) in progress_messages:
            del progress_messages[(user_id, message_id)]


from pyrogram import idle

if __name__ == "__main__":
    print("Starting URL Uploader Bot...")

    async def main():
        # Start background progress updater
        asyncio.create_task(progress_updater())

        # Start bot
        await app.start()

        print("Bot started successfully!")

        # Keep bot running
        await idle()

        # Stop bot cleanly
        await app.stop()

    asyncio.run(main())
