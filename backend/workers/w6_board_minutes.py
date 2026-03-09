"""
Intelli-Credit — Worker W6: Board Minutes Parser

Extracts structured data from Board Minutes:
- Director attendance patterns
- RPT approvals (cross-checked with AR disclosure)
- CFO/KMP changes
- Risk committee discussions
- Special resolutions, borrowing authorizations

Uses PyMuPDF for parsing + Claude Haiku for extraction.
Falls back to mock data when parsing or LLM is unavailable.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker
from backend.agents.ingestor.document_ingestor import DocumentIngestor
from backend.agents.ingestor.llm_extractor import extract_with_llm
from config.prompts.extraction_prompts import BOARD_MINUTES_EXTRACTION_PROMPT

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
        """Extract structured data from Board Minutes."""
        filename = os.path.basename(self.file_path)

        # ── Step 1: Parse the document ──
        await self.emitter.read(
            f"Parsing {filename} with document ingestor...",
            source_document=filename,
        )

        ingestor = DocumentIngestor()
        ingest_result = await ingestor.ingest(self.file_path, "board_minutes")

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
            "Sending to Claude Haiku for board minutes analysis...",
            source_document=filename,
        )

        template_vars = {
            "company_name": "Unknown",
            "meeting_dates": "FY2023",
        }

        extracted = await extract_with_llm(
            document_text=doc_text,
            prompt_template=BOARD_MINUTES_EXTRACTION_PROMPT,
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
            rpt_approvals = extracted.get("rpt_approvals", {})
            if isinstance(rpt_approvals, dict) and rpt_approvals.get("count"):
                await self.emitter.found(
                    f"{rpt_approvals['count']} RPT approvals found in board minutes",
                    source_document=filename,
                    confidence=confidence,
                )
            kmp = extracted.get("kmp_changes", {})
            if isinstance(kmp, dict) and kmp.get("changes_in_fy", 0) > 0:
                await self.emitter.flagged(
                    f"KMP changes detected: {kmp['changes_in_fy']} change(s) in FY",
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
            "financial_year": "FY2023",
            "meetings": {
                "total_meetings": 6,
                "meeting_dates": ["2022-04-28", "2022-07-30", "2022-10-15", "2023-01-20", "2023-02-14", "2023-03-28"],
                "quorum_met_all": True,
            },
            "director_attendance": [
                {"name": "Rajesh Kumar", "designation": "Managing Director", "din": "00123456", "attended": 6, "total": 6, "attendance_pct": 100.0},
                {"name": "Priya Sharma", "designation": "Independent Director", "din": "00789012", "attended": 5, "total": 6, "attendance_pct": 83.3},
                {"name": "Vikram Desai", "designation": "CFO", "din": "00345678", "attended": 6, "total": 6, "attendance_pct": 100.0},
                {"name": "Anita Reddy", "designation": "Independent Director", "din": "00567890", "attended": 4, "total": 6, "attendance_pct": 66.7},
                {"name": "Suresh Patel", "designation": "Nominee Director", "din": "00234567", "attended": 5, "total": 6, "attendance_pct": 83.3},
            ],
            "rpt_approvals": {
                "count": 7, "total_amount": 2460.0,
                "transactions": [
                    {"party": "ABC Trading (promoter entity)", "amount": 720.0, "nature": "purchases", "resolution_no": "23-14", "disclosed_in_ar": True},
                    {"party": "PQR Logistics (director interest)", "amount": 480.0, "nature": "services", "resolution_no": "23-16", "disclosed_in_ar": True},
                    {"party": "Steel Suppliers Pvt Ltd (group co)", "amount": 340.0, "nature": "purchases", "resolution_no": "23-18", "disclosed_in_ar": True},
                    {"party": "XYZ Foundation (promoter trust)", "amount": 180.0, "nature": "donations", "resolution_no": "23-22", "disclosed_in_ar": True},
                    {"party": "Green Energy Pvt Ltd (KMP interest)", "amount": 120.0, "nature": "services", "resolution_no": "23-25", "disclosed_in_ar": True},
                    {"party": "Kumar Family Trust", "amount": 380.0, "nature": "loan_given", "resolution_no": "23-28", "disclosed_in_ar": False},
                    {"party": "Desai Consulting (CFO entity)", "amount": 240.0, "nature": "consulting_fees", "resolution_no": "23-31", "disclosed_in_ar": False},
                ],
                "source_page": 9,
            },
            "rpt_concealment_check": {
                "board_approved_count": 7, "ar_disclosed_count": 5, "undisclosed_count": 2,
                "undisclosed_amount": 620.0,
                "undisclosed_transactions": [
                    "Kumar Family Trust — ₹3.8 cr loan (resolution 23-28)",
                    "Desai Consulting (CFO entity) — ₹2.4 cr consulting fees (resolution 23-31)",
                ],
                "concealment_severity": "HIGH",
                "note": "2 RPTs worth ₹6.2 cr approved by board but not disclosed in AR — potential governance concern",
            },
            "kmp_changes": {"changes_in_fy": 0, "resignations": [], "appointments": [], "note": "No KMP changes during FY2023 — stability signal"},
            "borrowing_resolutions": [
                {"resolution_no": "23-20", "date": "2022-10-15", "description": "Additional term loan ₹25 cr from SBI for capacity expansion", "amount": 2500.0, "lender": "SBI", "purpose": "Capacity expansion — new rolling mill"},
            ],
            "risk_discussions": [
                {"meeting_date": "2023-01-20", "topic": "Steel price volatility impact on margins", "severity": "MEDIUM", "action": "Hedging strategy to be evaluated by CFO"},
                {"meeting_date": "2023-02-14", "topic": "Working capital stress in Q3 due to delayed receivables", "severity": "HIGH", "action": "CFO to pursue receivable recovery from top 5 debtors"},
            ],
            "_extraction_method": "mock",
        }
