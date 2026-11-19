#!/usr/bin/env python3
"""
Ethiopian EV Spare Parts Price & Market Availability Scraper
Project: EV Spare Parts Import Prioritization for the Ethiopian Market

Target Vehicles:
1. BYD Seagull
2. BYD Yuan Up
3. Volkswagen ID.6

Ten Target Spare Parts:
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

Marketplaces:
- Jiji Ethiopia (https://jiji.com.et)
- Adey Market (https://adey-market.com)
"""

import os
import sys
import json
import logging
import sqlite3
import argparse
from typing import List, Dict, Any, Set

from src.jiji_scraper import JijiScraper
from src.adey_scraper import AdeyScraper
from src.data_cleaner import DataCleaner
from src.priority_scorer import PriorityScorer
from src.exporter import Exporter


# Configure Logging
log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
logging.basicConfig(level=logging.INFO, format=log_format)
log = logging.getLogger("main")


class PartsScraperOrchestrator:
    def __init__(self, base_dir: str):
        self.base_dir = base_dir
        self.config_dir = os.path.join(base_dir, "config")
        self.raw_db_path = os.path.join(base_dir, "data", "raw", "raw_parts_listings.sqlite")

        # Load configs
        with open(os.path.join(self.config_dir, "vehicles.json"), "r", encoding="utf-8") as f:
            self.vehicles_config = json.load(f)["vehicles"]

        with open(os.path.join(self.config_dir, "parts.json"), "r", encoding="utf-8") as f:
            self.parts_config = json.load(f)["parts"]

        with open(os.path.join(self.config_dir, "websites.json"), "r", encoding="utf-8") as f:
            self.websites_config = json.load(f)["marketplaces"]

        self.vehicles = [v["canonical_name"] for v in self.vehicles_config]
        self.parts = [p["canonical_name"] for p in self.parts_config]

        self.cleaner = DataCleaner()
        self.scorer = PriorityScorer()
        self.exporter = Exporter(base_dir)

        self._init_sqlite()
        self.seen_urls = self._load_seen_urls()

    def _init_sqlite(self):
        """Initialize SQLite database for storing raw scraped records and preventing duplicates."""
        os.makedirs(os.path.dirname(self.raw_db_path), exist_ok=True)
        with sqlite3.connect(self.raw_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS raw_listings (
                    record_id TEXT PRIMARY KEY,
                    vehicle_model TEXT,
                    model_year TEXT,
                    part_category TEXT,
                    part_position TEXT,
                    listing_title TEXT,
                    listing_description TEXT,
                    advertised_price REAL,
                    currency TEXT,
                    condition TEXT,
                    availability_status TEXT,
                    seller_name TEXT,
                    seller_location TEXT,
                    seller_contact_if_public TEXT,
                    marketplace TEXT,
                    listing_url TEXT UNIQUE,
                    date_collected TEXT,
                    advertised_compatibility TEXT,
                    OEM_part_number TEXT,
                    manufacturer_or_brand TEXT,
                    source_evidence TEXT,
                    confidence_level TEXT,
                    manual_verification_required TEXT
                )
            """)
            conn.commit()

    def _load_seen_urls(self) -> Set[str]:
        """Load already scraped URLs from SQLite to support resuming."""
        with sqlite3.connect(self.raw_db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT listing_url FROM raw_listings")
            rows = cursor.fetchall()
            return {r[0] for r in rows if r[0]}

    def _save_raw_to_sqlite(self, records: List[Dict[str, Any]]):
        """Save new records into SQLite database."""
        with sqlite3.connect(self.raw_db_path) as conn:
            cursor = conn.cursor()
            for r in records:
                try:
                    price_val = float(r["advertised_price"]) if r["advertised_price"] not in ("", None) else None
                except (ValueError, TypeError):
                    price_val = None

                cursor.execute("""
                    INSERT OR IGNORE INTO raw_listings VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    r.get("record_id"),
                    r.get("vehicle_model"),
                    r.get("model_year"),
                    r.get("part_category"),
                    r.get("part_position"),
                    r.get("listing_title"),
                    r.get("listing_description"),
                    price_val,
                    r.get("currency"),
                    r.get("condition"),
                    r.get("availability_status"),
                    r.get("seller_name"),
                    r.get("seller_location"),
                    r.get("seller_contact_if_public"),
                    r.get("marketplace"),
                    r.get("listing_url"),
                    r.get("date_collected"),
                    r.get("advertised_compatibility"),
                    r.get("OEM_part_number"),
                    r.get("manufacturer_or_brand"),
                    r.get("source_evidence"),
                    r.get("confidence_level"),
                    r.get("manual_verification_required")
                ))
            conn.commit()

    def _load_all_raw_from_sqlite(self) -> List[Dict[str, Any]]:
        """Load all raw records stored in SQLite."""
        with sqlite3.connect(self.raw_db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM raw_listings")
            rows = cursor.fetchall()
            records = []
            for row in rows:
                d = dict(row)
                if d["advertised_price"] is None:
                    d["advertised_price"] = ""
                records.append(d)
            return records

    def run_jiji(self, query_vehicle: str = None, query_part: str = None) -> List[Dict[str, Any]]:
        """Run Jiji scraper."""
        cfg = next((w for w in self.websites_config if w["slug"] == "jiji"), {})
        scraper = JijiScraper(cfg, seen_urls=self.seen_urls)

        print("\n" + "="*60)
        print("  SCRAPING JIJI ETHIOPIA (https://jiji.com.et)")
        print("="*60)

        if query_vehicle and query_part:
            records = scraper.search_query(f"{query_vehicle} {query_part}")
        elif query_vehicle:
            records = scraper.search_query(query_vehicle)
        elif query_part:
            records = scraper.search_query(f"byd {query_part}") + scraper.search_query(f"id6 {query_part}")
        else:
            records = scraper.scrape_all_targets(self.vehicles, self.parts)

        print(f"\n[+] Jiji Scrape Complete: {len(records)} new target listings collected.")
        self._save_raw_to_sqlite(records)
        self.seen_urls.update(r["listing_url"] for r in records if r.get("listing_url"))

        # Append scrape logs
        self.exporter.export_scrape_log(scraper.scrape_logs)
        return records

    def run_adey(self) -> List[Dict[str, Any]]:
        """Run Adey scraper."""
        cfg = next((w for w in self.websites_config if w["slug"] == "adey"), {})
        scraper = AdeyScraper(cfg, seen_urls=self.seen_urls)

        print("\n" + "="*60)
        print("  SCRAPING ADEY MARKET (https://adey-market.com)")
        print("="*60)

        records = scraper.scrape_all_targets(self.vehicles, self.parts)
        print(f"\n[+] Adey Market Ingestion Complete: {len(records)} target listings collected.")
        self._save_raw_to_sqlite(records)
        self.seen_urls.update(r["listing_url"] for r in records if r.get("listing_url"))

        # Append scrape logs
        self.exporter.export_scrape_log(scraper.scrape_logs)
        return records

    def run_cleaning_and_export(self):
        """Clean all data, compute price summaries and priority scoring, and export all 7 CSVs."""
        print("\n" + "="*60)
        print("  DATA CLEANING, SUMMARIZATION & PRIORITY SCORING")
        print("="*60)

        raw_records = self._load_all_raw_from_sqlite()
        print(f"[*] Total raw records in database: {len(raw_records)}")

        if not raw_records:
            print("[!] Warning: Database is empty. Running live scrapers first...")
            self.run_jiji()
            self.run_adey()
            raw_records = self._load_all_raw_from_sqlite()

        # 1. Clean and deduplicate
        cleaned_records, manual_review_records = self.cleaner.clean_dataset(raw_records)
        print(f"[+] Cleaned records after deduplication: {len(cleaned_records)}")
        print(f"[+] Records flagged for human manual review: {len(manual_review_records)}")

        # 2. Priority scoring calculation
        scored_parts = self.scorer.evaluate_part_priority(cleaned_records)

        # 3. Export all 7 CSV files
        p_raw = self.exporter.export_raw_listings(raw_records)
        p_clean = self.exporter.export_cleaned_listings(cleaned_records)
        p_price = self.exporter.export_price_summary(cleaned_records)
        p_avail = self.exporter.export_vehicle_part_availability(cleaned_records)
        p_review = self.exporter.export_manual_review(manual_review_records)
        p_ref = self.exporter.export_source_references(cleaned_records)
        p_score = self.exporter.export_priority_scoring_report(scored_parts)

        print("\n[+] Successfully generated all CSV deliverables:")
        print(f"  A. Raw listings:         {p_raw}")
        print(f"  B. Cleaned listings:     {p_clean}")
        print(f"  C. Price summary:        {p_price}")
        print(f"  D. Availability matrix:  {p_avail}")
        print(f"  E. Manual review queue:  {p_review}")
        print(f"  F. Scrape log:           {os.path.join(self.base_dir, 'logs', 'scrape_log.csv')}")
        print(f"  G. Source references:    {p_ref}")
        print(f"  H. Priority report:      {p_score}")

        self.display_summary_tables(cleaned_records, scored_parts)

    def display_summary_tables(self, cleaned_records: List[Dict[str, Any]], scored_parts: List[Dict[str, Any]]):
        """Display clean ASCII tables for terminal inspection."""
        print("\n" + "="*80)
        print("  PRIORITY SCORING SUMMARY: 10 SPARE PARTS RANKED FOR ETHIOPIAN IMPORT")
        print("="*80)
        print(f"{'Rank':<5}{'Part Category':<28}{'Score':<8}{'Demand':<8}{'Scarcity':<10}{'Compat':<8}{'Sourcing':<10}{'Median ETB':<12}")
        print("-" * 92)
        for p in scored_parts:
            print(f"{p['import_priority_rank']:<5}{p['part_category']:<28}{p['priority_score']:<8.2f}{p['demand_score']:<8.1f}{p['scarcity_score']:<10.1f}{p['compatibility_score']:<8.1f}{p['sourcing_score']:<10.1f}{p['median_price_etb']:<12}")
        print("-" * 92)

        print("\n" + "="*80)
        print("  VEHICLE & PART AVAILABILITY MATRIX (Total Advertisement Visibility)")
        print("="*80)
        import pandas as pd
        df = pd.DataFrame(cleaned_records)
        matrix = pd.crosstab(df["part_category"], df["vehicle_model"], margins=True, margins_name="Total")
        print(matrix.to_string())
        print("="*80 + "\n")


def print_menu():
    print("""
========================================================================
   ETHIOPIAN EV SPARE PARTS SCRAPER & IMPORT PRIORITIZATION TOOL
========================================================================
  Target Vehicles: BYD Seagull | BYD Yuan Up | Volkswagen ID.6
  10 Part Categories: Brake pads, Discs, Filters, Wipers, Lights, etc.
========================================================================
  [1] Scrape all vehicles and all parts (Jiji + Adey full run)
  [2] Scrape one selected vehicle
  [3] Scrape one selected part
  [4] Scrape Jiji Ethiopia only
  [5] Scrape Adey Market only
  [6] Export all 7 CSV files
  [7] Generate price summaries & Priority Scoring Report
  [8] Run end-to-end pipeline (Scrape -> Clean -> Score -> Export)
  [0] Exit
========================================================================
""")


def main():
    parser = argparse.ArgumentParser(description="Ethiopian EV Spare Parts Price & Availability Scraper")
    parser.add_argument("--all", action="store_true", help="Run full scraping and export")
    parser.add_argument("--jiji", action="store_true", help="Scrape Jiji only")
    parser.add_argument("--adey", action="store_true", help="Scrape Adey only")
    parser.add_argument("--export", action="store_true", help="Clean, score and export CSVs")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    orchestrator = PartsScraperOrchestrator(base_dir)

    if args.all:
        orchestrator.run_jiji()
        orchestrator.run_adey()
        orchestrator.run_cleaning_and_export()
        return
    elif args.jiji:
        orchestrator.run_jiji()
        orchestrator.run_cleaning_and_export()
        return
    elif args.adey:
        orchestrator.run_adey()
        orchestrator.run_cleaning_and_export()
        return
    elif args.export:
        orchestrator.run_cleaning_and_export()
        return

    # Interactive menu
    while True:
        print_menu()
        choice = input("Enter choice (0-8): ").strip()

        if choice == "1":
            orchestrator.run_jiji()
            orchestrator.run_adey()
            orchestrator.run_cleaning_and_export()
        elif choice == "2":
            print("\nSelect Vehicle:")
            for i, v in enumerate(orchestrator.vehicles, 1):
                print(f"  [{i}] {v}")
            v_idx = input("Vehicle number: ").strip()
            try:
                selected_v = orchestrator.vehicles[int(v_idx) - 1]
                orchestrator.run_jiji(query_vehicle=selected_v)
                orchestrator.run_cleaning_and_export()
            except (ValueError, IndexError):
                print("[!] Invalid selection.")
        elif choice == "3":
            print("\nSelect Part Category:")
            for i, p in enumerate(orchestrator.parts, 1):
                print(f"  [{i}] {p}")
            p_idx = input("Part number: ").strip()
            try:
                selected_p = orchestrator.parts[int(p_idx) - 1]
                orchestrator.run_jiji(query_part=selected_p)
                orchestrator.run_cleaning_and_export()
            except (ValueError, IndexError):
                print("[!] Invalid selection.")
        elif choice == "4":
            orchestrator.run_jiji()
            orchestrator.run_cleaning_and_export()
        elif choice == "5":
            orchestrator.run_adey()
            orchestrator.run_cleaning_and_export()
        elif choice == "6" or choice == "7":
            orchestrator.run_cleaning_and_export()
        elif choice == "8":
            orchestrator.run_jiji()
            orchestrator.run_adey()
            orchestrator.run_cleaning_and_export()
        elif choice == "0":
            print("\nExiting. Thank you!")
            break
        else:
            print("[!] Invalid choice. Please enter 0 to 8.")


if __name__ == "__main__":
    main()
