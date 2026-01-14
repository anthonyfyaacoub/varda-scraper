# 🚀 Quick Deploy Guide - Streamlit Cloud (5 minutes)

The **easiest** way to deploy your scraper and keep it running 24/7.

## Step 1: Push to GitHub

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit"

# Create GitHub repo, then:
git remote add origin https://github.com/YOUR_USERNAME/varda-scraper.git
git branch -M main
git push -u origin main
```

## Step 2: Deploy to Streamlit Cloud

1. Go to: https://share.streamlit.io/
2. Click **"New app"**
3. Connect your GitHub account
4. Select repository: `varda-scraper`
5. Branch: `main`
6. Main file path: `dashboard.py`
7. Click **"Deploy"**

## Step 3: Add API Key & Password (Optional)

1. In Streamlit Cloud dashboard, click **"Settings"** (⚙️)
2. Go to **"Secrets"** tab
3. Add this:

```toml
OPENAI_API_KEY = "your_actual_api_key_here"
HEADLESS_MODE = "true"
ACCESS_PASSWORD = "your_password_here"  # Optional: Remove this line for public access
```

**Access Control:**
- **With password:** Only people with the password can use it
- **Without password:** Anyone with the URL can use it (⚠️ they'll use your API credits!)

4. Click **"Save"**

## Step 4: Done! 🎉

Your app is now live at:
```
https://YOUR_APP_NAME.streamlit.app
```

It will run 24/7, even when your laptop is off!

---

## Troubleshooting

**App won't start?**
- Check that `OPENAI_API_KEY` is set in Secrets
- Verify `dashboard.py` is the main file path

**Playwright errors?**
- Streamlit Cloud installs browsers automatically
- If issues persist, check logs in Streamlit Cloud dashboard

**Need more resources?**
- Free tier has limits
- Consider VPS deployment (see DEPLOYMENT.md)

---

For other deployment options (Docker, VPS, Railway, etc.), see [DEPLOYMENT.md](DEPLOYMENT.md)
