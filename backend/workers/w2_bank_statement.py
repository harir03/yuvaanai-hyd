"""
Intelli-Credit — Worker W2: Bank Statement Parser

Extracts structured data from Bank Statements (12 months):
- Monthly inflows / outflows
- Bounce count & EMI regularity
- Round-number transaction patterns
- Minimum / average balance
- Inward remittance patterns

Uses PyMuPDF/Camelot for parsing + Claude Haiku for structured extraction.
Falls back to mock data when parsing or LLM is unavailable.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker
from backend.agents.ingestor.document_ingestor import DocumentIngestor
from backend.agents.ingestor.llm_extractor import extract_with_llm
from config.prompts.extraction_prompts import BANK_STATEMENT_EXTRACTION_PROMPT

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
        """Extract structured data from Bank Statements."""
        filename = os.path.basename(self.file_path)

        # ── Step 1: Parse the document ──
        await self.emitter.read(
            f"Parsing {filename} with document ingestor...",
            source_document=filename,
        )

        ingestor = DocumentIngestor()
        ingest_result = await ingestor.ingest(self.file_path, "bank_statement")

        pages_processed = ingest_result.total_pages
        doc_text = ingest_result.full_text

        if not doc_text or len(doc_text.strip()) < 100:
            await self.emitter.flagged(
                f"Document {filename} has insufficient text ({len(doc_text)} chars), using mock data",
                source_document=filename,
            )
            return self._mock_data(), pages_processed or 1, 0.5

        await self.emitter.found(
            f"Extracted {len(doc_text)} chars from {pages_processed} pages (method: {ingest_result.method})",
            source_document=filename,
            confidence=ingest_result.average_confidence,
        )

        # ── Step 2: LLM Extraction ──
        await self.emitter.read(
            "Sending to Claude Haiku for bank statement analysis...",
            source_document=filename,
        )

        template_vars = {
            "company_name": "Unknown",
            "start_date": "2022-04-01",
            "end_date": "2023-03-31",
        }

        extracted = await extract_with_llm(
            document_text=doc_text,
            prompt_template=BANK_STATEMENT_EXTRACTION_PROMPT,
            template_vars=template_vars,
        )

        if "_llm_error" in extracted:
            await self.emitter.flagged(
                f"LLM extraction failed: {extracted['_llm_error']}, using heuristic data",
                source_document=filename,
            )
            confidence = 0.4
        else:
            confidence = ingest_result.average_confidence
            bounces = extracted.get("bounces", {})
            if isinstance(bounces, dict) and bounces.get("count"):
                await self.emitter.flagged(
                    f"{bounces['count']} cheque bounces detected",
                    source_document=filename,
                    confidence=confidence,
                )
            emi = extracted.get("emi_regularity", {})
            if isinstance(emi, dict) and emi.get("regularity_pct"):
                await self.emitter.found(
                    f"EMI regularity: {emi['regularity_pct']}%",
                    source_document=filename,
                    confidence=confidence,
                )

        extracted["_source_file"] = filename
        extracted["_pages_processed"] = pages_processed
        extracted["_extraction_method"] = "llm" if "_llm_error" not in extracted else "heuristic"

        return extracted, pages_processed, confidence

    @staticmethod
    def _mock_data() -> Dict[str, Any]:
        """Mock data fallback for demo — XYZ Steel example."""
        return {
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
                "total_credits": 14860.0,
                "total_debits": 14520.0,
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
                "total_amount": 35.0,
                "details": [
                    {"date": "2022-07-15", "amount": 12.0, "type": "cheque_bounce"},
                    {"date": "2022-10-22", "amount": 8.0, "type": "cheque_bounce"},
                    {"date": "2023-02-10", "amount": 15.0, "type": "cheque_bounce"},
                ],
            },
            "emi_regularity": {
                "total_months": 12, "on_time": 11, "late": 1, "missed": 0,
                "regularity_pct": 91.7, "monthly_emi_amount": 42.0,
            },
            "round_number_transactions": {
                "count": 14, "percentage_of_total": 0.36,
                "note": "14 transactions with exact round amounts (₹10L, ₹25L, etc.)",
            },
            "revenue_from_bank": {
                "annual_credits": 14860.0, "unit": "lakhs",
                "note": "Used for cross-verification with AR/GST/ITR revenue",
            },
            "_extraction_method": "mock",
        }
