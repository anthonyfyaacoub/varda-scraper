"""
VARDA Lead Generation Scraper - Dashboard
Run with: streamlit run dashboard.py
"""

import streamlit as st
import queue
import threading
import os

# Page configuration - MUST be the FIRST Streamlit command
st.set_page_config(
    page_title="VARDA Lead Scraper",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

#######################################################################
# 🔐 AUTHENTICATION
#######################################################################

# Password protection - Set via environment variable or Streamlit secrets
# To disable: Set ACCESS_PASSWORD="" or don't set it
# To enable: Set ACCESS_PASSWORD="your_password" in environment or secrets
ACCESS_PASSWORD = os.getenv("ACCESS_PASSWORD", "")

# Try to get from Streamlit secrets (for Streamlit Cloud)
try:
    if hasattr(st, 'secrets') and 'ACCESS_PASSWORD' in st.secrets:
        ACCESS_PASSWORD = st.secrets['ACCESS_PASSWORD']
except:
    pass

# Check authentication if password is set
if ACCESS_PASSWORD:
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False
    
    if not st.session_state.authenticated:
        st.title("🔐 Authentication Required")
        password_input = st.text_input("Enter password:", type="password", key="auth_password")
        
        if st.button("Login"):
            if password_input == ACCESS_PASSWORD:
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("❌ Incorrect password. Access denied.")
                st.stop()
        else:
            st.stop()

import asyncio
import pandas as pd
from datetime import datetime
import time
import warnings
import logging

# Suppress Streamlit ScriptRunContext warnings from background threads
# This must be done before any Streamlit imports/usage
warnings.filterwarnings("ignore", message=".*ScriptRunContext.*")
warnings.filterwarnings("ignore", category=UserWarning, module="streamlit")
warnings.filterwarnings("ignore", message=".*missing ScriptRunContext.*")

# Set up logging to suppress ScriptRunContext warnings
logging.getLogger("streamlit.runtime.scriptrunner.script_runner").setLevel(logging.ERROR)
logging.getLogger("streamlit").setLevel(logging.ERROR)

# Also suppress at the root logger level for Streamlit modules
for logger_name in ["streamlit", "streamlit.runtime", "streamlit.runtime.scriptrunner"]:
    logger = logging.getLogger(logger_name)
    logger.setLevel(logging.ERROR)
    for handler in logger.handlers:
        if hasattr(handler, 'setLevel'):
            handler.setLevel(logging.ERROR)

# Import with error handling
try:
    from varda_scraper import (
        run_scraper, CATEGORIES, TIERS_TO_SCRAPE, 
        MIN_RATING, MAX_RATING, MIN_REVIEWS,
        MAX_REVIEWS_PER_BUSINESS, MIN_VIOLATIONS_TO_STOP,
        OUTPUT_DIR, export_leads
    )
except Exception as e:
    st.error(f"Error importing varda_scraper: {e}")
    import traceback
    st.code(traceback.format_exc())
    st.stop()

# Custom CSS for better styling
st.markdown("""
    <style>
    .main-header {
        font-size: 2.8rem;
        font-weight: bold;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1.5rem;
        text-align: center;
    }
    .stat-box {
        background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
        padding: 1.2rem;
        border-radius: 0.8rem;
        border-left: 5px solid #667eea;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
    }
    .lead-card {
        background: #ffffff;
        padding: 1.2rem;
        border-radius: 0.8rem;
        border: 2px solid #e0e0e0;
        margin-bottom: 1rem;
        box-shadow: 0 2px 8px rgba(0,0,0,0.08);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    .lead-card:hover {
        transform: translateY(-2px);
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .sidebar .sidebar-content {
        background: linear-gradient(180deg, #f8f9fa 0%, #e9ecef 100%);
    }
    h1, h2, h3 {
        color: #2c3e50;
    }
    .stButton>button {
        border-radius: 0.5rem;
        font-weight: 600;
        transition: all 0.3s;
    }
    .stButton>button:hover {
        transform: scale(1.02);
    }
    .metric-container {
        background: white;
        padding: 1rem;
        border-radius: 0.5rem;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    </style>
""", unsafe_allow_html=True)

# Initialize session state
if 'scraping' not in st.session_state:
    st.session_state.scraping = False
if 'leads' not in st.session_state:
    st.session_state.leads = []
if 'stats' not in st.session_state:
    st.session_state.stats = {}
if 'progress' not in st.session_state:
    st.session_state.progress = {"status": "idle", "message": "Ready to start"}
if 'csv_path' not in st.session_state:
    st.session_state.csv_path = None
if 'scraper_thread' not in st.session_state:
    st.session_state.scraper_thread = None
if 'scraper_done' not in st.session_state:
    st.session_state.scraper_done = False
if 'logs' not in st.session_state:
    st.session_state.logs = []
if 'current_business' not in st.session_state:
    st.session_state.current_business = None
if 'current_category' not in st.session_state:
    st.session_state.current_category = None
if 'current_area' not in st.session_state:
    st.session_state.current_area = None
# Use a module-level queue that can be accessed from any thread without warnings
_progress_queue = queue.Queue()

if 'progress_queue' not in st.session_state:
    st.session_state.progress_queue = _progress_queue

def update_progress(update):
    """Update progress using thread-safe queue - can be called from any thread"""
    # Use module-level queue to avoid accessing st.session_state from thread
    try:
        _progress_queue.put(update, block=False)
    except queue.Full:
        # Queue is full, skip this update
        pass
    except:
        # Any other error, skip silently
        pass

def process_progress_queue():
    """Process all pending updates from the queue - call this from main thread"""
    import datetime
    
    processed_count = 0
    max_updates_per_rerun = 50  # Limit updates per rerun to avoid blocking
    
    # Use module-level queue to avoid session state access issues
    while processed_count < max_updates_per_rerun:
        try:
            update = _progress_queue.get_nowait()
            processed_count += 1
            
            # Initialize logs if not exists
            if 'logs' not in st.session_state:
                st.session_state.logs = []
            
            # Add log entry
            log_entry = {
                "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
                "status": update.get("status", "info"),
                "message": update.get("message", ""),
                "data": {k: v for k, v in update.items() if k not in ["status", "message"]}
            }
            st.session_state.logs.append(log_entry)
            
            # Keep only last 500 log entries
            if len(st.session_state.logs) > 500:
                st.session_state.logs = st.session_state.logs[-500:]
            
            # Initialize other session state variables if needed
            if 'progress' not in st.session_state:
                st.session_state.progress = {}
            if 'leads' not in st.session_state:
                st.session_state.leads = []
            if 'stats' not in st.session_state:
                st.session_state.stats = {}
            
            # Update progress
            st.session_state.progress = update
            
            # Update current state
            if update.get("status") == "area_start":
                st.session_state.current_area = update.get("area", "")
            elif update.get("status") == "category_start":
                st.session_state.current_category = update.get("category", "")
            elif update.get("status") == "business_processing":
                st.session_state.current_business = update.get("business_name", "")
            
            if update.get("status") == "lead_found":
                lead = update.get("lead", {})
                # Avoid duplicates
                if not any(l.get("name") == lead.get("name") and l.get("website") == lead.get("website") 
                           for l in st.session_state.leads):
                    st.session_state.leads.append(lead)
            elif update.get("status") == "completed":
                st.session_state.stats = update.get("stats", {})
                st.session_state.scraping = False
                st.session_state.scraper_done = True
            elif update.get("status") == "error":
                st.session_state.progress = {"status": "error", "message": update.get("message", "Unknown error")}
                st.session_state.scraping = False
                st.session_state.scraper_done = True
        except queue.Empty:
            break
        except Exception as e:
            # Log error but continue processing
            print(f"Error processing progress update: {e}")
            break
    
    return processed_count

def run_scraper_thread(zip_codes, filters=None):
    """Run scraper in a separate thread"""
    try:
        import sys
        import platform
        
        # On Windows, we need to use ProactorEventLoopPolicy for subprocess support
        if platform.system() == 'Windows':
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            leads, training_data, stats = loop.run_until_complete(
                run_scraper(zip_codes=zip_codes, progress_callback=update_progress, filters=filters)
            )
        finally:
            loop.close()
    except Exception as e:
        import traceback
        error_msg = f"Error during scraping: {str(e)}\n{traceback.format_exc()}"
        print(f"ERROR: {error_msg}")  # Print to console for debugging
        
        # Provide helpful error message for common issues
        error_str = str(e)
        if "Executable doesn't exist" in error_str or "playwright install" in error_str.lower():
            user_message = "Playwright browsers not installed. Please run: playwright install chromium"
        elif "NotImplementedError" in error_str:
            user_message = "Windows event loop issue. Please restart the dashboard."
        else:
            user_message = f"Error: {str(e)[:200]}"  # Truncate long errors
        
        # Can't use st.error() from thread, so update progress instead
        update_progress({"status": "error", "message": user_message})

# Header
st.markdown('<div class="main-header">🛡️ VARDA Lead Generation Scraper</div>', unsafe_allow_html=True)

# Sidebar for configuration
with st.sidebar:
    st.header("⚙️ Configuration")
    
    # Zip code selection
    st.subheader("📍 Zip Codes")
    default_zip_codes = """92100
92200
92300
92400
92500
92130
92600
92160
92800
92110
78000
78100
78600
78400
78110
94300
94160
94100
94220
94000
94200
93100
93400
93500
93200
93300
91300
91120
91000
91160"""
    zip_input = st.text_area(
        "Enter zip codes (one per line)",
        value=default_zip_codes,
        help="Enter zip codes like '92100' or '78000'. One zip code per line. More accurate than area names."
    )
    zip_codes = [zip_code.strip() for zip_code in zip_input.split("\n") if zip_code.strip()]
    
    # Country selection
    country = st.selectbox(
        "Country",
        ["France", "Spain", "Germany", "Italy", "United Kingdom", "United States"],
        index=0,
        help="Select the country for the zip codes"
    )
    
    st.info(f"📌 {len(zip_codes)} zip code(s) configured for {country}")
    
    # Category selection
    st.subheader("🏷️ Categories")
    
    # Initialize selected categories in session state
    if 'selected_categories' not in st.session_state:
        # Default: all Tier 1 categories selected
        st.session_state.selected_categories = [
            {"name": cat, "tier": 1} for cat in CATEGORIES.get(1, [])
        ]
    
    # Show all available categories organized by tier
    st.write("**Select categories to scrape:**")
    
    selected_categories = []
    
    # All categories are now in Tier 1 (organized by business type)
    st.write("**Priority Categories (High Review Volume & Sensitivity):**")
    tier1_cats = CATEGORIES.get(1, [])
    tier1_selected = []
    
    # Group categories for better display
    category_groups = {
        "🍽️ Restaurants": ["restaurant", "bistro", "brasserie", "sushi restaurant", "indian restaurant"],
        "💊 Pharmacies": ["pharmacy"],
        "🔧 Car Services": ["car repair", "auto repair shop", "garage", "midas", "speedy", "mechanic", "car dealership"],
        "🦷 Dental": ["dentist", "orthodontist"],
        "🏠 Real Estate": ["real estate agency"],
        "💇 Beauty & Grooming": ["hair salon", "barber shop"],
        "✨ Aesthetic Centers": ["aesthetic clinic", "laser clinic", "botox clinic", "cryotherapy"],
        "🐾 Veterinarians": ["veterinarian"],
        "🔨 Home Services": ["plumber", "locksmith", "renovation contractor"]
    }
    
    for group_name, group_cats in category_groups.items():
        st.write(f"**{group_name}**")
        for cat in group_cats:
            if cat in tier1_cats:
                is_selected = any(c["name"] == cat and c["tier"] == 1 for c in st.session_state.selected_categories)
                if st.checkbox(cat, value=is_selected, key=f"cat_1_{cat}"):
                    tier1_selected.append({"name": cat, "tier": 1})
                elif not is_selected and cat in [c["name"] for c in st.session_state.selected_categories if c["tier"] == 1]:
                    # Keep it selected if it was already selected
                    tier1_selected.append({"name": cat, "tier": 1})
    
    # Add any remaining categories not in groups
    for cat in tier1_cats:
        if cat not in [c for group in category_groups.values() for c in group]:
            is_selected = any(c["name"] == cat and c["tier"] == 1 for c in st.session_state.selected_categories)
            if st.checkbox(cat, value=is_selected, key=f"cat_1_{cat}"):
                tier1_selected.append({"name": cat, "tier": 1})
            elif not is_selected and cat in [c["name"] for c in st.session_state.selected_categories if c["tier"] == 1]:
                tier1_selected.append({"name": cat, "tier": 1})
    
    selected_categories.extend(tier1_selected)
    
    # Tier 2 and 3 are empty now, but keep structure for future
    tier2_cats = CATEGORIES.get(2, [])
    tier3_cats = CATEGORIES.get(3, [])
    
    # Update session state
    st.session_state.selected_categories = selected_categories
    
    # Quick select buttons
    st.write("**Quick Select:**")
    quick_cols = st.columns(3)
    with quick_cols[0]:
        if st.button("✅ Select All", use_container_width=True):
            for cat in tier1_cats:
                st.session_state[f"cat_1_{cat}"] = True
            st.rerun()
    with quick_cols[1]:
        if st.button("❌ Clear All", use_container_width=True):
            for cat in tier1_cats + tier2_cats + tier3_cats:
                tier = 1 if cat in tier1_cats else (2 if cat in tier2_cats else 3)
                st.session_state[f"cat_{tier}_{cat}"] = False
            st.rerun()
    with quick_cols[2]:
        st.info(f"**{len(selected_categories)} selected**")
    
    if not selected_categories:
        st.warning("⚠️ Please select at least one category!")
    else:
        st.success(f"✅ {len(selected_categories)} category(ies) selected")
    
    # Filters - Editable from dashboard
    st.subheader("🔍 Filters")
    
    min_rating = st.slider(
        "Minimum Rating",
        min_value=0.0,
        max_value=5.0,
        value=float(MIN_RATING),
        step=0.1,
        help="Only process businesses with rating >= this value"
    )
    
    max_rating = st.slider(
        "Maximum Rating",
        min_value=0.0,
        max_value=5.0,
        value=float(MAX_RATING),
        step=0.1,
        help="Only process businesses with rating <= this value"
    )
    
    min_reviews = st.number_input(
        "Minimum Reviews",
        min_value=0,
        value=int(MIN_REVIEWS),
        step=1,
        help="Only process businesses with at least this many reviews"
    )
    
    max_reviews_per_business = st.number_input(
        "Max Reviews Per Business",
        min_value=10,
        max_value=200,
        value=int(MAX_REVIEWS_PER_BUSINESS),
        step=10,
        help="Maximum number of reviews to analyze per business"
    )
    
    min_violations_to_stop = st.number_input(
        "Stop After Violations",
        min_value=1,
        max_value=10,
        value=int(MIN_VIOLATIONS_TO_STOP),
        step=1,
        help="Stop analyzing reviews once this many violations are found"
    )

# Process progress queue - this handles updates from the background thread
updates_processed = process_progress_queue()

# Auto-refresh when scraping is active
if st.session_state.scraping:
    # Check if thread is still alive
    if st.session_state.scraper_thread and not st.session_state.scraper_thread.is_alive():
        if not st.session_state.scraper_done:
            # Thread finished but we didn't get a completion message
            st.session_state.scraping = False
            st.session_state.progress = {"status": "error", "message": "Scraper thread ended unexpectedly"}
    
    # Only rerun if we processed updates or if there are more in queue
    # Use a small delay to prevent excessive reruns
    queue_has_items = hasattr(st.session_state, 'progress_queue') and not st.session_state.progress_queue.empty()
    if updates_processed > 0 or queue_has_items:
        # Small delay to batch updates
        time.sleep(0.2)
        st.rerun()
    elif updates_processed == 0:
        # No updates, but still scraping - refresh every 2 seconds to check for new updates
        if 'last_refresh' not in st.session_state:
            st.session_state.last_refresh = time.time()
        elif time.time() - st.session_state.last_refresh > 2.0:
            st.session_state.last_refresh = time.time()
            st.rerun()

# Main content area
col1, col2 = st.columns([2, 1])

with col1:
    # Control buttons
    if not st.session_state.scraping:
        if st.button("🚀 Start Scraping", type="primary", use_container_width=True):
            if not zip_codes:
                st.error("Please enter at least one zip code!")
            else:
                if not selected_categories:
                    st.error("Please select at least one category!")
                elif not zip_codes:
                    st.error("Please enter at least one zip code!")
                else:
                    st.session_state.scraping = True
                    st.session_state.leads = []
                    st.session_state.stats = {}
                    st.session_state.progress = {"status": "starting", "message": "Initializing..."}
                    st.session_state.scraper_done = False
                    st.session_state.logs = []  # Clear logs
                    st.session_state.current_business = None
                    st.session_state.current_category = None
                    st.session_state.current_area = None
                    # Prepare filter parameters
                    filters = {
                        "min_rating": min_rating,
                        "max_rating": max_rating,
                        "min_reviews": min_reviews,
                        "max_reviews_per_business": max_reviews_per_business,
                        "min_violations_to_stop": min_violations_to_stop,
                        "categories": selected_categories,  # Pass selected categories
                        "country": country  # Pass country
                    }
                    # Start scraper in background thread
                    thread = threading.Thread(target=run_scraper_thread, args=(zip_codes, filters), daemon=True)
                    thread.start()
                    st.session_state.scraper_thread = thread
                    st.rerun()
    else:
        if st.button("⏹️ Stop Scraping", type="secondary", use_container_width=True):
            st.session_state.scraping = False
            st.warning("Scraping stopped. Results may be incomplete.")
            st.rerun()
    
    # Current Status Display with better styling
    if st.session_state.scraping:
        st.markdown("### 📍 Current Status")
        status_cols = st.columns(3)
        with status_cols[0]:
            st.markdown("""
                <div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 1rem; border-radius: 0.5rem; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">🌍 Zip Code</div>
                    <div style="font-size: 1.3rem; font-weight: bold; color: #2c3e50;">{}</div>
                </div>
            """.format(st.session_state.current_area if st.session_state.current_area else "Waiting..."), unsafe_allow_html=True)
        with status_cols[1]:
            st.markdown("""
                <div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 1rem; border-radius: 0.5rem; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">🏷️ Category</div>
                    <div style="font-size: 1.3rem; font-weight: bold; color: #2c3e50;">{}</div>
                </div>
            """.format(st.session_state.current_category if st.session_state.current_category else "Waiting..."), unsafe_allow_html=True)
        with status_cols[2]:
            business_name = st.session_state.current_business[:25] + "..." if st.session_state.current_business and len(st.session_state.current_business) > 25 else (st.session_state.current_business if st.session_state.current_business else "Waiting...")
            st.markdown("""
                <div style="background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%); padding: 1rem; border-radius: 0.5rem; text-align: center; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                    <div style="font-size: 0.9rem; color: #666; margin-bottom: 0.5rem;">🏢 Business</div>
                    <div style="font-size: 1.1rem; font-weight: bold; color: #2c3e50;">{}</div>
                </div>
            """.format(business_name), unsafe_allow_html=True)
    
    # Progress section
    st.subheader("📊 Progress")
    progress_container = st.container()
    
    with progress_container:
        status = st.session_state.progress.get("status", "idle")
        message = st.session_state.progress.get("message", "Ready")
        
        # Progress bar
        if status == "starting":
            st.progress(0.1, text="🔄 Initializing scraper...")
            st.info(f"🔄 {message}")
        elif status == "area_start":
            area = st.session_state.progress.get("area", "")
            st.progress(0.3, text=f"📍 Processing area: {area}")
            st.info(f"📍 Processing area: **{area}**")
        elif status == "category_start":
            category = st.session_state.progress.get("category", "")
            st.progress(0.5, text=f"🏷️ Searching: {category}")
            st.info(f"🏷️ Searching: **{category}**")
        elif status == "businesses_found":
            count = st.session_state.progress.get("count", 0)
            st.progress(0.6, text=f"✅ Found {count} businesses")
            st.success(f"✅ Found **{count}** businesses")
        elif status == "collecting_details":
            current = st.session_state.progress.get("current", 0)
            total = st.session_state.progress.get("total", 0)
            if total > 0:
                progress_val = 0.6 + (current / total) * 0.1
                st.progress(progress_val, text=f"📊 Collecting details: {current}/{total}")
            st.info(f"📊 Collecting details for businesses: **{current}/{total}**")
        elif status == "filtering":
            count = st.session_state.progress.get("count", 0)
            st.progress(0.65, text=f"🔍 Filtering: {count} businesses match criteria")
            st.info(f"🔍 Filtering: **{count}** businesses match your criteria")
        elif status == "business_processing":
            current = st.session_state.progress.get("current", 0)
            total = st.session_state.progress.get("total", 0)
            business_name = st.session_state.progress.get("business_name", "")
            if total > 0:
                progress_val = 0.7 + (current / total) * 0.2
                st.progress(progress_val, text=f"🔍 Processing: {current}/{total}")
            st.info(f"🔍 Processing business **{current}/{total}**: {business_name}")
        elif status == "lead_found":
            lead = st.session_state.progress.get("lead", {})
            total = st.session_state.progress.get("total_leads", 0)
            progress_val = min(0.7 + (total * 0.02), 0.95)
            st.progress(progress_val, text=f"🚩 Found {total} violation(s)")
            st.success(f"🚩 **Violation found!** {lead.get('name', 'Unknown')}")
        elif status == "completed":
            st.progress(1.0, text="✅ Scraping completed!")
            st.success("✅ Scraping completed!")
        elif status == "error":
            st.progress(0.0, text="❌ Error occurred")
            st.error(f"❌ {message}")
        else:
            if st.session_state.scraping:
                st.progress(0.1, text="🔄 Running...")
            st.info(f"ℹ️ {message}")
    
    # Live Log Viewer
    log_header_cols = st.columns([3, 1])
    with log_header_cols[0]:
        st.subheader("📝 Live Logs")
    with log_header_cols[1]:
        if st.button("🗑️ Clear Logs", key="clear_logs"):
            st.session_state.logs = []
            st.rerun()
    
    log_container = st.container()
    
    with log_container:
        if st.session_state.logs:
            # Show last 100 logs
            recent_logs = st.session_state.logs[-100:]
            
            # Create log display with color coding
            log_display = st.empty()
            log_text = ""
            
            for log in recent_logs:
                timestamp = log.get("timestamp", "")
                status = log.get("status", "info")
                status_icon = {
                    "starting": "🔄",
                    "area_start": "📍",
                    "category_start": "🏷️",
                    "businesses_found": "✅",
                    "collecting_details": "📊",
                    "filtering": "🔍",
                    "business_processing": "🔍",
                    "lead_found": "🚩",
                    "completed": "✅",
                    "error": "❌",
                    "info": "ℹ️"
                }.get(status, "ℹ️")
                
                message = log.get("message", "")
                
                # Add extra data if available
                extra_info = ""
                data = log.get("data", {})
                if status == "businesses_found" and "count" in data:
                    extra_info = f" ({data['count']} businesses)"
                elif status == "collecting_details":
                    if "current" in data and "total" in data:
                        extra_info = f" ({data['current']}/{data['total']})"
                elif status == "business_processing":
                    if "current" in data and "total" in data:
                        extra_info = f" ({data['current']}/{data['total']})"
                
                log_text += f"[{timestamp}] {status_icon} {message}{extra_info}\n"
            
            log_display.code(log_text, language=None)
            
            # Log controls
            log_controls_cols = st.columns(3)
            with log_controls_cols[0]:
                auto_scroll = st.checkbox("🔄 Auto-refresh", value=True, help="Automatically refresh logs while scraping")
            with log_controls_cols[1]:
                st.write(f"**Total logs:** {len(st.session_state.logs)}")
            with log_controls_cols[2]:
                if st.session_state.scraping and auto_scroll:
                    st.info("🔄 Auto-refreshing...")
        else:
            st.info("No logs yet. Start scraping to see activity.")
    
    # Real-time results with better styling
    st.markdown("### 🎯 Results")
    
    if st.session_state.leads:
        st.markdown(f"""
            <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 1rem; border-radius: 0.5rem; margin-bottom: 1rem; text-align: center;">
                <h3 style="color: white; margin: 0;">Found {len(st.session_state.leads)} businesses with violations</h3>
            </div>
        """, unsafe_allow_html=True)
        
        # Display leads in real-time with better cards
        for idx, lead in enumerate(st.session_state.leads, 1):
            violations_count = len(lead.get('flagged_reviews', []))
            with st.expander(f"🚩 {idx}. {lead.get('name', 'Unknown')} ({violations_count} violation{'s' if violations_count != 1 else ''})", expanded=False):
                col_a, col_b = st.columns(2)
                with col_a:
                    st.markdown("**Contact Information:**")
                    st.write(f"🌐 Website: {lead.get('website', 'N/A')}")
                    st.write(f"📧 Email: {lead.get('email', 'Not found')}")
                    st.write(f"📞 Phone: {lead.get('phone', 'N/A')}")
                with col_b:
                    st.markdown("**Business Details:**")
                    st.write(f"⭐ Rating: **{lead.get('rating', 'N/A')}**")
                    st.write(f"📝 Reviews: **{lead.get('review_count', 'N/A')}**")
                    st.write(f"🚩 Violations: **{violations_count}**")
                
                # Show top violations with better formatting
                flagged = lead.get('flagged_reviews', [])
                if flagged:
                    st.markdown("---")
                    st.markdown("**Top Violations:**")
                    for v_idx, violation in enumerate(flagged[:3], 1):
                        rating = violation.get('rating', '?')
                        reasoning = violation.get('classification', {}).get('reasoning', 'N/A')
                        st.markdown(f"""
                            <div style="background: #fff3cd; padding: 0.8rem; border-radius: 0.5rem; margin: 0.5rem 0; border-left: 4px solid #ffc107;">
                                <strong>Violation #{v_idx}:</strong> ⭐{rating}/5<br>
                                <em>{reasoning[:150]}{'...' if len(reasoning) > 150 else ''}</em>
                            </div>
                        """, unsafe_allow_html=True)
    else:
        st.info("💡 No violations found yet. Results will appear here as they are discovered.")

with col2:
    # Statistics
    st.subheader("📈 Statistics")
    
    if st.session_state.stats or st.session_state.scraping:
        stats = st.session_state.stats if st.session_state.stats else {}
        
        # Real-time stats
        stat_cols = st.columns(2)
        with stat_cols[0]:
            st.metric("🏢 Found", stats.get('found', 0))
            st.metric("🔍 Processed", stats.get('processed', 0))
            st.metric("📝 Reviews", stats.get('reviews', 0))
        with stat_cols[1]:
            st.metric("🚩 Violations", stats.get('violations', 0))
            st.metric("🎯 Leads", stats.get('leads', 0))
            if stats.get('violations', 0) > 0:
                potential = stats['violations'] * 24.99
                st.metric("💰 Potential", f"€{potential:.2f}")
        
        # Additional stats
        if stats.get('filtered', 0) > 0:
            st.divider()
            st.write("**Filter Stats:**")
            st.write(f"⏭️ Filtered out: {stats.get('filtered', 0)}")
            if stats.get('reviews_skipped', 0) > 0:
                st.write(f"⚡ Reviews skipped (early exit): {stats.get('reviews_skipped', 0)}")
        
        # Progress percentage
        if st.session_state.scraping and stats.get('found', 0) > 0:
            st.divider()
            processed_pct = (stats.get('processed', 0) / stats.get('found', 1)) * 100
            st.write(f"**Progress:** {processed_pct:.1f}% processed")
            st.progress(min(processed_pct / 100, 1.0))
    else:
        st.info("Statistics will appear here once scraping starts.")

# Download section (at the bottom)
st.divider()
st.subheader("💾 Download Results")

if st.session_state.leads:
    # Create CSV for download
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
    
    rows = []
    for lead in st.session_state.leads:
        flagged = lead.get("flagged_reviews", [])
        top_violations = flagged[:3]
        
        row = {
            "business_name": lead["name"],
            "website_url": lead.get("website", ""),
            "email": lead.get("email", ""),
            "phone": lead.get("phone", ""),
            "address": lead.get("address", ""),
            "rating": lead.get("rating", ""),
            "review_count": lead.get("review_count", ""),
            "zip_code": lead.get("zip_code", ""),
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
        
        rows.append(row)
    
    df = pd.DataFrame(rows)
    
    # Download button
    csv = df.to_csv(index=False)
    st.download_button(
        label="📥 Download CSV",
        data=csv,
        file_name=f"varda_leads_{timestamp}.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    # Show preview
    with st.expander("📋 Preview CSV"):
        st.dataframe(df, use_container_width=True)
else:
    st.info("No results to download yet. Start scraping to generate results.")

# Auto-refresh mechanism - simplified to avoid blocking
# Note: Manual refresh recommended for best experience
# The page will update when you click the refresh button or interact with the page
