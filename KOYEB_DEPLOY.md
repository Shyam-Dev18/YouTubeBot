# Quick Koyeb Deployment Guide

## 🚀 Deploy in 5 Minutes

### 1. Prepare Repository
```bash
# Initialize git (if not already)
git init
git add .
git commit -m "Ready for Koyeb deployment"

# Push to GitHub
git remote add origin https://github.com/YOUR_USERNAME/YOUR_REPO.git
git branch -M main
git push -u origin main
```

### 2. Deploy on Koyeb

1. **Go to Koyeb**: https://app.koyeb.com
2. **Create App** → **Deploy from GitHub**
3. **Select Repository** → Choose your repo
4. **Configure**:
   - Builder: **Dockerfile**
   - Branch: **main**
   - Port: **8080**
   - Health Check: **/health**

### 3. Add Environment Secrets

In Koyeb dashboard, add these secrets:

```
API_ID = YOUR_TELEGRAM_API_ID
API_HASH = YOUR_TELEGRAM_API_HASH
BOT_TOKEN = YOUR_BOT_TOKEN_FROM_BOTFATHER
PORT = 8080
```

**Where to get these?**
- `API_ID` & `API_HASH`: https://my.telegram.org/apps
- `BOT_TOKEN`: Chat with @BotFather on Telegram

### 4. Deploy!

Click **"Deploy"** and wait 3-5 minutes.

### 5. Verify

- Check **Logs** tab for: "✅ Bot started successfully!"
- Check **Health** status: Should be green
- Test bot: Send `/start` to your bot on Telegram

## 📊 Monitoring

- **Health Check**: Your bot URL + `/health`
- **Logs**: Koyeb dashboard → Logs tab
- **Restart**: If needed, click "Redeploy"

## ⚙️ Koyeb Configuration

**Recommended Settings:**
- **Region**: Closest to your users (e.g., Frankfurt for Europe)
- **Instance**: 
  - Free tier: Good for testing/personal use
  - Nano: Good for small groups (<50 users)
  - Small: Good for public bots (100+ users)
- **Scaling**: 
  - Min: 1 instance
  - Max: 1 instance (for session file safety)

## 🔧 Troubleshooting

### Bot not starting?
```bash
# Check logs for:
# ✅ "Web server started successfully"
# ✅ "Bot started successfully!"
```

### Environment variables not working?
- Verify secrets are added in Koyeb (not .env file)
- Check spelling matches exactly: `API_ID`, `API_HASH`, `BOT_TOKEN`
- Redeploy after adding secrets

### Health check failing?
- Ensure PORT is set to 8080
- Check if bot started (see logs)
- Wait 40 seconds after deployment starts

### "Session file" errors?
- Koyeb will create it automatically on first run
- Don't commit `.session` files to git

## 💡 Tips

1. **First deployment** takes longer (4-6 mins) - Docker image build
2. **Subsequent deploys** are faster (2-3 mins) - Cached layers
3. **Keep .env.example** in repo, but never commit actual .env
4. **Monitor logs** during first few test downloads
5. **Session persistence**: Koyeb persistent storage keeps your session

## 🎯 Testing Checklist

- [ ] Bot responds to `/start`
- [ ] Can paste YouTube URL
- [ ] Resolution buttons appear
- [ ] Download progress updates
- [ ] Upload progress updates
- [ ] Video received successfully
- [ ] Cancel button works
- [ ] Channel link button works

## 📈 Scaling

If you get many users:
1. Upgrade Koyeb instance (Nano → Small)
2. Consider adding Redis for queue management
3. Implement rate limiting per user
4. Add download cooldown periods

## 🔒 Security Notes

- ✅ Environment variables stored as Koyeb secrets
- ✅ Container runs as non-root user
- ✅ No sensitive data in logs
- ✅ Session files not exposed
- ✅ Temporary files auto-cleaned

## 📞 Support

- **Koyeb Docs**: https://www.koyeb.com/docs
- **Bot Issues**: Check GitHub Issues
- **Channel**: [@animarvelx](https://youtube.com/@animarvelx)

---

**Ready to deploy?** Push to GitHub and create your Koyeb app! 🚀
