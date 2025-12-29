from playwright.sync_api import sync_playwright
import time
import os

STATE_FILE = "auth_state.json"

def find_comments_container(page, timeout=30):
    """
    Multi-strategy approach to find the scrollable comments section.
    Returns the selector for the comments container or None.
    """
    start_time = time.time()
    
    strategies = [
        # Strategy 1: Find by overflow property and comment content
        """
        () => {
            const divs = document.querySelectorAll('div');
            for (let div of divs) {
                const style = window.getComputedStyle(div);
                const hasOverflow = style.overflowY === 'auto' || style.overflowY === 'scroll';
                const hasComments = div.querySelectorAll('span').length > 5;
                const isScrollable = div.scrollHeight > div.clientHeight;
                
                if (hasOverflow && hasComments && isScrollable) {
                    // Generate a unique selector
                    div.setAttribute('data-comments-container', 'true');
                    return '[data-comments-container="true"]';
                }
            }
            return null;
        }
        """,
        
        # Strategy 2: Find by article and scrollable child
        """
        () => {
            const article = document.querySelector('article');
            if (!article) return null;
            
            const scrollableDivs = article.querySelectorAll('div');
            for (let div of scrollableDivs) {
                const style = window.getComputedStyle(div);
                if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && 
                    div.scrollHeight > div.clientHeight) {
                    div.setAttribute('data-comments-container', 'true');
                    return '[data-comments-container="true"]';
                }
            }
            return null;
        }
        """,
        
        # Strategy 3: Find comment elements, then scrollable parent
        """
        () => {
            const commentSpans = document.querySelectorAll('span[dir="auto"]');
            if (commentSpans.length === 0) return null;
            
            let parent = commentSpans[0].parentElement;
            while (parent && parent !== document.body) {
                const style = window.getComputedStyle(parent);
                if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && 
                    parent.scrollHeight > parent.clientHeight) {
                    parent.setAttribute('data-comments-container', 'true');
                    return '[data-comments-container="true"]';
                }
                parent = parent.parentElement;
            }
            return null;
        }
        """
    ]
    
    for strategy in strategies:
        if time.time() - start_time > timeout:
            return None
            
        try:
            selector = page.evaluate(strategy)
            if selector:
                return selector
        except:
            continue
        
        time.sleep(1)
    
    return None

def scroll_comments_section(page, container_selector, max_scrolls=20, scroll_delay=1500):
    """
    Scroll the comments section and track progress.
    Returns list of comment data with text and potential links.
    """
    comments_data = []
    previous_count = 0
    no_new_comments_count = 0
    
    for scroll in range(max_scrolls):
        # Scroll the comments container
        try:
            page.evaluate(f"""
                () => {{
                    const container = document.querySelector('{container_selector}');
                    if (container) {{
                        container.scrollTop = container.scrollHeight;
                    }}
                }}
            """)
        except:
            print(f"   ⚠️  Lost container reference, re-finding...")
            return comments_data
        
        page.wait_for_timeout(scroll_delay)
        
        # Extract comments with their links
        current_comments = extract_comments_with_links(page)
        current_count = len(current_comments)
        
        # Update comments data
        for comment in current_comments:
            if not any(c['text'] == comment['text'] for c in comments_data):
                comments_data.append(comment)
        
        # Progress indicator
        if current_count > previous_count:
            print(f"   Scroll {scroll + 1}/{max_scrolls}: {len(comments_data)} comments loaded (+{len(comments_data) - previous_count})")
            previous_count = len(comments_data)
            no_new_comments_count = 0
        else:
            no_new_comments_count += 1
            print(f"   Scroll {scroll + 1}/{max_scrolls}: {len(comments_data)} comments (no new comments)")
            
            if no_new_comments_count >= 3:
                print("   ✅ No new comments loading. Reached the end.")
                break
    
    return comments_data

def extract_comments_with_links(page):
    """
    Extract comments along with their permalink if available.
    Uses multiple strategies to find comments.
    """
    return page.evaluate("""
        () => {
            const comments = [];
            
            // Strategy 1: Look for list items with role menuitem (most common)
            let commentContainers = document.querySelectorAll('ul li[role="menuitem"]');
            
            // Strategy 2: Look for ul > div structure
            if (commentContainers.length === 0) {
                commentContainers = document.querySelectorAll('ul > div');
            }
            
            // Strategy 3: Look for spans with dir="auto" and navigate up
            if (commentContainers.length === 0) {
                const spans = document.querySelectorAll('span[dir="auto"]');
                const containerSet = new Set();
                spans.forEach(span => {
                    let parent = span.parentElement;
                    let depth = 0;
                    while (parent && depth < 10) {
                        if (parent.tagName === 'LI' || parent.tagName === 'DIV') {
                            containerSet.add(parent);
                            break;
                        }
                        parent = parent.parentElement;
                        depth++;
                    }
                });
                commentContainers = Array.from(containerSet);
            }
            
            console.log(`Found ${commentContainers.length} potential comment containers`);
            
            commentContainers.forEach(container => {
                // Find comment text - try multiple selectors
                const textSpans = container.querySelectorAll('span[dir="auto"], span[class*="x193iq5w"]');
                let commentText = '';
                
                textSpans.forEach(span => {
                    const text = span.innerText.trim();
                    // Filter out usernames (typically @mentions or short single words)
                    if (text && text.length > 2 && !text.match(/^[@#]/) && text.split(' ').length > 1) {
                        if (!commentText || text.length > commentText.length) {
                            commentText = text;
                        }
                    }
                });
                
                if (!commentText) return;
                
                // Try to find comment link (timestamp or menu button)
                let commentLink = '';
                const timeLinks = container.querySelectorAll('a[href*="/c/"]');
                if (timeLinks.length > 0) {
                    commentLink = timeLinks[0].href;
                }
                
                // Get username if available
                let username = '';
                const userLinks = container.querySelectorAll('a[role="link"]');
                if (userLinks.length > 0) {
                    const possibleUsername = userLinks[0].innerText.trim();
                    if (possibleUsername && possibleUsername.length < 50) {
                        username = possibleUsername;
                    }
                }
                
                // Only add if we have actual comment text
                if (commentText.length > 3) {
                    comments.push({
                        text: commentText,
                        link: commentLink,
                        username: username
                    });
                }
            });
            
            console.log(`Extracted ${comments.length} valid comments`);
            return comments;
        }
    """)

def scrape_comments(post_url, max_scrolls=20, scroll_delay=1500):
    """
    Scrape comments from an Instagram post.
    Properly scrolls the comments section (not the entire page).
    
    Args:
        post_url: Instagram post URL
        max_scrolls: Number of times to scroll the comments section
        scroll_delay: Delay between scrolls in milliseconds
    
    Returns:
        List of comment dictionaries with text, link, and username
    """
    if not os.path.exists(STATE_FILE):
        print("❌ Not logged in. Please run login.py first.")
        return []
    
    with sync_playwright() as p:
        # Launch in visible mode for debugging
        browser = p.chromium.launch(
            headless=False,  # Changed to False to see what's happening
            args=['--disable-blink-features=AutomationControlled']  # Avoid detection
        )
        
        # Use realistic user agent and viewport to avoid detection
        context = browser.new_context(
            storage_state=STATE_FILE,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        
        # Set longer timeout for slow networks
        page.set_default_timeout(90000)  # 90 seconds for mobile hotspot
        
        print(f"🌐 Opening post...")
        try:
            # Use load event which is more reliable than networkidle
            page.goto(post_url, wait_until="load", timeout=60000)
            print("   ✅ Page loaded (load event)")
        except Exception as e:
            print(f"   ⚠️  load timeout, trying commit...")
            try:
                # Fallback to commit (earliest event)
                page.goto(post_url, wait_until="commit", timeout=30000)
                print("   ✅ Page loaded (commit event)")
            except Exception as e2:
                print(f"   ❌ Failed to load page: {e2}")
                browser.close()
                return []
        
        print("   ⏳ Waiting for Instagram to render content...")
        
        # Wait longer for slow connections
        page.wait_for_timeout(8000)
        
        # Wait for critical elements to appear
        print("   🔍 Looking for post content...")
        article_found = False
        for attempt in range(5):
            try:
                page.wait_for_selector('article', timeout=3000)
                print("   ✅ Post article detected")
                article_found = True
                break
            except:
                if attempt < 4:
                    print(f"   ⏳ Waiting for article... (attempt {attempt + 1}/5)")
                    page.wait_for_timeout(2000)
        
        if not article_found:
            print("   ⚠️  Warning: Could not find article element")
            print("   💡 The browser window will stay open - check if the post loaded")
            print("   📸 Taking screenshot for debugging...")
            page.screenshot(path="debug_screenshot.png")
            print("   💾 Screenshot saved as debug_screenshot.png")
        
        # Additional wait for dynamic content
        page.wait_for_timeout(3000)
        
        # Try to close any popups or notifications
        print("   🔍 Checking for popups...")
        try:
            # Common popup selectors
            popup_selectors = [
                'button:has-text("Not Now")',
                'button:has-text("Not now")',
                'button[aria-label*="Close"]',
                'svg[aria-label="Close"]',
                'button:has-text("Turn On")',  # Notifications popup
            ]
            
            for selector in popup_selectors:
                try:
                    button = page.wait_for_selector(selector, timeout=2000)
                    if button:
                        button.click()
                        print(f"   ✅ Closed popup")
                        page.wait_for_timeout(1000)
                        break
                except:
                    continue
        except:
            pass
        
        print(f"🔍 Detecting comments section...")
        container_selector = find_comments_container(page, timeout=30)
        
        if not container_selector:
            print("\n⚠️  Could not automatically detect comments section after 30 seconds.")
            print("📊 Attempting to extract any visible comments...")
            
            # Try to extract comments anyway
            comments_data = extract_comments_with_links(page)
            
            if len(comments_data) > 0:
                print(f"✅ Found {len(comments_data)} comments without scrolling!")
                print("💡 These are the initially loaded comments only.")
                browser.close()
                return comments_data
            
            print("📌 SWITCHING TO MANUAL SCROLLING MODE")
            print("   Please manually scroll the comments section in the browser.")
            print("   The browser will remain open for 60 seconds for manual scrolling.")
            print()
            
            print("⏳ Waiting 60 seconds for manual scrolling...")
            print("   Scroll the comments section now!")
            page.wait_for_timeout(60000)
            
            # Extract whatever comments are visible
            comments_data = extract_comments_with_links(page)
            browser.close()
            
            print(f"✅ Extracted {len(comments_data)} comments after manual scrolling")
            return comments_data
        
        print(f"✅ Found comments section!")
        print(f"📜 Scrolling to load comments (max {max_scrolls} scrolls)...")
        
        # Scroll and extract comments
        comments_data = scroll_comments_section(page, container_selector, max_scrolls, scroll_delay)
        
        browser.close()
        
        print(f"✅ Extracted {len(comments_data)} unique comments")
        return comments_data

def get_comments_text_only(comments_data):
    """
    Extract just the text from comments data for backward compatibility.
    """
    return [comment['text'] for comment in comments_data if comment.get('text')]