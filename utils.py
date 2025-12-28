import re
import emoji
import unicodedata

def normalize_text(text):
    """
    Normalize text for abuse detection by:
    - Converting to lowercase
    - Removing emojis
    - Replacing common symbol/letter substitutions
    - Removing special characters
    - Normalizing whitespace
    """
    if not text:
        return ""

    # Unicode normalize and remove diacritics (e.g., café -> cafe)
    text = unicodedata.normalize('NFKD', text)
    text = text.encode('ascii', 'ignore').decode('ascii')
    
    # Convert to lowercase
    text = text.lower()
    
    # Remove emojis
    text = emoji.replace_emoji(text, replace="")
    
    # Replace common symbol tricks and leetspeak
    replacements = {
        "☪️": "c",
        "✝️": "t",
        "@": "a",
        "4": "a",
        "3": "e",
        "0": "o",
        "1": "i",
        "5": "s",
        "7": "t",
        "$": "s",
        "!": "i",
        "*": "",
        "+": "t",
        "8": "b",
        "9": "g",
        "|": "i",
        "/": "",
        "\\": "",
        "(": "",
        ")": "",
        "-": "",
        "_": " "
    }
    
    for symbol, letter in replacements.items():
        text = text.replace(symbol, letter)

    # Collapse repeated characters (sooooo -> soo)
    text = re.sub(r'(.)\1{2,}', r'\1\1', text)
    
    # Remove all non-alphabetic characters except spaces
    text = re.sub(r"[^a-z ]", "", text)
    
    # Normalize whitespace (multiple spaces to single space)
    text = re.sub(r"\s+", " ", text).strip()
    
    return text