"""Data cleaning, normalization, deduplication, and quality audit module.

Produces a pristine cleaned dataset from raw listings while preserving raw data integrity:
- Removes duplicate listings by canonical URL and normalized (title, price, seller) signatures.
- Normalizes model names and part categories to strict canonical values.
- Flags missing values (does NOT convert missing price to 0.0).
- Identifies price outliers and suspicious duplicates.
- Generates manual review flags for uncertain compatibility or classifications.
"""

import re
import unicodedata
from typing import List, Dict, Any, Tuple
import pandas as pd

from .price_extractor import is_price_outlier, normalize_to_etb


def normalize_title(title: str) -> str:
    """Normalize string for deduplication signature."""
    if not title:
        return ""
    norm = unicodedata.normalize("NFKC", title).lower()
    # Strip special punctuation and normalize spacing
    norm = re.sub(r"[^\w\s]", " ", norm)
    return re.sub(r"\s+", " ", norm).strip()


class DataCleaner:
    def __init__(self):
        pass

    def deduplicate(self, raw_records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Deduplicate raw listings using URL and semantic signature.

        Returns:
            (unique_records, duplicate_records)
        """
        seen_urls = set()
        seen_signatures = set()
        unique = []
        duplicates = []

        for r in raw_records:
            url = r.get("listing_url", "").strip()
            title = r.get("listing_title", "")
            price = str(r.get("advertised_price", ""))
            seller = r.get("seller_name", "").strip().lower()
            vehicle = r.get("vehicle_model", "")
            part = r.get("part_category", "")

            # 1. Exact URL match
            if url and url in seen_urls:
                duplicates.append(dict(r, dedupe_reason="Exact URL duplicate"))
                continue

            # 2. Semantic Signature: (vehicle, part, normalized title head, price)
            norm_t = normalize_title(title)[:40]
            sig = (vehicle, part, norm_t, price, seller)

            if sig in seen_signatures:
                duplicates.append(dict(r, dedupe_reason="Semantic content duplicate"))
                continue

            if url:
                seen_urls.add(url)
            seen_signatures.add(sig)
            unique.append(r)

        return unique, duplicates

    def clean_record(self, r: Dict[str, Any]) -> Dict[str, Any]:
        """Perform normalization, auditing, and quality flagging on a single record."""
        cleaned = dict(r)

        # 1. Price checks
        price_val = cleaned.get("advertised_price")
        price_num = float(price_val) if price_val not in ("", None) else None
        currency = cleaned.get("currency") or ("ETB" if price_num is not None else "")
        cleaned["currency"] = currency

        price_etb = normalize_to_etb(price_num, currency)
        part_cat = cleaned.get("part_category", "Unclassified / Other")

        is_outlier, outlier_reason = is_price_outlier(price_etb, part_cat)

        # 2. Quality review triggers
        review_reasons = []
        if price_num is None:
            review_reasons.append("Missing advertised price")
        if is_outlier:
            review_reasons.append(f"Price outlier: {outlier_reason}")
        if not cleaned.get("model_year"):
            review_reasons.append("Unspecified model year")
        if cleaned.get("vehicle_model") in ("Unknown / Non-Target", ""):
            review_reasons.append("Uncertain vehicle compatibility")
        if cleaned.get("part_category") in ("Unclassified / Other", ""):
            review_reasons.append("Unclassified part category")
        if ";" in str(cleaned.get("advertised_compatibility", "")):
            review_reasons.append("Multi-vehicle fitment claimed by seller")
        if cleaned.get("confidence_level") == "Low":
            review_reasons.append("Low algorithm confidence score")

        cleaned["manual_verification_required"] = "True" if review_reasons else "False"
        cleaned["audit_notes"] = "; ".join(review_reasons) if review_reasons else "Verified clean"

        return cleaned

    def clean_dataset(self, raw_records: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Process full raw dataset into clean records and manual review queue.

        Returns:
            (cleaned_records, manual_review_records)
        """
        unique_records, _ = self.deduplicate(raw_records)
        cleaned_list = []
        manual_review_list = []

        for r in unique_records:
            cleaned = self.clean_record(r)
            cleaned_list.append(cleaned)
            if cleaned["manual_verification_required"] == "True":
                manual_review_list.append(cleaned)

        return cleaned_list, manual_review_list
