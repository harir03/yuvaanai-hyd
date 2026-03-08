"""
Intelli-Credit — Worker W6: Board Minutes Parser

Extracts structured data from Board Minutes:
- Director attendance patterns
- RPT approvals (cross-checked with AR disclosure)
- CFO/KMP changes
- Risk committee discussions
- Special resolutions, borrowing authorizations

T0/T3 implementation: Mock extraction for demo.
Future: PDF parser + LLM extraction for board resolution classification.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker

logger = logging.getLogger(__name__)


class BoardMinutesWorker(BaseDocumentWorker):
    """
    Worker W6 — Board Minutes.

    Parses board meeting minutes to extract governance data,
    RPT approvals, KMP changes, and risk committee observations.
    """

    worker_id = "W6"
    document_type = DocumentType.BOARD_MINUTES
    display_name = "W6 — Board Minutes Parser"

    async def _extract(self) -> Tuple[Dict[str, Any], int, float]:
        """
        Extract structured data from Board Minutes.

        Returns:
            (extracted_data, pages_processed, confidence)
        """
        filename = os.path.basename(self.file_path)

        await self.emitter.read(
            "Parsing board minutes — extracting meeting records for FY2023...",
            source_document=filename,
            source_page=1,
        )

        await self.emitter.found(
            "6 board meetings held in FY2023 (Apr 2022 – Mar 2023)",
            source_document=filename,
            source_page=1,
            confidence=0.95,
        )

        await self.emitter.read(
            "Analyzing director attendance across all meetings...",
            source_document=filename,
            source_page=2,
        )

        await self.emitter.found(
            "MD Rajesh Kumar: 6/6 meetings | ID Priya Sharma: 5/6 | CFO Vikram Desai: 6/6",
            source_document=filename,
            source_page=3,
            confidence=0.94,
        )

        await self.emitter.read(
            "Extracting Related Party Transaction approvals...",
            source_document=filename,
            source_page=8,
        )

        await self.emitter.found(
            "7 RPT approvals in board minutes — AR discloses only 5",
            source_document=filename,
            source_page=9,
            source_excerpt="Resolution No. 23-14: Approved purchase of steel from ABC Trading...",
            confidence=0.90,
        )

        # Critical RPT concealment signal
        await self.emitter.flagged(
            "RPT CONCEALMENT: Board approved 7 RPTs (₹24.6 cr) but AR discloses only 5 (₹18.4 cr) — "
            "2 undisclosed RPTs worth ₹6.2 cr",
            source_document=filename,
            source_page=9,
            confidence=0.92,
        )

        await self.emitter.read(
            "Checking for KMP changes, borrowing resolutions, risk discussions...",
            source_document=filename,
            source_page=14,
        )

        await self.emitter.found(
            "Borrowing authorization: Board approved additional ₹25 cr term loan from SBI",
            source_document=filename,
            source_page=15,
            confidence=0.91,
        )

        await self.emitter.found(
            "Risk committee noted: Steel price volatility, working capital stress in Q3",
            source_document=filename,
            source_page=18,
            confidence=0.86,
        )

        extracted_data = {
            "company_name": "XYZ Steel Industries Ltd",
            "financial_year": "FY2023",
            "meetings": {
                "total_meetings": 6,
                "meeting_dates": [
                    "2022-04-28", "2022-07-30", "2022-10-15",
                    "2023-01-20", "2023-02-14", "2023-03-28",
                ],
                "quorum_met_all": True,
            },
            "director_attendance": [
                {"name": "Rajesh Kumar", "designation": "Managing Director", "din": "00123456",
                 "attended": 6, "total": 6, "attendance_pct": 100.0},
                {"name": "Priya Sharma", "designation": "Independent Director", "din": "00789012",
                 "attended": 5, "total": 6, "attendance_pct": 83.3},
                {"name": "Vikram Desai", "designation": "CFO", "din": "00345678",
                 "attended": 6, "total": 6, "attendance_pct": 100.0},
                {"name": "Anita Reddy", "designation": "Independent Director", "din": "00567890",
                 "attended": 4, "total": 6, "attendance_pct": 66.7},
                {"name": "Suresh Patel", "designation": "Nominee Director", "din": "00234567",
                 "attended": 5, "total": 6, "attendance_pct": 83.3},
            ],
            "rpt_approvals": {
                "count": 7,
                "total_amount": 2460.0,  # lakhs
                "transactions": [
                    {"party": "ABC Trading (promoter entity)", "amount": 720.0,
                     "nature": "purchases", "resolution_no": "23-14", "disclosed_in_ar": True},
                    {"party": "PQR Logistics (director interest)", "amount": 480.0,
                     "nature": "services", "resolution_no": "23-16", "disclosed_in_ar": True},
                    {"party": "Steel Suppliers Pvt Ltd (group co)", "amount": 340.0,
                     "nature": "purchases", "resolution_no": "23-18", "disclosed_in_ar": True},
                    {"party": "XYZ Foundation (promoter trust)", "amount": 180.0,
                     "nature": "donations", "resolution_no": "23-22", "disclosed_in_ar": True},
                    {"party": "Green Energy Pvt Ltd (KMP interest)", "amount": 120.0,
                     "nature": "services", "resolution_no": "23-25", "disclosed_in_ar": True},
                    {"party": "Kumar Family Trust", "amount": 380.0,
                     "nature": "loan_given", "resolution_no": "23-28", "disclosed_in_ar": False},
                    {"party": "Desai Consulting (CFO entity)", "amount": 240.0,
                     "nature": "consulting_fees", "resolution_no": "23-31", "disclosed_in_ar": False},
                ],
                "source_page": 9,
            },
            "rpt_concealment_check": {
                "board_approved_count": 7,
                "ar_disclosed_count": 5,
                "undisclosed_count": 2,
                "undisclosed_amount": 620.0,  # lakhs
                "undisclosed_transactions": [
                    "Kumar Family Trust — ₹3.8 cr loan (resolution 23-28)",
                    "Desai Consulting (CFO entity) — ₹2.4 cr consulting fees (resolution 23-31)",
                ],
                "concealment_severity": "HIGH",
                "note": "2 RPTs worth ₹6.2 cr approved by board but not disclosed in AR — potential governance concern",
            },
            "kmp_changes": {
                "changes_in_fy": 0,
                "resignations": [],
                "appointments": [],
                "note": "No KMP changes during FY2023 — stability signal",
            },
            "borrowing_resolutions": [
                {
                    "resolution_no": "23-20",
                    "date": "2022-10-15",
                    "description": "Additional term loan ₹25 cr from SBI for capacity expansion",
                    "amount": 2500.0,  # lakhs
                    "lender": "SBI",
                    "purpose": "Capacity expansion — new rolling mill",
                },
            ],
            "risk_discussions": [
                {
                    "meeting_date": "2023-01-20",
                    "topic": "Steel price volatility impact on margins",
                    "severity": "MEDIUM",
                    "action": "Hedging strategy to be evaluated by CFO",
                },
                {
                    "meeting_date": "2023-02-14",
                    "topic": "Working capital stress in Q3 due to delayed receivables",
                    "severity": "HIGH",
                    "action": "CFO to pursue receivable recovery from top 5 debtors",
                },
            ],
        }

        pages_processed = 22
        confidence = 0.90

        return extracted_data, pages_processed, confidence
