"""Shared text normalization utilities for PDF text processing."""

import re


def normalize(text: str, level: str = "standard") -> str:
    """Normalize text for comparison.

    Args:
        text: Text to normalize.
        level: Normalization level:
            - "minimal": Case folding and whitespace collapsing only.
            - "standard": Plus smart-quote/dash/section-symbol normalization.
            - "aggressive": Plus strip all punctuation.

    Returns:
        Normalized text.
    """
    # Level 1 (minimal): Case and whitespace
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)

    if level == "minimal":
        return text

    # Level 2 (standard): Quote and dash normalization
    text = re.sub(r'[\u201c\u201d\u201e\u0022]', '"', text)
    text = re.sub(r"[\u2018\u2019\u201a\u0027]", "'", text)
    text = re.sub(r"[\u2014\u2013\u002d]+", "-", text)
    text = re.sub(r"\u00a7", "section", text)

    if level == "standard":
        return text

    # Level 3 (aggressive): Remove all punctuation
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def detect_doubled_chars(text: str) -> bool:
    """Detect if text has doubled characters from PDF extraction issues.

    Some PDFs are extracted with every character duplicated:
    "UUNNIITTEEDD SSTTAATTEESS" instead of "UNITED STATES".
    Returns True if >40% of sampled long words consist of consecutive
    identical character pairs.
    """
    words = text.split()
    long_words = [w for w in words if len(w) >= 6 and w.isalpha()]

    if len(long_words) < 10:
        return False

    sample_size = min(200, len(long_words))
    step = max(1, len(long_words) // sample_size)
    sample = long_words[::step][:sample_size]

    doubled_count = 0
    for word in sample:
        if len(word) % 2 != 0:
            continue
        pairs_match = sum(
            1 for i in range(0, len(word), 2)
            if i + 1 < len(word) and word[i] == word[i + 1]
        )
        total_pairs = len(word) // 2
        if total_pairs > 0 and pairs_match / total_pairs >= 0.8:
            doubled_count += 1

    return doubled_count / len(sample) >= 0.4


def fix_doubled_chars(text: str) -> str:
    """Remove doubled characters from PDF extraction.

    Replaces consecutive identical character pairs with single characters.
    E.g., "UUNNIITTEEDD  SSTTAATTEESS" -> "UNITED STATES"
    """
    return re.sub(r"(.)\1", r"\1", text)
