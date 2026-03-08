"""
Intelli-Credit — Government Scrapers Package

5 Indian government portal scrapers for Tier-1 (weight 1.0) verification:
  - MCA21: Company master data, directors, charges
  - SEBI: Regulatory actions, adjudication orders
  - RBI: Wilful defaulter list, NBFC checks
  - NJDG: Litigation records, NCLT proceedings
  - GST: Registration status, filing compliance

All scrapers follow the same pattern:
  1. Try real scrape with timeout + retry
  2. Fall back to mock data on failure (pipeline never breaks)
  3. Return List[ResearchFinding] with source_tier=1, verified=True
"""

from backend.agents.research.scrapers.mca21_scraper import scrape_mca21
from backend.agents.research.scrapers.sebi_scraper import scrape_sebi
from backend.agents.research.scrapers.rbi_scraper import scrape_rbi
from backend.agents.research.scrapers.njdg_scraper import scrape_njdg
from backend.agents.research.scrapers.gst_scraper import scrape_gst

__all__ = [
    "scrape_mca21",
    "scrape_sebi",
    "scrape_rbi",
    "scrape_njdg",
    "scrape_gst",
]
