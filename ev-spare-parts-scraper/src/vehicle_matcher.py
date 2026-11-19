"""Vehicle matching and compatibility identification module.

Matches listings against the three target EV models:
1. BYD Seagull (aliases: Seagull, Dolphin Mini, Atto 1)
2. BYD Yuan Up (aliases: Yuan Up, Atto 2)
3. Volkswagen ID.6 (aliases: VW ID.6, ID6, ID.6 Crozz, ID.6 X)

Strictly enforces negative patterns (e.g. bare 'ID', 'ID.4', 'caller ID', 'Yuan Plus')
and identifies multi-vehicle compatibility claims requiring manual verification.
"""

import os
import json
import re
import unicodedata
from typing import Dict, Any, List, Optional, Tuple


def normalize_text(text: str) -> str:
    """Normalize unicode (NFKC) and lowercase text for robust regex matching."""
    if not text:
        return ""
    folded = unicodedata.normalize("NFKC", text)
    return folded.lower().strip()


class VehicleMatcher:
    def __init__(self, config_path: Optional[str] = None):
        if config_path is None:
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            config_path = os.path.join(base_dir, "config", "vehicles.json")

        self.vehicles = []
        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.vehicles = data.get("vehicles", [])
        else:
            # Fallback inline configuration if config file is absent
            self.vehicles = [
                {
                    "canonical_name": "BYD Seagull",
                    "manufacturer": "BYD",
                    "aliases": ["byd seagull", "seagull", "dolphin mini", "atto 1", "በይድ ሲጋል", "ሲጋል"],
                    "negative_patterns": [r"\bbyd\s*seal\b", r"\bbyd\s*song\b", r"\bbyd\s*han\b", r"\bbyd\s*tang\b"],
                    "typical_years": ["2023", "2024", "2025"],
                    "platform": "BYD e-Platform 3.0",
                },
                {
                    "canonical_name": "BYD Yuan Up",
                    "manufacturer": "BYD",
                    "aliases": ["byd yuan up", "yuan up", "atto 2", "ዩዋን አፕ", "ይዋን አፕ"],
                    "negative_patterns": [r"\byuan\s*plus\b", r"\batto\s*3\b", r"\byuan\s*pro\b"],
                    "typical_years": ["2024", "2025"],
                    "platform": "BYD e-Platform 3.0",
                },
                {
                    "canonical_name": "Volkswagen ID.6",
                    "manufacturer": "Volkswagen",
                    "aliases": [
                        "volkswagen id.6", "volkswagen id6", "vw id.6", "vw id6",
                        "id.6 crozz", "id.6 x", "id6 crozz", "id6 x", "id.6", "id6",
                        "ፎልክስዋገን አይዲ 6", "አይዲ 6"
                    ],
                    "negative_patterns": [
                        r"\bvolkswagen\s*id\.?\s*[34]\b",
                        r"\bvw\s*id\.?\s*[34]\b",
                        r"\bid\.?\s*[34]\b(?!.*id\.?\s*6)",
                        r"\bid\.?\s*buzz\b",
                        r"\bcaller\s*id\b",
                        r"\bid\s*card\b",
                        r"\bnational\s*id\b",
                    ],
                    "typical_years": ["2021", "2022", "2023", "2024", "2025"],
                    "platform": "Volkswagen MEB Platform",
                },
            ]

    def extract_model_year(self, text: str) -> Optional[str]:
        """Extract plausible automotive model year (2018 - 2026)."""
        if not text:
            return None
        # Look for 4-digit year bounded by non-digits
        matches = re.findall(r"\b(20(?:1[89]|2[0-6]))\b", text)
        if matches:
            # Prefer the most recent year mentioned if multiple
            return sorted(matches, reverse=True)[0]
        return None

    def find_all_mentioned_vehicles(self, text: str) -> List[Dict[str, Any]]:
        """Identify all potential target vehicle matches in text."""
        norm = normalize_text(text)
        found = []

        for v in self.vehicles:
            canonical = v["canonical_name"]
            aliases = v.get("aliases", [])
            negative_patterns = v.get("negative_patterns", [])

            # Check if any negative pattern dominates and disqualifies
            disqualified = False
            for neg in negative_patterns:
                # If negative pattern matches and NO specific positive alias matches strongly
                if re.search(neg, norm, re.IGNORECASE):
                    # For ID.6, if "id4 id6" is mentioned, it is a shared part!
                    # Only disqualify if ID.6 is NOT explicitly mentioned
                    if canonical == "Volkswagen ID.6" and re.search(r"\b(id\.?\s*6|id6)\b", norm):
                        disqualified = False
                    elif canonical == "BYD Yuan Up" and re.search(r"\b(yuan\s*up|atto\s*2)\b", norm):
                        disqualified = False
                    else:
                        disqualified = True
                        break

            if disqualified:
                continue

            # Check positive aliases with word boundaries
            matched_alias = None
            for alias in aliases:
                escaped = re.escape(alias.lower())
                # Allow flexible whitespace and dots for models like id.6 or id 6
                flex_pattern = escaped.replace(r"\ ", r"\s*").replace(r"\.", r"[\.\s]?")
                if re.search(rf"\b{flex_pattern}\b", norm):
                    matched_alias = alias
                    break

            if matched_alias:
                found.append({
                    "canonical_name": canonical,
                    "matched_alias": matched_alias,
                    "platform": v.get("platform", ""),
                    "manufacturer": v.get("manufacturer", "")
                })

        return found

    def match_vehicle(self, title: str, description: str = "", attributes_str: str = "") -> Dict[str, Any]:
        """
        Classify listing into target vehicles.

        Returns dict with:
        - vehicle_model: Canonical name (e.g. 'BYD Seagull') or comma-separated if multiple
        - model_year: Extracted year string or None
        - advertised_compatibility: Raw compatibility string
        - confidence_level: 'High', 'Medium', 'Low'
        - manual_verification_required: bool
        - matching_evidence: snippet
        """
        full_text = f"{title} {description} {attributes_str}".strip()
        matches = self.find_all_mentioned_vehicles(full_text)
        model_year = self.extract_model_year(full_text)

        if not matches:
            return {
                "vehicle_model": "Unknown / Non-Target",
                "model_year": model_year,
                "advertised_compatibility": title[:100],
                "confidence_level": "Low",
                "manual_verification_required": True,
                "matching_evidence": "No target EV vehicle aliases found"
            }

        # Check for multi-vehicle listing
        if len(matches) > 1:
            models = [m["canonical_name"] for m in matches]
            models_str = "; ".join(models)
            evidence = f"Multiple models claimed: {models_str} (aliases: {[m['matched_alias'] for m in matches]})"
            return {
                "vehicle_model": models[0],  # Primary matched vehicle
                "all_matched_models": models,
                "model_year": model_year,
                "advertised_compatibility": models_str,
                "confidence_level": "Medium",
                "manual_verification_required": True,
                "matching_evidence": evidence
            }

        # Single vehicle match
        matched = matches[0]
        canonical = matched["canonical_name"]
        alias = matched["matched_alias"]

        # High confidence if title directly starts with or prominently contains canonical or strong alias
        norm_title = normalize_text(title)
        high_conf = bool(re.search(rf"\b{re.escape(alias.lower())}\b", norm_title))

        return {
            "vehicle_model": canonical,
            "all_matched_models": [canonical],
            "model_year": model_year,
            "advertised_compatibility": f"{canonical} (matched: '{alias}')",
            "confidence_level": "High" if high_conf else "Medium",
            "manual_verification_required": False if high_conf and model_year else True,
            "matching_evidence": f"Found alias '{alias}' in text"
        }
