"""Part category classification, position detection, and OEM specification matcher.

Enforces the exact ten required categories:
1. Brake pads
2. Brake discs / rotors
3. Cabin air filters
4. Wiper blades
5. Headlights
6. Tail lights
7. Side mirrors
8. Bumpers (front and rear)
9. Fenders / body panels
10. Shock absorbers

Extracts position (Front/Rear, Left/Right, Pair/Set), condition (new, used, refurbished),
assembly type, and potential OEM part numbers without inventing missing data.
"""

import os
import json
import re
import unicodedata
from typing import Dict, Any, List, Optional, Tuple


def normalize_part_text(text: str) -> str:
    """Normalize unicode and lowercase text for part matching."""
    if not text:
        return ""
    folded = unicodedata.normalize("NFKC", text)
    return folded.lower().strip()


class PartMatcher:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "parts.json")

        self.parts_config = []
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.parts_config = data.get("parts", [])
        else:
            # Inline fallback
            self.parts_config = [
                {"id": "brake_pads", "canonical_name": "Brake pads", "keywords": ["brake pad", "brake pads", "disc pad", "ፍሬን ሸራ", "ሸራ"]},
                {"id": "brake_discs_rotors", "canonical_name": "Brake discs / rotors", "keywords": ["brake disc", "brake rotor", "rotor", "ፍሬን ዲስክ"]},
                {"id": "cabin_air_filters", "canonical_name": "Cabin air filters", "keywords": ["cabin air filter", "cabin filter", "ac filter", "ካቢን ፊልተር"]},
                {"id": "wiper_blades", "canonical_name": "Wiper blades", "keywords": ["wiper blade", "windshield wiper", "wiper", "ዋይፐር"]},
                {"id": "headlights", "canonical_name": "Headlights", "keywords": ["headlight", "headlamp", "front lamp", "የፊት ማብራት", "የፊት መብራት", "ፋሮ"]},
                {"id": "tail_lights", "canonical_name": "Tail lights", "keywords": ["tail light", "taillight", "rear lamp", "የዋላ ፊረቻ", "የኋላ መብራት"]},
                {"id": "side_mirrors", "canonical_name": "Side mirrors", "keywords": ["side mirror", "wing mirror", "door mirror", "የጎን ስፖክይ", "ስፖክዮ"]},
                {"id": "bumpers", "canonical_name": "Bumpers (front and rear)", "keywords": ["bumper", "front bumper", "rear bumper", "ፓራወልት", "ፓራኦልት"]},
                {"id": "fenders_body_panels", "canonical_name": "Fenders / body panels", "keywords": ["fender", "wing", "quarter panel", "door skeleton", "የጎን በር"]},
                {"id": "shock_absorbers", "canonical_name": "Shock absorbers", "keywords": ["shock absorber", "shock", "damper", "strut", "አሞርዛተር", "አሞርሳተር"]},
            ]

    def extract_position(self, text: str) -> str:
        """
        Detect part physical orientation and position:
        Returns: 'Front Left', 'Front Right', 'Rear Left', 'Rear Right',
                 'Front', 'Rear', 'Left', 'Right', 'Pair / Set', or 'Unspecified'
        """
        norm = normalize_part_text(text)

        has_front = bool(re.search(r"\b(front|fwd|የፊት|ፊት)\b", norm))
        has_rear = bool(re.search(r"\b(rear|back|የኋላ|የዋላ|የዉሃላ|ኋላ)\b", norm))
        has_left = bool(re.search(r"\b(left|lh|driver\s*side|የግራ|ግራ)\b", norm))
        has_right = bool(re.search(r"\b(right|rh|passenger\s*side|የቀኝ|ቀኝ)\b", norm))
        has_pair = bool(re.search(r"\b(pair|set|both|2pcs|2\s*pieces|ጥንድ|ፊትና\s*ኋላ|ግራና\s*ቀኝ)\b", norm))

        if has_pair or (has_left and has_right) or (has_front and has_rear):
            return "Pair / Set"
        if has_front and has_left:
            return "Front Left"
        if has_front and has_right:
            return "Front Right"
        if has_rear and has_left:
            return "Rear Left"
        if has_rear and has_right:
            return "Rear Right"
        if has_front:
            return "Front"
        if has_rear:
            return "Rear"
        if has_left:
            return "Left"
        if has_right:
            return "Right"

        return "Unspecified"

    def extract_assembly_type(self, text: str) -> str:
        """Determine whether item is full assembly, glass only, cover only, etc."""
        norm = normalize_part_text(text)
        if re.search(r"\b(glass\s*only|mirror\s*glass|መስታወት\s*ብቻ)\b", norm):
            return "Glass Only"
        if re.search(r"\b(cover\s*only|cherga\s*cover|housing|shell|ካቨር)\b", norm):
            return "Cover / Housing Only"
        if re.search(r"\b(assembly|complete|ሙሉ|አሴምብሊ)\b", norm):
            return "Full Assembly"
        if re.search(r"\b(skeleton|bare\s*door|በር\s*ብቻ)\b", norm):
            return "Bare Skeleton / Panel"
        return "Standard Replacement"

    def extract_condition(self, text: str) -> str:
        """
        Extract item condition: 'new', 'used', 'refurbished', or 'unknown'.
        """
        norm = normalize_part_text(text)
        if re.search(r"\b(brand\s*new|new|አዲስ|ፋብሪካ|original\s*new)\b", norm):
            return "new"
        if re.search(r"\b(refurbished|rebuilt|reconditioned|የታደሰ)\b", norm):
            return "refurbished"
        if re.search(r"\b(used|second\s*hand|tokash|bale\s*bet|የተጠቀመ|ያገለገለ)\b", norm):
            return "used"
        return "unknown"

    def extract_oem_part_number(self, text: str) -> Optional[str]:
        """
        Extract genuine automotive OEM part numbers (e.g. 11A 941 015, BYD-48520, etc.).
        """
        if not text:
            return None
        # Common OEM formats:
        # VW: 3 digits + 1-2 letters + 3 digits + 3 digits (e.g. 11A 941 015 B or 5E0941015)
        # BYD: alphanumeric strings formatted like BYD-XXXXXXXX or 8-12 alphanumeric characters with hyphens
        patterns = [
            r"\b([0-9A-Z]{3}[\s-]?[0-9A-Z]{3}[\s-]?[0-9A-Z]{3}[A-Z]?)\b",
            r"\b(BYD[\s-]?[0-9A-Z]{5,10})\b",
            r"\bOEM\s*[:#]?\s*([0-9A-Z-]{6,14})\b",
            r"\bPart\s*(?:No|Number|#)\s*[:#]?\s*([0-9A-Z-]{6,14})\b",
        ]
        for p in patterns:
            m = re.search(p, text, re.IGNORECASE)
            if m:
                candidate = m.group(1).strip()
                # Exclude false positives like phone numbers or model years
                if not re.match(r"^\d{4}$", candidate) and not candidate.startswith("09") and not candidate.startswith("+251"):
                    return candidate
        return None

    def extract_manufacturer_or_brand(self, text: str) -> Optional[str]:
        """Extract part manufacturer / brand if mentioned."""
        norm = normalize_part_text(text)
        brands = [
            ("BYD Original", [r"\bbyd\s*original\b", r"\bbyd\s*oem\b", r"\bbyd\s*genuine\b"]),
            ("Volkswagen OEM", [r"\bvw\s*original\b", r"\bvolkswagen\s*original\b", r"\bvw\s*oem\b", r"\bvolkswagen\s*genuine\b"]),
            ("Bosch", [r"\bbosch\b"]),
            ("Brembo", [r"\bbrembo\b"]),
            ("Valeo", [r"\bvaleo\b"]),
            ("Denso", [r"\bdenso\b"]),
            ("Hella", [r"\bhella\b"]),
            ("Monroe", [r"\bmonroe\b"]),
            ("KYB", [r"\bkyb\b", r"\bkayaba\b"]),
            ("Original / OEM", [r"\boriginal\b", r"\boem\b", r"\bgenuine\b", r"\bኦሪጅናል\b"]),
            ("Aftermarket", [r"\baftermarket\b", r"\bcopy\b", r"\bኮፒ\b"]),
        ]
        for brand_name, patterns in brands:
            if any(re.search(p, norm) for p in patterns):
                return brand_name
        return None

    def match_part(self, title: str, description: str = "", attributes_str: str = "") -> Dict[str, Any]:
        """
        Classify text into one of the 10 exact categories.

        Returns dict:
        - part_category: Exact canonical name from the 10 categories, or 'Unclassified / Other'
        - part_position: Position string
        - assembly_type: Assembly string
        - condition: 'new', 'used', 'refurbished', 'unknown'
        - OEM_part_number: String or None
        - manufacturer_or_brand: String or None
        - confidence_level: 'High', 'Medium', 'Low'
        - manual_verification_required: bool
        - matching_evidence: snippet
        """
        full_text = f"{title} {description} {attributes_str}".strip()
        norm = normalize_part_text(full_text)

        matched_category = None
        matched_keyword = None
        highest_score = 0

        for part in self.parts_config:
            cat_name = part["canonical_name"]
            keywords = part.get("keywords", [])
            negatives = part.get("negative_keywords", [])

            # Check negative keywords first
            if any(re.search(rf"\b{re.escape(neg.lower())}\b", norm) for neg in negatives):
                # Only disqualify if negative keyword is present without a strong positive exact match in title
                norm_title = normalize_part_text(title)
                if not any(re.search(rf"\b{re.escape(kw.lower())}\b", norm_title) for kw in keywords):
                    continue

            for kw in keywords:
                escaped = re.escape(kw.lower())
                # Check for exact keyword match
                match = re.search(rf"\b{escaped}\b", norm)
                if match:
                    # Score priority: title match > description match, longer keyword > shorter keyword
                    score = len(kw) + (20 if re.search(rf"\b{escaped}\b", normalize_part_text(title)) else 0)
                    if score > highest_score:
                        highest_score = score
                        matched_category = cat_name
                        matched_keyword = kw

        position = self.extract_position(full_text)
        assembly_type = self.extract_assembly_type(full_text)
        condition = self.extract_condition(full_text)
        oem = self.extract_oem_part_number(full_text)
        brand = self.extract_manufacturer_or_brand(full_text)

        if not matched_category:
            return {
                "part_category": "Unclassified / Other",
                "part_position": position,
                "assembly_type": assembly_type,
                "condition": condition,
                "OEM_part_number": oem,
                "manufacturer_or_brand": brand,
                "confidence_level": "Low",
                "manual_verification_required": True,
                "matching_evidence": "No matching spare part keywords found"
            }

        # Confidence assessment
        norm_title = normalize_part_text(title)
        in_title = bool(re.search(rf"\b{re.escape(matched_keyword.lower())}\b", norm_title))

        confidence = "High" if in_title else "Medium"
        needs_review = False if in_title and position != "Unspecified" else True

        return {
            "part_category": matched_category,
            "part_position": position,
            "assembly_type": assembly_type,
            "condition": condition,
            "OEM_part_number": oem,
            "manufacturer_or_brand": brand,
            "confidence_level": confidence,
            "manual_verification_required": needs_review,
            "matching_evidence": f"Matched keyword '{matched_keyword}' (position: {position})"
        }
