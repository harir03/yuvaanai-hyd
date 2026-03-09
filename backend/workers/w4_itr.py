"""
Intelli-Credit — Worker W4: Income Tax Return (ITR) Parser

Extracts structured data from ITR filings:
- Schedule BP (Business/Profession income)
- Schedule BS (Balance Sheet)
- Revenue, expenses, depreciation
- ITR-vs-AR divergence signals
- Tax credits and deductions

Uses PyMuPDF for parsing + Claude Haiku for structured extraction.
Falls back to mock data when parsing or LLM is unavailable.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker
from backend.agents.ingestor.document_ingestor import DocumentIngestor
from backend.agents.ingestor.llm_extractor import extract_with_llm
from config.prompts.extraction_prompts import ITR_EXTRACTION_PROMPT

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
        """Extract structured data from ITR filing."""
        filename = os.path.basename(self.file_path)

        # ── Step 1: Parse the document ──
        await self.emitter.read(
            f"Parsing {filename} with document ingestor...",
            source_document=filename,
        )

        ingestor = DocumentIngestor()
        ingest_result = await ingestor.ingest(self.file_path, "itr")

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
            "Sending to Claude Haiku for ITR structured extraction...",
            source_document=filename,
        )

        template_vars = {
            "company_name": "Unknown",
            "pan": "Unknown",
            "assessment_years": "AY 2023-24",
        }

        extracted = await extract_with_llm(
            document_text=doc_text,
            prompt_template=ITR_EXTRACTION_PROMPT,
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
            schedule_bp = extracted.get("schedule_bp", {})
            if isinstance(schedule_bp, dict) and schedule_bp.get("turnover"):
                await self.emitter.found(
                    f"Schedule BP Turnover: ₹{schedule_bp['turnover']}",
                    source_document=filename,
                    confidence=confidence,
                )
            schedule_bs = extracted.get("schedule_bs", {})
            if isinstance(schedule_bs, dict) and schedule_bs.get("net_worth"):
                await self.emitter.found(
                    f"Schedule BS Net Worth: ₹{schedule_bs['net_worth']}",
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
            "pan": "AABCX1234F",
            "assessment_year": "AY 2023-24",
            "itr_form": "ITR-6",
            "company_name": "XYZ Steel Industries Ltd",
            "schedule_bp": {
                "turnover": 14080.0, "gross_profit": 2816.0, "depreciation": 482.0,
                "net_profit": 1142.0, "tax_payable": 297.2, "source_page": 4, "unit": "lakhs",
            },
            "schedule_bs": {
                "total_assets": 14860.0, "total_liabilities": 14860.0, "net_worth": 6180.0,
                "secured_loans": 5480.0, "unsecured_loans": 3200.0, "total_debt": 8680.0,
                "fixed_assets": 8240.0, "current_assets": 5120.0, "investments": 1500.0,
                "source_page": 9, "unit": "lakhs",
            },
            "depreciation": {
                "current_year": 482.0, "accumulated": 2340.0, "method": "WDV",
                "unit": "lakhs", "source_page": 12,
            },
            "tax_summary": {
                "gross_total_income": 1142.0, "deductions_80c_80d": 15.0,
                "taxable_income": 1127.0, "tax_payable": 297.2,
                "advance_tax_paid": 280.0, "tds_credit": 12.5,
                "self_assessment_tax": 4.7, "unit": "lakhs",
            },
            "brought_forward_losses": {
                "business_loss": 0.0, "capital_loss": 0.0, "unabsorbed_depreciation": 0.0,
            },
            "revenue_from_itr": {
                "turnover": 14080.0, "unit": "lakhs",
                "note": "Schedule BP turnover — used for cross-verification with AR/Bank/GST",
            },
            "itr_ar_divergence": {
                "itr_revenue": 14080.0, "ar_revenue_expected": 14230.0,
                "divergence_amount": 150.0, "divergence_pct": 1.1,
                "note": "Minor divergence — likely timing/classification difference",
            },
            "_extraction_method": "mock",
        }
