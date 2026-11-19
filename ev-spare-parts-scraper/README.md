# EV Spare Parts Import Prioritization for the Ethiopian Market

A data-driven web scraper, market intelligence engine, and multi-factor import prioritization framework tailored for the Ethiopian automotive aftermarket.

---

## 1. Project Overview & Motivation

Following the initial vehicle selection phase, this project investigates the availability, price structure, seller landscape, and cross-model compatibility of automotive spare parts for electric vehicles (EVs) in Ethiopia. 

The primary objective is to supply empirical marketplace evidence for an **Import Prioritization Model** that ranks ten essential spare-part categories across three key EV models actively circulating on Ethiopian roads:

1. **BYD Seagull** (including *Dolphin Mini*, *Atto 1*)
2. **BYD Yuan Up** (including *Atto 2*)
3. **Volkswagen ID.6** (including *ID.6 Crozz*, *ID.6 X*)

---

## 2. Ten Target Spare Part Categories

The framework is strictly configured for the ten required automotive categories:

| # | Part Category | Common Marketplace & Amharic Synonyms | Typical Position |
|---|---|---|---|
| 1 | **Brake pads** | Brake pad, disc pad, ፍሬን ሸራ, የፊት እግር ሸራ | Front, Rear, Pair |
| 2 | **Brake discs / rotors** | Brake disc, rotor, brake drum, ፍሬን ዲስክ | Front, Rear, Pair |
| 3 | **Cabin air filters** | Cabin filter, AC filter, pollen filter, ካቢን ፊልተር | Unspecified |
| 4 | **Wiper blades** | Wiper blade, windshield wiper, ዋይፐር | Pair / Set, Front |
| 5 | **Headlights** | Headlamp, LED headlight, front lamp, የፊት ማብራት, ፋሮ | Front Left, Front Right, Pair |
| 6 | **Tail lights** | Taillight, rear lamp, lightbar, የዋላ ፊረቻ, ስቶፕ | Rear Left, Rear Right, Rear |
| 7 | **Side mirrors** | Wing mirror, door mirror, BSD mirror, የጎን ስፖክይ | Left, Right, Pair |
| 8 | **Bumpers (front/rear)** | Bumper cover, reinforcement, ፓራወልት, ፓራኦልት | Front, Rear |
| 9 | **Fenders / body panels**| Front fender, quarter panel, door skeleton, የጎን በር | Front Left, Front Right |
| 10 | **Shock absorbers** | Strut, damper, suspension shock, አሞርዛተር | Front, Rear, Pair |

---

## 3. Marketplace Scraper Architecture & Access Rules

### Targeted Marketplaces
1. **Jiji Ethiopia** (`https://jiji.com.et/car-parts-and-accessories`):
   - Structured marketplace category for automotive parts.
   - Live HTTP requests extract item cards, prices, seller names, locations (Bole, Lideta, Kirkos, etc.), descriptions, and specifications.
   - Full rate limiting (`2.0s` delay), retries, and pagination support.
2. **Adey Market** (`https://adey-market.com/`):
   - Next.js marketplace with Telegram integration.
   - When accessible, extracts product cards. If the live server blocks or times out (TCP/SSL handshake delay), the scraper logs the event into `scrape_log.csv` and engages the traceable manual collection workflow with reference listings.

### Scraping Ethics & Compliance
- **Robots.txt & Rate Limiting:** All requests respect robots.txt crawling directives and enforce spacing delays between successive queries.
- **Anti-Bot & Access Protections:** The scraper strictly complies with system boundaries; it does **not** bypass CAPTCHA, authentication, or anti-bot protections. Blocked endpoints are gracefully logged.
- **Data Integrity:** Missing values are stored as blank/null. Missing prices are **never converted to zero**.

---

## 4. Multi-Factor Priority Scoring Model

Import prioritization is computed using five transparent, weighted factors on a **1.0 to 5.0** rating scale:

$$\text{Priority Score} = (0.30 \times \text{Demand}) + (0.25 \times \text{Scarcity}) + (0.20 \times \text{Compatibility}) + (0.15 \times \text{Sourcing Practicality}) + (0.10 \times \text{Evidence Confidence})$$

### Factor Definitions & Weights:
1. **Demand Evidence (30%):** Replacement frequency, normal wear cycle (e.g. stop-and-go Addis Ababa traffic heavily wears brake pads and filters), and collision vulnerability.
2. **Market Scarcity (25%):** Local market scarcity relative to vehicle population. Few or zero active listings indicates high import urgency.
3. **Vehicle Compatibility (20%):** Cross-platform interchangeability (e.g., VW MEB platform sharing between ID.4 and ID.6; BYD e-Platform 3.0 sharing between Seagull and E2/Dolphin).
4. **Sourcing Practicality (15%):** Freight economics, volumetric dimensional penalties, cargo weight, and transit fragility. Lightweight items (filters, wiper blades) score high ($5.0$); oversized plastic parts (bumpers) score lower ($1.5$).
5. **Evidence Confidence (10%):** Number of verified empirical listings, verified prices, and seller contact traceability.

---

## 5. Project Folder Structure

```
ev-spare-parts-scraper/
│
├── config/
│   ├── vehicles.json         # Target models, aliases, and negative patterns
│   ├── parts.json            # 10 part categories, keywords, Amharic terms
│   └── websites.json         # Marketplace URLs, selectors, rate limits
│
├── data/
│   ├── raw/
│   │   ├── raw_parts_listings.csv      # Uncleaned scraped listings
│   │   └── raw_parts_listings.sqlite   # SQLite storage for state & deduplication
│   ├── cleaned/
│   │   ├── cleaned_parts_listings.csv  # Deduplicated and normalized listings
│   │   ├── parts_price_summary.csv     # Min/Med/Mean/Max price statistics
│   │   ├── vehicle_part_availability.csv # 10x3 Availability Matrix
│   │   ├── manual_review.csv           # Human verification queue
│   │   └── source_references.csv       # Traceable URLs & evidence
│   └── reports/
│       └── priority_scoring_report.csv # 10 ranked parts with factor scores
│
├── src/
│   ├── __init__.py
│   ├── jiji_scraper.py       # Jiji Ethiopia live scraper
│   ├── adey_scraper.py       # Adey Market scraper & fallback workflow
│   ├── vehicle_matcher.py    # Strict EV model & alias matching engine
│   ├── part_matcher.py       # 10-category classifier & position detector
│   ├── price_extractor.py    # Price regex, currency, outlier detection
│   ├── data_cleaner.py       # Deduplication & data quality auditor
│   ├── priority_scorer.py    # Multi-factor mathematical scoring model
│   └── exporter.py           # Standardized CSV generator
│
├── notebooks/
│   └── price_analysis.ipynb  # Interactive data analysis & report
│
├── logs/
│   └── scrape_log.csv        # Systematic audit log of all scrape events
│
├── main.py                   # Interactive CLI & automation orchestrator
├── requirements.txt          # Python dependencies
└── README.md                 # Full documentation
```

---

## 6. Installation & Quick Start

### Prerequisites
- Python 3.11+
- Virtual environment recommended

### Installation
```bash
cd ev-spare-parts-scraper
python -m venv .venv
source .venv/bin/activate  # On Linux/macOS
# or on Windows:
.venv\Scripts\activate

pip install -r requirements.txt
```

### Running the Tool
Run the interactive terminal interface:
```bash
python main.py
```

Or run directly via command-line flags:
```bash
# Run end-to-end pipeline (scrape, clean, score, export all CSVs):
python main.py --all

# Run Jiji Ethiopia scraper only:
python main.py --jiji

# Run Adey Market scraper only:
python main.py --adey

# Re-run data cleaning, summarization, and export from local database:
python main.py --export
```

---

## 7. Required Deliverable Files & Schemas

The scraper automatically populates seven required CSV output files:

1. **`data/raw/raw_parts_listings.csv`**: Every extracted record in its raw, unmodified state (23 fields).
2. **`data/cleaned/cleaned_parts_listings.csv`**: Pristine deduplicated dataset with normalized prices, models, categories, and audit notes.
3. **`data/cleaned/parts_price_summary.csv`**: Aggregated price metrics (listing count, distinct sellers, minimum, median, mean, maximum price in ETB, price range, missing price counts).
4. **`data/cleaned/vehicle_part_availability.csv`**: Availability cross-tabulation matrix showing listings per part across BYD Seagull, BYD Yuan Up, and VW ID.6.
5. **`data/cleaned/manual_review.csv`**: Suspicious listings flagged for human review (missing price, multi-vehicle claims, outlier price, or low confidence).
6. **`logs/scrape_log.csv`**: Traceable log of each website access, query string, timestamp, status, and error messages.
7. **`data/cleaned/source_references.csv`**: Original URL verification registry for academic/internship audit defense.
8. **`data/reports/priority_scoring_report.csv`**: Ranked table of the 10 parts with individual factor scores and qualitative evidence fields.

---

## 8. Limitations and Manual Verification Protocol

1. **Seller Fitment Statements vs Engineering Reality:** Sellers frequently claim that a part fits "Seagull, E2, Yuan Up, Song Plus" in listing text to attract search traffic. The pipeline flags all multi-vehicle listings in `manual_review.csv` for technical verification against manufacturer parts catalogs.
2. **Market Visibility as a Proxy:** Marketplace advertisement counts represent active seller listings, not actual sales volumes. High visibility proves parts supply activity, while zero listings in combination with a high vehicle population proves critical scarcity.
3. **Volumetric Shipping Realities:** Body panels and bumpers have high local market prices (e.g. ETB 165,000 - 230,000) and high scarcity, but their low sourcing practicality score ($1.5 - 2.0$) reflects the reality of expensive ocean container freight. They should not be air-freighted.
