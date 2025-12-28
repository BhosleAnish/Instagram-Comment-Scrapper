from playwright.sync_api import sync_playwright, TimeoutError
import time

STATE_FILE = "auth_state.json"

def scrape_comments(post_url, max_scrolls=15, scroll_delay=2000):
    """
    Scrapes comments from an Instagram post.
    """
    comments = []
    
    with sync_playwright() as p:
        print("🚀 Launching browser...")
        
        # Launch with stealth settings
        browser = p.chromium.launch(
            headless=False,
            slow_mo=100,  # Slow down actions to appear more human
            args=[
                '--disable-blink-features=AutomationControlled',
                '--disable-dev-shm-usage',
                '--no-sandbox'
            ]
        )
        
        try:
            context = browser.new_context(
                storage_state=STATE_FILE,
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
            )
        except FileNotFoundError:
            print(f"❌ Auth state file '{STATE_FILE}' not found. Run login.py first.")
            browser.close()
            return []
        
        page = context.new_page()
        
        # Add extra stealth
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
        """)
        
        try:
            # Clean URL
            clean_url = post_url.split("?")[0]
            
            print(f"🔄 Navigating to: {clean_url}")
            print("⏳ This may take 30-60 seconds...")
            
            # Navigate with longer timeout and wait for load
            page.goto(clean_url, wait_until="load", timeout=90000)
            
            # Wait for page to settle
            print("⏳ Waiting for page to load...")
            time.sleep(5)
            
            # Check if we're actually logged in
            try:
                if page.locator("text=Log in").count() > 0:
                    print("❌ Not logged in! Please run login.py again.")
                    browser.close()
                    return []
            except:
                pass
            
            # Close any popups
            print("🔄 Checking for popups...")
            popup_texts = ["Not Now", "Not now", "Cancel", "Close"]
            for text in popup_texts:
                try:
                    page.click(f"button:has-text('{text}')", timeout=2000)
                    print(f"  ✓ Closed '{text}' popup")
                    time.sleep(1)
                except:
                    pass
            
            # Scroll page to trigger lazy loading
            print("🔄 Scrolling page...")
            for i in range(5):
                page.evaluate("window.scrollBy(0, 300)")
                time.sleep(0.5)
            
            # Wait for comments to appear
            print("⏳ Waiting for comments to load...")
            time.sleep(3)
            
            # Try to find and click "View all comments"
            print("🔄 Looking for 'View all comments'...")
            view_patterns = [
                'View all .* comments',
                'View .* comments',
                'comments'
            ]
            
            for pattern in view_patterns:
                try:
                    # Use regex to match
                    elements = page.locator(f"text=/{pattern}/i").all()
                    if elements:
                        elements[0].click(timeout=3000)
                        print("  ✓ Clicked to view all comments")
                        time.sleep(3)
                        break
                except Exception as e:
                    continue
            
            # Scroll within comments section
            print(f"🔄 Loading comments (this may take a while)...")
            last_height = 0
            no_change_count = 0
            
            for i in range(max_scrolls):
                # Scroll to bottom
                current_height = page.evaluate("document.body.scrollHeight")
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(scroll_delay / 1000)
                
                # Check if page height changed
                new_height = page.evaluate("document.body.scrollHeight")
                
                if new_height == last_height:
                    no_change_count += 1
                    if no_change_count >= 3:
                        print("  ℹ No more content loading")
                        break
                else:
                    no_change_count = 0
                    print(f"  ↓ Scroll {i+1}/{max_scrolls}")
                
                last_height = new_height
            
            print("✅ Finished loading")
            time.sleep(2)
            
            # Save screenshot for debugging
            try:
                page.screenshot(path="debug_screenshot.png", full_page=True)
                print("📸 Screenshot saved: debug_screenshot.png")
            except:
                pass
            
            # Extract comments
            print("🔄 Extracting comments...")
            
            # Get page HTML for debugging
            html_content = page.content()
            
            # Check if comments section exists
            if 'comment' in html_content.lower() or 'reply' in html_content.lower():
                print("  ✓ Found comments section in HTML")
            else:
                print("  ⚠ Comments section might not be loaded")
            
            # Multiple extraction strategies
            all_texts = set()
            
            # Strategy 1: Look for spans with dir attribute (common for comments)
            try:
                spans = page.locator("span[dir]").all()
                print(f"  📊 Found {len(spans)} span[dir] elements")
                for span in spans:
                    try:
                        txt = span.inner_text().strip()
                        if 5 < len(txt) < 500:
                            all_texts.add(txt)
                    except:
                        pass
            except Exception as e:
                print(f"  ⚠ Strategy 1 failed: {e}")
            
            # Strategy 2: All spans
            try:
                all_spans = page.locator("span").all()
                print(f"  📊 Found {len(all_spans)} total span elements")
                for span in all_spans[:1000]:  # Limit to first 1000
                    try:
                        txt = span.inner_text().strip()
                        if (5 < len(txt) < 500 and
                            not txt.startswith('http') and
                            txt.lower() not in ['reply', 'like', 'view', 'load more', 'view replies']):
                            all_texts.add(txt)
                    except:
                        pass
            except Exception as e:
                print(f"  ⚠ Strategy 2 failed: {e}")
            
            # Strategy 3: Look for article content
            try:
                articles = page.locator("article span").all()
                print(f"  📊 Found {len(articles)} article span elements")
                for span in articles:
                    try:
                        txt = span.inner_text().strip()
                        if 5 < len(txt) < 500:
                            all_texts.add(txt)
                    except:
                        pass
            except Exception as e:
                print(f"  ⚠ Strategy 3 failed: {e}")
            
            comments = list(all_texts)
            
            # Filter out common UI text
            ui_keywords = ['view', 'reply', 'like', 'follow', 'share', 'save', 'more', 'ago', 'hour', 'day', 'week']
            filtered_comments = []
            
            for comment in comments:
                comment_lower = comment.lower()
                # Keep if it doesn't match common UI patterns
                if not any(comment_lower == kw or comment_lower.startswith(kw + ' ') for kw in ui_keywords):
                    filtered_comments.append(comment)
            
            print(f"✅ Extracted {len(filtered_comments)} comments (filtered from {len(comments)} text elements)")
            
        except TimeoutError:
            print("❌ Page load timeout.")
            print("💡 Try:")
            print("   1. Check your internet connection")
            print("   2. Open the URL manually in browser to see if it loads")
            print("   3. Run login.py again")
        except Exception as e:
            print(f"❌ Error: {e}")
        finally:
            print("⏳ Closing browser...")
            time.sleep(2)
            browser.close()
    
    return filtered_comments