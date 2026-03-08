"""
Intelli-Credit — FinBERT Financial Text Risk Detector

Analyzes financial text for sentiment and hidden risk signals using
ProsusAI/finbert (HuggingFace transformers).

Falls back to keyword-based sentiment/risk analysis when transformers is unavailable.
Model loaded ONCE at startup (Section 17 performance rule).
"""

import logging
import re
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# ── Constants ──
MODEL_NAME = "ProsusAI/finbert"
MAX_LENGTH = 512

# Keyword dictionaries for fallback sentiment/risk analysis
_RISK_KEYWORDS = [
    "default", "defaulted", "wilful defaulter", "npa", "non-performing",
    "insolvency", "nclt", "bankruptcy", "liquidation", "winding up",
    "fraud", "fraudulent", "misappropriation", "embezzlement",
    "restructuring", "debt restructuring", "cdr", "s4a",
    "downgrade", "downgraded", "credit watch", "negative outlook",
    "qualified opinion", "adverse opinion", "disclaimer of opinion",
    "going concern", "material uncertainty", "material weakness",
    "litigation", "lawsuit", "criminal case", "prosecution",
    "regulatory action", "penalty", "fine", "censure", "debarred",
    "pledge", "pledged", "pledged shares", "invocation",
    "related party", "rpt", "related party transaction",
    "contingent liability", "off-balance sheet", "undisclosed",
    "circular trading", "round tripping", "shell company",
    "diversion of funds", "siphoning", "money laundering",
    "late filing", "non-compliance", "violation",
    "promoter exit", "stake sale", "dilution",
    "management change", "cfo resignation", "auditor change",
    "show-cause notice", "show cause", "sebi action", "rbi action",
    "qualified the report", "qualified report", "audit qualification",
    "inability to verify", "unverifiable",
]

# Severity weights: CRITICAL (1.0), HIGH (0.7), MEDIUM (0.4), LOW (0.2)
# A single CRITICAL keyword (e.g., "fraud") triggers risk detection alone.
_RISK_SEVERITY: Dict[str, float] = {
    # CRITICAL — hard-block territory, single keyword = definitive risk
    "wilful defaulter": 1.0, "fraud": 1.0, "fraudulent": 1.0,
    "money laundering": 1.0, "siphoning": 1.0, "criminal case": 1.0,
    # HIGH — serious concern, single keyword = strong risk signal
    "default": 0.7, "defaulted": 0.7, "npa": 0.7, "non-performing": 0.7,
    "insolvency": 0.7, "nclt": 0.7, "bankruptcy": 0.7, "liquidation": 0.7,
    "winding up": 0.7, "misappropriation": 0.7, "embezzlement": 0.7,
    "diversion of funds": 0.7, "round tripping": 0.7, "circular trading": 0.7,
    "shell company": 0.7, "going concern": 0.7, "material uncertainty": 0.7,
    "prosecution": 0.7,
    # MEDIUM — notable risk, needs corroboration
    "restructuring": 0.4, "debt restructuring": 0.4, "cdr": 0.4, "s4a": 0.4,
    "downgrade": 0.4, "downgraded": 0.4, "credit watch": 0.4,
    "negative outlook": 0.4, "qualified opinion": 0.4, "adverse opinion": 0.4,
    "disclaimer of opinion": 0.4, "material weakness": 0.4,
    "litigation": 0.4, "lawsuit": 0.4, "regulatory action": 0.4,
    "penalty": 0.4, "fine": 0.4, "censure": 0.4, "debarred": 0.4,
    "pledge": 0.4, "pledged": 0.4, "pledged shares": 0.4, "invocation": 0.4,
    "contingent liability": 0.4, "off-balance sheet": 0.4, "undisclosed": 0.4,
    "show-cause notice": 0.4, "show cause": 0.4, "sebi action": 0.4, "rbi action": 0.4,
    "qualified the report": 0.4, "qualified report": 0.4, "audit qualification": 0.4,
    "inability to verify": 0.4, "unverifiable": 0.4,
    # LOW — minor concern, monitoring only
    "related party": 0.2, "rpt": 0.2, "related party transaction": 0.2,
    "late filing": 0.2, "non-compliance": 0.2, "violation": 0.2,
    "promoter exit": 0.2, "stake sale": 0.2, "dilution": 0.2,
    "management change": 0.2, "cfo resignation": 0.2, "auditor change": 0.2,
}

# Severity threshold: total severity >= this triggers risk_detected
# A single CRITICAL (1.0) exceeds this; two MEDIUMs (0.4+0.4=0.8) also exceed.
RISK_SEVERITY_THRESHOLD = 0.6

_NEGATIVE_KEYWORDS = [
    "decline", "declining", "decreased", "deteriorated", "weakened",
    "loss", "losses", "negative", "adverse", "poor", "weak",
    "concern", "warning", "risk", "risky", "vulnerable",
    "slower", "contraction", "slowdown", "recession",
    "overdue", "delay", "delayed", "missed", "bounced",
    "stressed", "under stress", "pressure", "squeeze",
]

_POSITIVE_KEYWORDS = [
    "growth", "growing", "increased", "improvement", "strong",
    "robust", "healthy", "stable", "profitable", "profit",
    "upgrade", "upgraded", "positive outlook", "stable outlook",
    "expansion", "diversified", "order book", "capacity utilization",
    "government support", "pli", "subsidy", "incentive",
    "repayment", "regular repayment", "no default", "clean track",
    "unqualified opinion", "clean opinion",
]

# ── Singleton model holder ──
_model = None
_tokenizer = None
_mode: str = "uninitialized"  # "transformers" or "fallback"


def _init_model() -> None:
    """Load FinBERT model once. Fall back to keyword-based analysis."""
    global _model, _tokenizer, _mode
    if _mode != "uninitialized":
        return

    try:
        from transformers import AutoTokenizer, AutoModelForSequenceClassification
        import torch

        _tokenizer = AutoTokenizer.from_pretrained(MODEL_NAME)
        _model = AutoModelForSequenceClassification.from_pretrained(MODEL_NAME)
        _model.eval()
        _mode = "transformers"
        logger.info(f"[FinBERT] Loaded {MODEL_NAME} (transformers)")
    except ImportError:
        _model = None
        _tokenizer = None
        _mode = "fallback"
        logger.warning("[FinBERT] transformers/torch not available — using keyword fallback")
    except Exception as e:
        _model = None
        _tokenizer = None
        _mode = "fallback"
        logger.warning(f"[FinBERT] Failed to load {MODEL_NAME}: {e} — using keyword fallback")


def _keyword_analyze(text: str) -> Dict[str, Any]:
    """Keyword-based sentiment and risk analysis (fallback).

    Uses severity-weighted scoring: each risk keyword carries a severity
    weight (CRITICAL=1.0, HIGH=0.7, MEDIUM=0.4, LOW=0.2). A single
    CRITICAL keyword like "fraud investigation ongoing" triggers risk
    detection — not just a keyword count threshold.
    """
    text_lower = text.lower()

    # Match risk keywords with severity weighting
    risk_matches = []
    total_severity = 0.0
    max_severity = 0.0
    risk_detail = []
    for kw in _RISK_KEYWORDS:
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, text_lower):
            severity = _RISK_SEVERITY.get(kw, 0.4)
            risk_matches.append(kw)
            total_severity += severity
            max_severity = max(max_severity, severity)
            risk_detail.append({"keyword": kw, "severity": severity})

    negative_count = sum(
        1 for kw in _NEGATIVE_KEYWORDS
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower)
    )
    positive_count = sum(
        1 for kw in _POSITIVE_KEYWORDS
        if re.search(r"\b" + re.escape(kw) + r"\b", text_lower)
    )

    total_signals = negative_count + positive_count + len(risk_matches)
    if total_signals == 0:
        sentiment = "neutral"
        sentiment_score = 0.0
    else:
        net = positive_count - negative_count - len(risk_matches) * 1.5
        sentiment_score = max(-1.0, min(1.0, net / max(total_signals, 1)))
        if sentiment_score > 0.1:
            sentiment = "positive"
        elif sentiment_score < -0.1:
            sentiment = "negative"
        else:
            sentiment = "neutral"

    # Risk score: severity-weighted (total_severity / 3.0 caps at 1.0)
    risk_score = min(1.0, total_severity / 3.0)

    # Severity-based detection: single CRITICAL (1.0) exceeds threshold (0.6)
    risk_detected = total_severity >= RISK_SEVERITY_THRESHOLD

    return {
        "sentiment": sentiment,
        "sentiment_score": round(sentiment_score, 4),
        "risk_score": round(risk_score, 4),
        "risk_detected": risk_detected,
        "risk_keywords_found": risk_matches[:10],
        "risk_keywords_detail": sorted(risk_detail, key=lambda x: -x["severity"])[:10],
        "total_severity": round(total_severity, 2),
        "max_keyword_severity": round(max_severity, 2),
        "positive_signals": positive_count,
        "negative_signals": negative_count,
        "method": "keyword_fallback",
    }


def _transformers_analyze(text: str) -> Dict[str, Any]:
    """FinBERT-based sentiment analysis using HuggingFace transformers."""
    import torch

    # Truncate to MAX_LENGTH tokens
    inputs = _tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        max_length=MAX_LENGTH,
        padding=True,
    )

    with torch.no_grad():
        outputs = _model(**inputs)
        probs = torch.nn.functional.softmax(outputs.logits, dim=-1)[0]

    # FinBERT labels: positive, negative, neutral
    labels = ["positive", "negative", "neutral"]
    scores = {label: round(float(prob), 4) for label, prob in zip(labels, probs)}

    sentiment = max(scores, key=scores.get)
    sentiment_score = scores["positive"] - scores["negative"]  # [-1, 1]

    # Also run keyword detection for risk-specific signals
    keyword_result = _keyword_analyze(text)

    # Combine FinBERT sentiment with keyword risk detection
    risk_score = keyword_result["risk_score"]
    # Boost risk if FinBERT detects negative sentiment
    if sentiment == "negative":
        risk_score = min(1.0, risk_score + 0.2)

    return {
        "sentiment": sentiment,
        "sentiment_score": round(float(sentiment_score), 4),
        "sentiment_probabilities": scores,
        "risk_score": round(risk_score, 4),
        "risk_detected": keyword_result["risk_detected"] or (sentiment == "negative" and scores["negative"] > 0.7),
        "risk_keywords_found": keyword_result["risk_keywords_found"],
        "positive_signals": keyword_result["positive_signals"],
        "negative_signals": keyword_result["negative_signals"],
        "method": "finbert",
    }


def analyze_text(text: str) -> Dict[str, Any]:
    """Analyze a single text passage for sentiment and risk.

    Args:
        text: Financial text to analyze (e.g., auditor notes, management commentary).

    Returns:
        Dict with:
            - sentiment: "positive", "negative", or "neutral"
            - sentiment_score: float [-1, 1]
            - risk_score: float [0, 1] (higher = more risky)
            - risk_detected: bool (True if significant risk signals found)
            - risk_keywords_found: list of matched risk keywords
            - method: "finbert" or "keyword_fallback"
    """
    _init_model()

    if not text or not text.strip():
        return {
            "sentiment": "neutral",
            "sentiment_score": 0.0,
            "risk_score": 0.0,
            "risk_detected": False,
            "risk_keywords_found": [],
            "positive_signals": 0,
            "negative_signals": 0,
            "method": _mode if _mode != "uninitialized" else "fallback",
        }

    if _mode == "transformers" and _model is not None and _tokenizer is not None:
        try:
            return _transformers_analyze(text)
        except Exception as e:
            logger.warning(f"[FinBERT] Transformers analysis failed: {e} — falling back to keywords")

    return _keyword_analyze(text)


def analyze_batch(texts: List[str]) -> List[Dict[str, Any]]:
    """Analyze multiple text passages."""
    return [analyze_text(t) for t in texts]


def analyze_documents(document_texts: Dict[str, str]) -> Dict[str, Any]:
    """Analyze multiple document texts and aggregate results.

    Args:
        document_texts: Dict mapping document names to their text content.

    Returns:
        Dict with:
            - per_document: Dict of document name → analysis result
            - aggregate_risk_score: float [0, 1] (max across documents)
            - aggregate_sentiment: overall sentiment
            - risk_detected: bool
            - highest_risk_document: name of the document with highest risk
            - risk_texts: list of (document, text snippet, risk keywords) tuples
    """
    per_document = {}
    max_risk = 0.0
    max_risk_doc = ""
    risk_texts = []
    sentiments = []

    for doc_name, text in document_texts.items():
        result = analyze_text(text)
        per_document[doc_name] = result
        sentiments.append(result["sentiment_score"])

        if result["risk_score"] > max_risk:
            max_risk = result["risk_score"]
            max_risk_doc = doc_name

        if result["risk_detected"]:
            # Extract a relevant snippet around the first risk keyword
            snippet = text[:200] if text else ""
            risk_texts.append({
                "document": doc_name,
                "snippet": snippet,
                "risk_keywords": result["risk_keywords_found"],
                "risk_score": result["risk_score"],
            })

    # Aggregate sentiment
    avg_sentiment = sum(sentiments) / len(sentiments) if sentiments else 0.0
    if avg_sentiment > 0.1:
        agg_sentiment = "positive"
    elif avg_sentiment < -0.1:
        agg_sentiment = "negative"
    else:
        agg_sentiment = "neutral"

    return {
        "per_document": per_document,
        "aggregate_risk_score": round(max_risk, 4),
        "aggregate_sentiment": agg_sentiment,
        "aggregate_sentiment_score": round(avg_sentiment, 4),
        "risk_detected": max_risk > 0.4,
        "highest_risk_document": max_risk_doc,
        "risk_texts": risk_texts,
    }


def get_mode() -> str:
    """Return current mode ('transformers' or 'fallback')."""
    _init_model()
    return _mode


def reset() -> None:
    """Reset singleton (for testing)."""
    global _model, _tokenizer, _mode
    _model = None
    _tokenizer = None
    _mode = "uninitialized"
