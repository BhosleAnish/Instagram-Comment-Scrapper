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

# Configure your post URL here
POST_URL = "https://www.instagram.com/p/DRGQ0nIEwMz/c/17931983388134521/"


def detect_with_keyword_func(comment):
    """Wrapper for keyword detection."""
    if is_abusive(comment):
        return True, find_abusive_words(comment)
    return False, []


def save_results(comments, results_data, filename="results.json", detection_mode="keyword"):
    """Save results to JSON file."""
    results = {
        "post_url": POST_URL,
        "scan_time": datetime.now().isoformat(),
        "detection_mode": detection_mode,
        "total_comments": len(comments),
    }
    
    if detection_mode == "keyword":
        results["abusive_count"] = len(results_data)
        results["abusive_comments"] = results_data
        
    elif detection_mode == "ml":
        results["abusive_count"] = len(results_data)
        results["abusive_comments"] = results_data
        
    elif detection_mode == "hybrid":
        total_abusive = len(results_data["both"]) + len(results_data["ml_only"]) + len(results_data["keyword_only"])
        results["abusive_count"] = total_abusive
        results["detection_breakdown"] = {
            "caught_by_both": len(results_data["both"]),
            "ml_only": len(results_data["ml_only"]),
            "keyword_only": len(results_data["keyword_only"])
        }
        results["abusive_comments"] = results_data
    
    # Ensure everything is JSON serializable
    results = make_json_serializable(results)
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"💾 Results saved to {filename}")


def keyword_detection(comments):
    """Original keyword-based detection."""
    print("\n🔍 Running keyword detection...")
    abusive_data = []
    
    for comment in comments:
        if is_abusive(comment):
            normalized = normalize_text(comment)
            words_found = find_abusive_words(comment)
            abusive_data.append({
                "original": comment,
                "normalized": normalized,
                "matched_words": words_found
            })
    
    return abusive_data


def ml_detection(comments, threshold=0.5):
    """ML-based toxicity detection."""
    print(f"\n🔍 Running ML detection (threshold: {threshold})...")
    
    # Analyze all comments
    all_results = analyze_batch(comments, show_progress=True)
    
    # Filter abusive ones
    abusive_comments = get_abusive_comments(all_results, threshold=threshold)
    
    # Add severity levels
    for comment in abusive_comments:
        comment["severity"] = get_severity(comment["confidence"])
    
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
    print("=" * 70)
    
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
        
        print("\n⚠️  ABUSIVE COMMENTS:\n")
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
    parser.add_argument('--post', '-p', default=POST_URL, help='Post URL to scan')
    parser.add_argument('--mode', '-m', choices=['keyword', 'ml', 'hybrid'], default='ml',
                       help='Detection mode: keyword (fast), ml (accurate), hybrid (both)')
    parser.add_argument('--threshold', '-t', type=float, default=0.7,
                       help='ML confidence threshold (0.0-1.0, default: 0.5)')
    parser.add_argument('--test', action='store_true',
                       help='Test ML model with sample comments')
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
    
    print("=" * 70)
    print("📱 INSTAGRAM COMMENT ABUSE DETECTOR")
    print(f"   Mode: {args.mode.upper()}")
    if args.mode in ['ml', 'hybrid']:
        print(f"   Threshold: {args.threshold}")
    print("=" * 70)
    print()
    
    # Scrape comments
    print(f"🎯 Target Post: {args.post}")
    print()
    
    comments = scrape_comments(args.post, max_scrolls=20, scroll_delay=1500)
    
    if not comments:
        print("\n❌ No comments found. Please check:")
        print("   - You're logged in (run login.py)")
        print("   - The post URL is correct")
        print("   - The post has comments")
        return
    
    # Run detection based on mode
    if args.mode == 'keyword':
        results = keyword_detection(comments)
        display_keyword_results(results, comments)
        
    elif args.mode == 'ml':
        results = ml_detection(comments, threshold=args.threshold)
        display_ml_results(results, comments)
        
    elif args.mode == 'hybrid':
        results = hybrid_ml_keyword_detection(comments, detect_with_keyword_func)
        display_hybrid_results(results, comments)
    
    # Save results
    save_results(comments, results, detection_mode=args.mode)
    
    print("\n" + "=" * 70)
    print("\n💡 TIP: Adjust threshold with --threshold 0.3 (more sensitive)")
    print("        or --threshold 0.7 (less false positives)")


if __name__ == "__main__":
    main()