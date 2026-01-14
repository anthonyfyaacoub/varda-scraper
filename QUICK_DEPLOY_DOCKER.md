# 🚀 Quick Deploy - Railway.app (3 minutes)

**Easiest way to deploy with full Playwright support!**

## Step 1: Sign Up

1. Go to: **https://railway.app**
2. Click **"Start a New Project"**
3. Sign up with GitHub (free)

## Step 2: Deploy

1. Click **"Deploy from GitHub repo"**
2. Select your repository: **`varda-scraper`**
3. Railway automatically detects the Dockerfile - no configuration needed!

## Step 3: Add API Key

1. Click on your service
2. Go to **"Variables"** tab
3. Click **"New Variable"**
4. Add these:

```
OPENAI_API_KEY = your_actual_api_key_here
HEADLESS_MODE = true
ACCESS_PASSWORD = your_password_here
```

5. Click **"Add"**

## Step 4: Done! 🎉

Railway automatically:
- ✅ Builds your Docker image
- ✅ Installs Playwright browsers
- ✅ Deploys your app
- ✅ Provides HTTPS URL

Your app will be live at:
```
https://YOUR_APP.railway.app
```

**First build takes 3-5 minutes** (installing Playwright browsers).  
**Subsequent deployments are faster** (1-2 minutes).

---

## Why Railway?

- ✅ **Zero configuration** - Just connect GitHub
- ✅ **Automatic HTTPS** - No setup needed
- ✅ **Auto-deploy** - Deploys on every git push
- ✅ **Full Playwright support** - Docker handles everything
- ✅ **Free tier** - $5 credit/month

---

## Troubleshooting

**Build taking too long?**
- First build installs Playwright browsers (3-5 min)
- This is normal!

**App not starting?**
- Check logs in Railway dashboard
- Verify environment variables are set

**Need help?** See [DEPLOY_DOCKER.md](DEPLOY_DOCKER.md) for detailed guide.
