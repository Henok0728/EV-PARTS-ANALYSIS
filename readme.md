# Ethiopian EV Market & Spare Parts Import Prioritization Project

**Internship Research Program — Ethiopian Automotive Aftermarket Intelligence**  
**Repository Location:** `icog/`

---

## Executive Roadmap & Notebook Guide (For Non-Technical Management)

This project provides an end-to-end, empirical market investigation into the Ethiopian Electric Vehicle (EV) ecosystem. It is organized into a sequential set of interactive executive briefing notebooks:

| Step / Notebook | Executive Title | Purpose & Managerial Takeaway |
|---|---|---|
| [`1_EV_SELECTION.ipynb`](file:///c:/Users/henok/Documents/projects%20to%20do/icog/1_EV_SELECTION.ipynb) | **Phase 1: Vehicle Market Selection** | Evaluated EV market adoption in Ethiopia; selected **BYD Seagull**, **BYD Yuan Up**, and **Volkswagen ID.6** as core target vehicles. |
| [`2_RAW_DATA_SCRAPING.ipynb`](file:///c:/Users/henok/Documents/projects%20to%20do/icog/2_RAW_DATA_SCRAPING.ipynb) | **Operation 1: Raw Data Collection & Discovery** | Scraped 105 active listings across **Jiji Ethiopia** and **Adey Market**; logs crawler compliance and initial market visibility. |
| [`3_DATA_PREPARATION_AND_MATCHING.ipynb`](file:///c:/Users/henok/Documents/projects%20to%20do/icog/3_DATA_PREPARATION_AND_MATCHING.ipynb) | **Operation 2: Data Preparation & Entity Matching** | Resolves local slang, typos, and Amharic keywords (`ፍሬን ሸራ`, `ፓራወልት`); classifies exact positions (**Left/Right**, **Front/Rear**). |
| [`4_DATA_CLEANING_AND_AUDIT.ipynb`](file:///c:/Users/henok/Documents/projects%20to%20do/icog/4_DATA_CLEANING_AND_AUDIT.ipynb) | **Operation 3: Data Cleaning & Quality Audit** | Eliminates duplicate reposts, standardizes prices to Ethiopian Birr (ETB), flags 93 items for technical review, and prevents zero-price corruption. |
| [`5_PRICE_ANALYSIS_AND_PRIORITY_SCORING.ipynb`](file:///c:/Users/henok/Documents/projects%20to%20do/icog/5_PRICE_ANALYSIS_AND_PRIORITY_SCORING.ipynb) | **Operation 4: Price Analysis & Import Prioritization** | Computes the multi-factor scoring model ($0.30 \\times \\text{Demand} + 0.25 \\times \\text{Scarcity} + \\dots$); delivers the 1-to-10 ranked import action plan. |

---

## Production Scraper Engine

The underlying Python scraping, database, and export automation pipeline resides in:
[`icog/ev-spare-parts-scraper/`](file:///c:/Users/henok/Documents/projects%20to%20do/icog/ev-spare-parts-scraper/)

### Quick Command-Line Execution
To re-run or refresh the live pipeline from terminal:
```bash
cd "c:\Users\henok\Documents\projects to do\icog\ev-spare-parts-scraper"
py main.py --all
```
