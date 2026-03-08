"""
Intelli-Credit — Worker W5: Legal Notice Parser

Extracts structured data from Legal Notices / Court Orders:
- Claimant, respondent, claim type
- Claim amounts, filing dates, current status
- Forum (NCLT, ITAT, High Court, District Court, SEBI, Consumer)
- Links to ongoing litigation risk

T0/T3 implementation: Mock extraction for demo.
Future: PDF parser + LLM-based case classification.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker

logger = logging.getLogger(__name__)


class LegalNoticeWorker(BaseDocumentWorker):
    """
    Worker W5 — Legal Notice / Court Orders.

    Parses legal documents to extract case details, claim amounts,
    litigation status, and classify risk severity.
    """

    worker_id = "W5"
    document_type = DocumentType.LEGAL_NOTICE
    display_name = "W5 — Legal Notice Parser"

    async def _extract(self) -> Tuple[Dict[str, Any], int, float]:
        """
        Extract structured data from Legal Notices.

        Returns:
            (extracted_data, pages_processed, confidence)
        """
        filename = os.path.basename(self.file_path)

        await self.emitter.read(
            "Parsing legal notice documents — extracting case headers...",
            source_document=filename,
            source_page=1,
        )

        await self.emitter.found(
            "3 legal cases identified involving XYZ Steel Industries Ltd",
            source_document=filename,
            source_page=1,
            confidence=0.93,
        )

        await self.emitter.read(
            "Case 1: NCLT petition (Company Petition No. CP/123/2022)...",
            source_document=filename,
            source_page=2,
        )

        await self.emitter.found(
            "NCLT: Supplier claims ₹4.7 cr for unpaid invoices — hearing scheduled Apr 2024",
            source_document=filename,
            source_page=3,
            source_excerpt="Company Petition No. CP/123/2022 filed by M/s Steel Traders Pvt Ltd",
            confidence=0.91,
        )

        await self.emitter.read(
            "Case 2: ITAT appeal (ITA No. 456/MUM/2023)...",
            source_document=filename,
            source_page=6,
        )

        await self.emitter.found(
            "ITAT: Tax dispute ₹3.2 cr — disallowance of depreciation on certain assets",
            source_document=filename,
            source_page=7,
            confidence=0.89,
        )

        await self.emitter.read(
            "Case 3: Consumer forum complaint...",
            source_document=filename,
            source_page=10,
        )

        await self.emitter.found(
            "Consumer Forum: Product quality complaint ₹0.45 cr — minor, respond by Jun 2024",
            source_document=filename,
            source_page=11,
            confidence=0.87,
        )

        # Cross-reference with AR disclosure
        await self.emitter.flagged(
            "AR discloses 2 cases but 3 found in legal documents — 1 undisclosed case (consumer forum)",
            source_document=filename,
            source_page=11,
            confidence=0.88,
        )

        extracted_data = {
            "company_name": "XYZ Steel Industries Ltd",
            "total_cases": 3,
            "total_exposure": 835.0,  # lakhs (4.7cr + 3.2cr + 0.45cr = 8.35cr)
            "cases": [
                {
                    "case_id": "CP/123/2022",
                    "forum": "NCLT",
                    "forum_type": "civil",
                    "claimant": "M/s Steel Traders Pvt Ltd",
                    "respondent": "XYZ Steel Industries Ltd",
                    "claim_type": "unpaid_invoices",
                    "claim_amount": 470.0,  # lakhs
                    "filing_date": "2022-09-15",
                    "next_hearing": "2024-04-20",
                    "status": "pending",
                    "severity": "HIGH",
                    "disclosed_in_ar": True,
                    "source_page": 3,
                    "summary": "Supplier claims ₹4.7 cr for 6 months unpaid invoices for steel billets",
                },
                {
                    "case_id": "ITA/456/MUM/2023",
                    "forum": "ITAT",
                    "forum_type": "tax",
                    "claimant": "Income Tax Department",
                    "respondent": "XYZ Steel Industries Ltd",
                    "claim_type": "tax_dispute",
                    "claim_amount": 320.0,  # lakhs
                    "filing_date": "2023-02-10",
                    "next_hearing": "2024-06-15",
                    "status": "pending",
                    "severity": "MEDIUM",
                    "disclosed_in_ar": True,
                    "source_page": 7,
                    "summary": "Depreciation disallowance on revalued assets per AO order u/s 143(3)",
                },
                {
                    "case_id": "CC/789/2023",
                    "forum": "Consumer Forum",
                    "forum_type": "consumer",
                    "claimant": "Raj Constructions Pvt Ltd",
                    "respondent": "XYZ Steel Industries Ltd",
                    "claim_type": "product_quality",
                    "claim_amount": 45.0,  # lakhs
                    "filing_date": "2023-08-01",
                    "next_hearing": "2024-06-30",
                    "status": "pending",
                    "severity": "LOW",
                    "disclosed_in_ar": False,
                    "source_page": 11,
                    "summary": "Product quality complaint — TMT bars did not meet IS 1786:2008 standards",
                },
            ],
            "risk_classification": {
                "high_severity_cases": 1,
                "medium_severity_cases": 1,
                "low_severity_cases": 1,
                "nclt_active": True,
                "criminal_cases": 0,
                "regulatory_cases": 0,
            },
            "ar_disclosure_check": {
                "cases_in_legal_docs": 3,
                "cases_disclosed_in_ar": 2,
                "undisclosed_cases": 1,
                "undisclosed_details": ["CC/789/2023 — Consumer Forum complaint ₹0.45 cr not disclosed"],
                "note": "1 undisclosed case found — possible disclosure gap in Annual Report",
            },
            "total_contingent_liability": {
                "amount": 835.0,
                "unit": "lakhs",
                "note": "Total potential exposure from all 3 pending cases",
            },
        }

        pages_processed = 15
        confidence = 0.89

        return extracted_data, pages_processed, confidence
