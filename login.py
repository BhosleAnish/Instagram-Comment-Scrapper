from playwright.sync_api import sync_playwright
import os

STATE_FILE = "auth_state.json"

def login_instagram():
    """
    Opens Instagram login page and saves authentication state.
    This needs to be run once before using the scraper.
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
        print("   3. Wait until you see your feed/home page")
        print("   4. Press ENTER in this terminal")
        print()
        print("⏳ Waiting for login completion...")
        
        input("➡️  Press ENTER after you've logged in: ")
        
        # Save authentication state
        context.storage_state(path=STATE_FILE)
        browser.close()
    
    if os.path.exists(STATE_FILE):
        print()
        print("✅ Login session saved successfully!")
        print(f"📁 Saved to: {STATE_FILE}")
        print()
        print("🎯 You can now run main.py to scrape comments")
    else:
        print()
        print("❌ Failed to save login session")
        print("   Please try again")

if __name__ == "__main__":
    login_instagram()