"""
ML-based toxicity detection using pre-trained models.
Supports multiple backends: transformers (best), detoxify (fast), or textblob (basic).
"""

import warnings
warnings.filterwarnings('ignore')
from typing import List, Dict, Tuple
import sys
import re
from textblob import TextBlob

# Global model cache
_MODEL = None
_TOKENIZER = None
_MODEL_TYPE = None

def strip_emojis(text: str) -> str:
    """Remove emojis & weird symbols but keep punctuation."""
    return re.sub(r'[^\w\s.,!?]', '', text)

def initialize_transformers_model(model_name="unitary/toxic-bert"):
    """
    Initialize a transformers-based toxicity model.
    
    Recommended models:
    - "unitary/toxic-bert" - Good balance of speed and accuracy
    - "martin-ha/toxic-comment-model" - More detailed categories
    - "facebook/roberta-hate-speech-dynabench-r4-target" - Hate speech focused
    """
    global _MODEL, _TOKENIZER, _MODEL_TYPE
    
    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch
        
        print(f"🤖 Loading model: {model_name}")
        print("   (This may take a minute on first run...)")
        
        _TOKENIZER = AutoTokenizer.from_pretrained(model_name)
        _MODEL = AutoModelForSequenceClassification.from_pretrained(model_name)
        _MODEL.eval()  # Set to evaluation mode
        
        _MODEL_TYPE = "transformers"
        print("✅ Model loaded successfully!")
        return True
        
    except ImportError:
        print("❌ transformers not installed. Run: pip install transformers torch")
        return False
    except Exception as e:
        print(f"❌ Error loading model: {e}")
        return False


def initialize_detoxify_model():
    """
    Initialize Detoxify model (faster, easier to use).
    """
    global _MODEL, _MODEL_TYPE
    
    try:
        from detoxify import Detoxify
        
        print("🤖 Loading Detoxify model...")
        _MODEL = Detoxify('original')  # Options: 'original', 'unbiased', 'multilingual'
        _MODEL_TYPE = "detoxify"
        print("✅ Detoxify model loaded!")
        return True
        
    except ImportError:
        print("❌ detoxify not installed. Run: pip install detoxify")
        return False
    except Exception as e:
        print(f"❌ Error loading Detoxify: {e}")
        return False


def initialize_textblob_model():
    """
    Fallback: Use TextBlob for basic sentiment (not recommended for abuse detection).
    """
    global _MODEL_TYPE
    
    try:
        from textblob import TextBlob
        
        print("⚠️  Using TextBlob (basic sentiment only)")
        print("   For better results, install: pip install detoxify")
        _MODEL_TYPE = "textblob"
        return True
        
    except ImportError:
        print("❌ No ML libraries available. Install one of:")
        print("   pip install detoxify  (recommended)")
        print("   pip install transformers torch")
        print("   pip install textblob")
        return False


def auto_initialize():
    """Try to initialize the best available model."""
    # Try detoxify first (easiest and good performance)
    if initialize_detoxify_model():
        return True
    
    # Try transformers next (most flexible)
    if initialize_transformers_model():
        return True
    
    # Fallback to textblob (basic)
    if initialize_textblob_model():
        return True
    
    return False


def analyze_with_transformers(text: str) -> Dict:
    """Analyze text using transformers model."""
    import torch
    
    inputs = _TOKENIZER(text, return_tensors="pt", truncation=True, max_length=512)
    
    with torch.no_grad():
        outputs = _MODEL(**inputs)
        predictions = torch.nn.functional.softmax(outputs.logits, dim=-1)
    
    # Get labels
    labels = _MODEL.config.id2label
    scores = predictions[0].tolist()
    
    # Create result dict
    result = {label: score for label, score in zip(labels.values(), scores)}
    
    # Determine if toxic (threshold = 0.5)
    is_toxic = any(score > 0.5 for label, score in result.items() if label.lower() != 'neutral')
    
    return {
        "is_abusive": is_toxic,
        "scores": result,
        "max_score": max(result.values()),
        "max_category": max(result.items(), key=lambda x: x[1])[0]
    }


def analyze_with_detoxify(text: str) -> Dict:
    """Analyze text using Detoxify with safeguards."""
    
    cleaned_text = strip_emojis(text)
    results = _MODEL.predict(cleaned_text)

    # Filter weak signals
    filtered_scores = {k: v for k, v in results.items() if v >= 0.3}

    if filtered_scores:
        max_category, max_score = max(filtered_scores.items(), key=lambda x: x[1])
    else:
        max_category, max_score = "neutral", 0.0

    # POSITIVE SENTIMENT GUARD
    polarity = TextBlob(text).sentiment.polarity
    if polarity > 0.2:
        is_toxic = False
    else:
        is_toxic = max_score >= 0.7

    return {
        "is_abusive": is_toxic,
        "scores": results,
        "max_score": max_score,
        "max_category": max_category
    }



def analyze_with_textblob(text: str) -> Dict:
    """Basic sentiment with TextBlob (not ideal for abuse detection)."""
    from textblob import TextBlob
    
    blob = TextBlob(text)
    polarity = blob.sentiment.polarity  # -1 to 1
    
    # Very negative = potentially abusive (not accurate!)
    is_toxic = polarity < -0.5
    
    return {
        "is_abusive": is_toxic,
        "scores": {"polarity": polarity},
        "max_score": abs(polarity),
        "max_category": "negative" if polarity < 0 else "positive"
    }


def analyze_comment(text: str) -> Dict:
    """
    Analyze a single comment for toxicity.
    
    Returns:
        Dict with keys: is_abusive, scores, max_score, max_category
    """
    if _MODEL_TYPE is None:
        if not auto_initialize():
            return {
                "is_abusive": False,
                "scores": {},
                "max_score": 0.0,
                "max_category": "error",
                "error": "No model initialized"
            }
    
    try:
        if _MODEL_TYPE == "transformers":
            return analyze_with_transformers(text)
        elif _MODEL_TYPE == "detoxify":
            return analyze_with_detoxify(text)
        elif _MODEL_TYPE == "textblob":
            return analyze_with_textblob(text)
    except Exception as e:
        return {
            "is_abusive": False,
            "scores": {},
            "max_score": 0.0,
            "max_category": "error",
            "error": str(e)
        }


def analyze_batch(comments: List[str], show_progress: bool = True) -> List[Dict]:
    """
    Analyze multiple comments efficiently.
    
    Args:
        comments: List of comment strings
        show_progress: Show progress bar
        
    Returns:
        List of analysis results
    """
    if _MODEL_TYPE is None:
        if not auto_initialize():
            return []
    
    results = []
    total = len(comments)
    
    for i, comment in enumerate(comments):
        if show_progress and (i % 10 == 0 or i == total - 1):
            progress = (i + 1) / total * 100
            print(f"  📊 Progress: {i+1}/{total} ({progress:.1f}%)", end='\r')
        
        result = analyze_comment(comment)
        result["original"] = comment
        result["index"] = i
        results.append(result)
    
    if show_progress:
        print()  # New line after progress
    
    return results


def get_abusive_comments(results: List[Dict], threshold: float = 0.7) -> List[Dict]:
    abusive = []

    for result in results:
        confidence = result.get("max_score", 0)
        category = result.get("max_category", "neutral")

        if category == "neutral":
            continue

        if confidence >= threshold and result.get("is_abusive", False):
            abusive.append({
                "original": result["original"],
                "category": category,
                "confidence": confidence,
                "scores": result["scores"]
            })

    return abusive


def get_severity(score: float) -> str:
    """Convert score to severity level."""
    if score >= 0.9:
        return "severe"
    elif score >= 0.7:
        return "high"
    elif score >= 0.5:
        return "medium"
    elif score >= 0.3:
        return "low"
    else:
        return "none"


# Hybrid detection combining ML and keywords
def hybrid_ml_keyword_detection(comments: List[str], keyword_func) -> Dict:
    """
    Combine ML model with keyword detection for best results.
    
    Args:
        comments: List of comments
        keyword_func: Function that returns (is_abusive, matched_words) tuple
        
    Returns:
        Dictionary with categorized results
    """
    print("\n🔍 Running hybrid ML + Keyword detection...")
    
    # Stage 1: ML detection
    print("  🤖 Stage 1: ML analysis...")
    ml_results = analyze_batch(comments)
    ml_abusive = get_abusive_comments(ml_results, threshold=0.5)
    print(f"  ✓ ML found {len(ml_abusive)} abusive comments")
    
    # Stage 2: Keyword detection
    print("  📝 Stage 2: Keyword matching...")
    keyword_results = []
    for comment in comments:
        is_abuse, words = keyword_func(comment)
        if is_abuse:
            keyword_results.append({
                "comment": comment,
                "matched_words": words
            })
    print(f"  ✓ Keywords found {len(keyword_results)} potential violations")
    
    # Combine results
    ml_set = {r["original"] for r in ml_abusive}
    keyword_set = {r["comment"] for r in keyword_results}
    
    combined = {
        "both": [],
        "ml_only": [],
        "keyword_only": []
    }
    
    # Find overlaps
    for ml_result in ml_abusive:
        comment = ml_result["original"]
        if comment in keyword_set:
            keyword_info = next(r for r in keyword_results if r["comment"] == comment)
            combined["both"].append({
                **ml_result,
                "matched_words": keyword_info["matched_words"]
            })
        else:
            combined["ml_only"].append(ml_result)
    
    for kw_result in keyword_results:
        if kw_result["comment"] not in ml_set:
            combined["keyword_only"].append(kw_result)
    
    return combined


# Quick test function
def test_model():
    """Test the model with sample comments."""
    test_comments = [
        "This is a great post!",
        "You're an idiot",
        "I hope you die",
        "Nice pic bro",
        "Nobody cares about your opinion",
        "Beautiful photo! Where is this?",
        "You should delete your account"
    ]
    
    print("\n🧪 Testing ML model...\n")
    results = analyze_batch(test_comments, show_progress=False)
    
    for result in results:
        toxic_emoji = "🔴" if result["is_abusive"] else "🟢"
        print(f"{toxic_emoji} \"{result['original']}\"")
        print(f"   Category: {result['max_category']} | Score: {result['max_score']:.3f}")
        print()


if __name__ == "__main__":
    # Run test if executed directly
    test_model()