"""
Intelli-Credit — Worker W8: Rating Report Parser

Extracts structured data from Credit Rating Reports:
- Current rating, previous rating, outlook
- Rating rationale and key strengths/weaknesses
- Upgrade/downgrade history
- Watch/review status
- Peer comparison signals

T0/T3 implementation: Mock extraction for demo.
Future: PDF parser + LLM extraction for CRISIL/ICRA/CARE/India Ratings formats.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker

logger = logging.getLogger(__name__)


class RatingReportWorker(BaseDocumentWorker):
    """
    Worker W8 — Rating Report.

    Parses credit rating reports to extract current ratings,
    upgrade/downgrade history, and outlook assessment.
    """

    worker_id = "W8"
    document_type = DocumentType.RATING_REPORT
    display_name = "W8 — Rating Report Parser"

    async def _extract(self) -> Tuple[Dict[str, Any], int, float]:
        """
        Extract structured data from Rating Reports.

        Returns:
            (extracted_data, pages_processed, confidence)
        """
        filename = os.path.basename(self.file_path)

        await self.emitter.read(
            "Parsing credit rating report — identifying agency and rating details...",
            source_document=filename,
            source_page=1,
        )

        await self.emitter.found(
            "Rating Agency: CRISIL | Report Date: December 2023",
            source_document=filename,
            source_page=1,
            confidence=0.97,
        )

        await self.emitter.read(
            "Extracting current rating and outlook...",
            source_document=filename,
            source_page=2,
        )

        await self.emitter.found(
            "Current Rating: CRISIL BBB+ (Stable) | Long-term bank facilities ₹85 cr",
            source_document=filename,
            source_page=2,
            source_excerpt="CRISIL has assigned its 'CRISIL BBB+/Stable' rating to the long-term bank facilities",
            confidence=0.96,
        )

        await self.emitter.read(
            "Checking rating history for upgrades/downgrades...",
            source_document=filename,
            source_page=4,
        )

        await self.emitter.found(
            "Rating History: A- (2021) → BBB+ (2022) → BBB+ (2023) — downgraded from A- in Mar 2022",
            source_document=filename,
            source_page=4,
            confidence=0.94,
        )

        # Flag the downgrade
        await self.emitter.flagged(
            "RATING DOWNGRADE: A- → BBB+ (Mar 2022) — cited deteriorating debt metrics and WC stress",
            source_document=filename,
            source_page=4,
            confidence=0.93,
        )

        await self.emitter.read(
            "Extracting key strengths and weaknesses from rating rationale...",
            source_document=filename,
            source_page=6,
        )

        await self.emitter.found(
            "Strengths: 15yr track record, diversified customer base | "
            "Weaknesses: High working capital needs, cyclical steel sector, elevated D/E",
            source_document=filename,
            source_page=7,
            confidence=0.90,
        )

        await self.emitter.read(
            "Checking for watch/review status...",
            source_document=filename,
            source_page=8,
        )

        await self.emitter.found(
            "No active rating watch — outlook is Stable, next review due Jun 2024",
            source_document=filename,
            source_page=8,
            confidence=0.95,
        )

        extracted_data = {
            "company_name": "XYZ Steel Industries Ltd",
            "rating_agency": "CRISIL",
            "report_date": "2023-12-15",
            "current_rating": {
                "long_term": "BBB+",
                "short_term": "A2",
                "outlook": "Stable",
                "facility_type": "Long-term bank facilities",
                "facility_amount": 8500.0,  # lakhs
                "source_page": 2,
            },
            "rating_history": [
                {"date": "2023-12-15", "rating": "BBB+", "outlook": "Stable", "action": "Reaffirmed"},
                {"date": "2022-12-20", "rating": "BBB+", "outlook": "Stable", "action": "Reaffirmed"},
                {"date": "2022-03-10", "rating": "BBB+", "outlook": "Negative → Stable", "action": "Downgraded from A-"},
                {"date": "2021-06-15", "rating": "A-", "outlook": "Negative", "action": "Outlook revised to Negative"},
                {"date": "2020-12-01", "rating": "A-", "outlook": "Stable", "action": "Reaffirmed"},
            ],
            "downgrade_details": {
                "has_downgrade": True,
                "last_downgrade_date": "2022-03-10",
                "from_rating": "A-",
                "to_rating": "BBB+",
                "notches": 1,
                "reasons": [
                    "Deteriorating debt coverage metrics (DSCR declined from 1.6x to 1.2x)",
                    "Elevated working capital requirements due to steel price volatility",
                    "Debt-equity ratio increased from 1.1x to 1.35x",
                ],
                "source_page": 4,
            },
            "watch_status": {
                "on_watch": False,
                "watch_type": None,
                "next_review_date": "2024-06-30",
            },
            "key_strengths": [
                "Established track record of 15+ years in steel manufacturing",
                "Diversified customer base across construction, auto, and infrastructure",
                "Operational facilities in Maharashtra with proximity to raw material sources",
                "Experienced management with deep sector knowledge",
            ],
            "key_weaknesses": [
                "High working capital intensity inherent in steel trading/manufacturing",
                "Susceptibility to cyclical steel price fluctuations",
                "Elevated debt-equity ratio (1.35x) against industry median of 1.0x",
                "Customer concentration — top 5 customers contribute 45% of revenue",
            ],
            "financial_indicators_from_rating": {
                "revenue_fy23": 14230.0,  # lakhs (from rating report)
                "ebitda_margin": 15.0,     # %
                "pat_margin": 7.0,          # %
                "debt_equity": 1.35,
                "interest_coverage": 2.1,
                "current_ratio": 1.15,
                "source_page": 6,
            },
            "peer_comparison": {
                "industry_median_rating": "A-",
                "company_position": "Below median",
                "peer_companies": [
                    {"name": "Alpha Steel Ltd", "rating": "A", "outlook": "Stable"},
                    {"name": "Beta Metals Corp", "rating": "A-", "outlook": "Stable"},
                    {"name": "Gamma Iron Works", "rating": "BBB+", "outlook": "Positive"},
                ],
            },
        }

        pages_processed = 12
        confidence = 0.92

        return extracted_data, pages_processed, confidence
