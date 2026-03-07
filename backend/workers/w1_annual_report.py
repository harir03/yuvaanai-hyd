"""
Intelli-Credit — Worker W1: Annual Report Parser

Extracts structured financial data from Annual Reports:
- Revenue (3-year), EBITDA, PAT, Debt, Net Worth
- Related Party Transactions (RPTs)
- Auditor Qualifications
- Litigation Disclosure
- Director details, board composition

T0 implementation: Mock extraction for demo.
T1+ will integrate Unstructured.io + Camelot + LLM extraction.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker

logger = logging.getLogger(__name__)


class AnnualReportWorker(BaseDocumentWorker):
    """
    Worker W1 — Annual Report.

    Parses corporate annual reports to extract financial statements,
    auditor notes, RPTs, and governance data.
    """

    worker_id = "W1"
    document_type = DocumentType.ANNUAL_REPORT
    display_name = "W1 — Annual Report Parser"

    async def _extract(self) -> Tuple[Dict[str, Any], int, float]:
        """
        Extract structured data from an Annual Report.

        T0: Returns mock structured data simulating what the full
        Unstructured.io + Camelot + LLM pipeline would produce.

        Returns:
            (extracted_data, pages_processed, confidence)
        """
        filename = os.path.basename(self.file_path)

        # Emit reading events (simulating page-by-page processing)
        await self.emitter.read(
            "Parsing financial statements section...",
            source_document=filename,
            source_page=12,
        )

        await self.emitter.found(
            "Revenue FY2023: ₹142.3 crores (standalone)",
            source_document=filename,
            source_page=45,
            source_excerpt="Total Revenue from Operations: ₹1,42,30,00,000",
            confidence=0.92,
        )

        await self.emitter.found(
            "Revenue FY2022: ₹128.7 crores | FY2021: ₹115.4 crores",
            source_document=filename,
            source_page=46,
            confidence=0.90,
        )

        await self.emitter.read(
            "Scanning auditor's report for qualifications...",
            source_document=filename,
            source_page=8,
        )

        await self.emitter.found(
            "Auditor qualification: Emphasis of Matter on inventory valuation",
            source_document=filename,
            source_page=9,
            source_excerpt="We draw attention to Note 12 regarding inventory valuation methodology...",
            confidence=0.88,
        )

        await self.emitter.read(
            "Extracting Related Party Transactions (RPTs)...",
            source_document=filename,
            source_page=67,
        )

        await self.emitter.found(
            "5 Related Party Transactions totalling ₹18.4 crores disclosed",
            source_document=filename,
            source_page=68,
            confidence=0.85,
        )

        await self.emitter.read(
            "Extracting litigation disclosure from Notes to Accounts...",
            source_document=filename,
            source_page=72,
        )

        await self.emitter.found(
            "2 litigation cases disclosed: 1 tax dispute (₹3.2 cr), 1 commercial (₹1.8 cr)",
            source_document=filename,
            source_page=73,
            confidence=0.87,
        )

        # Mock extracted data — realistic for XYZ Steel example
        extracted_data = {
            "company_name": "XYZ Steel Industries Ltd",
            "cin": "L27100MH2001PLC123456",
            "financial_year": "FY2023",
            "revenue": {
                "fy2023": 14230.0,  # in lakhs
                "fy2022": 12870.0,
                "fy2021": 11540.0,
                "unit": "lakhs",
                "source_page": 45,
            },
            "ebitda": {
                "fy2023": 2134.5,
                "fy2022": 1802.0,
                "fy2021": 1615.0,
                "unit": "lakhs",
                "source_page": 45,
            },
            "pat": {
                "fy2023": 998.0,
                "fy2022": 812.0,
                "fy2021": 695.0,
                "unit": "lakhs",
                "source_page": 46,
            },
            "total_debt": {
                "fy2023": 8540.0,
                "unit": "lakhs",
                "source_page": 50,
            },
            "net_worth": {
                "fy2023": 6320.0,
                "unit": "lakhs",
                "source_page": 50,
            },
            "auditor_qualifications": [
                {
                    "type": "emphasis_of_matter",
                    "detail": "Inventory valuation methodology — Note 12",
                    "source_page": 9,
                },
            ],
            "rpts": {
                "count": 5,
                "total_amount": 1840.0,  # lakhs
                "transactions": [
                    {"party": "ABC Trading (promoter entity)", "amount": 720.0, "nature": "purchases"},
                    {"party": "PQR Logistics (director interest)", "amount": 480.0, "nature": "services"},
                    {"party": "Steel Suppliers Pvt Ltd (group co)", "amount": 340.0, "nature": "purchases"},
                    {"party": "XYZ Foundation (promoter trust)", "amount": 180.0, "nature": "donations"},
                    {"party": "Green Energy Pvt Ltd (KMP interest)", "amount": 120.0, "nature": "services"},
                ],
                "source_page": 68,
            },
            "litigation_disclosure": {
                "cases_disclosed": 2,
                "cases": [
                    {"type": "tax_dispute", "amount": 320.0, "status": "pending", "forum": "ITAT"},
                    {"type": "commercial", "amount": 180.0, "status": "pending", "forum": "NCLT"},
                ],
                "source_page": 73,
            },
            "directors": [
                {"name": "Rajesh Kumar", "designation": "Managing Director", "din": "00123456"},
                {"name": "Priya Sharma", "designation": "Independent Director", "din": "00789012"},
                {"name": "Vikram Desai", "designation": "CFO", "din": "00345678"},
            ],
            "auditor": {
                "name": "M/s. RST & Associates",
                "type": "Statutory Auditor",
                "opinion": "Qualified (with Emphasis of Matter)",
            },
        }

        pages_processed = 84
        confidence = 0.89

        return extracted_data, pages_processed, confidence
