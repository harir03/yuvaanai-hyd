"""
Intelli-Credit — NLP Entity Extraction Service

Wraps spaCy (standard NER) and GLiNER (zero-shot NER for Indian entities)
for extracting structured entities from financial documents.

Falls back to regex-based pattern matching when NLP libraries are unavailable.

Entity types extracted:
- Indian company identifiers: CIN, GSTIN, PAN, TAN, LLPIN
- Financial entities: amounts (₹ crores/lakhs), dates, percentages, ratios
- Legal entities: court names, case numbers, act references
- Person entities: names, designations (Director, CFO, CEO)
- Organization entities: company names, bank names, regulatory bodies

Models loaded ONCE at startup (Section 17 performance rule).
"""

import re
import logging
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

# ── Singleton holders ──
_spacy_model = None
_gliner_model = None
_mode: str = "uninitialized"  # "spacy+gliner", "spacy", "gliner", "regex"


# ── Entity types ──

@dataclass
class ExtractedEntity:
    """A single extracted entity from text."""
    text: str
    label: str
    start: int = 0
    end: int = 0
    confidence: float = 1.0
    source: str = "regex"  # "spacy", "gliner", or "regex"


@dataclass
class ExtractionResult:
    """Result of entity extraction from a text block."""
    entities: List[ExtractedEntity] = field(default_factory=list)
    mode: str = "regex"
    text_length: int = 0

    def by_label(self, label: str) -> List[ExtractedEntity]:
        """Filter entities by label."""
        return [e for e in self.entities if e.label == label]

    def unique_values(self, label: str) -> List[str]:
        """Get unique entity texts for a given label."""
        seen = set()
        result = []
        for e in self.entities:
            if e.label == label and e.text not in seen:
                seen.add(e.text)
                result.append(e.text)
        return result


# ── Indian entity patterns (regex) ──

# CIN: 21-char alphanumeric (e.g., U27100MH1907PLC000260)
_CIN_RE = re.compile(r'\b[UL]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}\b')

# GSTIN: 15-char (e.g., 27AABCU9603R1ZM)
_GSTIN_RE = re.compile(r'\b\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d][A-Z]\b')

# PAN: 10-char (e.g., AABCU9603R)
_PAN_RE = re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b')

# TAN: 10-char (e.g., MUMB12345A)
_TAN_RE = re.compile(r'\b[A-Z]{4}\d{5}[A-Z]\b')

# LLPIN: AAI-xxxx (e.g., AAI-1234)
_LLPIN_RE = re.compile(r'\bAAI-\d{4,}\b')

# Indian amounts: ₹ or Rs. followed by number with cr/crore/lakh/lakhs
_AMOUNT_RE = re.compile(
    r'(?:₹|Rs\.?|INR)\s*[\d,]+(?:\.\d+)?\s*(?:crore|crores|cr|lakh|lakhs|lac|million|mn|billion|bn)?',
    re.IGNORECASE,
)

# Percentages
_PERCENT_RE = re.compile(r'\b\d+(?:\.\d+)?\s*%')

# Ratios (e.g., 1.38x, 2.5:1)
_RATIO_RE = re.compile(r'\b\d+(?:\.\d+)?x\b|\b\d+(?:\.\d+)?:\d+(?:\.\d+)?\b')

# Dates (various Indian formats)
_DATE_RE = re.compile(
    r'\b(?:\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+\d{2,4}|FY\s*\d{2,4}(?:-\d{2,4})?)\b',
    re.IGNORECASE,
)

# Court names
_COURT_RE = re.compile(
    r'\b(?:Supreme Court|High Court|NCLT|NCLAT|District Court|Sessions Court|'
    r'Bombay High Court|Delhi High Court|Madras High Court|Calcutta High Court|'
    r'SAT|SEBI Adjudicating Officer|DRT|DRAT)\b',
    re.IGNORECASE,
)

# Case numbers (e.g., CP(IB)-123/NCLT/MB/2023)
_CASE_NO_RE = re.compile(
    r'\b(?:CP|CA|MA|OA|SA|WP|CRL|CMP)[\s(]*(?:IB|C)?[\s)]*[-/]?\s*\d+[-/]\w+[-/]\w+[-/]\d{4}\b',
    re.IGNORECASE,
)

# Regulatory body references
_REGULATOR_RE = re.compile(
    r'\b(?:RBI|SEBI|MCA|NCLT|NCLAT|IRDAI|PFRDA|NHB|NABARD|'
    r'Reserve Bank of India|Securities and Exchange Board|'
    r'Ministry of Corporate Affairs|Companies Act|'
    r'FEMA|PMLA|IBC|Insolvency and Bankruptcy Code)\b',
    re.IGNORECASE,
)

# Designation patterns
_DESIGNATION_RE = re.compile(
    r'\b(?:Director|Managing Director|MD|CEO|CFO|COO|CTO|'
    r'Chairman|Chairperson|Company Secretary|CS|'
    r'Independent Director|Whole-?time Director|'
    r'Additional Director|Nominee Director|'
    r'Chief Financial Officer|Auditor|Statutory Auditor)\b',
    re.IGNORECASE,
)

# GLiNER entity labels for zero-shot NER
GLINER_LABELS = [
    "company_name",
    "person_name",
    "designation",
    "indian_company_id",
    "financial_amount",
    "bank_name",
    "court_name",
    "regulatory_body",
    "legal_section",
    "location",
]


def _init_models() -> None:
    """Load NLP models once at startup. Fall back to regex if unavailable."""
    global _spacy_model, _gliner_model, _mode
    if _mode != "uninitialized":
        return

    spacy_ok = False
    gliner_ok = False

    # Try spaCy
    try:
        import spacy
        try:
            _spacy_model = spacy.load("en_core_web_sm")
            spacy_ok = True
            logger.info("[NER] Loaded spaCy model en_core_web_sm")
        except OSError:
            # Model not downloaded
            logger.warning("[NER] spaCy model en_core_web_sm not found — run: python -m spacy download en_core_web_sm")
    except ImportError:
        logger.warning("[NER] spaCy not installed — skipping")

    # Try GLiNER
    try:
        from gliner import GLiNER
        _gliner_model = GLiNER.from_pretrained("urchade/gliner_base")
        gliner_ok = True
        logger.info("[NER] Loaded GLiNER model urchade/gliner_base")
    except ImportError:
        logger.warning("[NER] GLiNER not installed — skipping")
    except Exception as e:
        logger.warning(f"[NER] GLiNER load failed: {e} — skipping")

    if spacy_ok and gliner_ok:
        _mode = "spacy+gliner"
    elif spacy_ok:
        _mode = "spacy"
    elif gliner_ok:
        _mode = "gliner"
    else:
        _mode = "regex"
        logger.warning("[NER] Neither spaCy nor GLiNER available — using regex-only extraction")


def _extract_regex(text: str) -> List[ExtractedEntity]:
    """Regex-based entity extraction for Indian financial documents."""
    entities = []

    for match in _CIN_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="CIN",
            start=match.start(), end=match.end(),
            confidence=0.95, source="regex",
        ))

    for match in _GSTIN_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="GSTIN",
            start=match.start(), end=match.end(),
            confidence=0.95, source="regex",
        ))

    for match in _PAN_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="PAN",
            start=match.start(), end=match.end(),
            confidence=0.90, source="regex",
        ))

    for match in _TAN_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="TAN",
            start=match.start(), end=match.end(),
            confidence=0.90, source="regex",
        ))

    for match in _LLPIN_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="LLPIN",
            start=match.start(), end=match.end(),
            confidence=0.95, source="regex",
        ))

    for match in _AMOUNT_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="AMOUNT",
            start=match.start(), end=match.end(),
            confidence=0.85, source="regex",
        ))

    for match in _PERCENT_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="PERCENTAGE",
            start=match.start(), end=match.end(),
            confidence=0.90, source="regex",
        ))

    for match in _RATIO_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="RATIO",
            start=match.start(), end=match.end(),
            confidence=0.85, source="regex",
        ))

    for match in _DATE_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="DATE",
            start=match.start(), end=match.end(),
            confidence=0.80, source="regex",
        ))

    for match in _COURT_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="COURT",
            start=match.start(), end=match.end(),
            confidence=0.90, source="regex",
        ))

    for match in _CASE_NO_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="CASE_NUMBER",
            start=match.start(), end=match.end(),
            confidence=0.85, source="regex",
        ))

    for match in _REGULATOR_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="REGULATOR",
            start=match.start(), end=match.end(),
            confidence=0.90, source="regex",
        ))

    for match in _DESIGNATION_RE.finditer(text):
        entities.append(ExtractedEntity(
            text=match.group(), label="DESIGNATION",
            start=match.start(), end=match.end(),
            confidence=0.85, source="regex",
        ))

    return entities


def _extract_spacy(text: str) -> List[ExtractedEntity]:
    """spaCy-based NER extraction."""
    if _spacy_model is None:
        return []

    doc = _spacy_model(text)
    entities = []
    for ent in doc.ents:
        # Map spaCy labels to our domain labels
        label_map = {
            "PERSON": "PERSON",
            "ORG": "ORGANIZATION",
            "GPE": "LOCATION",
            "DATE": "DATE",
            "MONEY": "AMOUNT",
            "PERCENT": "PERCENTAGE",
            "CARDINAL": "NUMBER",
            "LAW": "LEGAL_REFERENCE",
        }
        label = label_map.get(ent.label_, ent.label_)
        entities.append(ExtractedEntity(
            text=ent.text,
            label=label,
            start=ent.start_char,
            end=ent.end_char,
            confidence=0.80,
            source="spacy",
        ))
    return entities


def _extract_gliner(text: str) -> List[ExtractedEntity]:
    """GLiNER zero-shot NER for Indian financial entities."""
    if _gliner_model is None:
        return []

    try:
        predictions = _gliner_model.predict_entities(
            text,
            GLINER_LABELS,
            threshold=0.5,
        )
        entities = []
        for pred in predictions:
            entities.append(ExtractedEntity(
                text=pred["text"],
                label=pred["label"].upper(),
                start=pred["start"],
                end=pred["end"],
                confidence=pred.get("score", 0.7),
                source="gliner",
            ))
        return entities
    except Exception as e:
        logger.warning(f"[NER/GLiNER] Extraction failed: {e}")
        return []


def extract_entities(text: str) -> ExtractionResult:
    """Extract all entities from text using available NLP models.

    Uses the best available pipeline:
    1. spaCy + GLiNER + regex (all three)
    2. spaCy + regex
    3. GLiNER + regex
    4. regex only (fallback)

    Returns:
        ExtractionResult with deduplicated entities.
    """
    _init_models()

    all_entities: List[ExtractedEntity] = []

    # Always run regex (catches Indian-specific patterns)
    all_entities.extend(_extract_regex(text))

    # Add spaCy entities if available
    if _mode in ("spacy+gliner", "spacy"):
        all_entities.extend(_extract_spacy(text))

    # Add GLiNER entities if available
    if _mode in ("spacy+gliner", "gliner"):
        all_entities.extend(_extract_gliner(text))

    # Deduplicate by (text, label) — prefer higher confidence
    seen: Dict[Tuple[str, str], ExtractedEntity] = {}
    for ent in all_entities:
        key = (ent.text, ent.label)
        if key not in seen or ent.confidence > seen[key].confidence:
            seen[key] = ent

    return ExtractionResult(
        entities=list(seen.values()),
        mode=_mode,
        text_length=len(text),
    )


def extract_indian_ids(text: str) -> Dict[str, List[str]]:
    """Quick extraction of Indian identifiers only (CIN, GSTIN, PAN, TAN).

    Does not require NLP models — pure regex.
    """
    return {
        "cin": [m.group() for m in _CIN_RE.finditer(text)],
        "gstin": [m.group() for m in _GSTIN_RE.finditer(text)],
        "pan": [m.group() for m in _PAN_RE.finditer(text)],
        "tan": [m.group() for m in _TAN_RE.finditer(text)],
        "llpin": [m.group() for m in _LLPIN_RE.finditer(text)],
    }


def extract_financial_figures(text: str) -> List[Dict[str, str]]:
    """Extract financial amounts and ratios from text.

    Returns list of dicts with 'text', 'type' (amount/percentage/ratio).
    """
    figures = []
    for m in _AMOUNT_RE.finditer(text):
        figures.append({"text": m.group(), "type": "amount"})
    for m in _PERCENT_RE.finditer(text):
        figures.append({"text": m.group(), "type": "percentage"})
    for m in _RATIO_RE.finditer(text):
        figures.append({"text": m.group(), "type": "ratio"})
    return figures


def get_mode() -> str:
    """Return current NER mode."""
    _init_models()
    return _mode


def reset() -> None:
    """Reset singleton state (for testing)."""
    global _spacy_model, _gliner_model, _mode
    _spacy_model = None
    _gliner_model = None
    _mode = "uninitialized"
