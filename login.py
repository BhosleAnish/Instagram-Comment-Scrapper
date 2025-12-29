from playwright.sync_api import sync_playwright
import os
import time
import subprocess
import sys

STATE_FILE = "auth_state.json"

def is_logged_in(page):
    """
    Check if user is logged in by looking for indicators on the page.
    Returns True if logged in, False otherwise.
    """
    try:
        # Check for common logged-in indicators
        # Method 1: Check if we're redirected away from login page
        current_url = page.url
        if '/accounts/login' not in current_url:
            # Check for home feed or profile indicators
            if any(indicator in current_url for indicator in ['/', '/direct/', '/explore/']):
                return True
        
        # Method 2: Check for profile picture/avatar (indicates logged in)
        avatar_selectors = [
            'img[alt*="profile picture"]',
            'span[role="link"] img',
            'a[href*="/"] img[alt]'
        ]
        
        for selector in avatar_selectors:
            try:
                element = page.query_selector(selector)
                if element:
                    return True
            except:
                continue
        
        # Method 3: Check if login form is NOT present
        login_button = page.query_selector('button[type="submit"]')
        if not login_button:
            # If there's no login button and we're not on login page, likely logged in
            if '/accounts/login' not in current_url:
                return True
        
        return False
    except Exception as e:
        print(f"   Error checking login status: {e}")
        return False

def login_instagram():
    """
    Opens Instagram login page and automatically detects when user logs in.
    Then automatically runs main.py.
    """
    print("=" * 70)
    print("🔐 INSTAGRAM LOGIN")
    print("=" * 70)
    print()
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()
        
        print("🌐 Opening Instagram login page...")
        page.goto("https://www.instagram.com/accounts/login/")
        
        print()
        print("📝 Instructions:")
        print("   1. Log in to your Instagram account manually")
        print("   2. Complete any 2FA if required")
        print("   3. The script will automatically detect when you're logged in")
        print()
        print("⏳ Waiting for login (timeout: 60 seconds)...")
        print("   Checking every 10 seconds...")
        print()
        
        # Wait for login with timeout (60 seconds = 6 checks with 10 second intervals)
        max_attempts = 6
        attempt = 0
        logged_in = False
        
        while attempt < max_attempts:
            attempt += 1
            print(f"🔍 Check {attempt}/{max_attempts}...", end=" ")
            
            if is_logged_in(page):
                print("✅ Logged in!")
                logged_in = True
                break
            else:
                print("⏳ Not yet logged in")
                if attempt < max_attempts:
                    time.sleep(10)
        
        if not logged_in:
            print()
            print("⏱️  TIMEOUT: You didn't log in within 60 seconds")
            print("   Please try again and log in faster")
            browser.close()
            return False
        
        # Save authentication state
        print()
        print("💾 Saving login session...")
        context.storage_state(path=STATE_FILE)
        browser.close()
    
    if os.path.exists(STATE_FILE):
        print()
        print("✅ Login session saved successfully!")
        print(f"📁 Saved to: {STATE_FILE}")
        print()
        print("=" * 70)
        print("🚀 AUTOMATICALLY RUNNING MAIN.PY")
        print("=" * 70)
        print()
        
        # Automatically run main.py
        try:
            subprocess.run([sys.executable, "main.py"], check=True)
        except subprocess.CalledProcessError as e:
            print(f"\n❌ Error running main.py: {e}")
        except FileNotFoundError:
            print("\n❌ main.py not found in current directory")
        
        return True
    else:
        print()
        print("❌ Failed to save login session")
        print("   Please try again")
        return False

if __name__ == "__main__":
    login_instagram()