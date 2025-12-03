# YouTube Telegram Downloader Bot

A powerful Telegram bot for downloading YouTube videos with progress tracking and quality selection.

## Features

- 🎬 Download YouTube videos up to 850MB
- 📊 Real-time download and upload progress
- 🎯 Multiple quality options (1080p, 720p, 480p, etc.)
- 🖼️ Thumbnail preview during download
- ⚡ Fast H.264/AAC format without re-encoding
- 📺 Channel promotion button
- ❌ Cancel option at every step

## Deployment on Koyeb

### Prerequisites

1. **Telegram Bot Token**: Get from [@BotFather](https://t.me/botfather)
2. **Telegram API Credentials**: Get from [my.telegram.org](https://my.telegram.org)
3. **Koyeb Account**: Sign up at [koyeb.com](https://www.koyeb.com)

### Step-by-Step Deployment

#### 1. Push to GitHub

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/yourusername/youtube-telegram-bot.git
git push -u origin main
```

#### 2. Deploy on Koyeb

1. **Create New App**
   - Go to [Koyeb Dashboard](https://app.koyeb.com)
   - Click "Create App"
   - Select "GitHub" as deployment method

2. **Configure GitHub Repository**
   - Connect your GitHub account
   - Select your repository
   - Branch: `main`
   - Build type: Dockerfile

3. **Set Environment Variables**
   Add these secrets in Koyeb:
   ```
   API_ID=your_telegram_api_id
   API_HASH=your_telegram_api_hash
   BOT_TOKEN=your_bot_token_from_botfather
   PORT=8080
   ```

4. **Configure Service**
   - Name: `youtube-bot` (or your choice)
   - Region: Choose closest to your users
   - Instance type: Free tier (or higher for better performance)
   - Port: `8080`
   - Health check path: `/health`

5. **Deploy**
   - Click "Deploy"
   - Wait for build and deployment (3-5 minutes)
   - Check health status in dashboard

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `API_ID` | Telegram API ID from my.telegram.org | Yes |
| `API_HASH` | Telegram API Hash from my.telegram.org | Yes |
| `BOT_TOKEN` | Bot token from @BotFather | Yes |
| `PORT` | Port for health check server (default: 8080) | No |

### Health Check

The bot includes a health check endpoint at `/health` that returns:
- Status 200: Bot is running
- Status 503: Bot is shutting down
- Status 500: Error occurred

### Docker Compose (Local Testing)

```bash
# Create .env file with credentials
cp .env.example .env
# Edit .env with your credentials

# Build and run
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down
```

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file
cp .env.example .env
# Add your credentials to .env

# Run bot
python bot.py
```

## Usage

1. Start the bot: `/start`
2. Paste YouTube video URL
3. Select quality/resolution
4. Wait for download and upload
5. Receive video file

**Commands:**
- `/start` or `/help` - Show welcome message
- `/download` - Start download (or just paste URL)
- `/cancel` - Cancel current download
- `/status` - Check download status

## Technical Details

- **Framework**: Pyrogram (Telegram MTProto API)
- **Downloader**: yt-dlp
- **Video Processing**: FFmpeg (copy codec, no re-encoding)
- **Format**: MP4 with H.264 video and AAC audio
- **Max File Size**: 850MB (Telegram limit: 2GB)
- **Progress Updates**: Every 3 seconds or 5% change

## File Structure

```
.
├── bot.py              # Main bot application
├── config.py           # Configuration and settings
├── utils/
│   ├── downloader.py   # YouTube download logic
│   ├── helpers.py      # Helper functions
│   └── __init__.py
├── requirements.txt    # Python dependencies
├── Dockerfile          # Docker container config
├── docker-compose.yml  # Docker Compose config
└── .dockerignore       # Docker ignore patterns
```

## Troubleshooting

### Bot not responding
- Check Koyeb logs for errors
- Verify environment variables are set correctly
- Check bot token is valid with @BotFather

### Download fails
- Video might be too large (>850MB)
- Video might be age-restricted or private
- yt-dlp might need update (redeploy)

### Health check failing
- Ensure PORT is set to 8080
- Check if bot started successfully in logs
- Verify firewall/network settings

## Performance

- **Free Tier**: Suitable for personal use (5-10 users)
- **Paid Tier**: Recommended for public bots (100+ users)
- **Memory**: ~200-300MB base, +100-200MB per active download
- **Storage**: Temporary files cleaned automatically

## Security

- ✅ Non-root user in container
- ✅ Environment variables for secrets
- ✅ Temporary file cleanup
- ✅ Session files persisted
- ✅ Graceful shutdown handling

## License

MIT License - Feel free to modify and use

## Support

For issues and questions:
- Open GitHub issue
- Contact: [@animarvelx](https://youtube.com/@animarvelx)

## Credits

- [Pyrogram](https://github.com/pyrogram/pyrogram) - Telegram MTProto API
- [yt-dlp](https://github.com/yt-dlp/yt-dlp) - YouTube downloader
- [FFmpeg](https://ffmpeg.org/) - Video processing

---

**Note**: Respect YouTube's Terms of Service and copyright laws. This bot is for educational purposes.
