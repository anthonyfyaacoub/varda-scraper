# 🛡️ VARDA Lead Generation Scraper

A web scraping tool that finds businesses with Google review violations, perfect for lead generation.

## 🚀 Quick Start (Local Use)

**Want to run it locally?** See [README_SIMPLE.md](README_SIMPLE.md) for the easiest setup!

**For colleagues:** Just share the GitHub repo and they run `python setup.py` → `streamlit run dashboard.py`

## Features

- 🗺️ **Zip code-based scraping** - Search by zip codes (e.g., "92100", "92200") for accurate results
- 📊 **Real-time dashboard** - Watch results as they come in with live updates
- 📥 **CSV export** - Download results anytime
- 🤖 **AI-powered classification** - Automatically identifies review violations
- ☁️ **Cloud deployment ready** - Run 24/7 even when your laptop is off

## Setup

1. Install dependencies:
```bash
pip install -r requirements.txt
playwright install chromium
```

2. Configure your OpenAI API key:

**Option A: Environment variable (Recommended for cloud deployment)**
```bash
# Windows PowerShell
$env:OPENAI_API_KEY="your-api-key-here"

# Linux/Mac
export OPENAI_API_KEY="your-api-key-here"
```

**Option B: Direct in code**
Edit `varda_scraper.py` and set:
```python
OPENAI_API_KEY = "your-api-key-here"
```

## Usage

### Option 1: Dashboard (Recommended)

Run the Streamlit dashboard:
```bash
streamlit run dashboard.py
```

Then:
1. Enter zip codes in the sidebar (one per line, e.g., "92100", "92200")
2. Select categories to scrape
3. Configure filters (rating range, min reviews, etc.)
4. Click "Start Scraping"
5. Watch results appear in real-time
6. Download CSV when ready

### Option 2: Command Line

Edit `varda_scraper.py` and set:
```python
AREAS = ["Paris, France", "Paris suburbs, France"]
```

Then run:
```bash
python varda_scraper.py
```

## ☁️ Cloud Deployment (Run 24/7)

**Want to keep scraping even when your laptop is off?** See [DEPLOYMENT.md](DEPLOYMENT.md) for detailed instructions.

### Quick Options:

1. **Streamlit Cloud (FREE)** - Easiest option
   - Push code to GitHub
   - Deploy in 5 minutes
   - Free hosting with HTTPS
   - **Password protection available** - Control who can access it

2. **Docker** - Full control
   - Deploy to any cloud provider
   - Use provided Dockerfile

3. **VPS/Cloud Server** - Dedicated resources
   - DigitalOcean, AWS, Google Cloud, etc.
   - Full control and customization

### 🔐 Access Control

The dashboard includes **password protection** to control who can use it:

- **Private (Password Protected):** Set `ACCESS_PASSWORD` in environment/secrets
- **Public (No Password):** Don't set `ACCESS_PASSWORD` (⚠️ anyone can use your API credits!)

See [DEPLOYMENT.md](DEPLOYMENT.md) for complete guide with all options and security settings.

## Configuration

Edit these settings in `varda_scraper.py` or use environment variables:

- `OPENAI_API_KEY` - Your OpenAI API key (or set `OPENAI_API_KEY` env var)
- `HEADLESS_MODE` - Set to `"true"` for cloud deployment (or set `HEADLESS_MODE` env var)
- `AREAS` - List of areas to search (deprecated, use zip codes via dashboard)
- `TIERS_TO_SCRAPE` - Business categories (1=restaurants, 2=beauty, 3=services)
- `MIN_RATING` / `MAX_RATING` - Rating filter range
- `MIN_REVIEWS` - Minimum reviews required
- `MAX_REVIEWS_PER_BUSINESS` - Max reviews to analyze per business
- `MIN_VIOLATIONS_TO_STOP` - Stop analyzing after finding this many violations

## Output

Results are saved to:
- `output/violations_leads_[zip_code]_[timestamp].csv` - Main CSV file
- `output/violations_details_[timestamp].json` - Detailed JSON with all data
