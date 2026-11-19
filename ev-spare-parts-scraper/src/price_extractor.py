"""Price extraction and normalization module for Ethiopian EV spare parts.

Handles extraction of numeric prices, currency identification, outlier detection,
and missing value flags. Never converts missing prices to zero.
"""

import re
from typing import Optional, Tuple, Dict, Any


USD_TO_ETB_RATE = 155.0  # Reference exchange rate for cross-currency normalization

# Price regex patterns matching Ethiopian marketplace formats:
# "ETB 12,000", "12,000 ETB", "ETB 85,999", "12000 birr", "2.5 million birr", "$350", "350 USD"
PRICE_PATTERNS = [
    # ETB / Birr with magnitude (million / k)
    (re.compile(r"(?:etb|birr|\$|usd)?\s*(\d+(?:[.,]\d+)?)\s*(?:million|m)\s*(?:etb|birr)?", re.IGNORECASE), "ETB", 1e6),
    (re.compile(r"(?:etb|birr|\$|usd)?\s*(\d+(?:[.,]\d+)?)\s*(?:thousand|k)\s*(?:etb|birr)?", re.IGNORECASE), "ETB", 1e3),
    # Explicit ETB prefix or suffix: "ETB 12,000", "12,000 ETB", "12,000 birr"
    (re.compile(r"etb\s*[:.]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)", re.IGNORECASE), "ETB", 1.0),
    (re.compile(r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)\s*(?:etb|birr)\b", re.IGNORECASE), "ETB", 1.0),
    # USD prefix or suffix: "$350", "350 USD", "USD 350"
    (re.compile(r"\$\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)", re.IGNORECASE), "USD", 1.0),
    (re.compile(r"usd\s*[:.]?\s*(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)", re.IGNORECASE), "USD", 1.0),
    (re.compile(r"(\d{1,3}(?:,\d{3})*(?:\.\d+)?|\d+)\s*usd\b", re.IGNORECASE), "USD", 1.0),
    # Pure numbers with comma formatting if currency implied by context: "12,000"
    (re.compile(r"\b(\d{1,3}(?:,\d{3})+(?:\.\d+)?)\b"), "ETB", 1.0),
]

MISSING_PRICE_INDICATORS = [
    "price on request",
    "contact for price",
    "call for price",
    "call",
    "negotiable",
    "ask price",
    "በስልክ",
    "ደውለው ይጠይቁ",
    "ዋጋ በስልክ",
    "free",
    "n/a",
    "none",
    "unknown",
]


def clean_price_string(text: str) -> str:
    """Normalize whitespace and strip HTML artifacts from price text."""
    if not text:
        return ""
    text = re.sub(r"\s+", " ", text).strip()
    return text


def is_explicitly_missing_price(text: str) -> bool:
    """Detect whether price text explicitly indicates 'price on request'."""
    lower = clean_price_string(text).lower()
    return any(ind in lower for ind in MISSING_PRICE_INDICATORS)


def extract_price_and_currency(text: str) -> Tuple[Optional[float], Optional[str], str]:
    """
    Extract numeric price and currency from text.

    Returns:
        (advertised_price, currency, raw_price_string)
        - advertised_price: float value or None if missing. NEVER 0.0 for missing.
        - currency: 'ETB', 'USD', or None.
        - raw_price_string: original extracted text.
    """
    if not text:
        return None, None, ""

    cleaned = clean_price_string(text)

    if is_explicitly_missing_price(cleaned):
        return None, None, cleaned

    for pattern, currency, multiplier in PRICE_PATTERNS:
        match = pattern.search(cleaned)
        if match:
            raw_val_str = match.group(1).replace(",", "")
            try:
                val = float(raw_val_str) * multiplier
                # Plausibility check: EV spare parts in ETB are typically between 500 ETB and 2,000,000 ETB
                if currency == "ETB" and (val < 100 or val > 5000000):
                    continue
                if currency == "USD" and (val < 5 or val > 30000):
                    continue
                return round(val, 2), currency, match.group(0).strip()
            except (ValueError, TypeError):
                continue

    return None, None, cleaned


def normalize_to_etb(price: Optional[float], currency: Optional[str]) -> Optional[float]:
    """Convert price to ETB for uniform statistical comparison."""
    if price is None:
        return None
    if currency == "USD":
        return round(price * USD_TO_ETB_RATE, 2)
    return round(price, 2)


def is_price_outlier(price_etb: Optional[float], part_category: str) -> Tuple[bool, str]:
    """
    Check if an ETB price is a statistical or logical outlier for the given part category.
    Returns (is_outlier, reason).
    """
    if price_etb is None:
        return False, "Price missing"

    # Category-specific plausible ranges in ETB for Ethiopian market
    ranges = {
        "Brake pads": (1500, 150000),
        "Brake discs / rotors": (3000, 250000),
        "Cabin air filters": (500, 30000),
        "Wiper blades": (500, 25000),
        "Headlights": (15000, 500000),
        "Tail lights": (10000, 350000),
        "Side mirrors": (5000, 200000),
        "Bumpers (front and rear)": (15000, 600000),
        "Fenders / body panels": (10000, 400000),
        "Shock absorbers": (5000, 250000),
    }

    low, high = ranges.get(part_category, (500, 1000000))
    if price_etb < low:
        return True, f"Price {price_etb:,.0f} ETB unusually low for {part_category} (min expected: {low:,.0f} ETB)"
    if price_etb > high:
        return True, f"Price {price_etb:,.0f} ETB unusually high for {part_category} (max expected: {high:,.0f} ETB)"

    return False, "Plausible"
