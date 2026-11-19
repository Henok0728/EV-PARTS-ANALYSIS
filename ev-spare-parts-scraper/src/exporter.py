"""CSV Exporter module for Ethiopian EV Spare Parts Scraper.

Generates all 7 required CSV files in exact schemas:
A. raw_parts_listings.csv
B. cleaned_parts_listings.csv
C. parts_price_summary.csv
D. vehicle_part_availability.csv
E. manual_review.csv
F. scrape_log.csv
G. source_references.csv
Plus Priority Scoring Report.
"""

import os
import csv
from typing import List, Dict, Any
import pandas as pd


RAW_COLUMNS = [
    "record_id",
    "vehicle_model",
    "model_year",
    "part_category",
    "part_position",
    "listing_title",
    "listing_description",
    "advertised_price",
    "currency",
    "condition",
    "availability_status",
    "seller_name",
    "seller_location",
    "seller_contact_if_public",
    "marketplace",
    "listing_url",
    "date_collected",
    "advertised_compatibility",
    "OEM_part_number",
    "manufacturer_or_brand",
    "source_evidence",
    "confidence_level",
    "manual_verification_required",
]

CLEANED_COLUMNS = RAW_COLUMNS + ["audit_notes"]

LOG_COLUMNS = [
    "Website",
    "Search query",
    "Page URL",
    "Date and time",
    "Number of records collected",
    "Success/failure status",
    "Error message",
]

SOURCE_REF_COLUMNS = [
    "listing_url",
    "marketplace",
    "vehicle_model",
    "part_category",
    "date_collected",
    "seller_name",
    "seller_location",
    "advertised_price",
    "currency",
    "evidence_notes",
]


class Exporter:
    def __init__(self, output_dir: str):
        self.output_dir = output_dir
        self.raw_dir = os.path.join(output_dir, "data", "raw")
        self.cleaned_dir = os.path.join(output_dir, "data", "cleaned")
        self.reports_dir = os.path.join(output_dir, "data", "reports")
        self.logs_dir = os.path.join(output_dir, "logs")

        for d in [self.raw_dir, self.cleaned_dir, self.reports_dir, self.logs_dir]:
            os.makedirs(d, exist_ok=True)

    def export_raw_listings(self, records: List[Dict[str, Any]]) -> str:
        """Export A. raw_parts_listings.csv"""
        path = os.path.join(self.raw_dir, "raw_parts_listings.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=RAW_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        return path

    def export_cleaned_listings(self, records: List[Dict[str, Any]]) -> str:
        """Export B. cleaned_parts_listings.csv"""
        path = os.path.join(self.cleaned_dir, "cleaned_parts_listings.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=CLEANED_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(records)
        return path

    def export_price_summary(self, records: List[Dict[str, Any]]) -> str:
        """Export C. parts_price_summary.csv"""
        path = os.path.join(self.cleaned_dir, "parts_price_summary.csv")
        df = pd.DataFrame(records)

        if df.empty:
            summary_cols = [
                "vehicle_model", "part_category", "marketplace",
                "number_of_listings", "distinct_sellers", "minimum_price_etb",
                "median_price_etb", "mean_price_etb", "maximum_price_etb",
                "price_range_etb", "missing_prices_count"
            ]
            pd.DataFrame(columns=summary_cols).to_csv(path, index=False, encoding="utf-8-sig")
            return path

        summary_rows = []
        grouped = df.groupby(["vehicle_model", "part_category", "marketplace"])

        for (vehicle, part, marketplace), group in grouped:
            # Parse numeric prices
            prices = []
            missing_count = 0
            for p in group["advertised_price"]:
                try:
                    if p not in ("", None) and float(p) > 0:
                        prices.append(float(p))
                    else:
                        missing_count += 1
                except (ValueError, TypeError):
                    missing_count += 1

            distinct_sellers = group["seller_name"].replace("", None).dropna().nunique()
            num_listings = len(group)

            min_p = min(prices) if prices else None
            med_p = pd.Series(prices).median() if prices else None
            mean_p = pd.Series(prices).mean() if prices else None
            max_p = max(prices) if prices else None
            price_range = f"{min_p:,.0f} - {max_p:,.0f}" if min_p and max_p else "N/A"

            summary_rows.append({
                "vehicle_model": vehicle,
                "part_category": part,
                "marketplace": marketplace,
                "number_of_listings": num_listings,
                "distinct_sellers": distinct_sellers,
                "minimum_price_etb": f"{min_p:,.0f}" if min_p is not None else "N/A",
                "median_price_etb": f"{med_p:,.0f}" if med_p is not None else "N/A",
                "mean_price_etb": f"{mean_p:,.0f}" if mean_p is not None else "N/A",
                "maximum_price_etb": f"{max_p:,.0f}" if max_p is not None else "N/A",
                "price_range_etb": price_range,
                "missing_prices_count": missing_count,
            })

        summary_df = pd.DataFrame(summary_rows)
        summary_df.sort_values(by=["vehicle_model", "part_category"], inplace=True)
        summary_df.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def export_vehicle_part_availability(self, records: List[Dict[str, Any]]) -> str:
        """Export D. vehicle_part_availability.csv (Matrix: 10 parts x 3 vehicles)."""
        path = os.path.join(self.cleaned_dir, "vehicle_part_availability.csv")

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
        vehicles = ["BYD Seagull", "BYD Yuan Up", "Volkswagen ID.6"]

        matrix = {cat: {v: 0 for v in vehicles} for cat in categories}

        for r in records:
            cat = r.get("part_category")
            veh = r.get("vehicle_model")
            if cat in matrix and veh in matrix[cat]:
                matrix[cat][veh] += 1

        rows = []
        for cat in categories:
            row = {"part_category": cat}
            total = 0
            for v in vehicles:
                count = matrix[cat][v]
                row[v] = count
                total += count
            row["total_advertisements"] = total
            rows.append(row)

        df_matrix = pd.DataFrame(rows)
        df_matrix.to_csv(path, index=False, encoding="utf-8-sig")
        return path

    def export_manual_review(self, records: List[Dict[str, Any]]) -> str:
        """Export E. manual_review.csv"""
        path = os.path.join(self.cleaned_dir, "manual_review.csv")
        review_records = [r for r in records if r.get("manual_verification_required") == "True"]
        cols = CLEANED_COLUMNS
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(review_records)
        return path

    def export_scrape_log(self, logs: List[Dict[str, Any]]) -> str:
        """Export F. scrape_log.csv"""
        path = os.path.join(self.logs_dir, "scrape_log.csv")
        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=LOG_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(logs)
        return path

    def export_source_references(self, records: List[Dict[str, Any]]) -> str:
        """Export G. source_references.csv"""
        path = os.path.join(self.cleaned_dir, "source_references.csv")
        refs = []
        for r in records:
            refs.append({
                "listing_url": r.get("listing_url", ""),
                "marketplace": r.get("marketplace", ""),
                "vehicle_model": r.get("vehicle_model", ""),
                "part_category": r.get("part_category", ""),
                "date_collected": r.get("date_collected", ""),
                "seller_name": r.get("seller_name", ""),
                "seller_location": r.get("seller_location", ""),
                "advertised_price": r.get("advertised_price", ""),
                "currency": r.get("currency", ""),
                "evidence_notes": r.get("source_evidence", ""),
            })

        with open(path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.DictWriter(f, fieldnames=SOURCE_REF_COLUMNS, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(refs)
        return path

    def export_priority_scoring_report(self, scored_parts: List[Dict[str, Any]]) -> str:
        """Export Priority Scoring Report."""
        path = os.path.join(self.reports_dir, "priority_scoring_report.csv")
        df = pd.DataFrame(scored_parts)
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path
