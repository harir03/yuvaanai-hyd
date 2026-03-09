"""
Intelli-Credit — Worker W7: Shareholding Pattern Parser

Extracts structured data from Shareholding Pattern filings:
- Promoter holding %, institutional holding %
- Pledge status and recent pledge changes
- Cross-holdings between group entities
- Public/retail holding
- Top 10 shareholders

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
from config.prompts.extraction_prompts import SHAREHOLDING_PATTERN_EXTRACTION_PROMPT

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
        """Extract structured data from Shareholding Pattern."""
        filename = os.path.basename(self.file_path)

        # ── Step 1: Parse the document ──
        await self.emitter.read(
            f"Parsing {filename} with document ingestor...",
            source_document=filename,
        )

        ingestor = DocumentIngestor()
        ingest_result = await ingestor.ingest(self.file_path, "shareholding_pattern")

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
            "Sending to Claude Haiku for shareholding analysis...",
            source_document=filename,
        )

        template_vars = {
            "company_name": "Unknown",
            "period": "Q4 FY2023",
        }

        extracted = await extract_with_llm(
            document_text=doc_text,
            prompt_template=SHAREHOLDING_PATTERN_EXTRACTION_PROMPT,
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
            promoter = extracted.get("promoter_holding", {})
            if isinstance(promoter, dict) and promoter.get("percentage"):
                await self.emitter.found(
                    f"Promoter holding: {promoter['percentage']}%",
                    source_document=filename,
                    confidence=confidence,
                )
                pledged = promoter.get("pledged_pct", 0)
                if pledged and float(pledged) > 20:
                    await self.emitter.flagged(
                        f"HIGH PLEDGE: {pledged}% of promoter shares pledged",
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
            "filing_quarter": "Q4 FY2023 (Jan-Mar 2023)",
            "total_shares": 25000000, "face_value": 10.0, "paid_up_capital": 25000.0,
            "promoter_holding": {
                "shares": 15600000, "percentage": 62.4, "pledged_shares": 5928000,
                "pledged_pct": 38.0, "pledged_pct_previous_quarter": 22.0,
                "pledge_change": 16.0, "pledge_trend": "increasing",
                "encumbered_shares": 5928000, "source_page": 2,
            },
            "promoter_group_detail": [
                {"name": "Rajesh Kumar", "shares": 8750000, "pct": 35.0, "pledged": 3325000, "pledged_pct": 38.0},
                {"name": "Kumar Family Trust", "shares": 4350000, "pct": 17.4, "pledged": 1653000, "pledged_pct": 38.0},
                {"name": "Rajesh Kumar HUF", "shares": 2500000, "pct": 10.0, "pledged": 950000, "pledged_pct": 38.0},
            ],
            "institutional_holding": {
                "fii": {"shares": 2050000, "pct": 8.2},
                "dii_mutual_funds": {"shares": 3125000, "pct": 12.5},
                "insurance": {"shares": 1200000, "pct": 4.8},
                "banks_fi": {"shares": 525000, "pct": 2.1},
                "total_institutional": {"shares": 6900000, "pct": 27.6},
            },
            "public_holding": {"shares": 2500000, "pct": 10.0, "retail_shareholders": 8450},
            "cross_holdings": {
                "detected": True,
                "entities": [{"entity": "ABC Trading Pvt Ltd", "shares": 1050000, "pct": 4.2, "relationship": "RPT counterparty — purchases ₹7.2 cr/yr", "risk": "Potential circular arrangement"}],
            },
            "quarterly_trend": {
                "q1_fy23_promoter_pct": 64.0, "q2_fy23_promoter_pct": 63.5,
                "q3_fy23_promoter_pct": 62.8, "q4_fy23_promoter_pct": 62.4,
                "trend": "declining", "note": "Promoter diluting 1.6% over FY2023 — watch for further dilution",
            },
            "_extraction_method": "mock",
        }
