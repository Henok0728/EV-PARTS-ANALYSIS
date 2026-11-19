"""Jiji Ethiopia EV Spare Parts Scraper.

Collects spare parts listings from https://jiji.com.et/car-parts-and-accessories
for the 3 target EV models (BYD Seagull, BYD Yuan Up, VW ID.6) across the 10 parts.
Extracts listing details, handles pagination, respects rate limits, and records scrape logs.
"""

import os
import re
import time
import uuid
import logging
from datetime import datetime, timezone
from urllib.parse import urljoin, quote_plus
from typing import List, Dict, Any, Set, Optional

import requests
from bs4 import BeautifulSoup

from .vehicle_matcher import VehicleMatcher
from .part_matcher import PartMatcher
from .price_extractor import extract_price_and_currency

log = logging.getLogger("ev_scraper.jiji")


class JijiScraper:
    def __init__(self, config: Dict[str, Any], seen_urls: Optional[Set[str]] = None):
        self.config = config
        self.base_url = config.get("base_url", "https://jiji.com.et")
        self.category_url = config.get("category_url", "https://jiji.com.et/car-parts-and-accessories")
        self.search_url_template = config.get("search_url_template", "https://jiji.com.et/car-parts-and-accessories?query={query}&page={page}")
        self.rate_limit_delay = config.get("rate_limit_delay", 2.0)
        self.timeout = config.get("timeout", 20)
        self.max_pages = config.get("max_pages", 3)
        self.seen_urls = seen_urls if seen_urls is not None else set()

        self.session = requests.Session()
        headers = config.get("default_headers", {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9,am;q=0.8",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        })
        self.session.headers.update(headers)

        self.vehicle_matcher = VehicleMatcher()
        self.part_matcher = PartMatcher()
        self.scrape_logs: List[Dict[str, Any]] = []

    def _log_event(self, query: str, page_url: str, count: int, status: str, error_msg: str = ""):
        self.scrape_logs.append({
            "Website": "Jiji Ethiopia",
            "Search query": query,
            "Page URL": page_url,
            "Date and time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "Number of records collected": count,
            "Success/failure status": status,
            "Error message": error_msg,
        })

    def fetch_page(self, url: str) -> Optional[str]:
        """Fetch URL with retries and rate limiting."""
        for attempt in range(1, 4):
            try:
                time.sleep(self.rate_limit_delay)
                resp = self.session.get(url, timeout=self.timeout)
                if resp.status_code == 200:
                    return resp.text
                elif resp.status_code == 404:
                    log.info("Page not found (404): %s", url)
                    return None
                else:
                    log.warning("HTTP %d for %s (attempt %d/3)", resp.status_code, url, attempt)
            except Exception as e:
                log.warning("Fetch error for %s (attempt %d/3): %s", url, attempt, e)
                time.sleep(self.rate_limit_delay * attempt)
        return None

    def parse_card_or_detail(self, item_url: str, card_html_snippet: str = "") -> Optional[Dict[str, Any]]:
        """
        Extract detailed listing record from Jiji listing page.
        """
        if item_url in self.seen_urls:
            return None

        html = self.fetch_page(item_url)
        if not html:
            return None

        self.seen_urls.add(item_url)
        soup = BeautifulSoup(html, "html.parser")

        # 1. Listing Title
        title_el = soup.select_one("h1.qa-advert-title, h1.b-advert-title, h1")
        title = title_el.get_text(separator=" ", strip=True) if title_el else ""
        if not title and soup.title:
            title = soup.title.get_text(separator=" ", strip=True).split("|")[0].strip()

        # 2. Description
        desc_el = soup.select_one("div.qa-advert-description, div.b-advert__description-text, div[itemprop='description']")
        description = desc_el.get_text(separator=" ", strip=True) if desc_el else ""

        # 3. Advertised Price & Currency
        price_el = soup.select_one("span.qa-advert-price-view-value, div.qa-advert-price-view-title, div.b-alt-advert-price__text, [itemprop='price']")
        price_raw = price_el.get_text(separator=" ", strip=True) if price_el else ""
        price_num, currency, _ = extract_price_and_currency(price_raw or title or description)

        # 4. Attributes (Key-Value pairs on Jiji)
        attributes_dict = {}
        attr_elements = soup.select("div.b-advert-attribute")
        for attr in attr_elements:
            k_el = attr.select_one("div.b-advert-attribute__key")
            v_el = attr.select_one("div.b-advert-attribute__value")
            if k_el and v_el:
                k = k_el.get_text(strip=True)
                v = v_el.get_text(strip=True)
                attributes_dict[k] = v

        attr_str = " | ".join(f"{k}: {v}" for k, v in attributes_dict.items())

        # 5. Breadcrumbs
        breadcrumbs = [li.get_text(strip=True) for li in soup.select("ol.b-breadcrumbs li, [class*='breadcrumb'] li")]
        breadcrumb_str = " > ".join(breadcrumbs)

        # 6. Seller Name & Location
        seller_el = soup.select_one("div.b-seller-block__name, a.b-seller-block__name")
        seller_name = seller_el.get_text(strip=True) if seller_el else ""

        loc_el = soup.select_one("div.b-advert-info-statistics--region, div.b-advert-card__head-region")
        loc_text = loc_el.get_text(separator=" ", strip=True) if loc_el else ""
        # Clean region text (e.g. "Addis Ababa, Bole, 2 days ago 75 views" -> "Addis Ababa, Bole")
        seller_location = re.split(r",\s*\d+\s*(?:days?|hours?|weeks?|months?)\s*ago", loc_text, flags=re.IGNORECASE)[0].strip()
        if not seller_location and "Addis Ababa" in loc_text:
            seller_location = "Addis Ababa"

        # 7. Seller Public Contact (if visible)
        contact = ""
        phone_match = re.search(r"\b(09\d{8}|\+251\s*9\d{8}|07\d{8})\b", f"{title} {description}")
        if phone_match:
            contact = phone_match.group(1).replace(" ", "")

        # 8. Vehicle & Part Matching
        combined_text = f"{title} {description} {attr_str} {breadcrumb_str}".strip()
        v_res = self.vehicle_matcher.match_vehicle(title, description, attr_str)
        p_res = self.part_matcher.match_part(title, description, attr_str)

        # If vehicle or part is unclassified, check if target terms appear in breadcrumbs or attributes
        if v_res["vehicle_model"] == "Unknown / Non-Target":
            v_res = self.vehicle_matcher.match_vehicle(breadcrumb_str, attr_str)
        if p_res["part_category"] == "Unclassified / Other":
            p_res = self.part_matcher.match_part(breadcrumb_str, attr_str)

        # If it's still completely irrelevant to target vehicles or parts, skip it
        if v_res["vehicle_model"] == "Unknown / Non-Target" and p_res["part_category"] == "Unclassified / Other":
            return None

        # Condition
        attr_cond = attributes_dict.get("Condition", "").lower()
        if "brand new" in attr_cond or "new" in attr_cond:
            condition = "new"
        elif "used" in attr_cond:
            condition = "used"
        elif "refurbished" in attr_cond:
            condition = "refurbished"
        else:
            condition = p_res["condition"]

        # Availability status
        avail_status = "available"
        if re.search(r"\b(sold|out\s*of\s*stock|unavailable)\b", combined_text, re.IGNORECASE):
            avail_status = "out of stock"

        # Confidence level calculation
        v_conf = v_res.get("confidence_level", "Medium")
        p_conf = p_res.get("confidence_level", "Medium")
        if v_conf == "High" and p_conf == "High" and price_num is not None:
            confidence_level = "High"
        elif v_conf == "Low" or p_conf == "Low" or price_num is None:
            confidence_level = "Low"
        else:
            confidence_level = "Medium"

        # Manual review flag
        needs_review = (
            v_res.get("manual_verification_required", False)
            or p_res.get("manual_verification_required", False)
            or price_num is None
            or confidence_level == "Low"
            or v_res["vehicle_model"] == "Unknown / Non-Target"
            or p_res["part_category"] == "Unclassified / Other"
        )

        record_id = f"REC-JIJI-{uuid.uuid4().hex[:8].upper()}"
        evidence = f"Source: Jiji listing | {v_res['matching_evidence']} | {p_res['matching_evidence']}"

        return {
            "record_id": record_id,
            "vehicle_model": v_res["vehicle_model"],
            "model_year": v_res["model_year"] or "",
            "part_category": p_res["part_category"],
            "part_position": p_res["part_position"],
            "listing_title": title,
            "listing_description": description[:1000] if description else "",
            "advertised_price": price_num if price_num is not None else "",
            "currency": currency or ("ETB" if price_num else ""),
            "condition": condition,
            "availability_status": avail_status,
            "seller_name": seller_name or "",
            "seller_location": seller_location or "Addis Ababa, Ethiopia",
            "seller_contact_if_public": contact or "",
            "marketplace": "Jiji Ethiopia",
            "listing_url": item_url,
            "date_collected": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "advertised_compatibility": v_res["advertised_compatibility"],
            "OEM_part_number": p_res["OEM_part_number"] or "",
            "manufacturer_or_brand": p_res["manufacturer_or_brand"] or "",
            "source_evidence": evidence,
            "confidence_level": confidence_level,
            "manual_verification_required": "True" if needs_review else "False",
        }

    def search_query(self, query: str, max_pages: Optional[int] = None) -> List[Dict[str, Any]]:
        """Search Jiji for a query string across pages."""
        pages = max_pages or self.max_pages
        records = []

        log.info("Starting Jiji search for query: '%s' (max %d pages)", query, pages)

        for page in range(1, pages + 1):
            url = self.search_url_template.format(query=quote_plus(query), page=page)
            html = self.fetch_page(url)

            if not html:
                self._log_event(query, url, 0, "Failed", "Could not fetch HTML or empty response")
                break

            soup = BeautifulSoup(html, "html.parser")
            links = soup.select(self.config.get("selectors", {}).get("item_link", "a[href*='/car-parts-and-accessories/']"))

            item_urls = []
            for a in links:
                href = a.get("href", "")
                if href and ".html" in href:
                    clean_href = href.split("?")[0]
                    full_url = urljoin(self.base_url, clean_href)
                    if full_url not in self.seen_urls and full_url not in item_urls:
                        item_urls.append(full_url)

            page_records = []
            for item_url in item_urls:
                rec = self.parse_card_or_detail(item_url)
                if rec:
                    page_records.append(rec)
                    records.append(rec)

            self._log_event(query, url, len(page_records), "Success" if page_records else "Empty Result")
            log.info("Page %d for '%s': found %d valid target listings", page, query, len(page_records))

            if len(item_urls) == 0:
                # No more listings
                break

        return records

    def scrape_all_targets(self, vehicles: List[str], parts: List[str]) -> List[Dict[str, Any]]:
        """Execute systematic searches across all target vehicles and parts."""
        all_records = []

        # High priority specific searches:
        # 1. Base queries for each vehicle
        base_queries = [
            "byd seagull",
            "byd dolphin mini",
            "byd yuan up",
            "volkswagen id6",
            "volkswagen id.6",
            "vw id6",
            "byd spare parts",
            "id6 parts",
        ]

        # 2. Combinations of vehicle and part
        combo_queries = []
        for v in ["byd seagull", "byd yuan up", "id6"]:
            for p in ["brake pads", "bumper", "headlight", "side mirror", "tail light", "shock absorber"]:
                combo_queries.append(f"{v} {p}")

        all_queries = base_queries + combo_queries

        log.info("Executing Jiji scrape with %d query variations...", len(all_queries))

        for q in all_queries:
            recs = self.search_query(q, max_pages=2)
            all_records.extend(recs)

        return all_records
