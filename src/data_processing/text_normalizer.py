import re
import unicodedata

def normalize_text(text):
    """
    Normalize text by removing unnecessary characters,
    expanding shortened URLs, and unifying full-width/half-width characters.
    """
    # Remove unnecessary characters (emojis, special symbols, etc.)
    text = re.sub(r"[^\w\s@#:/]", "", text)

    # Expand shortened URLs (this requires network access and is not implemented here)
    # TODO: Implement URL expansion

    # Unify full-width/half-width characters
    text = unicodedata.normalize("NFKC", text)

    return text