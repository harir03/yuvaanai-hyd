"""
Intelli-Credit — Worker W5: Legal Notice Parser

Extracts structured data from Legal Notices / Court Orders:
- Claimant, respondent, claim type
- Claim amounts, filing dates, current status
- Forum (NCLT, ITAT, High Court, District Court, SEBI, Consumer)
- Links to ongoing litigation risk

Uses PyMuPDF for parsing + Claude Haiku for case classification.
Falls back to mock data when parsing or LLM is unavailable.
"""

import os
import logging
from typing import Dict, Any, Tuple

from backend.models.schemas import DocumentType
from backend.workers.base_worker import BaseDocumentWorker
from backend.agents.ingestor.document_ingestor import DocumentIngestor
from backend.agents.ingestor.llm_extractor import extract_with_llm
from config.prompts.extraction_prompts import LEGAL_NOTICE_EXTRACTION_PROMPT

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
        """Extract structured data from Legal Notices."""
        filename = os.path.basename(self.file_path)

        # ── Step 1: Parse the document ──
        await self.emitter.read(
            f"Parsing {filename} with document ingestor...",
            source_document=filename,
        )

        ingestor = DocumentIngestor()
        ingest_result = await ingestor.ingest(self.file_path, "legal_notice")

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
            "Sending to Claude Haiku for legal case classification...",
            source_document=filename,
        )

        template_vars = {"company_name": "Unknown"}

        extracted = await extract_with_llm(
            document_text=doc_text,
            prompt_template=LEGAL_NOTICE_EXTRACTION_PROMPT,
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
            cases = extracted.get("cases", [])
            if cases:
                await self.emitter.found(
                    f"{len(cases)} legal cases identified",
                    source_document=filename,
                    confidence=confidence,
                )
                for case in cases[:3]:
                    if isinstance(case, dict):
                        forum = case.get("forum", "Unknown")
                        amount = case.get("claim_amount", "N/A")
                        await self.emitter.found(
                            f"{forum}: claim amount ₹{amount}",
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
            "total_cases": 3,
            "total_exposure": 835.0,
            "cases": [
                {
                    "case_id": "CP/123/2022", "forum": "NCLT", "forum_type": "civil",
                    "claimant": "M/s Steel Traders Pvt Ltd", "respondent": "XYZ Steel Industries Ltd",
                    "claim_type": "unpaid_invoices", "claim_amount": 470.0,
                    "filing_date": "2022-09-15", "next_hearing": "2024-04-20",
                    "status": "pending", "severity": "HIGH", "disclosed_in_ar": True,
                    "source_page": 3, "summary": "Supplier claims ₹4.7 cr for 6 months unpaid invoices for steel billets",
                },
                {
                    "case_id": "ITA/456/MUM/2023", "forum": "ITAT", "forum_type": "tax",
                    "claimant": "Income Tax Department", "respondent": "XYZ Steel Industries Ltd",
                    "claim_type": "tax_dispute", "claim_amount": 320.0,
                    "filing_date": "2023-02-10", "next_hearing": "2024-06-15",
                    "status": "pending", "severity": "MEDIUM", "disclosed_in_ar": True,
                    "source_page": 7, "summary": "Depreciation disallowance on revalued assets per AO order u/s 143(3)",
                },
                {
                    "case_id": "CC/789/2023", "forum": "Consumer Forum", "forum_type": "consumer",
                    "claimant": "Raj Constructions Pvt Ltd", "respondent": "XYZ Steel Industries Ltd",
                    "claim_type": "product_quality", "claim_amount": 45.0,
                    "filing_date": "2023-08-01", "next_hearing": "2024-06-30",
                    "status": "pending", "severity": "LOW", "disclosed_in_ar": False,
                    "source_page": 11, "summary": "Product quality complaint — TMT bars did not meet IS 1786:2008 standards",
                },
            ],
            "risk_classification": {
                "high_severity_cases": 1, "medium_severity_cases": 1, "low_severity_cases": 1,
                "nclt_active": True, "criminal_cases": 0, "regulatory_cases": 0,
            },
            "ar_disclosure_check": {
                "cases_in_legal_docs": 3, "cases_disclosed_in_ar": 2, "undisclosed_cases": 1,
                "undisclosed_details": ["CC/789/2023 — Consumer Forum complaint ₹0.45 cr not disclosed"],
                "note": "1 undisclosed case found — possible disclosure gap in Annual Report",
            },
            "total_contingent_liability": {
                "amount": 835.0, "unit": "lakhs",
                "note": "Total potential exposure from all 3 pending cases",
            },
            "_extraction_method": "mock",
        }
