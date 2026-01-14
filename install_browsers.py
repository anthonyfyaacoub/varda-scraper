#!/usr/bin/env python3
"""
Standalone script to install Playwright browsers
Use this if setup.py gets stuck or you need to reinstall browsers
"""

import subprocess
import sys
import os

def main():
    print("""
    ╔══════════════════════════════════════════════════════════╗
    ║        Playwright Browser Installation Script            ║
    ╚══════════════════════════════════════════════════════════╝
    """)
    
    print("📦 Installing Playwright Chromium browser...")
    print("⏳ This may take 2-5 minutes. Please be patient...")
    print("   (Downloading ~200MB of browser files)\n")
    
    try:
        # Run playwright install with real-time output
        process = subprocess.Popen(
            [sys.executable, "-m", "playwright", "install", "chromium"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # Print output in real-time
        for line in process.stdout:
            print(line, end='', flush=True)
        
        process.wait()
        
        if process.returncode == 0:
            print("\n✅ Playwright browsers installed successfully!")
            print("\nYou can now run: streamlit run dashboard.py")
            return True
        else:
            print("\n❌ Installation failed with exit code:", process.returncode)
            print("\n💡 Try these solutions:")
            print("   1. Run as Administrator (Windows) or with sudo (Linux/Mac)")
            print("   2. Check your internet connection")
            print("   3. Try: pip install --upgrade playwright")
            print("   4. Then: python -m playwright install chromium")
            return False
            
    except KeyboardInterrupt:
        print("\n\n⚠️  Installation cancelled by user.")
        return False
    except Exception as e:
        print(f"\n❌ Error: {e}")
        print("\n💡 Try running manually:")
        print("   python -m playwright install chromium")
        return False

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
