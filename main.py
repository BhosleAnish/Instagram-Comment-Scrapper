import argparse
import json
from datetime import datetime
from scraper import scrape_comments
from detector import is_abusive, find_abusive_words
from utils import normalize_text

# Define make_json_serializable locally
def make_json_serializable(obj):
    """Convert numpy/torch types to Python native types for JSON serialization."""
    if isinstance(obj, dict):
        return {k: make_json_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [make_json_serializable(item) for item in obj]
    elif isinstance(obj, (bool, type(None), str)):
        return obj
    elif hasattr(obj, 'item'):  # numpy scalar
        return obj.item()
    elif hasattr(obj, 'tolist'):  # numpy array
        return obj.tolist()
    else:
        try:
            return float(obj)
        except (TypeError, ValueError):
            return str(obj)

# Try to import ML detector
try:
    from ml_detector import (
        analyze_batch, 
        get_abusive_comments, 
        hybrid_ml_keyword_detection,
        get_severity
    )
    ML_AVAILABLE = True
except ImportError as e:
    ML_AVAILABLE = False
    print(f"⚠️  ML detection not available: {e}")
    print("   Install: pip install detoxify")

def get_post_url():
    """
    Prompt user to enter Instagram post URL.
    Validates the URL format.
    """
    print("\n" + "=" * 70)
    print("📋 ENTER INSTAGRAM POST URL")
    print("=" * 70)
    
    while True:
        print("\nPlease paste the Instagram post URL:")
        print("Example: https://www.instagram.com/p/ABC123xyz/")
        print()
        url = input("➡️  URL: ").strip()
        
        # Basic validation
        if not url:
            print("\n❌ URL cannot be empty. Please try again.")
            continue
        
        if "instagram.com" not in url.lower():
            print("\n❌ Invalid URL. Must be an Instagram URL.")
            continue
        
        if "/p/" not in url and "/reel/" not in url:
            print("\n❌ Invalid format. URL should contain /p/ or /reel/")
            continue
        
        print(f"\n✅ URL accepted!")
        return url

def detect_with_keyword_func(comment):
    """Wrapper for keyword detection."""
    if is_abusive(comment):
        return True, find_abusive_words(comment)
    return False, []

def save_results(comments, results_data, post_url, filename="results.json", detection_mode="keyword"):
    """Save results to JSON file with better structure."""
    from datetime import datetime
    import json
    
    results = {
        "scan_metadata": {
            "post_url": post_url,
            "scan_time": datetime.now().isoformat(),
            "detection_mode": detection_mode,
            "total_comments_scanned": len(comments),
        }
    }
    
    if detection_mode == "keyword":
        results["summary"] = {
            "total_abusive": len(results_data),
            "abuse_rate": f"{len(results_data)/len(comments)*100:.1f}%" if comments else "0%"
        }
        results["abusive_comments"] = results_data
        
    elif detection_mode == "ml":
        # Group by severity
        severity_breakdown = {"severe": 0, "high": 0, "medium": 0, "low": 0}
        for item in results_data:
            severity_breakdown[item.get("severity", "low")] += 1
        
        results["summary"] = {
            "total_abusive": len(results_data),
            "abuse_rate": f"{len(results_data)/len(comments)*100:.1f}%" if comments else "0%",
            "severity_breakdown": severity_breakdown
        }
        results["abusive_comments"] = results_data
        
    elif detection_mode == "hybrid":
        total_abusive = len(results_data["both"]) + len(results_data["ml_only"]) + len(results_data["keyword_only"])
        results["summary"] = {
            "total_abusive": total_abusive,
            "abuse_rate": f"{total_abusive/len(comments)*100:.1f}%" if comments else "0%",
            "detection_breakdown": {
                "caught_by_both": len(results_data["both"]),
                "ml_only": len(results_data["ml_only"]),
                "keyword_only": len(results_data["keyword_only"])
            }
        }
        results["abusive_comments"] = results_data
    
    # Ensure everything is JSON serializable
    results = make_json_serializable(results)
    
    # Save JSON
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n💾 Results saved to {filename}")
    
    # Also save as CSV for easy viewing in Excel
    save_results_as_csv(results, results_data, detection_mode, filename.replace('.json', '.csv'))

def save_results_as_csv(results, results_data, detection_mode, filename="results.csv"):
    """Save results as CSV for easy viewing."""
    import csv
    
    try:
        with open(filename, 'w', newline='', encoding='utf-8') as f:
            if detection_mode == "keyword":
                writer = csv.writer(f)
                writer.writerow(['#', 'Comment', 'Username', 'Matched Keywords', 'Comment Link'])
                for i, item in enumerate(results_data, 1):
                    writer.writerow([
                        i,
                        item.get('original', ''),
                        item.get('username', ''),
                        ', '.join(item.get('matched_words', [])),
                        item.get('link', '')
                    ])
            
            elif detection_mode == "ml":
                writer = csv.writer(f)
                writer.writerow(['#', 'Comment', 'Username', 'Severity', 'Confidence', 'Category', 'Comment Link'])
                for i, item in enumerate(results_data, 1):
                    writer.writerow([
                        i,
                        item.get('original', ''),
                        item.get('username', ''),
                        item.get('severity', '').upper(),
                        f"{item.get('confidence', 0):.2%}",
                        item.get('category', ''),
                        item.get('link', '')
                    ])
            
            elif detection_mode == "hybrid":
                writer = csv.writer(f)
                writer.writerow(['#', 'Detection Method', 'Comment', 'Username', 'Details', 'Comment Link'])
                
                idx = 1
                for item in results_data.get('both', []):
                    writer.writerow([
                        idx,
                        'BOTH (High Confidence)',
                        item.get('original', ''),
                        item.get('username', ''),
                        f"Keywords: {', '.join(item.get('matched_words', []))} | ML: {item.get('category', '')} ({item.get('confidence', 0):.2%})",
                        item.get('link', '')
                    ])
                    idx += 1
                
                for item in results_data.get('ml_only', []):
                    writer.writerow([
                        idx,
                        'ML Only',
                        item.get('original', ''),
                        item.get('username', ''),
                        f"{item.get('severity', '').upper()} | {item.get('category', '')} ({item.get('confidence', 0):.2%})",
                        item.get('link', '')
                    ])
                    idx += 1
                
                for item in results_data.get('keyword_only', []):
                    writer.writerow([
                        idx,
                        'Keyword Only',
                        item.get('comment', ''),
                        item.get('username', ''),
                        f"Matched: {', '.join(item.get('matched_words', []))}",
                        item.get('link', '')
                    ])
                    idx += 1
        
        print(f"📊 Results also saved as CSV: {filename}")
    except Exception as e:
        print(f"   ⚠️  Could not save CSV: {e}")

def keyword_detection(comments, comment_map):
    """Original keyword-based detection."""
    print("\n🔍 Running keyword detection...")
    abusive_data = []
    
    for comment in comments:
        if is_abusive(comment):
            normalized = normalize_text(comment)
            words_found = find_abusive_words(comment)
            
            # Get comment metadata (link, username)
            metadata = comment_map.get(comment, {})
            
            # If not found, try partial match
            if not metadata:
                for map_text, map_data in comment_map.items():
                    if comment in map_text or map_text in comment:
                        metadata = map_data
                        break
            
            abusive_data.append({
                "original": comment,
                "normalized": normalized,
                "matched_words": words_found,
                "link": metadata.get('link', ''),
                "username": metadata.get('username', '')
            })
    
    # Count metadata
    with_username = sum(1 for c in abusive_data if c.get('username'))
    with_link = sum(1 for c in abusive_data if c.get('link'))
    
    print(f"   ✅ Found {len(abusive_data)} abusive comments")
    print(f"   📊 Metadata status:")
    print(f"      - {with_username}/{len(abusive_data)} have usernames")
    print(f"      - {with_link}/{len(abusive_data)} have comment links")
    
    return abusive_data

def ml_detection(comments, comment_map, threshold=0.5):
    """ML-based toxicity detection."""
    print(f"\n🔍 Running ML detection (threshold: {threshold})...")
    print(f"   Analyzing {len(comments)} comments...")
    
    # Analyze all comments
    all_results = analyze_batch(comments, show_progress=True)
    
    print(f"   ✅ Analysis complete")
    print(f"   🔍 Filtering abusive comments (threshold: {threshold})...")
    
    # Filter abusive ones
    abusive_comments = get_abusive_comments(all_results, threshold=threshold)
    
    print(f"   ✅ Found {len(abusive_comments)} abusive comments")
    print(f"   📝 Adding metadata (username, links)...")
    
    # Add severity levels and metadata
    for comment in abusive_comments:
        comment["severity"] = get_severity(comment["confidence"])
        
        # Add link and username from comment_map
        comment_text = comment.get("original", "")
        metadata = comment_map.get(comment_text, {})
        
        comment["link"] = metadata.get('link', '')
        comment["username"] = metadata.get('username', '')
        
        # Debug: Check if metadata was found
        if not metadata:
            # Try to find partial match (in case of text differences)
            for map_text, map_data in comment_map.items():
                if comment_text in map_text or map_text in comment_text:
                    comment["link"] = map_data.get('link', '')
                    comment["username"] = map_data.get('username', '')
                    break
    
    # Count how many have metadata
    with_username = sum(1 for c in abusive_comments if c.get('username'))
    with_link = sum(1 for c in abusive_comments if c.get('link'))
    
    print(f"   📊 Metadata status:")
    print(f"      - {with_username}/{len(abusive_comments)} have usernames")
    print(f"      - {with_link}/{len(abusive_comments)} have comment links")
    
    return abusive_comments

def display_keyword_results(results, comments):
    """Display keyword detection results."""
    print("\n" + "=" * 70)
    print("📊 RESULTS (KEYWORD DETECTION)")
    print("=" * 70)
    print(f"Total comments scanned: {len(comments)}")
    print(f"Abusive comments found: {len(results)}")
    if comments:
        print(f"Abuse rate: {len(results)/len(comments)*100:.1f}%")
    print("=" * 70)
    
    if results:
        print("\n⚠️  ABUSIVE COMMENTS:\n")
        for i, data in enumerate(results, 1):
            print(f"{i}. {data['original']}")
            print(f"   Normalized: {data['normalized']}")
            print(f"   🔍 Matched: {', '.join(data['matched_words'])}")
            if data.get('username'):
                print(f"   👤 User: {data['username']}")
            if data.get('link'):
                print(f"   🔗 Link: {data['link']}")
            print()
    else:
        print("\n✅ No abusive comments detected!")

def display_ml_results(results, comments):
    """Display ML detection results."""
    print("\n" + "=" * 70)
    print("📊 RESULTS (ML DETECTION)")
    print("=" * 70)
    print(f"Total comments scanned: {len(comments)}")
    print(f"Abusive comments found: {len(results)}")
    if comments:
        print(f"Abuse rate: {len(results)/len(comments)*100:.1f}%")
    
    if results:
        # Group by severity
        severity_groups = {}
        for r in results:
            sev = r["severity"]
            if sev not in severity_groups:
                severity_groups[sev] = []
            severity_groups[sev].append(r)
        
        print("\nBreakdown by severity:")
        for sev in ["severe", "high", "medium", "low"]:
            if sev in severity_groups:
                print(f"  {sev.upper()}: {len(severity_groups[sev])}")
        
        print("=" * 70)
        
        print("\n⚠️  ALL ABUSIVE COMMENTS:\n")
        for i, data in enumerate(results, 1):
            severity_emoji = {
                "severe": "🔴",
                "high": "🟠",
                "medium": "🟡",
                "low": "🟢"
            }.get(data["severity"], "⚪")
            
            print(f"{i}. {severity_emoji} {data['original']}")
            print(f"   Severity: {data['severity'].upper()} ({data['confidence']:.2%})")
            print(f"   Category: {data['category']}")
            
            # Show username and link
            if data.get('username'):
                print(f"   👤 User: {data['username']}")
            if data.get('link'):
                print(f"   🔗 Link: {data['link']}")
            
            # Show top scores
            if data.get("scores"):
                top_scores = sorted(data["scores"].items(), key=lambda x: x[1], reverse=True)[:3]
                score_str = ", ".join([f"{k}: {v:.2%}" for k, v in top_scores])
                print(f"   Scores: {score_str}")
            print()
    else:
        print("\n✅ No abusive comments detected!")

def display_hybrid_results(results, comments):
    """Display hybrid detection results."""
    total = len(results['both']) + len(results['ml_only']) + len(results['keyword_only'])
    
    print("\n" + "=" * 70)
    print("📊 RESULTS (HYBRID DETECTION)")
    print("=" * 70)
    print(f"Total comments scanned: {len(comments)}")
    print(f"Abusive comments found: {total}")
    if comments:
        print(f"Abuse rate: {total/len(comments)*100:.1f}%")
    print()
    print("Detection breakdown:")
    print(f"  ✓ Caught by BOTH methods: {len(results['both'])}")
    print(f"  ✓ ML only: {len(results['ml_only'])}")
    print(f"  ✓ Keyword only: {len(results['keyword_only'])}")
    print("=" * 70)
    
    if results['both']:
        print("\n✅ CAUGHT BY BOTH METHODS (High Confidence):\n")
        for i, data in enumerate(results['both'], 1):
            print(f"{i}. {data['original']}")
            print(f"   Keywords: {', '.join(data['matched_words'])}")
            print(f"   ML Category: {data['category']} ({data['confidence']:.2%})")
            print()
    
    if results['ml_only']:
        print("\n🤖 ML ONLY (Keywords missed - Context-based abuse):\n")
        for i, data in enumerate(results['ml_only'], 1):
            print(f"{i}. {data['original']}")
            print(f"   Severity: {data['severity'].upper()} ({data['confidence']:.2%})")
            print(f"   Category: {data['category']}")
            print()
    
    if results['keyword_only']:
        print("\n📝 KEYWORD ONLY (ML disagrees - Possible false positives):\n")
        for i, data in enumerate(results['keyword_only'], 1):
            print(f"{i}. {data['comment']}")
            print(f"   Matched: {', '.join(data['matched_words'])}")
            print()

def main():
    parser = argparse.ArgumentParser(description="Instagram comment abuse detector with ML")
    parser.add_argument('--post', '-p', default=None, help='Post URL to scan (optional - will prompt if not provided)')
    parser.add_argument('--mode', '-m', choices=['keyword', 'ml', 'hybrid'], default='ml',
                       help='Detection mode: keyword (fast), ml (accurate), hybrid (both)')
    parser.add_argument('--threshold', '-t', type=float, default=0.7,
                       help='ML confidence threshold (0.0-1.0, default: 0.7)')
    parser.add_argument('--test', action='store_true',
                       help='Test ML model with sample comments')
    parser.add_argument('--scrolls', '-s', type=int, default=50,
                       help='Number of scrolls to load comments (default: 50)')
    parser.add_argument('--scroll-delay', '-d', type=int, default=1500,
                       help='Delay between scrolls in ms (default: 1500)')
    args = parser.parse_args()
    
    # Test mode
    if args.test:
        if not ML_AVAILABLE:
            print("❌ ML detection not available for testing")
            print("   Install: pip install detoxify")
            return
        from ml_detector import test_model
        test_model()
        return
    
    # Check if ML is available for ml/hybrid modes
    if args.mode in ['ml', 'hybrid'] and not ML_AVAILABLE:
        print("❌ ML detection requires installation:")
        print("   pip install detoxify")
        print("\n   Alternative: pip install transformers torch")
        return
    
    # Print header
    print("=" * 70)
    print("📱 INSTAGRAM COMMENT ABUSE DETECTOR")
    print("=" * 70)
    
    # Get post URL from user input or command line argument
    if args.post:
        post_url = args.post
        print(f"\n✅ Using provided URL: {post_url}")
    else:
        post_url = get_post_url()
    
    print("\n" + "=" * 70)
    print("⚙️  DETECTION SETTINGS")
    print("=" * 70)
    print(f"   Mode: {args.mode.upper()}")
    if args.mode in ['ml', 'hybrid']:
        print(f"   Threshold: {args.threshold}")
    print(f"   Max scrolls: {args.scrolls}")
    print(f"   Scroll delay: {args.scroll_delay}ms")
    print("=" * 70)
    
    # Scrape comments
    print(f"\n🎯 Target Post: {post_url}")
    print()
    
    comments_data = scrape_comments(post_url, max_scrolls=args.scrolls, scroll_delay=args.scroll_delay)
    
    if not comments_data:
        print("\n❌ No comments found. Please check:")
        print("   - You're logged in (run login.py)")
        print("   - The post URL is correct")
        print("   - The post has comments")
        return
    
    # Extract text for compatibility with detection functions
    from scraper import get_comments_text_only
    comments = get_comments_text_only(comments_data)
    
    # Create a mapping of comment text to full data (for links)
    comment_map = {c['text']: c for c in comments_data if c.get('text')}
    
    print(f"\n📊 Comment extraction summary:")
    print(f"   Total comments: {len(comments)}")
    print(f"   Comments with usernames: {sum(1 for c in comments_data if c.get('username'))}")
    print(f"   Comments with links: {sum(1 for c in comments_data if c.get('link'))}")
    
    # Save all extracted comments for debugging
    try:
        with open("all_comments_debug.json", "w", encoding="utf-8") as f:
            json.dump(comments_data, f, indent=2, ensure_ascii=False)
        print(f"   💾 Debug: All comments saved to all_comments_debug.json")
    except:
        pass
    
    # Debug: Show sample of comment_map
    if len(comment_map) > 0:
        sample = list(comment_map.items())[0]
        print(f"\n   📝 Sample comment data:")
        print(f"      Text: {sample[0][:50]}...")
        print(f"      Username: {sample[1].get('username', 'N/A')}")
        print(f"      Link: {'Yes' if sample[1].get('link') else 'No'}")
    
    # Run detection based on mode
    if args.mode == 'keyword':
        results = keyword_detection(comments, comment_map)
        display_keyword_results(results, comments)
        
    elif args.mode == 'ml':
        results = ml_detection(comments, comment_map, threshold=args.threshold)
        display_ml_results(results, comments)
        
    elif args.mode == 'hybrid':
        results = hybrid_ml_keyword_detection(comments, detect_with_keyword_func)
        display_hybrid_results(results, comments)
    
    # Save results
    save_results(comments, results, post_url, detection_mode=args.mode)
    
    print("\n" + "=" * 70)
    print("💡 TIPS:")
    print("   • Results saved in both JSON and CSV formats")
    print("   • Open results.csv in Excel for easy viewing")
    print("   • Adjust threshold: --threshold 0.3 (more sensitive) or 0.7 (less false positives)")
    print("   • Load more comments: --scrolls 100 (default: 50)")
    print("   • Faster/slower scrolling: --scroll-delay 1000 (default: 1500ms)")
    print("=" * 70)

if __name__ == "__main__":
    main()