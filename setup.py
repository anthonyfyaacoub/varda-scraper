#!/usr/bin/env python3
"""
Simple setup script for VARDA Scraper
Run: python setup.py
"""

import subprocess
import sys
import os

def run_command(cmd, description):
    """Run a command and handle errors"""
    print(f"\n{'='*60}")
    print(f"📦 {description}")
    print(f"{'='*60}")
    try:
        result = subprocess.run(cmd, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} - Success!")
        if result.stdout:
            print(result.stdout)
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} - Failed!")
        print(f"Error: {e.stderr}")
        return False

def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║     VARDA Lead Generation Scraper - Setup Script        ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    # Check Python version
    if sys.version_info < (3, 8):
        print("❌ Python 3.8 or higher is required!")
        sys.exit(1)
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detected")
    
    # Step 1: Install Python dependencies
    if not run_command(
        f"{sys.executable} -m pip install --upgrade pip",
        "Upgrading pip"
    ):
        print("\n❌ Failed to upgrade pip. Please install pip manually.")
        sys.exit(1)
    
    if not run_command(
        f"{sys.executable} -m pip install -r requirements.txt",
        "Installing Python dependencies"
    ):
        print("\n❌ Failed to install dependencies. Check requirements.txt")
        sys.exit(1)
    
    # Step 2: Install Playwright browsers
    if not run_command(
        f"{sys.executable} -m playwright install chromium",
        "Installing Playwright Chromium browser"
    ):
        print("\n❌ Failed to install Playwright browsers.")
        print("   You may need to install system dependencies manually.")
        print("   See README.md for details.")
        sys.exit(1)
    
    # Step 3: Install system dependencies (optional, platform-specific)
    if sys.platform.startswith('linux'):
        print("\n⚠️  Linux detected. You may need to install system dependencies.")
        print("   Run: playwright install-deps chromium")
        print("   Or install manually (see README.md)")
    elif sys.platform == 'darwin':
        print("\n✅ macOS detected. System dependencies should be fine.")
    elif sys.platform == 'win32':
        print("\n✅ Windows detected. System dependencies should be fine.")
    
    # Step 4: Create .env file if it doesn't exist
    if not os.path.exists('.env'):
        print("\n" + "="*60)
        print("📝 Creating .env file")
        print("="*60)
        api_key = input("Enter your OpenAI API key: ").strip()
        if api_key:
            with open('.env', 'w') as f:
                f.write(f"OPENAI_API_KEY={api_key}\n")
                f.write("HEADLESS_MODE=false\n")
            print("✅ .env file created!")
        else:
            print("⚠️  No API key provided. You'll need to set OPENAI_API_KEY in .env")
    else:
        print("\n✅ .env file already exists")
    
    # Step 5: Create output directory
    os.makedirs('output', exist_ok=True)
    print("\n✅ Output directory ready")
    
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║                    Setup Complete! 🎉                     ║
    ╚══════════════════════════════════════════════════════════╝
    
    To run the scraper:
    
    1. Start the dashboard:
       streamlit run dashboard.py
    
    2. Open your browser:
       http://localhost:8501
    
    3. Configure and start scraping!
    
    For more details, see README.md
    """)

if __name__ == "__main__":
    main()
