"""
Intelli-Credit — Worker W8: Rating Report Parser

Extracts structured data from Credit Rating Reports:
- Current rating, previous rating, outlook
- Rating rationale and key strengths/weaknesses
- Upgrade/downgrade history
- Watch/review status
- Peer comparison signals

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
from config.prompts.extraction_prompts import RATING_REPORT_EXTRACTION_PROMPT

logger = logging.getLogger(__name__)


class RatingReportWorker(BaseDocumentWorker):
    """
    Worker W8 — Rating Report.

    Parses credit rating reports to extract current ratings,
    upgrade/downgrade history, and outlook assessment.
    """

    worker_id = "W8"
    document_type = DocumentType.RATING_REPORT
    display_name = "W8 — Rating Report Parser"

    async def _extract(self) -> Tuple[Dict[str, Any], int, float]:
        """Extract structured data from Rating Reports."""
        filename = os.path.basename(self.file_path)

        # ── Step 1: Parse the document ──
        await self.emitter.read(
            f"Parsing {filename} with document ingestor...",
            source_document=filename,
        )

        ingestor = DocumentIngestor()
        ingest_result = await ingestor.ingest(self.file_path, "rating_report")

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
            "Sending to Claude Haiku for rating report analysis...",
            source_document=filename,
        )

        template_vars = {
            "company_name": "Unknown",
            "rating_agency": "Unknown",
        }

        extracted = await extract_with_llm(
            document_text=doc_text,
            prompt_template=RATING_REPORT_EXTRACTION_PROMPT,
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
            current = extracted.get("current_rating", {})
            if isinstance(current, dict) and current.get("long_term"):
                await self.emitter.found(
                    f"Current Rating: {current.get('long_term')} ({current.get('outlook', 'N/A')})",
                    source_document=filename,
                    confidence=confidence,
                )
            downgrade = extracted.get("downgrade_details", {})
            if isinstance(downgrade, dict) and downgrade.get("has_downgrade"):
                await self.emitter.flagged(
                    f"Rating downgrade detected: {downgrade.get('from_rating')} → {downgrade.get('to_rating')}",
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
            "rating_agency": "CRISIL",
            "report_date": "2023-12-15",
            "current_rating": {
                "long_term": "BBB+", "short_term": "A2", "outlook": "Stable",
                "facility_type": "Long-term bank facilities", "facility_amount": 8500.0, "source_page": 2,
            },
            "rating_history": [
                {"date": "2023-12-15", "rating": "BBB+", "outlook": "Stable", "action": "Reaffirmed"},
                {"date": "2022-12-20", "rating": "BBB+", "outlook": "Stable", "action": "Reaffirmed"},
                {"date": "2022-03-10", "rating": "BBB+", "outlook": "Negative → Stable", "action": "Downgraded from A-"},
                {"date": "2021-06-15", "rating": "A-", "outlook": "Negative", "action": "Outlook revised to Negative"},
                {"date": "2020-12-01", "rating": "A-", "outlook": "Stable", "action": "Reaffirmed"},
            ],
            "downgrade_details": {
                "has_downgrade": True, "last_downgrade_date": "2022-03-10",
                "from_rating": "A-", "to_rating": "BBB+", "notches": 1,
                "reasons": [
                    "Deteriorating debt coverage metrics (DSCR declined from 1.6x to 1.2x)",
                    "Elevated working capital requirements due to steel price volatility",
                    "Debt-equity ratio increased from 1.1x to 1.35x",
                ],
                "source_page": 4,
            },
            "watch_status": {"on_watch": False, "watch_type": None, "next_review_date": "2024-06-30"},
            "key_strengths": [
                "Established track record of 15+ years in steel manufacturing",
                "Diversified customer base across construction, auto, and infrastructure",
                "Operational facilities in Maharashtra with proximity to raw material sources",
                "Experienced management with deep sector knowledge",
            ],
            "key_weaknesses": [
                "High working capital intensity inherent in steel trading/manufacturing",
                "Susceptibility to cyclical steel price fluctuations",
                "Elevated debt-equity ratio (1.35x) against industry median of 1.0x",
                "Customer concentration — top 5 customers contribute 45% of revenue",
            ],
            "financial_indicators_from_rating": {
                "revenue_fy23": 14230.0, "ebitda_margin": 15.0, "pat_margin": 7.0,
                "debt_equity": 1.35, "interest_coverage": 2.1, "current_ratio": 1.15, "source_page": 6,
            },
            "peer_comparison": {
                "industry_median_rating": "A-", "company_position": "Below median",
                "peer_companies": [
                    {"name": "Alpha Steel Ltd", "rating": "A", "outlook": "Stable"},
                    {"name": "Beta Metals Corp", "rating": "A-", "outlook": "Stable"},
                    {"name": "Gamma Iron Works", "rating": "BBB+", "outlook": "Positive"},
                ],
            },
            "_extraction_method": "mock",
        }
