# 🛡️ VARDA Lead Generation Scraper - Simple Setup

**Easy-to-use scraper that finds businesses with Google review violations.**

## 🚀 Quick Start (5 minutes)

### Step 1: Clone or Download

```bash
git clone https://github.com/anthonyfyaacoub/varda-scraper.git
cd varda-scraper
```

Or download ZIP and extract it.

### Step 2: Run Setup Script

**Windows:**
```bash
python setup.py
```

**Mac/Linux:**
```bash
python3 setup.py
```

The script will:
- ✅ Install all Python dependencies
- ✅ Install Playwright browsers
- ✅ Create .env file (asks for your API key)
- ✅ Set up everything automatically

### Step 3: Run the Dashboard

**Windows:**
```bash
run.bat
```

**Mac/Linux:**
```bash
chmod +x run.sh
./run.sh
```

Or manually:
```bash
streamlit run dashboard.py
```

### Step 4: Open Browser

Go to: **http://localhost:8501**

---

## 📋 Manual Setup (If Script Doesn't Work)

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install Playwright Browsers

```bash
playwright install chromium
```

**Linux users may also need:**
```bash
playwright install-deps chromium
```

### 3. Create .env File

Create a file named `.env` in the project folder:

```
OPENAI_API_KEY=your_api_key_here
HEADLESS_MODE=false
```

### 4. Run Dashboard

```bash
streamlit run dashboard.py
```

---

## 👥 Sharing with Colleagues

### Option 1: Share GitHub Repository (Easiest)

1. **Make sure your code is pushed to GitHub**
2. **Give them the repository URL**
3. **They run:**
   ```bash
   git clone https://github.com/anthonyfyaacoub/varda-scraper.git
   cd varda-scraper
   python setup.py
   streamlit run dashboard.py
   ```

### Option 2: Share ZIP File

1. **Zip the entire folder** (except `output/` and `.env`)
2. **Send them the ZIP**
3. **They:**
   - Extract ZIP
   - Run `python setup.py`
   - Create `.env` with their API key
   - Run `streamlit run dashboard.py`

### Option 3: Docker (Advanced)

If they have Docker installed:

```bash
docker-compose up
```

---

## ⚙️ Configuration

### API Key

Get your OpenAI API key from: https://platform.openai.com/api-keys

Add it to `.env`:
```
OPENAI_API_KEY=sk-proj-your-key-here
```

### Default Settings

The scraper is pre-configured with:
- **Zip codes:** 30 priority zip codes in France (92, 78, 94, 93, 91)
- **Categories:** 10 priority categories (restaurants, pharmacies, car repair, etc.)
- **Rating filter:** 1.0 - 4.0 stars
- **Min reviews:** 10

You can change these in the dashboard!

---

## 🎯 How to Use

1. **Start the dashboard:** `streamlit run dashboard.py`
2. **Open:** http://localhost:8501
3. **Configure:**
   - Select zip codes (or use defaults)
   - Select categories
   - Set filters (rating, reviews)
4. **Click "Start Scraping"**
5. **Watch results appear in real-time**
6. **Download CSV when done**

---

## 📁 Output Files

Results are saved to `output/` folder:
- `violations_leads_[zip_code]_[timestamp].csv` - Main results
- `violations_details_[timestamp].json` - Detailed data

---

## 🐛 Troubleshooting

### "Playwright browsers not found" or installation stuck

**Option 1: Use the standalone installer**
```bash
python install_browsers.py
```

**Option 2: Install manually**
```bash
python -m playwright install chromium
```

**Option 3: If stuck, cancel and try:**
```bash
pip install --upgrade playwright
python -m playwright install chromium
```

**Windows users:** Try running PowerShell/CMD as Administrator

### Can't delete Playwright browser folder (chromium-1200)

If you can't delete the folder manually:

**Option 1: Use the cleanup script (Recommended)**
1. Right-click `cleanup_playwright.bat` → Run as Administrator
2. It will kill processes, take ownership, and delete the folder

**Option 2: Use PowerShell script**
1. Right-click PowerShell → Run as Administrator
2. Run: `.\delete_chromium.ps1`

**Option 3: Manual PowerShell commands**
```powershell
# Run PowerShell as Administrator, then:
taskkill /F /IM chrome.exe /T
$path = "$env:LOCALAPPDATA\ms-playwright\chromium-1200"
takeown /F $path /R /D Y
icacls $path /grant "${env:USERNAME}:F" /T
Remove-Item $path -Recurse -Force
```

**Option 4: Restart computer**
Sometimes files are locked by Windows. Restart and try deleting again.

### "Module not found"

```bash
pip install -r requirements.txt
```

### "OpenAI API key error"

Make sure `.env` file exists with:
```
OPENAI_API_KEY=your_key_here
```

### Port already in use

Change port:
```bash
streamlit run dashboard.py --server.port=8502
```

---

## 📞 Need Help?

- Check `README.md` for detailed documentation
- Check logs in the dashboard
- Make sure all dependencies are installed

---

## ✅ That's It!

You're ready to scrape! Just run `streamlit run dashboard.py` and start finding leads.
