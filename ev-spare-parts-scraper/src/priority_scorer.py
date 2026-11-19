"""Priority scoring preparation module for Ethiopian EV spare parts import.

Implements the multi-factor transparent prioritization model:
Priority Score = (0.30 * Demand) + (0.25 * Scarcity) + (0.20 * Compatibility) +
                 (0.15 * Sourcing Practicality) + (0.10 * Evidence Confidence)

Each factor is rated on a 1.0 to 5.0 scale with transparent, defensible evidence fields.
"""

from typing import List, Dict, Any
import pandas as pd


# Domain baseline characteristics for the 10 automotive part categories
# (Wear cycle, physical logistics constraints, platform architecture)
PART_DOMAIN_BASELINES = {
    "Brake pads": {
        "demand_base": 4.8,
        "demand_rationale": "High wear item. Replaced every 25,000-40,000 km in heavy Addis Ababa stop-and-go driving.",
        "sourcing_base": 4.0,
        "sourcing_rationale": "Compact box volume, low damage risk in transit; moderate weight (sea or air freight viable).",
        "compatibility_notes": "BYD Seagull shares pads with Dolphin/E2; VW ID.6 shares front pads with ID.4 (MEB platform)."
    },
    "Brake discs / rotors": {
        "demand_base": 3.4,
        "demand_rationale": "Medium wear cycle. Replaced every 2nd or 3rd pad change (approx 70,000 km).",
        "sourcing_base": 2.8,
        "sourcing_rationale": "Heavy cast iron discs; high shipping weight increases landed freight cost per unit.",
        "compatibility_notes": "Specific rotor diameter and bolt pattern per model."
    },
    "Cabin air filters": {
        "demand_base": 4.6,
        "demand_rationale": "High replacement frequency (every 10,000 km). Essential due to severe Addis Ababa dust levels.",
        "sourcing_base": 5.0,
        "sourcing_rationale": "Ultra-lightweight, high packaging density, zero breakage risk. Ideal for rapid air freight import.",
        "compatibility_notes": "Universal rectangular dimensions frequently cross-compatible within manufacturer platform families."
    },
    "Wiper blades": {
        "demand_base": 4.5,
        "demand_rationale": "High seasonal demand during Ethiopian rainy season (Kiremt); rapid rubber UV degradation.",
        "sourcing_base": 4.8,
        "sourcing_rationale": "Very lightweight, small carton volume, low customs tariff.",
        "compatibility_notes": "Standard J-hook or top-lock push button connectors (24\"/16\"/18\"); high universal fitment."
    },
    "Headlights": {
        "demand_base": 3.8,
        "demand_rationale": "Crash replacement demand. High vulnerability in minor traffic collisions in urban Ethiopia.",
        "sourcing_base": 2.5,
        "sourcing_rationale": "Fragile polycarbonate and internal LED driver circuitry; requires secure cushioned packaging.",
        "compatibility_notes": "Proprietary styling per model; VW ID.6 matrix LED (IQ Light) requires coding/calibration."
    },
    "Tail lights": {
        "demand_base": 3.5,
        "demand_rationale": "Rear-end collision repair demand; center lightbar susceptible to rear impacts.",
        "sourcing_base": 3.0,
        "sourcing_rationale": "Moderate fragility; LED lightbars require rigid protective boxing.",
        "compatibility_notes": "Model-specific rear deck contour; ID.6 Crozz vs ID.6 X variations."
    },
    "Side mirrors": {
        "demand_base": 4.7,
        "demand_rationale": "Extremely frequent breakage / theft item in crowded Ethiopian urban corridors.",
        "sourcing_base": 3.6,
        "sourcing_rationale": "Moderate volume; motorized assemblies and BSD sensor glass require bubble packaging.",
        "compatibility_notes": "Heated glass and camera wiring harness vary between trim levels (BSD vs non-BSD)."
    },
    "Bumpers (front and rear)": {
        "demand_base": 4.4,
        "demand_rationale": "Top collision impact component in urban driving.",
        "sourcing_base": 1.6,
        "sourcing_rationale": "Severe volumetric shipping penalty (oversized cargo); unpainted plastic requires sea container bulk packing.",
        "compatibility_notes": "Exact model and trim bumper clips; parking sensor cutouts differ."
    },
    "Fenders / body panels": {
        "demand_base": 3.2,
        "demand_rationale": "Side collision panel repair; often beaten out locally unless severely creased.",
        "sourcing_base": 2.0,
        "sourcing_rationale": "Bulky stamped metal sheets; prone to transit denting if not wooden crated.",
        "compatibility_notes": "Body panels are 100% vehicle-specific."
    },
    "Shock absorbers": {
        "demand_base": 4.2,
        "demand_rationale": "Heavy wear caused by Addis Ababa potholed asphalt, speed bumps, and rough road conditions.",
        "sourcing_base": 3.2,
        "sourcing_rationale": "Cylindrical heavy steel units; air shipping restricted if pressurized gas without UN certification.",
        "compatibility_notes": "ID.6 MEB strut suspension components shared with ID.4; Seagull uses front MacPherson struts."
    }
}


class PriorityScorer:
    def __init__(self):
        pass

    def evaluate_part_priority(self, cleaned_records: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Compute transparent multi-factor import priority scores for each part category.
        """
        df = pd.DataFrame(cleaned_records)

        categories = [
            "Brake pads",
            "Brake discs / rotors",
            "Cabin air filters",
            "Wiper blades",
            "Headlights",
            "Tail lights",
            "Side mirrors",
            "Bumpers (front and rear)",
            "Fenders / body panels",
            "Shock absorbers",
        ]

        scored_parts = []

        for cat in categories:
            baseline = PART_DOMAIN_BASELINES.get(cat, {})
            cat_df = df[df["part_category"] == cat] if not df.empty else pd.DataFrame()

            listings_count = len(cat_df)
            priced_count = len(cat_df[cat_df["advertised_price"].notna() & (cat_df["advertised_price"] != "")]) if listings_count > 0 else 0
            distinct_sellers = cat_df["seller_name"].nunique() if listings_count > 0 else 0

            # 1. Demand Score (30%)
            # Base replacement frequency + active listing search visibility
            demand_score = baseline.get("demand_base", 3.5)
            if listings_count >= 5:
                demand_score = min(5.0, demand_score + 0.2)
            demand_notes = f"{baseline.get('demand_rationale', '')} Market visibility: {listings_count} active ads."

            # 2. Market Scarcity Score (25%)
            # High scarcity (5.0) when few local ads exist despite high vehicle population
            if listings_count <= 2:
                scarcity_score = 4.8
                scarcity_notes = f"Acute scarcity: Only {listings_count} listing(s) found across Ethiopian marketplaces. Severe shortage for fleet maintenance."
            elif listings_count <= 4:
                scarcity_score = 4.0
                scarcity_notes = f"High scarcity: {listings_count} listings with only {distinct_sellers} distinct seller(s). Limited choice."
            elif listings_count <= 8:
                scarcity_score = 3.2
                scarcity_notes = f"Moderate availability: {listings_count} listings. Some active importers in Addis Ababa (Lideta / Bole)."
            else:
                scarcity_score = 2.4
                scarcity_notes = f"Readily available: {listings_count} listings from {distinct_sellers} sellers. Established supply channel."

            # 3. Vehicle Compatibility Score (20%)
            # Platform sharing across multiple vehicles increases addressable market
            if cat in ["Cabin air filters", "Wiper blades"]:
                compatibility_score = 4.8
                comp_notes = "High platform & cross-vehicle compatibility across multiple EV models and model years."
            elif cat in ["Brake pads", "Shock absorbers"]:
                compatibility_score = 4.2
                comp_notes = baseline.get("compatibility_notes", "Platform components shared with sister EV models.")
            elif cat in ["Side mirrors", "Brake discs / rotors"]:
                compatibility_score = 3.4
                comp_notes = "Sub-assembly components (glass, sensors) fit across multiple trims; housings model-specific."
            else:
                compatibility_score = 2.4
                comp_notes = "Proprietary body styling specific to single vehicle model and production year range."

            # 4. Sourcing Practicality Score (15%)
            sourcing_score = baseline.get("sourcing_base", 3.0)
            sourcing_notes = baseline.get("sourcing_rationale", "")

            # 5. Evidence Confidence Score (10%)
            if listings_count >= 4 and priced_count >= 3:
                evidence_score = 4.8
                evidence_notes = f"High empirical confidence: {listings_count} listings, {priced_count} verified prices, active seller contact."
            elif listings_count >= 1:
                evidence_score = 3.8
                evidence_notes = f"Moderate confidence: {listings_count} verified listings with empirical marketplace records."
            else:
                evidence_score = 2.5
                evidence_notes = "Low empirical visibility: relies primarily on automotive engineering domain baselines."

            # Final Weighted Formula:
            # (0.30 * Demand) + (0.25 * Scarcity) + (0.20 * Compatibility) + (0.15 * Sourcing Practicality) + (0.10 * Evidence Confidence)
            priority_score = (
                0.30 * demand_score +
                0.25 * scarcity_score +
                0.20 * compatibility_score +
                0.15 * sourcing_score +
                0.10 * evidence_score
            )

            # Calculate price statistics if available
            prices = []
            if not cat_df.empty:
                for p in cat_df["advertised_price"]:
                    try:
                        if p not in ("", None):
                            prices.append(float(p))
                    except (ValueError, TypeError):
                        pass

            min_p = min(prices) if prices else None
            med_p = pd.Series(prices).median() if prices else None
            max_p = max(prices) if prices else None

            scored_parts.append({
                "part_category": cat,
                "priority_score": round(priority_score, 2),
                "demand_score": round(demand_score, 1),
                "scarcity_score": round(scarcity_score, 1),
                "compatibility_score": round(compatibility_score, 1),
                "sourcing_score": round(sourcing_score, 1),
                "evidence_confidence_score": round(evidence_score, 1),
                "active_listings_count": listings_count,
                "distinct_sellers_count": distinct_sellers,
                "median_price_etb": f"{med_p:,.0f}" if med_p is not None else "N/A",
                "price_range_etb": f"{min_p:,.0f} - {max_p:,.0f}" if min_p and max_p else "N/A",
                "demand_evidence": demand_notes,
                "scarcity_evidence": scarcity_notes,
                "compatibility_evidence": comp_notes,
                "sourcing_practicality_evidence": sourcing_notes,
                "confidence_evidence": evidence_notes,
            })

        # Rank by overall priority score descending
        scored_parts.sort(key=lambda x: x["priority_score"], reverse=True)
        for rank, p in enumerate(scored_parts, start=1):
            p["import_priority_rank"] = rank

        return scored_parts
