"""
Intelli-Credit — ReportLab PDF Score Report Generator

Generates a formatted PDF score report with:
  - Score gauge visualization (colored arc)
  - Module breakdown table
  - Per-metric detail tables
  - Hard block section
  - Loan terms
  - Color-coded impact values

Uses ReportLab for PDF generation with a professional layout.
"""

import io
import logging
import math
import os
from datetime import datetime
from typing import Any, Dict, List, Optional

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm, mm
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    PageBreak,
)
from reportlab.graphics.shapes import Drawing, Wedge, String, Circle, Line
from reportlab.graphics import renderPDF

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────
# Color Constants
# ──────────────────────────────────────────────

_TEAL = colors.HexColor("#0d9488")
_RED = colors.HexColor("#dc2626")
_GREEN = colors.HexColor("#059669")
_AMBER = colors.HexColor("#d97706")
_ORANGE = colors.HexColor("#ea580c")
_DARK_RED = colors.HexColor("#991b1b")
_SLATE_800 = colors.HexColor("#1e293b")
_SLATE_500 = colors.HexColor("#64748b")
_SLATE_100 = colors.HexColor("#f1f5f9")
_SLATE_50 = colors.HexColor("#f8fafc")
_WHITE = colors.white


def _score_color(score: int) -> colors.Color:
    if score >= 750:
        return _GREEN
    elif score >= 650:
        return _TEAL
    elif score >= 550:
        return _AMBER
    elif score >= 450:
        return _ORANGE
    elif score >= 350:
        return _RED
    return _DARK_RED


def _impact_color(impact: int) -> colors.Color:
    return _GREEN if impact > 0 else _RED


# ──────────────────────────────────────────────
# Score Gauge Drawing
# ──────────────────────────────────────────────

def _create_score_gauge(score: int, width: float = 200, height: float = 120) -> Drawing:
    """Create a semicircular score gauge visualization."""
    d = Drawing(width, height)
    cx, cy = width / 2, 30
    radius = 70

    # Background arc segments (colored bands)
    bands = [
        (0, 350, _DARK_RED),     # Default Risk
        (350, 450, _RED),        # Very Poor
        (450, 550, _ORANGE),     # Poor
        (550, 650, _AMBER),      # Fair
        (650, 750, _TEAL),       # Good
        (750, 850, _GREEN),      # Excellent
    ]
    for low, high, color in bands:
        start_angle = 180 - (high / 850 * 180)
        end_angle = 180 - (low / 850 * 180)
        wedge = Wedge(cx, cy, radius, start_angle, end_angle,
                       fillColor=color, strokeColor=_WHITE, strokeWidth=0.5)
        d.add(wedge)

    # Inner white circle to create arc effect
    inner = Circle(cx, cy, radius * 0.6, fillColor=_WHITE, strokeColor=_WHITE)
    d.add(inner)

    # Score needle position
    needle_angle = 180 - (min(score, 850) / 850 * 180)
    rad = math.radians(needle_angle)
    needle_len = radius * 0.55
    nx = cx + needle_len * math.cos(rad)
    ny = cy + needle_len * math.sin(rad)
    needle = Line(cx, cy, nx, ny, strokeColor=_SLATE_800, strokeWidth=2)
    d.add(needle)

    # Center dot
    center_dot = Circle(cx, cy, 4, fillColor=_SLATE_800, strokeColor=_WHITE)
    d.add(center_dot)

    # Score text
    score_text = String(cx, cy - 20, str(score),
                         fontSize=24, fillColor=_score_color(score),
                         textAnchor="middle", fontName="Helvetica-Bold")
    d.add(score_text)

    # "/ 850" text
    max_text = String(cx, cy - 35, "/ 850",
                       fontSize=10, fillColor=_SLATE_500,
                       textAnchor="middle", fontName="Helvetica")
    d.add(max_text)

    return d


# ──────────────────────────────────────────────
# PDF Styles
# ──────────────────────────────────────────────

def _get_styles() -> dict:
    """Get custom paragraph styles for the report."""
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "ReportTitle", parent=base["Title"],
            fontSize=20, textColor=_SLATE_800,
            alignment=TA_CENTER, spaceAfter=12,
        ),
        "heading1": ParagraphStyle(
            "H1", parent=base["Heading1"],
            fontSize=14, textColor=_SLATE_800,
            spaceBefore=16, spaceAfter=8,
        ),
        "heading2": ParagraphStyle(
            "H2", parent=base["Heading2"],
            fontSize=12, textColor=_SLATE_800,
            spaceBefore=12, spaceAfter=6,
        ),
        "body": ParagraphStyle(
            "Body", parent=base["Normal"],
            fontSize=10, textColor=_SLATE_800,
            spaceAfter=4,
        ),
        "body_center": ParagraphStyle(
            "BodyCenter", parent=base["Normal"],
            fontSize=10, textColor=_SLATE_800,
            alignment=TA_CENTER, spaceAfter=4,
        ),
        "small": ParagraphStyle(
            "Small", parent=base["Normal"],
            fontSize=8, textColor=_SLATE_500,
            alignment=TA_CENTER,
        ),
        "score_band": ParagraphStyle(
            "ScoreBand", parent=base["Normal"],
            fontSize=16, alignment=TA_CENTER,
            spaceAfter=8,
        ),
    }


# ──────────────────────────────────────────────
# Table Builder
# ──────────────────────────────────────────────

def _make_table(headers: List[str], rows: List[List[str]],
                col_widths: Optional[List[float]] = None) -> Table:
    """Build a styled ReportLab table."""
    data = [headers] + rows

    table = Table(data, colWidths=col_widths, repeatRows=1)
    style = TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), _SLATE_100),
        ("TEXTCOLOR", (0, 0), (-1, 0), _SLATE_800),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 9),
        ("FONTSIZE", (0, 1), (-1, -1), 8),
        ("TEXTCOLOR", (0, 1), (-1, -1), _SLATE_800),
        ("ALIGN", (0, 0), (-1, 0), "CENTER"),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [_WHITE, _SLATE_50]),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ("LEFTPADDING", (0, 0), (-1, -1), 4),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
    ])
    table.setStyle(style)
    return table


# ──────────────────────────────────────────────
# Main Generator
# ──────────────────────────────────────────────

def generate_score_pdf(context: Dict[str, Any], output_path: Optional[str] = None) -> bytes:
    """Generate a score report PDF.

    Args:
        context: Dict with keys matching score_report.html template.
        output_path: Optional file path. If None, returns bytes only.

    Returns:
        PDF content as bytes.
    """
    buffer = io.BytesIO()
    styles = _get_styles()

    doc = SimpleDocTemplate(
        buffer, pagesize=A4,
        topMargin=2 * cm, bottomMargin=2 * cm,
        leftMargin=2 * cm, rightMargin=2 * cm,
        title=f"Score Report — {context.get('company_name', 'Unknown')}",
        author="Intelli-Credit AI Engine",
    )

    elements = []
    page_width = A4[0] - 4 * cm  # usable width

    # ── Title ──
    elements.append(Paragraph("CREDIT SCORE REPORT", styles["title"]))
    elements.append(Spacer(1, 4 * mm))

    # ── Header Info ──
    company_name = context.get("company_name", "Unknown")
    session_id = context.get("session_id", "N/A")
    date_str = context.get("date", datetime.utcnow().strftime("%Y-%m-%d"))

    header_data = [
        ["Company", company_name],
        ["Assessment ID", session_id],
        ["Date", date_str],
    ]
    header_table = _make_table(["Field", "Value"], header_data,
                                col_widths=[4 * cm, page_width - 4 * cm])
    elements.append(header_table)
    elements.append(Spacer(1, 8 * mm))

    # ── Score Gauge ──
    score = context.get("score", 0)
    score_band = str(context.get("score_band", "N/A"))
    outcome = str(context.get("outcome", "PENDING"))
    recommendation = context.get("recommendation", "")

    elements.append(Paragraph("Overall Score", styles["heading1"]))

    gauge = _create_score_gauge(score)
    elements.append(gauge)
    elements.append(Spacer(1, 2 * mm))

    color_hex = _score_color(score).hexval() if hasattr(_score_color(score), "hexval") else "#1e293b"
    elements.append(Paragraph(
        f'<font color="{color_hex}" size="18"><b>{score_band}</b></font>',
        styles["body_center"],
    ))
    elements.append(Paragraph(f"<b>Outcome:</b> {outcome}", styles["body_center"]))
    if recommendation:
        elements.append(Paragraph(f"<b>Recommendation:</b> {recommendation}", styles["body_center"]))
    elements.append(Spacer(1, 6 * mm))

    # ── Module Breakdown Table ──
    modules = context.get("modules", [])
    elements.append(Paragraph("Module Breakdown", styles["heading1"]))

    if modules:
        mod_rows = []
        for mod in modules:
            mod_score = _get(mod, "score", 0)
            sign = "+" if mod_score > 0 else ""
            mod_rows.append([
                _get(mod, "module"),
                f"{sign}{mod_score}",
                f"+{_get(mod, 'max_positive', 0)}",
                str(_get(mod, "max_negative", 0)),
                str(len(_get(mod, "metrics", []))),
            ])
        base_score = context.get("base_score", 350)
        mod_rows.append(["Base Score", str(base_score), "", "", ""])
        mod_rows.append(["FINAL SCORE", f"{score} / 850", "", "", ""])

        mod_table = _make_table(
            ["Module", "Score", "Max (+)", "Max (−)", "Metrics"],
            mod_rows,
            col_widths=[4 * cm, 3 * cm, 2.5 * cm, 2.5 * cm, 2.5 * cm],
        )
        elements.append(mod_table)
    elements.append(Spacer(1, 6 * mm))

    # ── Per-Module Metric Details ──
    elements.append(Paragraph("Detailed Metric Analysis", styles["heading1"]))
    for mod in modules:
        mod_name = _get(mod, "module", "Unknown")
        mod_score = _get(mod, "score", 0)
        elements.append(Paragraph(f"{mod_name} — {mod_score} points", styles["heading2"]))

        metrics = _get(mod, "metrics", [])
        if metrics:
            metric_rows = []
            for m in metrics:
                impact = _get(m, "score_impact", 0)
                sign = "+" if impact > 0 else ""
                confidence = _get(m, "confidence", 0)
                conf_pct = f"{confidence * 100:.0f}%" if isinstance(confidence, (int, float)) else str(confidence)
                metric_rows.append([
                    _get(m, "metric_name"),
                    _get(m, "metric_value"),
                    _get(m, "benchmark_context", ""),
                    f"{sign}{impact}",
                    f"{_get(m, 'source_document')} p.{_get(m, 'source_page')}",
                    conf_pct,
                ])
            metric_table = _make_table(
                ["Metric", "Value", "Benchmark", "Impact", "Source", "Conf."],
                metric_rows,
                col_widths=[3 * cm, 2 * cm, 3 * cm, 1.5 * cm, 3.5 * cm, 1.5 * cm],
            )
            elements.append(metric_table)
        elements.append(Spacer(1, 4 * mm))

    # ── Hard Blocks ──
    hard_blocks = context.get("hard_blocks", [])
    if hard_blocks:
        elements.append(Paragraph("Hard Block Triggers", styles["heading1"]))
        hb_rows = []
        for hb in hard_blocks:
            hb_rows.append([
                _get(hb, "trigger"),
                str(_get(hb, "score_cap")),
                _get(hb, "evidence"),
                _get(hb, "source"),
            ])
        hb_table = _make_table(
            ["Trigger", "Score Cap", "Evidence", "Source"],
            hb_rows,
            col_widths=[4 * cm, 2.5 * cm, 5 * cm, 3 * cm],
        )
        elements.append(hb_table)
        elements.append(Spacer(1, 6 * mm))

    # ── Loan Terms ──
    loan_terms = context.get("loan_terms")
    if loan_terms:
        elements.append(Paragraph("Recommended Terms", styles["heading1"]))
        lt_rows = [
            ["Sanction", f"{_get(loan_terms, 'sanction_pct')}% of requested amount"],
            ["Rate", _get(loan_terms, "rate")],
            ["Tenure", _get(loan_terms, "tenure")],
            ["Review", _get(loan_terms, "review")],
        ]
        lt_table = _make_table(["Parameter", "Value"], lt_rows,
                                col_widths=[4 * cm, page_width - 4 * cm])
        elements.append(lt_table)
        elements.append(Spacer(1, 6 * mm))

    # ── Footer ──
    elements.append(Spacer(1, 12 * mm))
    elements.append(Paragraph(
        f"Generated by Intelli-Credit AI Engine | {date_str}",
        styles["small"],
    ))
    elements.append(Paragraph(
        "Score methodology: 5Cs Framework (Capacity, Character, Capital, "
        "Collateral, Conditions) + Compound Risk",
        styles["small"],
    ))

    # Build PDF
    doc.build(elements)
    content = buffer.getvalue()

    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as f:
            f.write(content)
        logger.info("[Score-PDF] Saved to %s (%d bytes)", output_path, len(content))

    return content


def _get(obj, key, default="N/A"):
    """Safely get from dict or object."""
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ──────────────────────────────────────────────
# Convenience: Build context from ScoreResponse
# ──────────────────────────────────────────────

def build_score_context(score_response, assessment=None) -> Dict[str, Any]:
    """Build a score report context from a ScoreResponse and optional AssessmentSummary."""
    sr = score_response
    ctx = {
        "company_name": _get(sr, "company_name", "Unknown"),
        "session_id": _get(sr, "session_id", ""),
        "score": _get(sr, "score", 0),
        "score_band": str(_get(sr, "score_band", "N/A")),
        "outcome": str(_get(sr, "outcome", "PENDING")),
        "recommendation": _get(sr, "recommendation", ""),
        "base_score": _get(sr, "base_score", 350),
        "date": datetime.utcnow().strftime("%Y-%m-%d"),
    }

    modules = _get(sr, "modules", [])
    ctx["modules"] = [
        m.model_dump() if hasattr(m, "model_dump") else m
        for m in modules
    ]

    hb = _get(sr, "hard_blocks", [])
    ctx["hard_blocks"] = [
        h.model_dump() if hasattr(h, "model_dump") else h
        for h in hb
    ]

    lt = _get(sr, "loan_terms", None)
    if lt:
        ctx["loan_terms"] = lt.model_dump() if hasattr(lt, "model_dump") else lt

    return ctx
