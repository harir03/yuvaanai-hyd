"""
Intelli-Credit — Worker W2: Bank Statement Parser

Extracts structured data from Bank Statements (12 months):
- Monthly inflows / outflows
- Bounce count & EMI regularity
- Round-number transaction patterns
- Minimum / average balance
- Inward remittance patterns

T0 implementation: Mock extraction for demo.
T1+ will integrate Camelot/Tabula + LLM extraction.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker

logger = logging.getLogger(__name__)


class BankStatementWorker(BaseDocumentWorker):
    """
    Worker W2 — Bank Statement.

    Parses 12-month bank statements to extract cash flow patterns,
    bounce behavior, EMI regularity, and red-flag transactions.
    """

    worker_id = "W2"
    document_type = DocumentType.BANK_STATEMENT
    display_name = "W2 — Bank Statement Parser"

    async def _extract(self) -> Tuple[Dict[str, Any], int, float]:
        """
        Extract structured data from Bank Statements.

        T0: Returns mock data simulating real extraction.

        Returns:
            (extracted_data, pages_processed, confidence)
        """
        filename = os.path.basename(self.file_path)

        await self.emitter.read(
            "Parsing bank statement header — account details...",
            source_document=filename,
            source_page=1,
        )

        await self.emitter.found(
            "Account: HDFC Bank CA 50100123456789, XYZ Steel Industries Ltd",
            source_document=filename,
            source_page=1,
            confidence=0.95,
        )

        await self.emitter.read(
            "Analyzing 12 months of transaction data (Apr 2022 – Mar 2023)...",
            source_document=filename,
            source_page=2,
        )

        await self.emitter.found(
            "Total credits: ₹148.6 cr | Total debits: ₹145.2 cr | 3,847 transactions",
            source_document=filename,
            source_page=2,
            confidence=0.93,
        )

        await self.emitter.read(
            "Scanning for EMI payments, bounces, and round-number patterns...",
            source_document=filename,
            source_page=5,
        )

        await self.emitter.flagged(
            "3 cheque bounces detected: Jul-22 (₹12L), Oct-22 (₹8L), Feb-23 (₹15L)",
            source_document=filename,
            source_page=7,
            confidence=0.91,
        )

        await self.emitter.found(
            "EMI regularity: 11/12 months on-time (91.7%)",
            source_document=filename,
            source_page=12,
            confidence=0.94,
        )

        # Mock extracted data — realistic for XYZ Steel
        extracted_data = {
            "bank_name": "HDFC Bank",
            "account_number": "50100123456789",
            "account_type": "Current Account",
            "period": {"from": "2022-04-01", "to": "2023-03-31"},
            "monthly_summary": [
                {"month": "Apr-22", "credits": 1180.0, "debits": 1145.0, "closing_balance": 285.0},
                {"month": "May-22", "credits": 1220.0, "debits": 1190.0, "closing_balance": 315.0},
                {"month": "Jun-22", "credits": 1150.0, "debits": 1175.0, "closing_balance": 290.0},
                {"month": "Jul-22", "credits": 1310.0, "debits": 1280.0, "closing_balance": 320.0},
                {"month": "Aug-22", "credits": 1240.0, "debits": 1210.0, "closing_balance": 350.0},
                {"month": "Sep-22", "credits": 1180.0, "debits": 1160.0, "closing_balance": 370.0},
                {"month": "Oct-22", "credits": 1290.0, "debits": 1320.0, "closing_balance": 340.0},
                {"month": "Nov-22", "credits": 1350.0, "debits": 1310.0, "closing_balance": 380.0},
                {"month": "Dec-22", "credits": 1200.0, "debits": 1230.0, "closing_balance": 350.0},
                {"month": "Jan-23", "credits": 1270.0, "debits": 1240.0, "closing_balance": 380.0},
                {"month": "Feb-23", "credits": 1160.0, "debits": 1195.0, "closing_balance": 345.0},
                {"month": "Mar-23", "credits": 1310.0, "debits": 1265.0, "closing_balance": 390.0},
            ],
            "aggregate": {
                "total_credits": 14860.0,   # lakhs
                "total_debits": 14520.0,     # lakhs (adjusted for unit consistency)
                "average_monthly_credits": 1238.3,
                "average_monthly_debits": 1210.0,
                "average_balance": 343.0,
                "minimum_balance": 285.0,
                "maximum_balance": 390.0,
                "transaction_count": 3847,
                "unit": "lakhs",
            },
            "bounces": {
                "count": 3,
                "total_amount": 35.0,  # lakhs
                "details": [
                    {"date": "2022-07-15", "amount": 12.0, "type": "cheque_bounce"},
                    {"date": "2022-10-22", "amount": 8.0, "type": "cheque_bounce"},
                    {"date": "2023-02-10", "amount": 15.0, "type": "cheque_bounce"},
                ],
            },
            "emi_regularity": {
                "total_months": 12,
                "on_time": 11,
                "late": 1,
                "missed": 0,
                "regularity_pct": 91.7,
                "monthly_emi_amount": 42.0,  # lakhs
            },
            "round_number_transactions": {
                "count": 14,
                "percentage_of_total": 0.36,
                "note": "14 transactions with exact round amounts (₹10L, ₹25L, etc.)",
            },
            "revenue_from_bank": {
                "annual_credits": 14860.0,
                "unit": "lakhs",
                "note": "Used for cross-verification with AR/GST/ITR revenue",
            },
        }

        pages_processed = 24
        confidence = 0.91

        return extracted_data, pages_processed, confidence
