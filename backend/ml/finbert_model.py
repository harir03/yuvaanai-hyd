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
    "pledge", "pledged shares", "invocation",
    "related party", "rpt", "related party transaction",
    "contingent liability", "off-balance sheet", "undisclosed",
    "circular trading", "round tripping", "shell company",
    "diversion of funds", "siphoning", "money laundering",
    "late filing", "non-compliance", "violation",
    "promoter exit", "stake sale", "dilution",
    "management change", "cfo resignation", "auditor change",
]

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

    Scans for domain-specific keywords and computes sentiment scores.
    """
    text_lower = text.lower()

    # Count keyword matches
    risk_matches = []
    for kw in _RISK_KEYWORDS:
        # Word boundary match to avoid partial matches
        pattern = r"\b" + re.escape(kw) + r"\b"
        if re.search(pattern, text_lower):
            risk_matches.append(kw)

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
        # Normalize to [-1, 1]
        sentiment_score = max(-1.0, min(1.0, net / max(total_signals, 1)))
        if sentiment_score > 0.1:
            sentiment = "positive"
        elif sentiment_score < -0.1:
            sentiment = "negative"
        else:
            sentiment = "neutral"

    # Risk score: 0 (safe) to 1 (very risky)
    risk_score = min(1.0, len(risk_matches) / 5.0)  # 5+ risk keywords → max risk
    risk_detected = len(risk_matches) >= 2  # Need at least 2 risk signals

    return {
        "sentiment": sentiment,
        "sentiment_score": round(sentiment_score, 4),
        "risk_score": round(risk_score, 4),
        "risk_detected": risk_detected,
        "risk_keywords_found": risk_matches[:10],  # Cap at 10
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
