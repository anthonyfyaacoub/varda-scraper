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

#######################################################################
# 🔑 CONFIGURATION - EDIT THIS SECTION
#######################################################################

# API Key - Use environment variable for security (REQUIRED for cloud deployment)
# Set OPENAI_API_KEY environment variable - NEVER hardcode your API key!
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable is required! Set it in your environment or Streamlit secrets.")

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
    1: [
        # Restaurants (high volume of reviews)
        "restaurant", "bistro", "brasserie", "sushi restaurant", "indian restaurant",
        # Pharmacies (medical reputation, sensitive to scam/thief accusations)
        "pharmacy",
        # Car Repair / Garages (often attacked for overcharging)
        "car repair", "auto repair shop", "garage", "midas", "speedy", "mechanic",
        # Dentists / Orthodontists (high ticket service, reputation vital)
        "dentist", "orthodontist",
        # Real Estate Agencies (trust is their currency)
        "real estate agency",
        # Hair Salons / Barbers (emotional business, sensitive to bad pictures)
        "hair salon", "barber shop",
        # Car Dealerships (high value sales)
        "car dealership",
        # Aesthetic Centers (high trust needed)
        "aesthetic clinic", "laser clinic", "botox clinic", "cryotherapy",
        # Veterinarians (emotional, pet owners leave very long reviews)
        "veterinarian",
        # Renovation / Plumbers / Locksmiths (emergency services, often called scammers)
        "plumber", "locksmith", "renovation contractor"
    ],
    2: [],  # Reserved for future use
    3: [],  # Reserved for future use
}

#######################################################################
# AI CLASSIFIER
#######################################################################

_client = None

def get_openai_client():
    """Lazy initialization of OpenAI client"""
    global _client
    if _client is None:
        _client = OpenAI(api_key=OPENAI_API_KEY)
    return _client

GOOGLE_POLICY_PROMPT = """You are an expert at analyzing Google Business reviews for policy violations.

Based on Google's official Maps User Generated Content Policy, reviews can be removed if they contain:

## DECEPTIVE CONTENT
1. **FAKE_ENGAGEMENT**: Fake reviews, paid reviews, bot content, not based on real experience
2. **CONFLICT_OF_INTEREST**: Reviews from competitors, employees, business owners
3. **IMPERSONATION**: Pretending to be someone else
4. **MISINFORMATION**: False health/medical claims, deceptive content
5. **MISREPRESENTATION**: False claims about products/services

## INAPPROPRIATE CONTENT
6. **HARASSMENT**: Threats, doxxing, personal attacks
7. **HATE_SPEECH**: Attacks on protected groups (race, religion, gender, etc.)
8. **OFFENSIVE_CONTENT**: Deliberate provocation, unsubstantiated criminal accusations
9. **OBSCENITY_PROFANITY**: Profane language used to offend
10. **SEXUALLY_EXPLICIT**: Sexual content
11. **VIOLENCE_GORE**: Graphic violence, animal cruelty

## OTHER VIOLATIONS
12. **OFF_TOPIC**: Political commentary, rants, not about the business
13. **SPAM_ADVERTISING**: Promotional content, links, phone numbers
14. **PERSONAL_INFORMATION**: Posting others' private info
15. **DANGEROUS_CONTENT**: Content promoting harm or illegal activities

Respond with ONLY valid JSON:
{
  "has_violation": true/false,
  "violation_types": ["CATEGORY_NAME"],
  "confidence": 0.0-1.0,
  "reasoning": "Brief explanation for removal request"
}

IMPORTANT:
- Low star rating alone is NOT a violation
- Negative factual experiences are NOT violations
- Only flag CLEAR policy violations"""


def classify_review(reviewer_name: str, rating: int, text: str, date: str) -> dict:
    try:
        client = get_openai_client()
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": GOOGLE_POLICY_PROMPT},
                {"role": "user", "content": f'Review by "{reviewer_name}" ({rating} stars, {date}):\n"{text}"'},
            ],
            temperature=0.1,
            max_tokens=400,
        )
        content = response.choices[0].message.content or ""
        clean_json = content.replace("```json", "").replace("```", "").strip()
        result = json.loads(clean_json)
        return {
            "has_violation": result.get("has_violation", False),
            "violation_types": result.get("violation_types", []),
            "confidence": result.get("confidence", 0.0),
            "reasoning": result.get("reasoning", ""),
        }
    except Exception as e:
        return {"has_violation": False, "violation_types": [], "confidence": 0.0, "reasoning": f"Error: {e}"}


#######################################################################
# SCRAPER FUNCTIONS
#######################################################################

async def sleep(ms: int):
    await asyncio.sleep(ms / 1000)


async def accept_cookies(page):
    # Try multiple selectors and be more aggressive
    selectors = [
        'button:has-text("Accept all")',
        'button:has-text("Aceptar todo")',
        'button:has-text("Tout accepter")',
        'button[aria-label*="Accept all"]',
        'button[aria-label*="Aceptar todo"]',
        'button:has-text("Accept")',
        'button:has-text("Aceptar")',
        # Try by button text content
        'button',
    ]
    
    for selector in selectors:
        try:
            if selector == 'button':
                # For the generic button selector, check text content
                buttons = await page.locator('button').all()
                for btn in buttons:
                    text = await btn.text_content() or ""
                    if any(phrase in text.lower() for phrase in ["accept all", "aceptar todo", "accept", "aceptar"]):
                        if await btn.is_visible(timeout=1000):
                            await btn.click()
                            await sleep(2000)
                            return
            else:
                btn = page.locator(selector)
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    await sleep(2000)
                    return
        except:
            continue
    
    # If still not found, try clicking any visible button in the cookie dialog area
    try:
        cookie_area = page.locator('div[role="dialog"], div[jsaction*="cookie"]')
        if await cookie_area.is_visible(timeout=2000):
            buttons = await cookie_area.locator('button').all()
            for btn in buttons:
                text = await btn.text_content() or ""
                if any(phrase in text.lower() for phrase in ["accept", "aceptar", "all", "todo"]):
                    await btn.click()
                    await sleep(2000)
                    return
    except:
        pass


async def check_and_handle_google_verification(page):
    """
    Check for Google verification prompts (CAPTCHA, "verify you're not a robot", etc.)
    and wait for user to manually solve it.
    """
    verification_selectors = [
        'text="verify you\'re not a robot"',
        'text="verify"',
        'text="I\'m not a robot"',
        'iframe[title*="reCAPTCHA"]',
        'iframe[title*="challenge"]',
        'div:has-text("unusual traffic")',
        'div:has-text("suspicious activity")',
        'button:has-text("Verify")',
    ]
    
    for selector in verification_selectors:
        try:
            element = page.locator(selector)
            if await element.is_visible(timeout=2000):
                print("\n⚠️  Google verification detected!")
                print("   Please solve the CAPTCHA/verification in the browser window.")
                print("   Waiting for you to complete it...")
                
                # Wait for verification to be completed
                max_wait = 300  # 5 minutes max wait
                waited = 0
                while waited < max_wait:
                    try:
                        if not await element.is_visible(timeout=1000):
                            print("   ✅ Verification appears to be completed!")
                            await sleep(2000)
                            return True
                    except:
                        # Element might have disappeared
                        print("   ✅ Verification appears to be completed!")
                        await sleep(2000)
                        return True
                    await sleep(2000)
                    waited += 2
                    if waited % 30 == 0:
                        print(f"   ⏳ Still waiting... ({waited}s)")
                
                print("   ⚠️  Timeout waiting for verification")
                return False
        except:
            continue
    
    return False


async def safe_goto(page, url: str, retries: int = 2):
    for attempt in range(retries):
        try:
            # Add hl=en parameter if not already present to force English
            if "hl=" not in url:
                separator = "&" if "?" in url else "?"
                url = f"{url}{separator}hl=en"
            
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await sleep(1500)
            
            # Check for Google verification after navigation
            await check_and_handle_google_verification(page)
            
            return True
        except:
            if attempt < retries - 1:
                await sleep(1000)
    return False


async def scrape_all_businesses(page, zip_code: str, category: str, country: str = "France", min_rating: float = 0.0, max_rating: float = 5.0, min_reviews: int = 0, progress_callback=None) -> list:
    """
    Scrape businesses from Google Maps search results.
    Extracts rating and review count directly from search results for immediate filtering.
    """
    search_query = f"{category} {zip_code} {country}"
    # Force English language with hl parameter
    url = f"https://www.google.com/maps/search/{search_query.replace(' ', '+')}?hl=en"
    
    print(f"   🔍 Searching: {search_query}")
    
    if not await safe_goto(page, url):
        return []
    
    await accept_cookies(page)
    await sleep(1500)
    
    # Check for verification after initial load
    await check_and_handle_google_verification(page)

    businesses = []
    last_count = 0
    no_new_count = 0

    results_panel = page.locator('div[role="feed"]')
    try:
        await results_panel.wait_for(timeout=10000)
    except:
        print(f"   ⚠️ No results found")
        return []

    print(f"   📜 Scrolling to find businesses (filtering: {min_rating}-{max_rating}⭐, {min_reviews}+ reviews)...")
    if progress_callback:
        progress_callback({"status": "filtering", "message": f"Scrolling and filtering businesses ({min_rating}-{max_rating}⭐, {min_reviews}+ reviews)..."})
    
    max_scroll_attempts = 100
    scroll_attempt = 0
    
    while no_new_count < 10 and scroll_attempt < max_scroll_attempts:
        # Get all business items from the feed
        items = await page.locator('div[role="feed"] > div > div > a[href*="/maps/place/"]').all()

        for item in items:
            try:
                name = await item.get_attribute("aria-label")
                href = await item.get_attribute("href")
                
                if not name or not href:
                    continue
                
                # Skip if already found
                if any(b["name"] == name for b in businesses):
                    continue
                
                # Extract rating and review count from the search result item
                rating = 0.0
                review_count = 0
                
                try:
                    # Get the parent container that holds the business info
                    parent_container = item.locator("xpath=ancestor::div[contains(@class, 'Nv2PK') or contains(@class, 'THOPZb')]").first
                    
                    # Try multiple methods to extract rating
                    # Method 1: Look for aria-label with rating
                    try:
                        rating_elem = parent_container.locator('span[aria-label*="star"], span[aria-label*="rating"]').first
                        if await rating_elem.is_visible(timeout=500):
                            aria_label = await rating_elem.get_attribute("aria-label") or ""
                            rating_match = re.search(r'(\d+[,\.]\d+)', aria_label)
                            if rating_match:
                                rating = float(rating_match.group(1).replace(",", "."))
                    except:
                        pass
                    
                    # Method 2: Look for text content with rating pattern
                    if rating == 0.0:
                        try:
                            container_text = await parent_container.text_content() or ""
                            # Look for rating pattern (e.g., "4.5" or "4,5")
                            rating_match = re.search(r'(\d+[,\.]\d+)\s*(?:star|⭐)', container_text[:300])
                            if not rating_match:
                                rating_match = re.search(r'(\d+[,\.]\d+)', container_text[:200])
                            if rating_match:
                                rating_str = rating_match.group(1).replace(",", ".")
                                rating = float(rating_str)
                        except:
                            pass
                    
                    # Extract review count
                    try:
                        # Look for review count in aria-label or text
                        review_elem = parent_container.locator('span:has-text("("), button:has-text("(")').first
                        if await review_elem.is_visible(timeout=500):
                            review_text = await review_elem.text_content() or ""
                            review_match = re.search(r'\(([\d,\.]+)\)', review_text)
                            if review_match:
                                review_str = review_match.group(1).replace(",", "").replace(".", "")
                                review_count = int(review_str)
                    except:
                        pass
                    
                    # Fallback: Try to find review count in container text
                    if review_count == 0:
                        try:
                            container_text = await parent_container.text_content() or ""
                            review_match = re.search(r'\(([\d,\.]+)\s*(?:review|Review|reseña|Reseña)', container_text[:400])
                            if not review_match:
                                review_match = re.search(r'\(([\d,\.]+)\)', container_text[:400])
                            if review_match:
                                review_str = review_match.group(1).replace(",", "").replace(".", "")
                                review_count = int(review_str)
                        except:
                            pass
                except:
                    pass
                
                # FILTER IMMEDIATELY - only add if matches criteria
                if rating >= min_rating and rating <= max_rating and review_count >= min_reviews:
                    businesses.append({
                        "name": name,
                        "url": href,
                        "category": category,
                        "rating": rating,
                        "review_count": review_count
                    })
                    if progress_callback:
                        progress_callback({
                            "status": "business_found_filtered",
                            "business_name": name[:50],
                            "rating": rating,
                            "review_count": review_count,
                            "message": f"✓ Found: {name[:50]} ({rating}⭐, {review_count} reviews)"
                        })
                else:
                    # Log filtered businesses for debugging
                    if rating > 0 or review_count > 0:
                        print(f"      ⏭️  Filtered: {name[:30]}... - ⭐{rating} ({review_count} reviews)", end="\r")
                        if progress_callback and scroll_attempt % 5 == 0:  # Only log every 5th filtered to avoid spam
                            progress_callback({
                                "status": "business_filtered_out",
                                "business_name": name[:50],
                                "rating": rating,
                                "review_count": review_count,
                                "message": f"✗ Filtered: {name[:50]} ({rating}⭐, {review_count} reviews) - outside range"
                            })
            except Exception as e:
                pass

        if len(businesses) == last_count:
            no_new_count += 1
        else:
            no_new_count = 0
            print(f"   📍 Found {len(businesses)} matching businesses...", end="\r")
            if progress_callback:
                progress_callback({
                    "status": "businesses_found",
                    "count": len(businesses),
                    "message": f"Found {len(businesses)} matching businesses so far..."
                })
        
        last_count = len(businesses)
        scroll_attempt += 1

        # Scroll more aggressively to get more results
        try:
            for _ in range(3):
                await results_panel.evaluate("el => el.scrollBy(0, 1500)")
                await sleep(500)
        except:
            break

        # Check for end of list
        try:
            end = page.locator('span:has-text("end of the list"), span:has-text("You\'ve reached the end")')
            if await end.is_visible(timeout=500):
                print(f"   ✅ Reached end of results")
                break
        except:
            pass
        
        # Also check if we've scrolled enough
        if scroll_attempt % 20 == 0:
            print(f"   📊 Still scrolling... ({len(businesses)} matching businesses found so far)")

    print(f"   ✅ Found {len(businesses)} matching businesses                    ")
    return businesses


async def scrape_business_details(page, business: dict) -> Optional[dict]:
    try:
        # Add hl=en to business URL to force English
        biz_url = business["url"]
        if "hl=" not in biz_url:
            separator = "&" if "?" in biz_url else "?"
            biz_url = f"{biz_url}{separator}hl=en"
        
        if not await safe_goto(page, biz_url):
            return None

        details = {
            "name": business["name"],
            "category": business["category"],
            "google_maps_url": business["url"],
            "address": "", "phone": "", "email": "", "website": "",
            "rating": 0.0, "review_count": 0,
        }

        await sleep(1000)

        # Rating and review count from header
        try:
            header = page.locator('div[role="main"]').first
            header_text = await header.text_content() or ""
            
            rating_match = re.search(r'(\d[,\.]\d)', header_text[:100])
            if rating_match:
                details["rating"] = float(rating_match.group(1).replace(",", "."))
            
            review_match = re.search(r'\(([\d,\.]+)\)', header_text[:200])
            if review_match:
                num_str = review_match.group(1)
                if '.' in num_str and ',' not in num_str:
                    num_str = num_str.replace('.', '')
                else:
                    num_str = num_str.replace(',', '')
                details["review_count"] = int(num_str)
        except:
            pass

        # Address
        try:
            addr_btn = page.locator('button[data-item-id="address"]')
            if await addr_btn.is_visible(timeout=1500):
                addr = await addr_btn.get_attribute("aria-label") or ""
                details["address"] = addr.replace("Address: ", "").replace("Dirección: ", "")
        except:
            pass

        # Phone
        try:
            phone_btn = page.locator('button[data-item-id*="phone"]')
            if await phone_btn.is_visible(timeout=1500):
                phone = await phone_btn.get_attribute("aria-label") or ""
                details["phone"] = phone.replace("Phone: ", "").replace("Teléfono: ", "")
        except:
            pass

        # Website
        try:
            web_link = page.locator('a[data-item-id="authority"]')
            if await web_link.is_visible(timeout=1500):
                details["website"] = await web_link.get_attribute("href") or ""
        except:
            pass

        return details
    except:
        return None


async def scrape_email_from_website(page, website_url: str) -> str:
    if not website_url:
        return ""
    try:
        await page.goto(website_url, wait_until="domcontentloaded", timeout=8000)
        await sleep(1000)
        content = await page.content()
        emails = re.findall(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}', content)
        filtered = [e for e in emails if not any(x in e.lower() for x in 
            ['example', 'test', 'domain', 'sentry', 'wix', 'schema', 'wordpress'])]
        return filtered[0] if filtered else ""
    except:
        return ""


async def scrape_reviews(page, max_reviews: int) -> list:
    reviews = []
    start_time = time.time()
    max_scraping_time = 120  # Maximum 2 minutes per business
    
    try:
        reviews_tab = page.locator('button[role="tab"]:has-text("Reviews"), button[role="tab"]:has-text("Reseñas")')
        try:
            if await reviews_tab.is_visible(timeout=3000):
                await reviews_tab.click()
                await sleep(2000)
        except:
            pass

        try:
            # Try to find the sort button - look for various selectors
            sort_selectors = [
                'button[aria-label*="Sort"]',
                'button[aria-label*="Ordenar"]',
                'button[data-value*="sort"]',
                'button:has-text("Sort")',
                'button:has-text("Ordenar")',
            ]
            
            sort_btn = None
            for selector in sort_selectors:
                try:
                    btn = page.locator(selector)
                    if await btn.is_visible(timeout=1000):
                        sort_btn = btn
                        break
                except:
                    continue
            
            if sort_btn:
                await sort_btn.click()
                await sleep(1000)
                
                # Try to find and click "Lowest rating" or "Rating" option
                rating_options = [
                    'div[role="menuitemradio"]:has-text("Lowest")',
                    'div[role="menuitemradio"]:has-text("lowest")',
                    'div[role="menuitemradio"]:has-text("Lowest rating")',
                    'div[role="menuitemradio"]:has-text("Rating")',
                    'div[role="menuitemradio"]:has-text("rating")',
                    'div[role="menuitemradio"]:has-text("peor")',
                    'div[role="menuitemradio"]:has-text("Peor")',
                    'div[role="menuitemradio"][data-value*="rating"]',
                    'div[role="menuitemradio"][data-value*="lowest"]',
                ]
                
                clicked = False
                for option_selector in rating_options:
                    try:
                        option = page.locator(option_selector)
                        if await option.is_visible(timeout=1000):
                            await option.click()
                            await sleep(2000)
                            print("      📉 Sorted by rating")
                            clicked = True
                            break
                    except:
                        continue
                
                # If rating sort not found, try to find any sort option and click it
                if not clicked:
                    try:
                        menu_items = await page.locator('div[role="menuitemradio"]').all()
                        for item in menu_items:
                            text = await item.text_content() or ""
                            aria_label = await item.get_attribute("aria-label") or ""
                            if any(word in (text + aria_label).lower() for word in ["rating", "lowest", "worst", "peor", "calificación"]):
                                await item.click()
                                await sleep(2000)
                                print("      📉 Sorted by rating")
                                clicked = True
                                break
                    except:
                        pass
                
                if not clicked:
                    print("      ⚠️  Could not find rating sort option, proceeding with default order")
        except Exception as e:
            print(f"      ⚠️  Could not sort reviews: {e}")

        # Wait for reviews panel to load
        reviews_panel = None
        try:
            reviews_panel = page.locator("div.m6QErb.DxyBCb")
            await reviews_panel.wait_for(timeout=5000)
        except:
            # Try alternative selector
            try:
                reviews_panel = page.locator('div[role="main"]').locator('div').filter(has_text=re.compile(r'review|reseña', re.I)).first
                await reviews_panel.wait_for(timeout=3000)
            except:
                print("      ⚠️  Could not find reviews panel")
                return []

        scroll_attempts = 0
        last_count = 0
        no_new_count = 0
        max_scroll_attempts = 30  # Increased but with timeout protection

        while len(reviews) < max_reviews and scroll_attempts < max_scroll_attempts:
            # Check timeout
            if time.time() - start_time > max_scraping_time:
                print(f"      ⏱️  Timeout: Stopped after {max_scraping_time}s")
                break
            
            review_elements = await page.locator("div.jftiEf").all()
            
            if not review_elements:
                # No reviews found, try scrolling once more
                if reviews_panel:
                    try:
                        await reviews_panel.evaluate("el => el.scrollBy(0, 1000)")
                        await sleep(1000)
                    except:
                        pass
                scroll_attempts += 1
                continue

            reviews_before = len(reviews)
            
            for el in review_elements:
                if len(reviews) >= max_reviews:
                    break
                try:
                    # Expand "More" button if present
                    try:
                        more_btn = el.locator("button.w8nwRe")
                        if await more_btn.is_visible(timeout=200):
                            await more_btn.click()
                            await sleep(200)
                    except:
                        pass

                    # Extract review data
                    reviewer = await el.locator("div.d4r55").text_content() or "Anonymous"
                    rating = 0
                    try:
                        rating_attr = await el.locator("span.kvMYJc").get_attribute("aria-label")
                        if rating_attr:
                            match = re.search(r"(\d)", rating_attr)
                            if match:
                                rating = int(match.group(1))
                    except:
                        pass
                    
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
                    # Skip this review element if there's an error
                    continue

            # Check if we got new reviews
            if len(reviews) == last_count:
                no_new_count += 1
                if no_new_count >= 5:  # Increased threshold before giving up
                    print(f"      ⚠️  No new reviews found after {no_new_count} attempts, stopping")
                    break
            else:
                no_new_count = 0
            
            last_count = len(reviews)

            # Scroll to load more reviews
            if reviews_panel and len(reviews) < max_reviews:
                try:
                    await reviews_panel.evaluate("el => el.scrollBy(0, 800)")
                    await sleep(800)  # Wait for new content to load
                except Exception as e:
                    print(f"      ⚠️  Scroll error: {e}")
                    break
            
            scroll_attempts += 1
            
            # Check for verification periodically
            if scroll_attempts % 5 == 0:
                await check_and_handle_google_verification(page)
                
    except Exception as e:
        print(f"      ⚠️  Error scraping reviews: {e}")
    
    # Filter out any empty reviews that might have slipped through
    reviews = [r for r in reviews if r.get("text", "").strip() and len(r.get("text", "").strip()) > 3]
    
    # Sort reviews by rating (lowest first) to prioritize worst reviews
    reviews.sort(key=lambda x: x["rating"])
    
    print(f"      ✅ Collected {len(reviews)} reviews with text")
    return reviews[:max_reviews]


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
            row[f"review_{i+1}_date"] = ""
    
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
    """Install Playwright browsers if they don't exist - LOCAL USE ONLY"""
    import subprocess
    import sys
    import asyncio
    import os
    import glob
    
    # Check multiple possible browser paths
    possible_paths = [
        os.path.expanduser("~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell"),
        os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome"),
        os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-win/chrome.exe"),
        os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-mac/Chromium.app/Contents/MacOS/Chromium"),
    ]
    
    # Check if any browser exists
    for path_pattern in possible_paths:
        if glob.glob(path_pattern):
            return True
    
    # Browsers not found, try to install them (only for local use)
    # Skip in cloud environments - they should install during build
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("RENDER") or os.getenv("STREAMLIT_SERVER_PORT"):
        # In cloud, browsers should be pre-installed
        print("⚠️  Cloud environment detected - browsers should be pre-installed")
        return True
    
    # Local installation
    if progress_callback is not None:
        progress_callback({"status": "info", "message": "Installing Playwright browsers (this may take 1-2 minutes)..."})
    print("Installing Playwright browsers...")
    
    try:
        # Run playwright install in a subprocess (async)
        process = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "playwright", "install", "chromium",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=300)
        
        if process.returncode == 0:
            print("✅ Playwright browsers installed successfully")
            if progress_callback is not None:
                progress_callback({"status": "info", "message": "✅ Playwright browsers installed successfully"})
            return True
        else:
            error_msg = stderr.decode() if stderr else "Unknown error"
            print(f"❌ Failed to install browsers: {error_msg}")
            print("💡 Try running manually: python -m playwright install chromium")
            if progress_callback is not None:
                progress_callback({"status": "error", "message": f"Failed to install Playwright browsers. Run: python -m playwright install chromium"})
            return False
    except asyncio.TimeoutError:
        error_msg = "Browser installation timed out"
        print(f"❌ {error_msg}")
        print("💡 Try running manually: python -m playwright install chromium")
        if progress_callback is not None:
            progress_callback({"status": "error", "message": error_msg})
        return False
    except Exception as e:
        print(f"Error installing browsers: {e}")
        print("💡 Try running manually: python -m playwright install chromium")
        if progress_callback is not None:
            progress_callback({"status": "error", "message": f"Error installing browsers: {str(e)[:200]}"})
        return False

async def run_scraper(zip_codes=None, progress_callback=None, filters=None):
    """
    Run the scraper for given zip codes.
    
    Args:
        zip_codes: List of zip codes (e.g., ["75001", "75002"])
        progress_callback: Optional function to call with progress updates (for dashboard)
        filters: Optional dict with filter values (min_rating, max_rating, min_reviews, country, etc.)
    """
    if zip_codes is None:
        zip_codes = AREAS  # Fallback for backward compatibility
    
    # Get country from filters or default
    country = filters.get("country", "France") if filters else "France"
    
    # Use filters from parameter or defaults
    if filters:
        min_rating = filters.get("min_rating", MIN_RATING)
        max_rating = filters.get("max_rating", MAX_RATING)
        min_reviews = filters.get("min_reviews", MIN_REVIEWS)
        max_reviews_per_business = filters.get("max_reviews_per_business", MAX_REVIEWS_PER_BUSINESS)
        min_violations_to_stop = filters.get("min_violations_to_stop", MIN_VIOLATIONS_TO_STOP)
    else:
        min_rating = MIN_RATING
        max_rating = MAX_RATING
        min_reviews = MIN_REVIEWS
        max_reviews_per_business = MAX_REVIEWS_PER_BUSINESS
        min_violations_to_stop = MIN_VIOLATIONS_TO_STOP
    
    all_leads = []
    # Removed training_data collection for optimization - uncomment if needed
    # all_training_data = []
    stats = {"found": 0, "processed": 0, "filtered": 0, "reviews": 0, "violations": 0, "leads": 0, "reviews_skipped": 0}
    
    # Track processed businesses to avoid duplicates across categories
    processed_businesses = {}  # key: business URL, value: business details
    
    # Create output directory and timestamp for incremental saving
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    # Use categories from filters if provided, otherwise use defaults
    if filters and "categories" in filters and filters["categories"]:
        categories_to_scrape = filters["categories"]
    else:
        # Default: use TIERS_TO_SCRAPE
        categories_to_scrape = []
        for tier in TIERS_TO_SCRAPE:
            for cat in CATEGORIES[tier]:
                categories_to_scrape.append({"name": cat, "tier": tier})

    print("=" * 60)
    print("  🛡️  VARDA Lead Generation Scraper")
    print("=" * 60)
    print(f"  📍 Zip codes: {zip_codes}")
    print(f"  🌍 Country: {country}")
    print(f"  🏷️  Categories: {len(categories_to_scrape)}")
    print(f"  ⭐ Rating: {min_rating} - {max_rating}")
    print(f"  📝 Min reviews: {min_reviews}")
    print(f"  📁 Results saved to: {OUTPUT_DIR}/violations_leads_*_{timestamp}.csv")
    print("=" * 60)
    
    if progress_callback:
        progress_callback({
            "status": "starting", 
            "message": f"Starting scraper for {len(zip_codes)} zip code(s)",
            "zip_codes_count": len(zip_codes)
        })
    
    # Install Playwright browsers if needed (for Streamlit Cloud)
    if progress_callback:
        progress_callback({"status": "info", "message": "Checking Playwright browsers..."})
    await install_playwright_browsers_if_needed(progress_callback)

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
        
        # Remove webdriver property and other automation indicators
        await page.add_init_script("""
            // Remove webdriver property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            
            // Override language properties
            Object.defineProperty(navigator, 'language', {
                get: function() { return 'en-US'; }
            });
            Object.defineProperty(navigator, 'languages', {
                get: function() { return ['en-US', 'en']; }
            });
            
            // Remove automation indicators
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Array;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Promise;
            delete window.cdc_adoQpoasnfa76pfcZLmcfl_Symbol;
            
            // Override permissions
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
            
            // Override plugins
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5]
            });
        """)
        
        # Set user agent to a real browser
        await page.set_extra_http_headers({
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        })

        try:
            for zip_code in zip_codes:
                print(f"\n📮 ZIP CODE: {zip_code}")
                print("-" * 50)
                
                if progress_callback:
                    progress_callback({"status": "area_start", "area": zip_code, "message": f"Processing zip code: {zip_code}"})

                for cat_info in categories_to_scrape:
                    category = cat_info["name"]
                    tier = cat_info["tier"]
                    print(f"\n🏷️  {category.upper()} (Tier {tier})")
                    
                    if progress_callback:
                        progress_callback({"status": "category_start", "category": category, "message": f"Searching {category} in {zip_code}"})

                    # Scrape businesses with IMMEDIATE filtering - rating extracted from search results
                    businesses = await scrape_all_businesses(page, zip_code, category, country, min_rating, max_rating, min_reviews, progress_callback)
                    
                    # Count total found (before filtering) - we'll estimate based on what we filtered
                    # Note: We can't know total without filtering, so we'll track filtered separately
                    total_scraped = len(businesses)  # These are already filtered
                    stats["found"] += total_scraped
                    
                    if progress_callback:
                        progress_callback({"status": "businesses_found", "count": total_scraped, "message": f"Found {total_scraped} businesses matching criteria"})

                    if not businesses:
                        continue

                    # Process businesses - they're already filtered, just get full details
                    print(f"\n   📊 Processing {len(businesses)} businesses (already filtered)...")
                    if progress_callback:
                        progress_callback({"status": "collecting_details", "current": 0, "total": len(businesses), "message": f"Processing {len(businesses)} businesses"})
                    
                    for i, biz in enumerate(businesses):
                        name_short = biz['name'][:35] + "..." if len(biz['name']) > 35 else biz['name']
                        rating = biz.get("rating", 0.0)
                        review_count = biz.get("review_count", 0)
                        
                        # Check if this business was already processed in another category
                        biz_url = biz.get("url", "")
                        if biz_url in processed_businesses:
                            continue
                        
                        print(f"\n   [{i+1}/{len(businesses)}] {name_short}")
                        print(f"      ⭐ {rating} | 📝 {review_count} reviews")
                        
                        if progress_callback:
                            progress_callback({
                                "status": "business_processing",
                                "current": i + 1,
                                "total": len(businesses),
                                "business_name": name_short,
                                "message": f"Processing business {i+1}/{len(businesses)}: {name_short}"
                            })
                        
                        # Get full business details (address, phone, website, etc.)
                        details = await scrape_business_details(page, biz)
                        if not details:
                            continue
                        
                        # Update with rating/review count from search results (more accurate)
                        details["rating"] = rating
                        details["review_count"] = review_count
                        
                        # Mark this business as processed
                        processed_businesses[biz_url] = details

                        stats["processed"] += 1

                        # Email - scrape if website is available
                        if details["website"]:
                            print(f"      🌐 Checking website for email...")
                            email = await scrape_email_from_website(page, details["website"])
                            details["email"] = email
                            if email:
                                print(f"      📧 Found: {email}")

                        # Reviews - add hl=en to force English
                        review_url = biz["url"]
                        if "hl=" not in review_url:
                            separator = "&" if "?" in review_url else "?"
                            review_url = f"{review_url}{separator}hl=en"
                        
                        if not await safe_goto(page, review_url):
                            if progress_callback:
                                progress_callback({
                                    "status": "error",
                                    "message": f"⚠️ Could not load reviews page for {name_short}"
                                })
                            continue
                        print(f"      📝 Scraping reviews (sorted by worst rating first)...")
                        if progress_callback:
                            progress_callback({
                                "status": "scraping_reviews",
                                "message": f"📝 Scraping reviews for {name_short}..."
                            })
                        reviews = await scrape_reviews(page, max_reviews_per_business)
                        print(f"      📝 Got {len(reviews)} reviews")
                        if progress_callback:
                            progress_callback({
                                "status": "reviews_collected",
                                "count": len(reviews),
                                "message": f"📝 Collected {len(reviews)} reviews for {name_short}"
                            })
                        
                        # Show rating distribution
                        if reviews:
                            rating_dist = {}
                            for r in reviews:
                                rating_dist[r["rating"]] = rating_dist.get(r["rating"], 0) + 1
                            dist_str = ", ".join([f"{k}⭐: {v}" for k, v in sorted(rating_dist.items())])
                            print(f"      📊 Rating distribution: {dist_str}")

                        if not reviews:
                            continue

                        # Classify (reviews already sorted by worst rating first)
                        # OPTIMIZATION: Stop early once we find enough violations
                        print(f"      🤖 Classifying reviews (stopping after {min_violations_to_stop} violations)...")
                        flagged_reviews = []
                        reviews_classified = 0

                        if progress_callback:
                            progress_callback({
                                "status": "classifying_reviews",
                                "message": f"🤖 Classifying {len(reviews)} reviews for {name_short}..."
                            })
                        for j, review in enumerate(reviews):
                            print(f"         {j+1}/{len(reviews)} ({review['rating']}⭐)...", end="\r")
                            if progress_callback and j % 3 == 0:  # Update every 3rd review to avoid spam
                                progress_callback({
                                    "status": "classifying_reviews",
                                    "current": j + 1,
                                    "total": len(reviews),
                                    "message": f"🤖 Classifying review {j+1}/{len(reviews)} for {name_short}..."
                                })
                            classification = classify_review(review["reviewer_name"], review["rating"], review["text"], review["date"])
                            stats["reviews"] += 1
                            reviews_classified += 1

                            # Only save to training data if violation found (saves space/time)
                            if classification["has_violation"]:
                                stats["violations"] += 1
                                flagged_reviews.append({**review, "classification": classification})
                                
                                if progress_callback:
                                    progress_callback({
                                        "status": "violation_found",
                                        "violation_count": len(flagged_reviews),
                                        "message": f"🚩 Violation #{len(flagged_reviews)} found in {name_short}'s reviews"
                                    })
                                
                                # Early exit: if we found enough violations, stop classifying
                                if len(flagged_reviews) >= min_violations_to_stop:
                                    remaining = len(reviews) - (j + 1)
                                    stats["reviews_skipped"] = stats.get("reviews_skipped", 0) + remaining
                                    print(f"         ✅ Found {len(flagged_reviews)} violations, stopping early...", end="\r")
                                    if progress_callback:
                                        progress_callback({
                                            "status": "info",
                                            "message": f"✅ Found {min_violations_to_stop} violations, stopping analysis"
                                        })
                                    break

                            await sleep(100)

                        print(f"                              ", end="\r")
                        if reviews_classified < len(reviews):
                            print(f"      ⚡ Optimized: Classified {reviews_classified}/{len(reviews)} reviews (found violations early)")

                        if flagged_reviews:
                            print(f"      🚩 {len(flagged_reviews)} violations found!")
                            stats["leads"] += 1
                            
                            # Create lead object
                            lead = {
                                "name": details["name"], "email": details["email"],
                                "website": details["website"], "phone": details["phone"],
                                "address": details["address"], "google_maps_url": details["google_maps_url"],
                                "rating": rating, "review_count": review_count,
                                "category": category, "tier": tier, "zip_code": zip_code,
                                "flagged_reviews": flagged_reviews,
                            }
                            
                            all_leads.append(lead)
                            
                            # Print detailed violation information to console
                            print_violation_details(lead, flagged_reviews)
                            
                            if progress_callback:
                                progress_callback({
                                    "status": "lead_found",
                                    "lead": lead,
                                    "violations_count": len(flagged_reviews),
                                    "message": f"🚩 LEAD FOUND: {lead['name']} - {len(flagged_reviews)} violation(s) detected!"
                                })
                            
                            # Save immediately to CSV for real-time viewing
                            try:
                                save_lead_incrementally(lead, OUTPUT_DIR, timestamp, zip_code)
                                csv_filename = f"violations_leads_{zip_code}_{timestamp}.csv"
                                print(f"      💾 Saved to: {OUTPUT_DIR}/{csv_filename}")
                                
                                if progress_callback:
                                    progress_callback({
                                        "status": "lead_found",
                                        "lead": lead,
                                        "total_leads": len(all_leads),
                                        "message": f"Found violation: {lead['name']}"
                                    })
                            except Exception as e:
                                print(f"      ⚠️  Error saving incrementally: {e}")
                        else:
                            print(f"      ✅ No violations")

        finally:
            # Don't close persistent context, just close pages
            await browser.close()

    if progress_callback:
        progress_callback({"status": "completed", "stats": stats, "leads": all_leads, "message": "Scraping completed!"})
    
    return all_leads, [], stats  # Return empty training_data list


#######################################################################
# EXPORT FUNCTIONS
#######################################################################

def export_leads(leads: list, training_data: list):
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")

    # Optimized CSV output - exactly what you need for email outreach
    if leads:
        rows = []
        for lead in leads:
            flagged = lead.get("flagged_reviews", [])
            
            # Take top 3 violations (already sorted by worst rating first)
            top_violations = flagged[:3]
            
            row = {
                "business_name": lead["name"],
                "website_url": lead.get("website", ""),
                "email": lead.get("email", ""),
                "phone": lead.get("phone", ""),
                "violations_count": len(flagged),
            }
            
            # Add 3 sample reviews with reason and confidence
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
            
            rows.append(row)

        df = pd.DataFrame(rows)
        csv_path = f"{OUTPUT_DIR}/violations_leads_{timestamp}.csv"
        df.to_csv(csv_path, index=False)
        print(f"✅ Violations CSV: {csv_path} ({len(rows)} businesses with violations)")
        
        # Also create a detailed JSON file with all violation details for reference
        json_path = f"{OUTPUT_DIR}/violations_details_{timestamp}.json"
        with open(json_path, 'w', encoding='utf-8') as f:
            json.dump(leads, f, indent=2, ensure_ascii=False)
        print(f"✅ Detailed JSON: {json_path}")

    # Training data (optional - comment out if not needed)
    # if training_data:
    #     jsonl_path = f"{OUTPUT_DIR}/training_data_{timestamp}.jsonl"
    #     with open(jsonl_path, 'w', encoding='utf-8') as f:
    #         for item in training_data:
    #             f.write(json.dumps({"text": item["text"], "rating": item["rating"],
    #                 "label": 1 if item["has_violation"] else 0,
    #                 "violation_types": item["violation_types"],
    #                 "confidence": item["confidence"], "reasoning": item["reasoning"]}, ensure_ascii=False) + '\n')
    #     print(f"✅ Training JSONL: {jsonl_path} ({len(training_data)} samples)")


#######################################################################
# RUN
#######################################################################

if __name__ == "__main__":
    print("🚀 Starting scraper...\n")
    start_time = time.time()

    leads, training_data, stats = asyncio.run(run_scraper(areas=AREAS))

    elapsed = time.time() - start_time
    print("\n" + "=" * 60)
    print("  📊 RESULTS")
    print("=" * 60)
    print(f"  ⏱️  Time: {int(elapsed//60)}m {int(elapsed%60)}s")
    print(f"  🏢 Found: {stats['found']}")
    print(f"  🔍 Processed: {stats['processed']}")
    print(f"  📝 Reviews classified: {stats['reviews']}")
    if stats.get('reviews_skipped', 0) > 0:
        print(f"  ⚡ Reviews skipped (early exit): {stats['reviews_skipped']}")
    print(f"  🚩 Violations found: {stats['violations']}")
    print(f"  🎯 Businesses with violations: {stats['leads']}")
    print(f"  💰 Potential: €{stats['violations'] * 24.99:.2f}")
    print("=" * 60)

    export_leads(leads, training_data)
    print("\n✅ Done!")