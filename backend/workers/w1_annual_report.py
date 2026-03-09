"""
Intelli-Credit — Worker W1: Annual Report Parser

Extracts structured financial data from Annual Reports:
- Revenue (3-year), EBITDA, PAT, Debt, Net Worth
- Related Party Transactions (RPTs)
- Auditor Qualifications
- Litigation Disclosure
- Director details, board composition

Uses PyMuPDF for text extraction + Claude Haiku for structured extraction.
Falls back to mock data when document parsing or LLM is unavailable.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker
from backend.agents.ingestor.document_ingestor import DocumentIngestor
from backend.agents.ingestor.llm_extractor import extract_with_llm, is_llm_available
from config.prompts.extraction_prompts import ANNUAL_REPORT_EXTRACTION_PROMPT

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

        Pipeline: PyMuPDF → Claude Haiku → Structured JSON
        Falls back to mock data if file is empty or LLM unavailable.
        """
        filename = os.path.basename(self.file_path)

        # ── Step 1: Parse the document ──
        await self.emitter.read(
            f"Parsing {filename} with document ingestor...",
            source_document=filename,
        )

        ingestor = DocumentIngestor()
        ingest_result = await ingestor.ingest(self.file_path, "annual_report")

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
            "Sending to Claude Haiku for structured financial extraction...",
            source_document=filename,
        )

        template_vars = {
            "company_name": "Unknown",
            "fy_current": "2023",
            "fy_prev1": "2022",
            "fy_prev2": "2021",
        }

        extracted = await extract_with_llm(
            document_text=doc_text,
            prompt_template=ANNUAL_REPORT_EXTRACTION_PROMPT,
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
            # Emit key findings
            revenue = extracted.get("revenue", {})
            if isinstance(revenue, dict):
                fy_val = revenue.get("fy2023") or revenue.get("fy_current")
                if fy_val:
                    await self.emitter.found(
                        f"Revenue FY2023: ₹{fy_val}",
                        source_document=filename,
                        confidence=confidence,
                    )

            rpts = extracted.get("rpts", {})
            if isinstance(rpts, dict) and rpts.get("count"):
                await self.emitter.found(
                    f"{rpts['count']} Related Party Transactions found",
                    source_document=filename,
                    confidence=confidence,
                )

            auditor_quals = extracted.get("auditor_qualifications", [])
            if auditor_quals:
                await self.emitter.flagged(
                    f"Auditor qualifications detected: {len(auditor_quals)} item(s)",
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
            "company_name": "XYZ Steel Industries Ltd",
            "cin": "L27100MH2001PLC123456",
            "financial_year": "FY2023",
            "revenue": {
                "fy2023": 14230.0,
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
            "total_debt": {"fy2023": 8540.0, "unit": "lakhs", "source_page": 50},
            "net_worth": {"fy2023": 6320.0, "unit": "lakhs", "source_page": 50},
            "auditor_qualifications": [
                {"type": "emphasis_of_matter", "detail": "Inventory valuation methodology — Note 12", "source_page": 9},
            ],
            "rpts": {
                "count": 5,
                "total_amount": 1840.0,
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
            "auditor": {"name": "M/s. RST & Associates", "type": "Statutory Auditor", "opinion": "Qualified (with Emphasis of Matter)"},
            "_extraction_method": "mock",
        }
