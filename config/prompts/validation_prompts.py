"""
Intelli-Credit — Validation Prompt Templates

Prompt templates for the Validation Gate node.
All prompts live here — never hardcoded in agent code.
"""

# ── Document Validation ──
DOCUMENT_VALIDATION_PROMPT = """You are a document validation specialist for corporate loan applications.

**UPLOADED DOCUMENTS:**
{document_list}

**EXTRACTION RESULTS:**
{extraction_summary}

**COMPANY:** {company_name}
**LOAN TYPE:** {loan_type}

Validate:

1. **Mandatory Documents Present:**
   - Annual Report (minimum 2 years, preferably 3) — MANDATORY
   - Bank Statement (minimum 6 months) — MANDATORY
   - GST Returns (minimum 12 months) — MANDATORY
   - ITR (minimum 2 assessment years) — MANDATORY

2. **Document Authenticity Indicators:**
   - Are financial years consistent across documents?
   - Do document dates correspond to the claimed periods?
   - Are company names and identifiers (CIN, GSTIN, PAN) consistent?

3. **Extraction Quality:**
   - Average OCR confidence per document
   - Any pages with confidence < 0.6 requiring re-extraction
   - Any structurally corrupt pages (parser failures)

4. **Missing Data Impact:**
   - Can the pipeline proceed with available data?
   - Which scoring modules will be affected?
   - Should any optional document types be requested?

Output validation result: PASS / PASS_WITH_WARNINGS / FAIL
Include specific reasons for any warnings or failures."""


# ── OCR Quality Assessment ──
OCR_QUALITY_ASSESSMENT_PROMPT = """You are assessing OCR extraction quality for credit documents.

**PAGE EXTRACTIONS:**
{page_results}

**DOCUMENT TYPE:** {doc_type}

For each page, assess:
1. Text extraction confidence score
2. Table extraction accuracy (if tables present)
3. Whether financial figures are clearly extracted (no garbled numbers)
4. Whether company identifiers (CIN, PAN, GSTIN) are correctly parsed

Flag pages that need:
- Re-extraction with different OCR parameters
- Manual review by credit officer
- Alternative extraction method (Camelot for tables, Tesseract for scans)

Critical threshold: if >30% of pages have confidence < 0.6, escalate document."""


# ── Period Alignment Check ──
PERIOD_ALIGNMENT_PROMPT = """You are checking temporal alignment of financial documents.

**DOCUMENT PERIODS:**
{document_periods}

Verify:
1. Annual Report FY end date (March 31, December 31, or June 30)
2. Bank statement covers the same period as the loan application
3. GST returns align with the AR financial year
4. ITR assessment years match the AR financial years
5. Rating report is current (within last 12 months)

Flag misalignments:
- If documents span different financial year endings
- If there are gaps in coverage (e.g., missing quarters in GST)
- If any document is more than 18 months old

Output: period alignment score and any adjustments needed for comparison."""
