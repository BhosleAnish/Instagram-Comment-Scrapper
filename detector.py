import csv
import re
from utils import normalize_text

CSV_PATH = "offensive.csv"

def load_abusive_words():
    """Load abusive words from CSV file."""
    words = set()
    
    try:
        with open(CSV_PATH, newline="", encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader, None)  # skip header row
            
            row_count = 0
            for row in reader:
                row_count += 1
                for cell in row:
                    if not cell or not cell.strip():
                        continue
                    
                    # Normalize the word
                    clean_word = normalize_text(cell.strip())
                    
                    # Ignore very short words (likely noise)
                    if len(clean_word) >= 2:
                        words.add(clean_word)
            
            print(f"✅ Loaded {len(words)} unique abusive terms from {row_count} rows")
        
    except FileNotFoundError:
        print(f"❌ CSV file '{CSV_PATH}' not found!")
    except Exception as e:
        print(f"❌ Error loading CSV: {e}")
    
    return words

# Load words once at module import (not every time function is called)
ABUSIVE_WORDS = load_abusive_words()

# Pre-compile the pattern ONCE for efficiency
if ABUSIVE_WORDS:
    sorted_words = sorted(ABUSIVE_WORDS, key=len, reverse=True)
    escaped = [re.escape(word) for word in sorted_words]
    PATTERN = re.compile(r'\b(' + '|'.join(escaped) + r')\b', re.IGNORECASE)
else:
    PATTERN = None

def is_abusive(comment):
    """Check if comment contains abusive words."""
    if not PATTERN:
        return False
    
    clean = normalize_text(comment)
    return bool(PATTERN.search(clean))

def find_abusive_words(comment):
    """Return list of abusive words found in comment."""
    if not PATTERN:
        return []
    
    clean = normalize_text(comment)
    matches = PATTERN.findall(clean)
    return list(set(matches))