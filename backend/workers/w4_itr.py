"""
Intelli-Credit — Worker W4: Income Tax Return (ITR) Parser

Extracts structured data from ITR filings:
- Schedule BP (Business/Profession income)
- Schedule BS (Balance Sheet)
- Revenue, expenses, depreciation
- ITR-vs-AR divergence signals
- Tax credits and deductions

T0/T3 implementation: Mock extraction for demo.
Future: PDF/Excel parser + LLM extraction for ITR-6 format.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker

logger = logging.getLogger(__name__)


class ITRWorker(BaseDocumentWorker):
    """
    Worker W4 — Income Tax Return.

    Parses ITR-6 filings to extract Schedule BP income, Schedule BS
    balance sheet, and flags divergences with Annual Report figures.
    """

    worker_id = "W4"
    document_type = DocumentType.ITR
    display_name = "W4 — ITR Parser"

    async def _extract(self) -> Tuple[Dict[str, Any], int, float]:
        """
        Extract structured data from ITR filing.

        Returns:
            (extracted_data, pages_processed, confidence)
        """
        filename = os.path.basename(self.file_path)

        await self.emitter.read(
            "Parsing ITR-6 filing — Schedule BP (Business/Profession)...",
            source_document=filename,
            source_page=1,
        )

        await self.emitter.found(
            "PAN: AABCX1234F | AY 2023-24 | XYZ Steel Industries Ltd",
            source_document=filename,
            source_page=1,
            confidence=0.97,
        )

        await self.emitter.read(
            "Extracting Schedule BP — Profit & Loss from Business...",
            source_document=filename,
            source_page=3,
        )

        await self.emitter.found(
            "Gross Total Income: ₹11,42,00,000 | Tax Payable: ₹2,97,20,000",
            source_document=filename,
            source_page=4,
            source_excerpt="Schedule BP: Turnover ₹1,40,80,00,000; Gross Profit ₹28,16,00,000",
            confidence=0.94,
        )

        await self.emitter.read(
            "Extracting Schedule BS — Balance Sheet as per ITR...",
            source_document=filename,
            source_page=8,
        )

        await self.emitter.found(
            "ITR Balance Sheet: Total Assets ₹148.6 cr, Net Worth ₹61.8 cr, Total Debt ₹86.8 cr",
            source_document=filename,
            source_page=9,
            confidence=0.92,
        )

        await self.emitter.read(
            "Checking depreciation schedule and brought-forward losses...",
            source_document=filename,
            source_page=12,
        )

        await self.emitter.found(
            "Depreciation claimed: ₹4.82 cr | No brought-forward losses",
            source_document=filename,
            source_page=12,
            confidence=0.90,
        )

        # Flag potential AR vs ITR divergence
        await self.emitter.flagged(
            "ITR revenue ₹140.8 cr vs AR revenue ₹142.3 cr — ₹1.5 cr divergence (1.1%)",
            source_document=filename,
            source_page=4,
            confidence=0.91,
        )

        extracted_data = {
            "pan": "AABCX1234F",
            "assessment_year": "AY 2023-24",
            "itr_form": "ITR-6",
            "company_name": "XYZ Steel Industries Ltd",
            "schedule_bp": {
                "turnover": 14080.0,  # lakhs
                "gross_profit": 2816.0,
                "depreciation": 482.0,
                "net_profit": 1142.0,
                "tax_payable": 297.2,
                "source_page": 4,
                "unit": "lakhs",
            },
            "schedule_bs": {
                "total_assets": 14860.0,  # lakhs
                "total_liabilities": 14860.0,
                "net_worth": 6180.0,
                "secured_loans": 5480.0,
                "unsecured_loans": 3200.0,
                "total_debt": 8680.0,
                "fixed_assets": 8240.0,
                "current_assets": 5120.0,
                "investments": 1500.0,
                "source_page": 9,
                "unit": "lakhs",
            },
            "depreciation": {
                "current_year": 482.0,
                "accumulated": 2340.0,
                "method": "WDV",
                "unit": "lakhs",
                "source_page": 12,
            },
            "tax_summary": {
                "gross_total_income": 1142.0,
                "deductions_80c_80d": 15.0,
                "taxable_income": 1127.0,
                "tax_payable": 297.2,
                "advance_tax_paid": 280.0,
                "tds_credit": 12.5,
                "self_assessment_tax": 4.7,
                "unit": "lakhs",
            },
            "brought_forward_losses": {
                "business_loss": 0.0,
                "capital_loss": 0.0,
                "unabsorbed_depreciation": 0.0,
            },
            "revenue_from_itr": {
                "turnover": 14080.0,
                "unit": "lakhs",
                "note": "Schedule BP turnover — used for cross-verification with AR/Bank/GST",
            },
            "itr_ar_divergence": {
                "itr_revenue": 14080.0,
                "ar_revenue_expected": 14230.0,
                "divergence_amount": 150.0,
                "divergence_pct": 1.1,
                "note": "Minor divergence — likely timing/classification difference",
            },
        }

        pages_processed = 18
        confidence = 0.91

        return extracted_data, pages_processed, confidence
