# 🚀 Quick Setup Guide - Get Running in 5 Minutes

## Step 1: Push Code to GitHub

Open PowerShell/Terminal in your project folder and run:

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit"

# Create a new repository on GitHub.com first, then:
git remote add origin https://github.com/YOUR_USERNAME/varda-scraper.git
git branch -M main
git push -u origin main
```

**Don't have a GitHub account?** 
- Go to https://github.com and sign up (free)
- Click "New repository"
- Name it `varda-scraper`
- Don't initialize with README
- Copy the repository URL

---

## Step 2: Deploy to Streamlit Cloud

1. Go to: **https://share.streamlit.io/**
2. Click **"Sign in"** (use your GitHub account)
3. Click **"New app"**
4. Fill in:
   - **Repository:** Select `varda-scraper`
   - **Branch:** `main`
   - **Main file path:** `dashboard.py`
5. Click **"Deploy"**

---

## Step 3: Add Your API Key & Password

1. In Streamlit Cloud, click **"Settings"** (⚙️ icon)
2. Go to **"Secrets"** tab
3. Paste this (replace with your actual values):

```toml
OPENAI_API_KEY = "sk-proj-your-actual-api-key-here"
HEADLESS_MODE = "true"
ACCESS_PASSWORD = "your-secure-password-here"
```

**Where to get your OpenAI API key?**
- Go to: https://platform.openai.com/api-keys
- Click "Create new secret key"
- Copy it and paste above

**Password:** Choose any password you want (users will need this to access the dashboard)

4. Click **"Save"**

---

## Step 4: Wait for Deployment

- Streamlit will automatically install everything (takes 2-3 minutes)
- You'll see "Your app is live!" when ready
- Your app URL will be: `https://YOUR_APP_NAME.streamlit.app`

---

## Step 5: Test It!

1. Open your app URL
2. Enter the password you set
3. Configure zip codes and categories
4. Click "Start Scraping"
5. Watch it work! 🎉

---

## That's It! ✅

Your scraper is now running 24/7 in the cloud. You can:
- Access it from any device
- Share it with your team (give them the password)
- Close your laptop - it keeps running!

---

## Troubleshooting

**"App won't start"**
- Check that `OPENAI_API_KEY` is set correctly in Secrets
- Make sure there are no typos

**"Can't push to GitHub"**
- Make sure you created the repository on GitHub first
- Check that the repository URL is correct

**"Password not working"**
- Make sure `ACCESS_PASSWORD` is set in Secrets
- Try refreshing the page

**Need help?** Check `DEPLOYMENT.md` for more detailed instructions.
