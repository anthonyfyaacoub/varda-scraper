# 🚀 START HERE - VARDA Scraper

## For You (Local Use)

1. **Run setup:**
   ```bash
   python setup.py
   ```

2. **Start dashboard:**
   ```bash
   streamlit run dashboard.py
   ```
   Or double-click `run.bat` (Windows) or `run.sh` (Mac/Linux)

3. **Open:** http://localhost:8501

**That's it!** Everything is pre-configured with your zip codes and categories.

---

## For Your Colleague

### Option 1: GitHub (Easiest)

1. **Give them this:**
   ```
   https://github.com/anthonyfyaacoub/varda-scraper
   ```

2. **They run:**
   ```bash
   git clone https://github.com/anthonyfyaacoub/varda-scraper.git
   cd varda-scraper
   python setup.py
   streamlit run dashboard.py
   ```

### Option 2: ZIP File

1. **Zip the folder** (don't include `output/` or `.env`)
2. **Send them the ZIP**
3. **They:**
   - Extract it
   - Run `python setup.py`
   - Create `.env` file with their API key:
     ```
     OPENAI_API_KEY=their_key_here
     HEADLESS_MODE=false
     ```
   - Run `streamlit run dashboard.py`

---

## What's Included

✅ **30 priority zip codes** pre-configured (92, 78, 94, 93, 91)  
✅ **10 priority categories** ready to go  
✅ **Smart filtering** - only processes businesses in your rating range  
✅ **Real-time dashboard** - see everything as it happens  
✅ **CSV export** - download results anytime  

---

## Need Help?

- **Setup issues?** See `README_SIMPLE.md`
- **Detailed docs?** See `README.md`
- **Deployment?** See `DEPLOY_DOCKER.md` (but local is easier!)

---

## Quick Troubleshooting

**"Playwright not found" or installation stuck**

Use the standalone installer:
```bash
python install_browsers.py
```

Or install manually:
```bash
python -m playwright install chromium
```

If stuck, cancel and try:
```bash
pip install --upgrade playwright
python -m playwright install chromium
```

**"Module not found"**
```bash
pip install -r requirements.txt
```

**"API key error"**
Create `.env` file with your OpenAI API key

---

**Ready to go!** Just run `python setup.py` then `streamlit run dashboard.py` 🎉
