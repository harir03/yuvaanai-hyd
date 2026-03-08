"""
Intelli-Credit — Worker W7: Shareholding Pattern Parser

Extracts structured data from Shareholding Pattern filings:
- Promoter holding %, institutional holding %
- Pledge status and recent pledge changes
- Cross-holdings between group entities
- Public/retail holding
- Top 10 shareholders

T0/T3 implementation: Mock extraction for demo.
Future: BSE/NSE XBRL parser + tabular extraction.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker

logger = logging.getLogger(__name__)


class ShareholdingWorker(BaseDocumentWorker):
    """
    Worker W7 — Shareholding Pattern.

    Parses quarterly shareholding filings to extract promoter holding,
    pledge status, institutional patterns, and cross-holding signals.
    """

    worker_id = "W7"
    document_type = DocumentType.SHAREHOLDING_PATTERN
    display_name = "W7 — Shareholding Pattern Parser"

    async def _extract(self) -> Tuple[Dict[str, Any], int, float]:
        """
        Extract structured data from Shareholding Pattern.

        Returns:
            (extracted_data, pages_processed, confidence)
        """
        filename = os.path.basename(self.file_path)

        await self.emitter.read(
            "Parsing shareholding pattern — Q4 FY2023 filing...",
            source_document=filename,
            source_page=1,
        )

        await self.emitter.found(
            "Total paid-up capital: 2,50,00,000 shares | Face value ₹10",
            source_document=filename,
            source_page=1,
            confidence=0.96,
        )

        await self.emitter.read(
            "Extracting promoter and promoter group holdings...",
            source_document=filename,
            source_page=2,
        )

        await self.emitter.found(
            "Promoter holding: 62.4% (1,56,00,000 shares) | Of which 38.0% pledged",
            source_document=filename,
            source_page=2,
            source_excerpt="Category I(A)(1): Indian Promoters - 1,56,00,000 shares (62.40%)",
            confidence=0.95,
        )

        # Flag high pledge
        await self.emitter.flagged(
            "HIGH PLEDGE ALERT: 38% of promoter shares pledged — increased from 22% last quarter (+16%)",
            source_document=filename,
            source_page=2,
            confidence=0.94,
        )

        await self.emitter.read(
            "Analyzing institutional investor patterns...",
            source_document=filename,
            source_page=4,
        )

        await self.emitter.found(
            "FII: 8.2% | DII (MF): 12.5% | Insurance: 4.8% | Banks: 2.1%",
            source_document=filename,
            source_page=4,
            confidence=0.93,
        )

        await self.emitter.read(
            "Checking for cross-holdings and group company links...",
            source_document=filename,
            source_page=6,
        )

        await self.emitter.flagged(
            "Cross-holding detected: ABC Trading holds 4.2% — ABC Trading is also an RPT counterparty",
            source_document=filename,
            source_page=6,
            confidence=0.88,
        )

        extracted_data = {
            "company_name": "XYZ Steel Industries Ltd",
            "filing_quarter": "Q4 FY2023 (Jan-Mar 2023)",
            "total_shares": 25000000,
            "face_value": 10.0,
            "paid_up_capital": 25000.0,  # lakhs
            "promoter_holding": {
                "shares": 15600000,
                "percentage": 62.4,
                "pledged_shares": 5928000,
                "pledged_pct": 38.0,
                "pledged_pct_previous_quarter": 22.0,
                "pledge_change": 16.0,
                "pledge_trend": "increasing",
                "encumbered_shares": 5928000,
                "source_page": 2,
            },
            "promoter_group_detail": [
                {"name": "Rajesh Kumar", "shares": 8750000, "pct": 35.0,
                 "pledged": 3325000, "pledged_pct": 38.0},
                {"name": "Kumar Family Trust", "shares": 4350000, "pct": 17.4,
                 "pledged": 1653000, "pledged_pct": 38.0},
                {"name": "Rajesh Kumar HUF", "shares": 2500000, "pct": 10.0,
                 "pledged": 950000, "pledged_pct": 38.0},
            ],
            "institutional_holding": {
                "fii": {"shares": 2050000, "pct": 8.2},
                "dii_mutual_funds": {"shares": 3125000, "pct": 12.5},
                "insurance": {"shares": 1200000, "pct": 4.8},
                "banks_fi": {"shares": 525000, "pct": 2.1},
                "total_institutional": {"shares": 6900000, "pct": 27.6},
            },
            "public_holding": {
                "shares": 2500000,
                "pct": 10.0,
                "retail_shareholders": 8450,
            },
            "top_10_shareholders": [
                {"name": "Rajesh Kumar", "shares": 8750000, "pct": 35.0, "category": "Promoter"},
                {"name": "Kumar Family Trust", "shares": 4350000, "pct": 17.4, "category": "Promoter Group"},
                {"name": "HDFC Mutual Fund", "shares": 1875000, "pct": 7.5, "category": "DII"},
                {"name": "Rajesh Kumar HUF", "shares": 2500000, "pct": 10.0, "category": "Promoter Group"},
                {"name": "Goldman Sachs FII", "shares": 1250000, "pct": 5.0, "category": "FII"},
                {"name": "ABC Trading Pvt Ltd", "shares": 1050000, "pct": 4.2, "category": "Body Corporate"},
                {"name": "LIC of India", "shares": 1200000, "pct": 4.8, "category": "Insurance"},
                {"name": "SBI MF", "shares": 1250000, "pct": 5.0, "category": "DII"},
                {"name": "Fidelity FII", "shares": 800000, "pct": 3.2, "category": "FII"},
                {"name": "Banks (aggregate)", "shares": 525000, "pct": 2.1, "category": "Banks/FI"},
            ],
            "cross_holdings": {
                "detected": True,
                "entities": [
                    {
                        "entity": "ABC Trading Pvt Ltd",
                        "shares": 1050000,
                        "pct": 4.2,
                        "relationship": "RPT counterparty — purchases ₹7.2 cr/yr",
                        "risk": "Potential circular arrangement",
                    },
                ],
            },
            "quarterly_trend": {
                "q1_fy23_promoter_pct": 64.0,
                "q2_fy23_promoter_pct": 63.5,
                "q3_fy23_promoter_pct": 62.8,
                "q4_fy23_promoter_pct": 62.4,
                "trend": "declining",
                "note": "Promoter diluting 1.6% over FY2023 — watch for further dilution",
            },
        }

        pages_processed = 8
        confidence = 0.93

        return extracted_data, pages_processed, confidence
