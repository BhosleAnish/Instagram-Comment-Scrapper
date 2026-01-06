from playwright.sync_api import sync_playwright
import time
import os

STATE_FILE = "auth_state.json"

def click_view_replies_buttons(page):
    """Find and click all 'View replies' buttons."""
    strategies = [
        r"""
        () => {
            let clicked = 0;
            const elements = document.querySelectorAll('button, span, div[role="button"]');
            for (let el of elements) {
                const text = el.innerText?.toLowerCase() || '';
                if ((text.includes('view') && text.includes('repl')) || 
                    text.includes('view all') && text.includes('repl')) {
                    try {
                        el.click();
                        clicked++;
                    } catch(e) {}
                }
            }
            return clicked;
        }
        """,
        r"""
        () => {
            let clicked = 0;
            const spans = document.querySelectorAll('span');
            for (let span of spans) {
                const text = span.innerText?.trim() || '';
                if (/view\s+(all\s+)?\d*\s*repl/i.test(text)) {
                    let parent = span;
                    let depth = 0;
                    while (parent && depth < 5) {
                        if (parent.tagName === 'BUTTON' || parent.getAttribute('role') === 'button') {
                            try {
                                parent.click();
                                clicked++;
                                break;
                            } catch(e) {}
                        }
                        parent = parent.parentElement;
                        depth++;
                    }
                    if (depth >= 5) {
                        try {
                            span.click();
                            clicked++;
                        } catch(e) {}
                    }
                }
            }
            return clicked;
        }
        """
    ]
    
    total_clicked = 0
    for strategy in strategies:
        try:
            count = page.evaluate(strategy)
            if count > 0:
                total_clicked += count
                break
        except:
            continue
    
    return total_clicked

def extract_comments_with_links(page):
    """Extract ALL comments with flexible selectors."""
    js_code = r"""
        () => {
            const comments = [];
            const seenTexts = new Set();
            
            const blacklist = [
                'see translation', 'view all', 'view reply', 'view replies', 
                'like', 'likes', 'reply', 'meta ai', 'instagram from meta',
                'john doe', 'add a comment'
            ];
            
            const isBlacklisted = (text) => {
                const lower = text.toLowerCase().trim();
                if (/^\d+$/.test(lower)) return true;
                return blacklist.some(word => lower.includes(word));
            };
            
            const profileLinks = document.querySelectorAll('a[href^="/"][role="link"]');
            console.log(`Found ${profileLinks.length} potential profile links`);
            
            profileLinks.forEach(link => {
                const href = link.getAttribute('href');
                
                if (!href || href === '/' || href.includes('/p/') || href.includes('/reel/')) {
                    return;
                }
                
                const username = href.replace(/\//g, '').trim();
                if (!username || username.length > 40) return;
                
                let container = link.parentElement;
                let depth = 0;
                
                while (container && depth < 15) {
                    const spans = container.querySelectorAll('span');
                    if (spans.length >= 3) {
                        break;
                    }
                    container = container.parentElement;
                    depth++;
                }
                
                if (!container) return;
                
                let commentText = '';
                const spans = container.querySelectorAll('span');
                
                for (let span of spans) {
                    const text = span.innerText?.trim() || '';
                    
                    if (!text || text === username || isBlacklisted(text)) {
                        continue;
                    }
                    
                    const wordCount = text.split(/\s+/).length;
                    const hasEmoji = /[\u2600-\u27BF\uD800-\uDFFF\uE000-\uF8FF]/.test(text);
                    
                    if (wordCount >= 3 || text.length >= 10 || hasEmoji) {
                        if (!commentText || text.length > commentText.length) {
                            commentText = text;
                        }
                    }
                }
                
                if (!commentText || commentText.length < 2) return;
                
                if (seenTexts.has(commentText)) return;
                seenTexts.add(commentText);
                
                let commentLink = '';
                const allLinks = container.querySelectorAll('a[href*="/c/"]');
                if (allLinks.length > 0) {
                    commentLink = allLinks[0].href;
                }
                
                comments.push({
                    text: commentText,
                    link: commentLink,
                    username: username
                });
            });
            
            console.log(`Extracted ${comments.length} unique comments`);
            return comments;
        }
    """
    
    return page.evaluate(js_code)

def scrape_comments(post_url, max_scrolls=50, scroll_delay=1500):
    """Scrape comments from Instagram post."""
    if not os.path.exists(STATE_FILE):
        print("❌ Not logged in. Please run login.py first.")
        return []
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        context = browser.new_context(
            storage_state=STATE_FILE,
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080}
        )
        page = context.new_page()
        page.set_default_timeout(90000)
        
        print(f"🌐 Opening post...")
        try:
            page.goto(post_url, wait_until="load", timeout=60000)
            print("   ✅ Page loaded")
        except Exception as e:
            print(f"   ❌ Failed to load: {e}")
            browser.close()
            return []
        
        page.wait_for_timeout(8000)
        
        if "instagram.com" in page.url and "/accounts/login" not in page.url:
            print("   ✅ Instagram page detected")
        else:
            print("   ⚠️  May not be on correct page")
        
        print("   🔍 Checking for popups...")
        try:
            for selector in ['button:has-text("Not Now")', 'button[aria-label*="Close"]']:
                try:
                    btn = page.wait_for_selector(selector, timeout=2000)
                    if btn:
                        btn.click()
                        page.wait_for_timeout(500)
                except:
                    pass
        except:
            pass
        
        print(f"\n📜 Starting comment extraction (max {max_scrolls} scrolls)...")
        
        print("   🔍 Finding scrollable comments section...")
        comments_container = page.evaluate(r"""
            () => {
                const divs = document.querySelectorAll('div');
                for (let div of divs) {
                    const style = window.getComputedStyle(div);
                    const hasOverflow = style.overflowY === 'auto' || style.overflowY === 'scroll';
                    const hasHeight = div.scrollHeight > div.clientHeight;
                    const profileLinks = div.querySelectorAll('a[href^="/"][role="link"]');
                    
                    if (hasOverflow && hasHeight && profileLinks.length > 3) {
                        div.setAttribute('data-comments-scroll', 'true');
                        return true;
                    }
                }
                return false;
            }
        """)
        
        if comments_container:
            print("   ✅ Found scrollable comments container")
        else:
            print("   ⚠️  Couldn't find scrollable container")
        
        print("   📝 Extracting visible comments...")
        comments_data = extract_comments_with_links(page)
        print(f"   ✅ Found {len(comments_data)} initial comments")
        
        print("   🔘 Clicking initial 'View replies' buttons...")
        initial_clicks = click_view_replies_buttons(page)
        if initial_clicks > 0:
            print(f"   ✅ Clicked {initial_clicks} initial buttons")
            page.wait_for_timeout(2000)
            comments_data = extract_comments_with_links(page)
            print(f"   ✅ Total after initial replies: {len(comments_data)}")
        else:
            print(f"   ℹ️  No initial 'View replies' buttons found")
        
        previous_count = len(comments_data)
        no_new_count = 0
        
        for scroll in range(max_scrolls):
            # Extract before scrolling
            current_comments = extract_comments_with_links(page)
            
            for comment in current_comments:
                if not any(c['text'] == comment['text'] for c in comments_data):
                    comments_data.append(comment)
            
            new_count = len(comments_data) - previous_count
            
            if new_count > 0:
                print(f"   Scroll {scroll + 1}/{max_scrolls}: {len(comments_data)} comments (+{new_count})")
                previous_count = len(comments_data)
                no_new_count = 0
            else:
                no_new_count += 1
                if scroll % 5 == 0:
                    print(f"   Scroll {scroll + 1}/{max_scrolls}: {len(comments_data)} comments (no new)")
            
            # CHANGED: Increased to 8 empty scrolls instead of 5
            if no_new_count >= 8:
                print(f"   ⏹️  No new comments for 8 scrolls. Stopping.")
                break
            
            scrolled = page.evaluate(r"""
                () => {
                    const container = document.querySelector('div[data-comments-scroll="true"]');
                    if (container) {
                        const oldScroll = container.scrollTop;
                        // CHANGED: Smaller scroll increments (200px instead of 400px)
                        container.scrollTop += 200;
                        return {success: true, moved: container.scrollTop > oldScroll};
                    }
                    
                    const article = document.querySelector('article');
                    if (article) {
                        const divs = article.querySelectorAll('div');
                        for (let div of divs) {
                            const style = window.getComputedStyle(div);
                            if ((style.overflowY === 'auto' || style.overflowY === 'scroll') && 
                                div.scrollHeight > div.clientHeight) {
                                const oldScroll = div.scrollTop;
                                div.scrollTop += 200;
                                if (div.scrollTop > oldScroll) {
                                    return {success: true, moved: true, method: 'fallback'};
                                }
                            }
                        }
                    }
                    
                    return {success: false, moved: false};
                }
            """)
            
            if not scrolled.get('moved') and scroll == 0:
                print(f"   ⚠️  Warning: Scroll didn't move")
            
            page.wait_for_timeout(scroll_delay)
            
            # CHANGED: Check for replies every 3 scrolls instead of 5
            if scroll > 0 and scroll % 3 == 0:
                print(f"   🔍 Checking for 'View replies' buttons...")
                clicks = click_view_replies_buttons(page)
                if clicks > 0:
                    print(f"   ✅ Clicked {clicks} 'View replies' button(s)")
                    page.wait_for_timeout(2000)
                    
                    new_comments = extract_comments_with_links(page)
                    for comment in new_comments:
                        if not any(c['text'] == comment['text'] for c in comments_data):
                            comments_data.append(comment)
                    
                    new_after_replies = len(comments_data) - previous_count
                    if new_after_replies > 0:
                        print(f"   ✅ Added {new_after_replies} comments from replies")
                        previous_count = len(comments_data)
                        no_new_count = 0
                else:
                    print(f"   ℹ️  No 'View replies' buttons found")
        
        print(f"\n   🔘 Final pass: Clicking all remaining 'View replies'...")
        
        # First, scroll to absolute bottom to make sure all comments are loaded
        page.evaluate(r"""
            () => {
                const container = document.querySelector('div[data-comments-scroll="true"]');
                if (container) {
                    container.scrollTop = container.scrollHeight;
                } else {
                    window.scrollTo(0, document.body.scrollHeight);
                }
            }
        """)
        page.wait_for_timeout(2000)
        
        # Then scroll to top
        page.evaluate(r"""
            () => {
                const container = document.querySelector('div[data-comments-scroll="true"]');
                if (container) {
                    container.scrollTop = 0;
                } else {
                    window.scrollTo(0, 0);
                }
            }
        """)
        page.wait_for_timeout(1500)
        
        total_clicks = 0
        for attempt in range(10):
            page.evaluate(f"""
                () => {{
                    const container = document.querySelector('div[data-comments-scroll="true"]');
                    if (container) {{
                        container.scrollTop += {attempt * 200};
                    }}
                }}
            """)
            page.wait_for_timeout(600)
            
            clicks = click_view_replies_buttons(page)
            if clicks > 0:
                total_clicks += clicks
                page.wait_for_timeout(1500)
        
        if total_clicks > 0:
            print(f"   ✅ Clicked {total_clicks} more buttons in final pass")
            page.wait_for_timeout(2000)
            
            final_comments = extract_comments_with_links(page)
            for comment in final_comments:
                if not any(c['text'] == comment['text'] for c in comments_data):
                    comments_data.append(comment)
            
            print(f"   ✅ Total comments after final pass: {len(comments_data)}")
        else:
            print(f"   ℹ️  No additional reply buttons found")
        
        print(f"\n   🧹 Cleaning extracted data...")
        cleaned = []
        junk = ['see translation', 'view all', 'view repl', 'meta ai', '© 202', 
                'add a comment', 'contact uploading']
        
        for comment in comments_data:
            text = comment.get('text', '').lower()
            
            if any(j in text for j in junk):
                continue
            
            if text.isdigit():
                continue
            
            # CHANGED: Allow even shorter comments (2+ chars instead of 5+)
            # This captures "😂😂", "🐷", "no"
            if len(comment.get('text', '')) < 2:
                continue
            
            cleaned.append(comment)
        
        removed = len(comments_data) - len(cleaned)
        if removed > 0:
            print(f"   ✅ Removed {removed} junk entries")
        
        browser.close()
        print(f"\n✅ Extracted {len(cleaned)} valid comments")
        return cleaned

def get_comments_text_only(comments_data):
    """Extract text only for backward compatibility."""
    return [comment['text'] for comment in comments_data if comment.get('text')]