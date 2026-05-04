"""
Normalize user queries before routing and dataset matching.
"""
from __future__ import annotations

import re
import unicodedata

from ai_datanalysis.core.vi_vocab import VI_ABBREVIATIONS

# NOTE: do NOT expand min/max here - router INTENT_KEYWORDS checks for
# "min"/"max" directly. Expanding them breaks ranking intent detection.
ABBREVIATIONS: dict[str, str] = VI_ABBREVIATIONS


def remove_accents(text: str) -> str:
    """Convert accented Vietnamese text to ASCII for stable matching."""
    text = str(text).replace("\u0111", "d").replace("\u0110", "D")
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return ascii_text.encode("ascii", "ignore").decode("ascii")


def expand_abbreviations(text: str) -> str:
    """Expand common abbreviations using regex replacements."""
    for pattern, replacement in ABBREVIATIONS.items():
        text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)
    return text


def normalize_query(query: str) -> str:
    """
    Complete normalization pipeline:
    1. lowercase + strip
    2. remove Vietnamese accents
    3. expand abbreviations
    4. collapse whitespace
    """
    if not query:
        return ""

    query = query.lower().strip()
    query = remove_accents(query)
    query = expand_abbreviations(query)
    query = re.sub(r"\s+", " ", query)
    return query.strip()
