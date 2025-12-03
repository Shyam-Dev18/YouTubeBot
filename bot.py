import os
import asyncio
import logging
import sys
from typing import Dict, Optional
from datetime import datetime
from aiohttp import web

from pyrogram import Client, filters
from pyrogram.types import (
    Message, InlineKeyboardMarkup, 
    InlineKeyboardButton, CallbackQuery
)
from pyrogram.enums import ParseMode

from config import config
from utils.downloader import YouTubeDownloader
from utils.helpers import (
    format_size, cleanup_temp_files, 
    is_valid_youtube_url
)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Global state management
class BotState:
    def __init__(self):
        self.active_downloads: Dict[int, asyncio.Task] = {}
        self.user_data: Dict[int, Dict] = {}
        self.downloader = YouTubeDownloader()
        self.shutting_down = False
        
    async def cleanup_user(self, user_id: int):
        """Clean up user data and cancel tasks"""
        if user_id in self.active_downloads:
            task = self.active_downloads[user_id]
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            del self.active_downloads[user_id]
        
        if user_id in self.user_data:
            data = self.user_data[user_id]
            if 'temp_files' in data:
                for file_path in data['temp_files']:
                    if os.path.exists(file_path):
                        try:
                            os.remove(file_path)
                        except:
                            pass
            del self.user_data[user_id]

bot_state = BotState()

# Initialize Pyrogram client
app = Client(
    "youtube_bot",
    api_id=config.API_ID,
    api_hash=config.API_HASH,
    bot_token=config.BOT_TOKEN,
    workers=100,
    sleep_threshold=60,
    in_memory=False
)

# Health check server
async def health_check(request):
    """Health check endpoint for UptimeRobot"""
    try:
        if bot_state.shutting_down:
            return web.Response(status=503, text="Bot is shutting down")
        
        return web.Response(text="Bot is Alive and Running")
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return web.Response(status=500, text=f"Error: {str(e)}")

async def start_web_server():
    """Starts the aiohttp web server."""
    server = web.Application()
    server.router.add_get("/", health_check)
    server.router.add_get("/health", health_check)
    runner = web.AppRunner(server)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", config.HEALTH_PORT)
    await site.start()
    logger.info(f"✅ Web server started on port {config.HEALTH_PORT}")
    return runner

async def shutdown_handler():
    """Handle graceful shutdown"""
    if bot_state.shutting_down:
        return
    
    logger.info("Shutdown requested...")
    bot_state.shutting_down = True
    
    for user_id in list(bot_state.active_downloads.keys()):
        await bot_state.cleanup_user(user_id)
    
    cleanup_temp_files()
    logger.info("Shutdown complete")

# ===== MESSAGE HANDLERS =====

@app.on_message(filters.command(["start", "help"]) & filters.private)
async def start_command(client: Client, message: Message):
    """Handle start command"""
    user_id = message.from_user.id
    
    welcome_text = """
🎬 **YouTube Video Downloader Bot**

**Features:**
• Max file size: 850MB
• Fast download & merge without re-encoding
• Shows progress during download
• Choose from available resolutions
• MP4 format with H.264/AAC codecs

**How to use:**
1. Paste a YouTube video URL
2. Choose resolution from buttons
3. Wait for download and automatic upload

⚠️ **Note:** Only one download at a time per user.

**Now, please paste your YouTube video URL below:**
    """
    
    # Mark user as waiting for URL
    bot_state.user_data[user_id] = {
        'waiting_for_url': True,
        'chat_id': message.chat.id
    }
    
    await message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )
    logger.info(f"User {user_id} started bot")

@app.on_message(filters.command("download") & filters.private)
async def download_command(client: Client, message: Message):
    """Handle download command"""
    user_id = message.from_user.id
    
    # Check if user already has an active download
    if user_id in bot_state.active_downloads:
        await message.reply_text(
            "⚠️ You already have an active download. "
            "Please wait for it to complete or use /cancel."
        )
        return
    
    # Check if bot is shutting down
    if bot_state.shutting_down:
        await message.reply_text("⚠️ Bot is shutting down. Please try again later.")
        return
    
    # Extract URL from command
    if len(message.command) < 2:
        # Mark user as waiting for URL
        bot_state.user_data[user_id] = {
            'waiting_for_url': True,
            'chat_id': message.chat.id
        }
        await message.reply_text(
            "📎 **Please paste your YouTube video URL:**",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    url = message.command[1]
    
    # Process the URL
    await process_video_url(client, message, url)

@app.on_message(filters.text & filters.private & ~filters.command(["start", "help", "download", "cancel", "status"]))
async def handle_url_message(client: Client, message: Message):
    """Handle URL messages from users"""
    user_id = message.from_user.id
    
    # Check if user is waiting for URL
    if user_id not in bot_state.user_data or not bot_state.user_data[user_id].get('waiting_for_url'):
        return
    
    url = message.text.strip()
    
    # Validate URL
    if not is_valid_youtube_url(url):
        await message.reply_text(
            "❌ Invalid YouTube URL. Please send a valid YouTube video link."
        )
        return
    
    # Process the URL
    await process_video_url(client, message, url)

async def process_video_url(client: Client, message: Message, url: str):
    """Process YouTube video URL and show resolution options"""
    user_id = message.from_user.id
    
    # Check if user already has an active download
    if user_id in bot_state.active_downloads:
        await message.reply_text(
            "⚠️ You already have an active download. "
            "Please wait for it to complete or use /cancel."
        )
        return
    
    # Initialize user data
    bot_state.user_data[user_id] = {
        'url': url,
        'chat_id': message.chat.id,
        'status_message_id': None,
        'status_message': None,
        'temp_files': [],
        'start_time': datetime.now(),
        'waiting_for_url': False
    }
    
    try:
        # Get video info
        status_msg = await message.reply_text("📡 Fetching video information...")
        bot_state.user_data[user_id]['status_message_id'] = status_msg.id
        bot_state.user_data[user_id]['status_message'] = status_msg
        
        # Get available resolutions
        formats = await bot_state.downloader.get_available_resolutions(url)
        
        if not formats:
            await status_msg.edit_text("❌ No compatible formats found.")
            await bot_state.cleanup_user(user_id)
            return
        
        # Create resolution buttons (2 buttons per row for better layout)
        keyboard = []
        current_row = []
        
        for i, format_info in enumerate(formats, 1):
            resolution = format_info.get('resolution', 'Unknown')
            size = format_info.get('size', 'Unknown')
            
            # Extract just the resolution quality (e.g., "1920x1080" -> "1080p")
            if 'x' in resolution:
                height = resolution.split('x')[-1]
                text = f"{height}p {size}"
            else:
                text = f"{resolution} {size}"
            
            callback_data = f"format_{user_id}_{format_info['format_id']}"
            
            current_row.append(InlineKeyboardButton(text, callback_data=callback_data))
            
            # Add 2 buttons per row
            if len(current_row) >= 2 or i == len(formats):
                keyboard.append(current_row)
                current_row = []
        
        # Add cancel and channel link buttons
        keyboard.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")])
        keyboard.append([InlineKeyboardButton("📺 Visit Our Channel", url="https://youtube.com/@animarvelx")])
        
        # Send video info with buttons and thumbnail
        info_text = f"**📹 Title:** {formats[0]['title']}\n"
        info_text += f"**⏱ Duration:** {formats[0]['duration']}\n"
        info_text += f"**👤 Channel:** {formats[0]['channel']}\n\n"
        info_text += "**Select resolution:**"
        
        if formats[0].get('thumbnail'):
            try:
                # Delete text message and send thumbnail with caption
                await status_msg.delete()
                status_msg = await client.send_photo(
                    chat_id=message.chat.id,
                    photo=formats[0]['thumbnail'],
                    caption=info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN
                )
                bot_state.user_data[user_id]['status_message_id'] = status_msg.id
                bot_state.user_data[user_id]['status_message'] = status_msg
                bot_state.user_data[user_id]['thumbnail_url'] = formats[0]['thumbnail']
            except Exception as thumb_error:
                # If thumbnail fails, send text message instead
                logger.warning(f"Failed to send thumbnail: {thumb_error}")
                status_msg = await message.reply_text(
                    info_text,
                    reply_markup=InlineKeyboardMarkup(keyboard),
                    parse_mode=ParseMode.MARKDOWN,
                    disable_web_page_preview=True
                )
                bot_state.user_data[user_id]['status_message_id'] = status_msg.id
                bot_state.user_data[user_id]['status_message'] = status_msg
        else:
            await status_msg.edit_text(
                info_text,
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode=ParseMode.MARKDOWN,
                disable_web_page_preview=True
            )
            bot_state.user_data[user_id]['status_message'] = status_msg
        
        logger.info(f"Sent {len(formats)} resolution options to user {user_id}")
        
    except Exception as e:
        logger.error(f"Error fetching video info: {e}")
        await message.reply_text(f"❌ Error: {str(e)}")
        await bot_state.cleanup_user(user_id)

@app.on_callback_query()
async def handle_callback(client: Client, callback_query: CallbackQuery):
    """Handle inline button callbacks"""
    user_id = callback_query.from_user.id
    
    # Check if bot is shutting down
    if bot_state.shutting_down:
        await callback_query.answer("Bot is shutting down", show_alert=True)
        return
    
    data = callback_query.data
    
    if data.startswith("format_"):
        try:
            _, callback_user_id, format_id = data.split("_", 2)
            callback_user_id = int(callback_user_id)
            
            # Verify user owns this callback
            if user_id != callback_user_id:
                await callback_query.answer("This is not your download!", show_alert=True)
                return
            
            await callback_query.answer("Starting download...")
            
            # Get user data
            user_data = bot_state.user_data.get(callback_user_id)
            if not user_data:
                await callback_query.answer("Session expired", show_alert=True)
                return
            
            # Get format info for display
            formats = await bot_state.downloader.get_available_resolutions(user_data['url'])
            format_info = next((f for f in formats if f['format_id'] == format_id), None)
            
            if not format_info:
                try:
                    await callback_query.message.edit_caption("❌ Selected format no longer available.")
                except:
                    await callback_query.message.edit_text("❌ Selected format no longer available.")
                await bot_state.cleanup_user(callback_user_id)
                return
            
            # Start download task
            task = asyncio.create_task(
                download_and_send_video(client, callback_user_id, format_id, format_info, callback_query.message)
            )
            bot_state.active_downloads[user_id] = task
            
        except Exception as e:
            logger.error(f"Callback error: {e}")
            await callback_query.answer("Error starting download", show_alert=True)
    
    elif data.startswith("cancel_"):
        try:
            _, callback_user_id = data.split("_")
            callback_user_id = int(callback_user_id)
            
            if user_id != callback_user_id:
                await callback_query.answer("This is not your download!", show_alert=True)
                return
            
            await callback_query.answer("Cancelling...")
            await bot_state.cleanup_user(callback_user_id)
            
            try:
                await callback_query.message.edit_caption("✅ Download cancelled.")
            except:
                try:
                    await callback_query.message.edit_text("✅ Download cancelled.")
                except:
                    await callback_query.message.delete()
                    await client.send_message(callback_query.message.chat.id, "✅ Download cancelled.")
            
        except Exception as e:
            logger.error(f"Cancel error: {e}")

async def download_and_send_video(client: Client, user_id: int, format_id: str, format_info: Dict, status_msg):
    """Download and send video to user"""
    user_data = bot_state.user_data.get(user_id)
    if not user_data:
        return
    
    chat_id = user_data['chat_id']
    url = user_data['url']
    thumbnail_url = user_data.get('thumbnail_url')
    
    # Create buttons with cancel and channel link
    def create_buttons(show_cancel=True):
        buttons = []
        if show_cancel:
            buttons.append([InlineKeyboardButton("❌ Cancel", callback_data=f"cancel_{user_id}")])
        buttons.append([InlineKeyboardButton("📺 Visit Our Channel", url="https://youtube.com/@animarvelx")])
        return InlineKeyboardMarkup(buttons)
    
    try:
        last_progress_time = datetime.now()
        last_progress_percent = 0
        is_downloading = True
        
        resolution = format_info.get('resolution', 'selected resolution')
        title = format_info.get('title', 'Video')
        
        # Extract quality (e.g., "1920x1080" -> "1080p")
        if 'x' in resolution:
            height = resolution.split('x')[-1]
            quality = f"{height}p"
        else:
            quality = resolution
        
        def download_progress_callback(percent: float):
            nonlocal last_progress_time, last_progress_percent, is_downloading
            
            if not is_downloading:
                return
            
            # Only update every 3 seconds or if progress changed significantly
            now = datetime.now()
            time_diff = (now - last_progress_time).total_seconds()
            
            if time_diff >= 3 or abs(percent - last_progress_percent) >= 5:
                progress_bar = "█" * int(percent / 5) + "░" * (20 - int(percent / 5))
                caption_text = f"**{title}**\n\n⏬ **Downloading {quality}**\n{progress_bar} {percent:.1f}%"
                
                async def update_message():
                    try:
                        if thumbnail_url:
                            await status_msg.edit_caption(
                                caption=caption_text,
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=create_buttons(show_cancel=True)
                            )
                        else:
                            await status_msg.edit_text(
                                caption_text,
                                parse_mode=ParseMode.MARKDOWN,
                                reply_markup=create_buttons(show_cancel=True)
                            )
                    except Exception as e:
                        logger.debug(f"Progress update failed: {e}")
                
                # Schedule the coroutine in the event loop
                asyncio.create_task(update_message())
                last_progress_time = now
                last_progress_percent = percent
        
        # Initial download message
        initial_caption = f"**{title}**\n\n⏬ **Starting download {quality}**\n░░░░░░░░░░░░░░░░░░░░ 0.0%"
        try:
            if thumbnail_url:
                await status_msg.edit_caption(
                    caption=initial_caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=create_buttons(show_cancel=True)
                )
            else:
                await status_msg.edit_text(
                    initial_caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=create_buttons(show_cancel=True)
                )
        except Exception as e:
            logger.warning(f"Failed to update initial message: {e}")
        
        # Download video
        download_path = await bot_state.downloader.download_video(
            url, 
            format_id, 
            user_id,
            progress_callback=download_progress_callback
        )
        
        is_downloading = False
        
        if not download_path or not os.path.exists(download_path):
            error_msg = f"**{title}**\n\n❌ Download failed."
            try:
                if thumbnail_url:
                    await status_msg.edit_caption(
                        caption=error_msg,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=create_buttons(show_cancel=False)
                    )
                else:
                    await status_msg.edit_text(
                        error_msg,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=create_buttons(show_cancel=False)
                    )
            except:
                pass
            return
        
        user_data['temp_files'].append(download_path)
        
        # Check file size
        file_size = os.path.getsize(download_path)
        if file_size > config.MAX_FILE_SIZE:
            error_msg = f"**{title}**\n\n❌ File size ({format_size(file_size)}) exceeds 850MB limit."
            try:
                if thumbnail_url:
                    await status_msg.edit_caption(
                        caption=error_msg,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=create_buttons(show_cancel=False)
                    )
                else:
                    await status_msg.edit_text(
                        error_msg,
                        parse_mode=ParseMode.MARKDOWN,
                        reply_markup=create_buttons(show_cancel=False)
                    )
            except:
                pass
            return
        
        # Get video info for caption
        duration = format_info.get('duration', '')
        channel = format_info.get('channel', '')
        
        # Reset progress tracking for upload
        last_progress_time = datetime.now()
        last_progress_percent = 0
        
        async def upload_progress_callback(current: int, total: int):
            nonlocal last_progress_time, last_progress_percent
            
            if total == 0:
                return
            
            percent = (current / total) * 100
            
            # Only update every 3 seconds or if progress changed significantly
            now = datetime.now()
            time_diff = (now - last_progress_time).total_seconds()
            
            if time_diff >= 3 or abs(percent - last_progress_percent) >= 5:
                progress_bar = "█" * int(percent / 5) + "░" * (20 - int(percent / 5))
                upload_caption = f"**{title}**\n\n📤 **Uploading to Telegram**\n{progress_bar} {percent:.1f}%"
                
                try:
                    if thumbnail_url:
                        await status_msg.edit_caption(
                            caption=upload_caption,
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=create_buttons(show_cancel=True)
                        )
                    else:
                        await status_msg.edit_text(
                            upload_caption,
                            parse_mode=ParseMode.MARKDOWN,
                            reply_markup=create_buttons(show_cancel=True)
                        )
                    last_progress_time = now
                    last_progress_percent = percent
                except Exception as e:
                    logger.debug(f"Upload progress update failed: {e}")
        
        # Initial upload message
        upload_caption = f"**{title}**\n\n📤 **Uploading to Telegram**\n░░░░░░░░░░░░░░░░░░░░ 0.0%"
        try:
            if thumbnail_url:
                await status_msg.edit_caption(
                    caption=upload_caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=create_buttons(show_cancel=True)
                )
            else:
                await status_msg.edit_text(
                    upload_caption,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=create_buttons(show_cancel=True)
                )
        except Exception as e:
            logger.debug(f"Upload status update failed: {e}")
        
        # Prepare final caption
        final_caption = f"**{title}**\n"
        if quality:
            final_caption += f"📺 {quality}\n"
        if duration:
            final_caption += f"⏱ {duration}\n"
        if channel:
            final_caption += f"👤 {channel}\n"
        final_caption += f"📦 {format_size(file_size)}\n\n✅ Downloaded via @{client.me.username}"
        
        # Split caption if too long
        if len(final_caption) > config.MAX_MESSAGE_LENGTH:
            final_caption = final_caption[:config.MAX_MESSAGE_LENGTH - 100] + "..."
        
        # Send video with upload progress
        try:
            sent_video = await client.send_video(
                chat_id=chat_id,
                video=download_path,
                caption=final_caption,
                parse_mode=ParseMode.MARKDOWN,
                supports_streaming=True,
                progress=upload_progress_callback,
                reply_markup=create_buttons(show_cancel=False)
            )
            
            # Delete the thumbnail message after successful upload
            try:
                await status_msg.delete()
            except:
                pass
            
        except Exception as upload_error:
            logger.error(f"Upload error: {upload_error}")
            
            # Try without streaming if streaming fails
            try:
                sent_video = await client.send_video(
                    chat_id=chat_id,
                    video=download_path,
                    caption=final_caption,
                    parse_mode=ParseMode.MARKDOWN,
                    supports_streaming=False,
                    progress=upload_progress_callback,
                    reply_markup=create_buttons(show_cancel=False)
                )
                
                # Delete the thumbnail message after successful upload
                try:
                    await status_msg.delete()
                except:
                    pass
                    
            except Exception as e:
                # Delete thumbnail message even on error
                try:
                    await status_msg.delete()
                except:
                    pass
                    
                await client.send_message(
                    chat_id,
                    f"❌ Upload failed: {str(e)}",
                    reply_markup=create_buttons(show_cancel=False)
                )
        
    except asyncio.CancelledError:
        try:
            if thumbnail_url:
                await status_msg.edit_caption("❌ Download cancelled.")
            else:
                await status_msg.edit_text("❌ Download cancelled.")
        except:
            await client.send_message(chat_id, "❌ Download cancelled.")
    except Exception as e:
        logger.error(f"Error in download process: {e}")
        try:
            if thumbnail_url:
                await status_msg.edit_caption(f"❌ Error: {str(e)}")
            else:
                await status_msg.edit_text(f"❌ Error: {str(e)}")
        except:
            await client.send_message(chat_id, f"❌ Error: {str(e)}")
    finally:
        # Cleanup
        await bot_state.cleanup_user(user_id)
        cleanup_temp_files(user_data.get('temp_files', []))

@app.on_message(filters.command("cancel") & filters.private)
async def cancel_command(client: Client, message: Message):
    """Handle cancel command"""
    user_id = message.from_user.id
    
    if user_id not in bot_state.active_downloads:
        await message.reply_text("No active download to cancel.")
        return
    
    await bot_state.cleanup_user(user_id)
    await message.reply_text("✅ Download cancelled.")

@app.on_message(filters.command("status") & filters.private)
async def status_command(client: Client, message: Message):
    """Handle status command"""
    user_id = message.from_user.id
    
    if bot_state.shutting_down:
        await message.reply_text("⚠️ Bot is shutting down.")
    elif user_id in bot_state.active_downloads:
        task = bot_state.active_downloads[user_id]
        if task.done():
            await message.reply_text("✅ Download completed.")
        else:
            await message.reply_text("⏳ Download in progress...")
    else:
        await message.reply_text("No active downloads.")

# --------------------------------------------------------------------------
# MAIN EXECUTION
# --------------------------------------------------------------------------

async def main():
    """Main function"""
    # Ensure temp directory exists
    os.makedirs(config.TEMP_DIR, exist_ok=True)
    
    # Cleanup old temp files on startup
    cleanup_temp_files()
    
    logger.info("Starting YouTube Downloader Bot...")
    
    # Start Web Server FIRST
    logger.info("Starting web server...")
    try:
        runner = await start_web_server()
        logger.info("✅ Web server started successfully")
    except Exception as e:
        logger.error(f"❌ Failed to start web server: {e}")
        return
    
    # Start Bot
    try:
        await app.start()
        
        me = await app.get_me()
        logger.info(f"✅ Bot started successfully!")
        logger.info(f"   Name: {me.first_name}")
        logger.info(f"   Username: @{me.username}")
        logger.info(f"   ID: {me.id}")
        logger.info(f"   Health check: http://localhost:{config.HEALTH_PORT}/health")
        logger.info("Bot is now listening for messages. Send /start to your bot")
        
        # Keep bot running forever
        await asyncio.Event().wait()
        
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received, shutting down...")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        # Clean shutdown
        await shutdown_handler()
        if app.is_connected:
            await app.stop()
        
        # Cleanup web server
        if 'runner' in locals():
            await runner.cleanup()

if __name__ == "__main__":
    # Validate credentials
    if not config.API_ID or not config.API_HASH or not config.BOT_TOKEN:
        print("❌ Missing credentials in .env file")
        sys.exit(1)
    
    logger.info(f"Config loaded:")
    logger.info(f"  API_ID: {config.API_ID}")
    logger.info(f"  API_HASH: {config.API_HASH[:10]}...")
    logger.info(f"  BOT_TOKEN: {config.BOT_TOKEN[:20]}...")
    
    # Get the event loop and run main
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)