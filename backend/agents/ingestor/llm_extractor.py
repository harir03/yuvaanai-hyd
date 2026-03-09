"""
Intelli-Credit — LLM Extraction Service

Calls Claude (Haiku for extraction, Sonnet for complex reasoning) to
extract structured JSON from document text using prompt templates.

Falls back to a regex-based heuristic extractor when no API key is set.
"""

import json
import logging
import re
from typing import Dict, Any, Optional

from config.settings import settings

logger = logging.getLogger(__name__)

# ── LLM availability ──
_HAS_LLM = False
_llm_haiku = None
_llm_sonnet = None


def _init_llm():
    """Lazily initialize LLM clients."""
    global _HAS_LLM, _llm_haiku, _llm_sonnet

    if _llm_haiku is not None:
        return

    if not settings.anthropic_api_key:
        logger.warning("[LLM] No ANTHROPIC_API_KEY set — using heuristic fallback")
        _HAS_LLM = False
        return

    try:
        from langchain_anthropic import ChatAnthropic

        _llm_haiku = ChatAnthropic(
            model="claude-3-5-haiku-20241022",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
            max_tokens=4096,
        )
        _llm_sonnet = ChatAnthropic(
            model="claude-sonnet-4-20250514",
            api_key=settings.anthropic_api_key,
            temperature=0.0,
            max_tokens=8192,
        )
        _HAS_LLM = True
        logger.info("[LLM] Claude Haiku + Sonnet initialized")
    except Exception as e:
        logger.warning(f"[LLM] Failed to initialize: {e}")
        _HAS_LLM = False


async def extract_with_llm(
    document_text: str,
    prompt_template: str,
    template_vars: Dict[str, Any],
    use_sonnet: bool = False,
    max_text_chars: int = 80000,
) -> Dict[str, Any]:
    """
    Extract structured data from document text using Claude.

    Args:
        document_text: The raw text extracted from the document.
        prompt_template: Prompt template string with {placeholders}.
        template_vars: Variables to fill into the prompt template.
        use_sonnet: If True, use Sonnet (complex reasoning). Default: Haiku (extraction).
        max_text_chars: Maximum characters of document text to send.

    Returns:
        Parsed JSON dict from LLM response, or heuristic fallback.
    """
    _init_llm()

    # Truncate text if too long
    if len(document_text) > max_text_chars:
        document_text = document_text[:max_text_chars] + "\n\n[... truncated ...]"

    # Fill template
    template_vars["document_text"] = document_text
    try:
        filled_prompt = prompt_template.format(**template_vars)
    except KeyError as e:
        logger.warning(f"[LLM] Prompt template missing key: {e}")
        filled_prompt = prompt_template

    if _HAS_LLM:
        return await _call_llm(filled_prompt, use_sonnet)
    else:
        logger.info("[LLM] No API key — using heuristic extraction")
        return _heuristic_extract(document_text)


async def _call_llm(prompt: str, use_sonnet: bool) -> Dict[str, Any]:
    """Call Claude and parse JSON response."""
    model = _llm_sonnet if use_sonnet else _llm_haiku
    model_name = "Sonnet" if use_sonnet else "Haiku"

    try:
        logger.info(f"[LLM] Calling Claude {model_name} ({len(prompt)} chars)")

        response = await model.ainvoke(
            f"You are a financial document extraction specialist. "
            f"Return ONLY valid JSON, no markdown, no explanation.\n\n{prompt}"
        )

        raw = response.content if hasattr(response, "content") else str(response)

        # Extract JSON from response (handle markdown code blocks)
        json_str = _extract_json_from_response(raw)
        result = json.loads(json_str)
        logger.info(f"[LLM] Claude {model_name} returned {len(result)} top-level keys")
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"[LLM] JSON parse failed: {e}")
        # Try to salvage partial JSON
        try:
            partial = _extract_json_from_response(raw)
            return json.loads(partial)
        except Exception:
            return {"_llm_error": "JSON parse failed", "_raw_response": raw[:500]}

    except Exception as e:
        logger.error(f"[LLM] Claude {model_name} call failed: {e}")
        return {"_llm_error": str(e)}


def _extract_json_from_response(text: str) -> str:
    """Extract JSON from LLM response, handling markdown code blocks."""
    # Try to find JSON in code blocks
    code_block_match = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if code_block_match:
        return code_block_match.group(1).strip()

    # Try to find raw JSON (starts with { or [)
    text = text.strip()
    if text.startswith("{") or text.startswith("["):
        return text

    # Try to find embedded JSON object
    brace_match = re.search(r"\{[\s\S]*\}", text)
    if brace_match:
        return brace_match.group(0)

    return text


def _heuristic_extract(text: str) -> Dict[str, Any]:
    """
    Basic regex-based extraction when no LLM is available.
    Extracts numbers, currency amounts, and common patterns.
    """
    result: Dict[str, Any] = {"_extraction_method": "heuristic"}

    # Extract currency amounts (₹ or Rs or INR)
    amounts = re.findall(
        r"(?:₹|Rs\.?|INR)\s*([\d,]+(?:\.\d+)?)\s*(?:crore|cr|lakh|L)?",
        text, re.IGNORECASE,
    )
    if amounts:
        result["currency_amounts_found"] = [a.replace(",", "") for a in amounts[:20]]

    # Extract percentages
    pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", text)
    if pcts:
        result["percentages_found"] = pcts[:20]

    # Extract dates
    dates = re.findall(
        r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}|\d{4}[-/]\d{1,2}[-/]\d{1,2}",
        text,
    )
    if dates:
        result["dates_found"] = dates[:20]

    # Extract GSTIN
    gstin = re.findall(r"\d{2}[A-Z]{5}\d{4}[A-Z]\d[A-Z\d][A-Z]", text)
    if gstin:
        result["gstin"] = gstin[0]

    # Extract PAN
    pan = re.findall(r"[A-Z]{5}\d{4}[A-Z]", text)
    if pan:
        result["pan"] = pan[0]

    # Extract CIN
    cin = re.findall(r"[LU]\d{5}[A-Z]{2}\d{4}[A-Z]{3}\d{6}", text)
    if cin:
        result["cin"] = cin[0]

    # Extract company names (lines with "Ltd" or "Limited")
    companies = re.findall(r"([A-Z][\w\s]+(?:Ltd|Limited|Pvt|Private)[\w\s]*)", text)
    if companies:
        result["company_names"] = list(set(companies[:10]))

    # Revenue/financial keywords
    for keyword in ["revenue", "turnover", "ebitda", "profit", "loss", "debt", "net worth"]:
        pattern = rf"(?i){keyword}[\s:]*(?:₹|Rs\.?|INR)?\s*([\d,]+(?:\.\d+)?)"
        match = re.search(pattern, text)
        if match:
            result[keyword] = match.group(1).replace(",", "")

    # Page count estimate
    page_markers = re.findall(r"Page\s+(\d+)", text, re.IGNORECASE)
    if page_markers:
        result["estimated_pages"] = max(int(p) for p in page_markers)

    return result


def is_llm_available() -> bool:
    """Check if LLM is available."""
    _init_llm()
    return _HAS_LLM
