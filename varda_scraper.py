"""
VARDA Lead Generation Scraper
Run locally: python varda_scraper.py
"""

import asyncio
import os
import json
import re
import time
from datetime import datetime
from typing import Optional
from playwright.async_api import async_playwright
from openai import OpenAI
import pandas as pd

# Load environment variables from .env file (for local use)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv not installed, use system env vars only

#######################################################################
# 🔑 CONFIGURATION - EDIT THIS SECTION
#######################################################################

# API Key - Load from .env file or environment variable
# For local use: Create .env file with OPENAI_API_KEY=your_key_here
# For cloud: Set OPENAI_API_KEY environment variable
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    print("⚠️  WARNING: OPENAI_API_KEY not found!")
    print("   Create a .env file with: OPENAI_API_KEY=your_key_here")
    print("   Or set environment variable: export OPENAI_API_KEY=your_key_here")
    # Don't raise error immediately - let dashboard handle it gracefully

# Location
AREAS = ["Paris, France"]  # Add more areas like "Paris suburbs, France" or "Madrid, Spain"
# Note: This will be overridden by dashboard if running via Streamlit

# Tiers: [1] = restaurants, [2] = beauty, [3] = services, or combine [1,2,3]
TIERS_TO_SCRAPE = [1]

# Filters
MIN_RATING = 1.0
MAX_RATING = 4.0
MIN_REVIEWS = 10

# Scraping limits
MAX_REVIEWS_PER_BUSINESS = 50
MIN_VIOLATIONS_TO_STOP = 3  # Stop classifying once we find this many violations

# Browser - Auto-detect headless mode based on environment
# Set HEADLESS_MODE=true environment variable to force headless, or HEADLESS_MODE=false to force GUI
# Defaults to True in cloud environments (detected by checking for common cloud env vars)
_is_cloud_env = any(os.getenv(var) for var in ["STREAMLIT_SERVER_PORT", "PORT", "DYNO", "VERCEL", "RAILWAY_ENVIRONMENT"])
HEADLESS = os.getenv("HEADLESS_MODE", str(_is_cloud_env)).lower() == "true"

# Output - Use environment variable or default
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./output")

#######################################################################
# CATEGORIES
#######################################################################

CATEGORIES = {
    # Tier 1 - Restaurants (highest priority)
    1: [
        "restaurant",
        "cafe",
        "bistro",
        "brasserie",
        "pizzeria",
        "fast food",
        "bakery",
        "bar",
    ],
    # Tier 2 - Beauty & Personal Care
    2: [
        "hair salon",
        "nail salon",
        "beauty salon",
        "spa",
        "barbershop",
        "cosmetics",
        "tattoo",
    ],
    # Tier 3 - Services
    3: [
        "car repair",
        "auto repair",
        "mechanic",
        "plumber",
        "electrician",
        "locksmith",
        "dry cleaner",
        "laundry",
        "pharmacy",
        "dentist",
        "veterinarian",
        "pet groomer",
        "gym",
        "fitness",
        "yoga",
        "massage",
        "acupuncture",
        "chiropractor",
        "lawyer",
        "accountant",
        "real estate",
        "moving company",
        "cleaning service",
        "landscaping",
        "roofer",
        "contractor",
    ],
}

# Get all categories as a flat list for easy access
ALL_CATEGORIES = [cat for tier_cats in CATEGORIES.values() for cat in tier_cats]

#######################################################################
# HELPER FUNCTIONS
#######################################################################

def get_openai_client():
    """Lazy initialization of OpenAI client to avoid import errors"""
    if not OPENAI_API_KEY:
        raise ValueError("OPENAI_API_KEY is required!")
    return OpenAI(api_key=OPENAI_API_KEY)

# Lazy client initialization
_client = None

def classify_review(review_text: str, rating: float) -> dict:
    """
    Classify a review to determine if it contains Google review policy violations.
    Returns a dict with 'is_violation', 'confidence', 'violation_types', and 'reasoning'.
    """
    if not review_text or len(review_text.strip()) < 10:
        return {
            "is_violation": False,
            "confidence": 0.0,
            "violation_types": [],
            "reasoning": "Review text too short or empty"
        }
    
    try:
        client = get_openai_client()
        
        prompt = f"""You are an expert at detecting Google review policy violations. Analyze the following review and determine if it violates Google's review policies.

Review Text: "{review_text}"
Rating: {rating}/5

Google's review policies prohibit:
1. Spam and fake content (fake reviews, duplicate reviews, reviews from fake accounts)
2. Off-topic reviews (reviews that don't relate to the business or experience)
3. Restricted content (illegal content, dangerous content, sexually explicit content, offensive content, hate speech)
4. Conflict of interest (reviews by competitors, reviews by employees/owners, reviews incentivized by discounts)
5. Impersonation (pretending to be someone else)

Analyze this review and respond ONLY with valid JSON in this exact format:
{{
    "is_violation": true/false,
    "confidence": 0.0-1.0,
    "violation_types": ["type1", "type2"] or [],
    "reasoning": "Brief explanation of why this is or isn't a violation"
}}

Be strict but fair. Only flag clear violations. If unsure, set is_violation to false and lower confidence."""

        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are an expert at detecting Google review policy violations. Always respond with valid JSON only."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=300
        )
        
        result_text = response.choices[0].message.content.strip()
        
        # Try to extract JSON from response
        json_match = re.search(r'\{[^}]+\}', result_text, re.DOTALL)
        if json_match:
            result = json.loads(json_match.group())
        else:
            # Fallback: try parsing the whole response
            result = json.loads(result_text)
        
        # Validate result structure
        if not isinstance(result, dict):
            raise ValueError("Invalid response format")
        
        return {
            "is_violation": result.get("is_violation", False),
            "confidence": float(result.get("confidence", 0.0)),
            "violation_types": result.get("violation_types", []),
            "reasoning": result.get("reasoning", "No reasoning provided")
        }
        
    except Exception as e:
        # If classification fails, default to not a violation
        print(f"      Warning: Classification error for review: {str(e)[:100]}")
        return {
            "is_violation": False,
            "confidence": 0.0,
            "violation_types": [],
            "reasoning": f"Classification error: {str(e)[:100]}"
        }


async def scrape_business_details(page, business_url: str) -> dict:
    """Scrape detailed information from a business page"""
    try:
        await page.goto(business_url, wait_until="networkidle", timeout=30000)
        await asyncio.sleep(2)  # Give page time to load
        
        details = {
            "website": "",
            "phone": "",
            "email": "",
            "rating": 0.0,
            "review_count": 0
        }
        
        # Get rating and review count
        try:
            rating_elem = page.locator('div.F7nice span[aria-hidden="true"]').first
            if await rating_elem.is_visible(timeout=2000):
                rating_text = await rating_elem.text_content() or ""
                rating_match = re.search(r'(\d[,\.]\d)', rating_text)
                if rating_match:
                    details["rating"] = float(rating_match.group(1).replace(",", "."))
        except:
            pass
        
        try:
            review_count_elem = page.locator('div.F7nice button[aria-label*="review"]').first
            if await review_count_elem.is_visible(timeout=2000):
                review_text = await review_count_elem.get_attribute("aria-label") or ""
                review_match = re.search(r'([\d,\.]+)', review_text)
                if review_match:
                    num_str = review_match.group(1).replace(",", "").replace(".", "")
                    details["review_count"] = int(num_str) if num_str.isdigit() else 0
        except:
            pass
        
        # Get website
        try:
            website_button = page.locator('a[data-item-id="authority"]').first
            if await website_button.is_visible(timeout=3000):
                details["website"] = await website_button.get_attribute("href") or ""
        except:
            pass
        
        # Get phone
        try:
            phone_button = page.locator('button[data-item-id*="phone"]').first
            if await phone_button.is_visible(timeout=2000):
                phone_text = await phone_button.get_attribute("data-item-id") or ""
                phone_match = re.search(r'tel:([+\d\s\-\(\)]+)', phone_text)
                if phone_match:
                    details["phone"] = phone_match.group(1)
        except:
            pass
        
        return details
        
    except Exception as e:
        print(f"      Error scraping business details: {e}")
        return {"website": "", "phone": "", "email": "", "rating": 0.0, "review_count": 0}


async def scrape_email_from_website(page, website_url: str) -> str:
    """Scrape email from a business website"""
    if not website_url or not website_url.startswith("http"):
        return ""
    
    try:
        await page.goto(website_url, wait_until="networkidle", timeout=15000)
        await asyncio.sleep(1)
        
        # Get page content
        content = await page.content()
        
        # Look for email patterns
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        emails = re.findall(email_pattern, content)
        
        # Filter out common non-business emails
        filtered_emails = [e for e in emails if not any(x in e.lower() for x in ['example.com', 'test.com', 'placeholder', 'noreply', 'no-reply'])]
        
        if filtered_emails:
            return filtered_emails[0]
        
        return ""
    except Exception as e:
        return ""


async def scrape_all_businesses(page, zip_code: str, category: str, country: str, min_rating: float, max_rating: float, min_reviews: int, progress_callback=None) -> list:
    """Scrape all businesses from search results for a zip code and category"""
    businesses = []
    
    # Build search query
    query = f"{category} {zip_code} {country}"
    
    if progress_callback:
        progress_callback({"status": "searching", "message": f"Searching for {category} in {zip_code}..."})
    
    # Navigate to Google Maps search
    search_url = f"https://www.google.com/maps/search/{query.replace(' ', '+')}"
    await page.goto(search_url, wait_until="networkidle", timeout=30000)
    await asyncio.sleep(3)  # Wait for results to load
    
    # Scroll to load more results
    scroll_attempt = 0
    max_scroll_attempts = 20
    no_new_count = 0
    
    while no_new_count < 10 and scroll_attempt < max_scroll_attempts:
        items_before = len(businesses)
        items = await page.locator('div[role="feed"] > div > div > a[href*="/maps/place/"]').all()
        
        for item in items:
            try:
                name = await item.get_attribute("aria-label")
                href = await item.get_attribute("href")
                
                # Extract rating and review count from the search result item
                rating = 0.0
                review_count = 0
                
                # Try to find rating from aria-label of the star span
                rating_span = item.locator('span.kvMYJc')
                if await rating_span.is_visible(timeout=100):
                    rating_attr = await rating_span.get_attribute("aria-label")
                    if rating_attr:
                        match = re.search(r'(\d[,\.]\d)', rating_attr)
                        if match:
                            rating = float(match.group(1).replace(",", "."))
                
                # Fallback: search for rating pattern in the item's text content
                if rating == 0.0:
                    item_text = await item.text_content() or ""
                    rating_match = re.search(r'(\d[,\.]\d)\s*stars?', item_text)
                    if rating_match:
                        rating = float(rating_match.group(1).replace(",", "."))

                # Extract review count
                review_match = re.search(r'\(([\d,\.]+)\)', await item.text_content() or "")
                if review_match:
                    num_str = review_match.group(1)
                    if '.' in num_str and ',' not in num_str: # Handle 1.234 for 1,234
                        num_str = num_str.replace('.', '')
                    else:
                        num_str = num_str.replace(',', '')
                    review_count = int(num_str)

                # Filter immediately
                if name and href and not any(b["name"] == name for b in businesses):
                    if min_rating <= rating <= max_rating and review_count >= min_reviews:
                        businesses.append({
                            "name": name,
                            "url": href,
                            "category": category,
                            "rating": rating,
                            "review_count": review_count
                        })
                        if progress_callback:
                            progress_callback({"status": "business_found_filtered", "business_name": name, "rating": rating, "review_count": review_count, "message": f"Found & filtered: {name} ({rating}⭐, {review_count} reviews)"})
                    else:
                        if progress_callback:
                            progress_callback({"status": "business_filtered_out", "business_name": name, "rating": rating, "review_count": review_count, "message": f"Filtered out: {name} ({rating}⭐, {review_count} reviews) - outside criteria"})
            except Exception as e:
                # print(f"Error processing item: {e}")
                pass
        
        # Check if we found new businesses
        if len(businesses) == items_before:
            no_new_count += 1
        else:
            no_new_count = 0
        
        # Scroll down to load more
        scroll_attempt += 1
        try:
            await page.evaluate("""
                const feed = document.querySelector('div[role="feed"]');
                if (feed) {
                    feed.scrollTop = feed.scrollHeight;
                }
            """)
            await asyncio.sleep(2)
        except:
            break
    
    if progress_callback:
        progress_callback({"status": "businesses_found", "count": len(businesses), "message": f"Found {len(businesses)} businesses matching criteria"})
    
    return businesses


async def scrape_reviews(page, max_reviews: int) -> list:
    """Scrape reviews from a business page"""
    reviews = []
    
    try:
        # Wait for reviews section
        await page.wait_for_selector('div[data-review-id]', timeout=10000)
    except:
        # No reviews found
        return reviews
    
    # Scroll to load more reviews
    scroll_attempts = 0
    max_scrolls = 15
    
    while len(reviews) < max_reviews and scroll_attempts < max_scrolls:
        # Get all review elements
        review_elements = await page.locator('div[data-review-id]').all()
        
        if not review_elements:
            break
        
        reviews_before = len(reviews)
        
        for el in review_elements:
            try:
                # Get reviewer name
                reviewer = ""
                reviewer_selectors = [
                    "div.d4r55",
                    "div.TSUbDb",
                    "span.X43Kjb"
                ]
                for selector in reviewer_selectors:
                    try:
                        reviewer_elem = el.locator(selector).first
                        if await reviewer_elem.is_visible(timeout=100):
                            reviewer = await reviewer_elem.text_content() or ""
                            if reviewer.strip():
                                break
                    except:
                        continue
                
                # Get rating
                rating = 0
                rating_selectors = [
                    "span.kvMYJc",
                    "span[aria-label*='star']"
                ]
                for selector in rating_selectors:
                    try:
                        rating_elem = el.locator(selector).first
                        if await rating_elem.is_visible(timeout=100):
                            rating_attr = await rating_elem.get_attribute("aria-label")
                            if rating_attr:
                                rating_match = re.search(r'(\d)', rating_attr)
                                if rating_match:
                                    rating = int(rating_match.group(1))
                                    break
                    except:
                        continue
                
                if rating == 0:
                    continue
                    
                # Get review text - try multiple selectors
                text = ""
                text_selectors = [
                    "span.wiI7pd",
                    "span[data-value]",
                    "div.MyEned",
                ]
                for selector in text_selectors:
                    try:
                        text_elem = el.locator(selector).first
                        if await text_elem.is_visible(timeout=100):
                            text = await text_elem.text_content() or ""
                            if text.strip():
                                break
                    except:
                        continue
                
                date = await el.locator("span.rsqaWe").text_content() or ""

                # Only add reviews with actual text content (not empty/whitespace)
                text_clean = text.strip() if text else ""
                if text_clean and len(text_clean) > 3:  # Must have at least 3 characters
                    # Check for duplicates
                    if not any(r["text"].strip() == text_clean for r in reviews):
                        reviews.append({
                            "reviewer_name": reviewer.strip(), 
                            "rating": rating, 
                            "text": text_clean, 
                            "date": date.strip()
                        })
            except Exception as e:
                continue
        
        # Check if we got new reviews
        if len(reviews) == reviews_before:
            scroll_attempts += 1
        else:
            scroll_attempts = 0
        
        # Scroll to load more reviews
        if len(reviews) < max_reviews:
            try:
                # Scroll the reviews container
                await page.evaluate("""
                    const reviewList = document.querySelector('div[role="feed"]');
                    if (reviewList) {
                        reviewList.scrollTop = reviewList.scrollHeight;
                    }
                """)
                await asyncio.sleep(1.5)
            except:
                break
    
    # Sort by rating (lowest first - most likely to be violations)
    reviews.sort(key=lambda x: x["rating"])
    
    print(f"      ✅ Collected {len(reviews)} reviews with text")



#######################################################################
# MAIN SCRAPER
#######################################################################

def save_lead_incrementally(lead: dict, output_dir: str, timestamp: str, area: str = ""):
    """Save a single lead to CSV immediately for real-time viewing"""
    safe_area = area.replace(",", "").replace(" ", "_")[:30] if area else ""
    csv_filename = f"violations_leads_{safe_area}_{timestamp}.csv" if safe_area else f"violations_leads_{timestamp}.csv"
    csv_path = f"{output_dir}/{csv_filename}"
    
    flagged = lead.get("flagged_reviews", [])
    top_violations = flagged[:3]
    
    row = {
        "business_name": lead["name"],
        "website_url": lead.get("website", ""),
        "email": lead.get("email", ""),
        "phone": lead.get("phone", ""),
        "violations_count": len(flagged),
    }
    
    for i in range(3):
        if i < len(top_violations):
            v = top_violations[i]
            row[f"review_{i+1}_text"] = v["text"]
            row[f"review_{i+1}_reason"] = v["classification"]["reasoning"]
            row[f"review_{i+1}_confidence"] = round(v["classification"]["confidence"], 2)
            row[f"review_{i+1}_rating"] = v["rating"]
            row[f"review_{i+1}_reviewer"] = v["reviewer_name"]
            row[f"review_{i+1}_date"] = v["date"]
        else:
            row[f"review_{i+1}_text"] = ""
            row[f"review_{i+1}_reason"] = ""
            row[f"review_{i+1}_confidence"] = ""
            row[f"review_{i+1}_rating"] = ""
            row[f"review_{i+1}_reviewer"] = ""
    
    # Append to CSV (create if doesn't exist)
    file_exists = os.path.exists(csv_path)
    df = pd.DataFrame([row])
    df.to_csv(csv_path, mode='a', header=not file_exists, index=False)


def print_violation_details(lead: dict, flagged_reviews: list):
    """Print detailed violation information to console"""
    print(f"\n      {'='*60}")
    print(f"      🚩 VIOLATION FOUND: {lead['name']}")
    print(f"      {'='*60}")
    print(f"      📍 Website: {lead.get('website', 'N/A')}")
    print(f"      📧 Email: {lead.get('email', 'Not found')}")
    print(f"      📞 Phone: {lead.get('phone', 'Not found')}")
    print(f"      ⭐ Rating: {lead.get('rating', 'N/A')} | 📝 Reviews: {lead.get('review_count', 'N/A')}")
    print(f"      🚨 Total Violations: {len(flagged_reviews)}")
    print(f"      {'-'*60}")
    
    for idx, v in enumerate(flagged_reviews[:3], 1):
        print(f"\n      Violation #{idx}:")
        print(f"         ⭐ Rating: {v['rating']}/5")
        print(f"         👤 Reviewer: {v['reviewer_name']}")
        print(f"         📅 Date: {v['date']}")
        print(f"         🎯 Confidence: {v['classification']['confidence']:.2%}")
        print(f"         🏷️  Types: {', '.join(v['classification']['violation_types']) if v['classification']['violation_types'] else 'N/A'}")
        print(f"         💬 Review Text: {v['text'][:200]}{'...' if len(v['text']) > 200 else ''}")
        print(f"         📋 Reason: {v['classification']['reasoning']}")
    
    print(f"      {'='*60}\n")


async def install_playwright_browsers_if_needed(progress_callback=None):
    """Check if Playwright browsers are installed - don't auto-install"""
    import os
    import platform
    import glob
    
    # Skip in cloud environments - they should install during build
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER") or os.getenv("STREAMLIT_SERVER_PORT"):
        return True
    
    # Check common installation paths
    system = platform.system()
    
    if system == "Windows":
        local_appdata = os.getenv("LOCALAPPDATA", os.path.expanduser("~\\AppData\\Local"))
        playwright_dir = os.path.join(local_appdata, "ms-playwright")
        # Check if ms-playwright directory exists
        if os.path.exists(playwright_dir):
            # Look for any chromium folder
            chromium_folders = [d for d in os.listdir(playwright_dir) if d.startswith("chromium-")]
            if chromium_folders:
                # Check if chrome.exe exists in any chromium folder
                for folder in chromium_folders:
                    chrome_exe = os.path.join(playwright_dir, folder, "chrome-win", "chrome.exe")
                    if os.path.isfile(chrome_exe):
                        return True
        # Fallback: use glob pattern
        possible_paths = [
            os.path.join(local_appdata, "ms-playwright", "chromium-*", "chrome-win", "chrome.exe"),
        ]
    elif system == "Darwin":  # macOS
        possible_paths = [
            os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-mac/Chromium.app"),
            os.path.expanduser("~/Library/Caches/ms-playwright/chromium-*/chrome-mac/Chromium.app"),
        ]
    else:  # Linux
        possible_paths = [
            os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome"),
            os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"),
        ]
    
    # Check if any browser exists
    for path_pattern in possible_paths:
        try:
            matches = glob.glob(path_pattern)
            if matches:
                # Verify it exists
                for match in matches:
                    if os.path.isfile(match) or os.path.isdir(match):
                        # Browsers found - return silently
                        return True
        except Exception:
            continue
    
    # Browsers not found - don't auto-install, just return False
    if progress_callback is not None:
        progress_callback({"status": "error", "message": "Playwright browsers not found. Please run: python -m playwright install chromium"})
    
    return False


async def run_scraper(zip_codes=None, progress_callback=None, filters=None):
    """
    Main scraper function
    
    Args:
        zip_codes: List of zip codes to scrape (e.g., ["92100", "92200"])
        progress_callback: Optional callback function for progress updates
        filters: Optional dict with min_rating, max_rating, min_reviews, etc.
    
    Returns:
        Tuple of (leads_list, training_data_dict, stats_dict)
    """
    if not zip_codes:
        zip_codes = ["92100", "92200"]  # Default
    
    if not filters:
        filters = {
            "min_rating": MIN_RATING,
            "max_rating": MAX_RATING,
            "min_reviews": MIN_REVIEWS,
            "max_reviews_per_business": MAX_REVIEWS_PER_BUSINESS,
            "min_violations_to_stop": MIN_VIOLATIONS_TO_STOP,
        }
    
    country = filters.get("country", "France")
    categories = filters.get("categories", ALL_CATEGORIES)
    
    if progress_callback:
        progress_callback({"status": "starting", "message": "Starting scraper..."})
    
    # Check if Playwright browsers are installed (don't auto-install)
    browsers_installed = await install_playwright_browsers_if_needed(progress_callback)
    if not browsers_installed:
        # Browsers not installed - stop here
        if progress_callback:
            progress_callback({"status": "error", "message": "Playwright browsers not installed. Please run: python -m playwright install chromium"})
        raise RuntimeError("Playwright browsers not installed. Please run: python -m playwright install chromium")

    async with async_playwright() as p:
        # Use persistent browser context to maintain language and login settings
        user_data_dir = os.path.join(OUTPUT_DIR, "browser_data")
        os.makedirs(user_data_dir, exist_ok=True)
        
        browser = await p.chromium.launch_persistent_context(
            user_data_dir=user_data_dir,
            headless=HEADLESS,
            locale="en-US",
            viewport={"width": 1280, "height": 800},
            # Force English language
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9"
            },
            # Set language preferences and make browser undetectable
            args=[
                "--lang=en-US",
                "--accept-lang=en-US,en",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-setuid-sandbox",
            ],
            # Remove automation indicators
            ignore_https_errors=False,
        )
        page = await browser.new_page()
        
        # Set extra headers to avoid detection
        await page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        })
        
        # Inject script to remove webdriver property
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        leads = []
        training_data = {"violations": [], "non_violations": []}
        stats = {
            "total_businesses_found": 0,
            "total_businesses_processed": 0,
            "total_reviews_scraped": 0,
            "total_violations_found": 0,
            "total_leads": 0,
        }
        
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        
        try:
            for zip_code in zip_codes:
                if progress_callback:
                    progress_callback({"status": "area_start", "area": zip_code, "message": f"Processing zip code: {zip_code}"})
                
                for category in categories:
                    if progress_callback:
                        progress_callback({"status": "category_start", "category": category, "message": f"Processing category: {category}"})
                    
                    # Scrape businesses for this zip code and category
                    businesses = await scrape_all_businesses(
                        page, zip_code, category, country,
                        filters["min_rating"], filters["max_rating"], filters["min_reviews"],
                        progress_callback
                    )
                    
                    stats["total_businesses_found"] += len(businesses)
                    
                    if progress_callback:
                        progress_callback({"status": "businesses_found", "count": len(businesses), "message": f"Found {len(businesses)} businesses for {category} in {zip_code}"})
                    
                    # Process each business
                    for idx, business in enumerate(businesses, 1):
                        if progress_callback:
                            progress_callback({"status": "business_processing", "business_name": business["name"], "current": idx, "total": len(businesses), "message": f"Processing {business['name']} ({idx}/{len(businesses)})"})
                        
                        try:
                            # Get business details
                            details = await scrape_business_details(page, business["url"])
                            business.update(details)
                            
                            # Scrape reviews
                            if progress_callback:
                                progress_callback({"status": "scraping_reviews", "business_name": business["name"], "message": f"Scraping reviews for {business['name']}..."})
                            
                            reviews = await scrape_reviews(page, filters["max_reviews_per_business"])
                            stats["total_reviews_scraped"] += len(reviews)
                            
                            if progress_callback:
                                progress_callback({"status": "reviews_collected", "count": len(reviews), "message": f"Collected {len(reviews)} reviews"})
                            
                            # Classify reviews
                            if progress_callback:
                                progress_callback({"status": "classifying_reviews", "current": 0, "total": len(reviews), "message": "Classifying reviews..."})
                            
                            flagged_reviews = []
                            violation_count = 0
                            
                            for review_idx, review in enumerate(reviews, 1):
                                if progress_callback:
                                    progress_callback({"status": "classifying_reviews", "current": review_idx, "total": len(reviews), "message": f"Classifying review {review_idx}/{len(reviews)}"})
                                
                                classification = classify_review(review["text"], review["rating"])
                                
                                if classification["is_violation"]:
                                    review["classification"] = classification
                                    flagged_reviews.append(review)
                                    violation_count += 1
                                    
                                    if progress_callback:
                                        progress_callback({"status": "violation_found", "violation_count": violation_count, "message": f"Violation found! ({violation_count} total)"})
                                    
                                    # Stop if we found enough violations
                                    if violation_count >= filters["min_violations_to_stop"]:
                                        break
                            
                            # If we found violations, this is a lead
                            if flagged_reviews:
                                # Try to get email from website
                                email = ""
                                if business.get("website"):
                                    if progress_callback:
                                        progress_callback({"status": "info", "message": f"Scraping email from {business.get('website', '')}"})
                                    email = await scrape_email_from_website(page, business["website"])
                                
                                lead = {
                                    "name": business["name"],
                                    "website": business.get("website", ""),
                                    "email": email,
                                    "phone": business.get("phone", ""),
                                    "rating": business.get("rating", 0.0),
                                    "review_count": business.get("review_count", 0),
                                    "flagged_reviews": flagged_reviews,
                                    "zip_code": zip_code,
                                    "category": category,
                                }
                                
                                leads.append(lead)
                                stats["total_violations_found"] += len(flagged_reviews)
                                stats["total_leads"] += 1
                                
                                # Save immediately
                                save_lead_incrementally(lead, OUTPUT_DIR, timestamp, zip_code)
                                
                                if progress_callback:
                                    progress_callback({"status": "lead_found", "lead": lead, "violations_count": len(flagged_reviews), "message": f"🚩 LEAD FOUND: {business['name']} ({len(flagged_reviews)} violations)"})
                                
                                print_violation_details(lead, flagged_reviews)
                            
                            stats["total_businesses_processed"] += 1
                            
                        except Exception as e:
                            print(f"      Error processing business {business.get('name', 'unknown')}: {e}")
                            continue
                    
                    await asyncio.sleep(1)  # Small delay between categories
                
                await asyncio.sleep(2)  # Small delay between zip codes
            
            if progress_callback:
                progress_callback({"status": "completed", "stats": stats, "message": "Scraping completed!"})
        
        finally:
            await browser.close()
    
    return leads, training_data, stats


def export_leads(leads: list, output_dir: str = OUTPUT_DIR):
    """Export leads to CSV and JSON files"""
    if not leads:
        print("No leads to export.")
        return
    
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    
    # Export to CSV
    csv_data = []
    for lead in leads:
        flagged = lead.get("flagged_reviews", [])
        top_violations = flagged[:3]
        
        row = {
            "business_name": lead["name"],
            "website_url": lead.get("website", ""),
            "email": lead.get("email", ""),
            "phone": lead.get("phone", ""),
            "rating": lead.get("rating", 0.0),
            "review_count": lead.get("review_count", 0),
            "violations_count": len(flagged),
            "zip_code": lead.get("zip_code", ""),
            "category": lead.get("category", ""),
        }
        
        for i in range(3):
            if i < len(top_violations):
                v = top_violations[i]
                row[f"review_{i+1}_text"] = v["text"]
                row[f"review_{i+1}_reason"] = v["classification"]["reasoning"]
                row[f"review_{i+1}_confidence"] = round(v["classification"]["confidence"], 2)
                row[f"review_{i+1}_rating"] = v["rating"]
                row[f"review_{i+1}_reviewer"] = v["reviewer_name"]
                row[f"review_{i+1}_date"] = v["date"]
            else:
                row[f"review_{i+1}_text"] = ""
                row[f"review_{i+1}_reason"] = ""
                row[f"review_{i+1}_confidence"] = ""
                row[f"review_{i+1}_rating"] = ""
                row[f"review_{i+1}_reviewer"] = ""
                row[f"review_{i+1}_date"] = ""
        
        csv_data.append(row)
    
    df = pd.DataFrame(csv_data)
    csv_path = f"{output_dir}/violations_leads_{timestamp}.csv"
    df.to_csv(csv_path, index=False)
    print(f"\n✅ Exported {len(leads)} leads to {csv_path}")
    
    # Export to JSON
    json_path = f"{output_dir}/violations_details_{timestamp}.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(leads, f, indent=2, ensure_ascii=False)
    print(f"✅ Exported detailed data to {json_path}")


if __name__ == "__main__":
    # Example usage
    zip_codes = ["92100", "92200"]
    leads, training_data, stats = asyncio.run(run_scraper(zip_codes=zip_codes))
    export_leads(leads)
    print(f"\n📊 Stats: {stats}")
