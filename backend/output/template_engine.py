"""
Intelli-Credit — Jinja2 Template Engine

Renders CAM and Score Report templates to HTML, which are then consumed
by the .docx and .pdf generators. Provides a single render() interface
that accepts template name + context dict.

Templates live in config/templates/.
"""

import logging
import os
from typing import Any, Dict

from jinja2 import Environment, FileSystemLoader, select_autoescape

logger = logging.getLogger(__name__)

# Template directory: config/templates/
_TEMPLATE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "config",
    "templates",
)

_env: Environment | None = None


def _get_env() -> Environment:
    """Get or create the Jinja2 Environment (singleton)."""
    global _env
    if _env is None:
        _env = Environment(
            loader=FileSystemLoader(_TEMPLATE_DIR),
            autoescape=select_autoescape(["html"]),
            trim_blocks=True,
            lstrip_blocks=True,
        )
        # Custom filters
        _env.filters["inr"] = _filter_inr
        _env.filters["score_color"] = _filter_score_color
        _env.filters["band_color"] = _filter_band_color
        _env.filters["abs"] = lambda x: abs(x) if isinstance(x, (int, float)) else x
        logger.info("[Templates] Jinja2 environment initialized from %s", _TEMPLATE_DIR)
    return _env


def reset_env():
    """Reset the singleton (for testing)."""
    global _env
    _env = None


# ══════════════════════════════════════════════
# Custom Filters
# ══════════════════════════════════════════════

def _filter_inr(value) -> str:
    """Format a number as Indian Rupee string (₹ XX,XX,XXX)."""
    try:
        num = float(value)
        if num >= 1e7:
            return f"₹{num / 1e7:.2f} Cr"
        elif num >= 1e5:
            return f"₹{num / 1e5:.2f} L"
        else:
            return f"₹{num:,.0f}"
    except (ValueError, TypeError):
        return str(value)


def _filter_score_color(score: int) -> str:
    """Return a color hex for score value."""
    if score >= 750:
        return "#059669"   # emerald-600
    elif score >= 650:
        return "#0d9488"   # teal-600
    elif score >= 550:
        return "#d97706"   # amber-600
    elif score >= 450:
        return "#ea580c"   # orange-600
    elif score >= 350:
        return "#dc2626"   # red-600
    return "#991b1b"       # red-800


def _filter_band_color(band: str) -> str:
    """Return a color hex for score band."""
    colors = {
        "Excellent": "#059669",
        "Good": "#0d9488",
        "Fair": "#d97706",
        "Poor": "#ea580c",
        "Very Poor": "#dc2626",
        "Default Risk": "#991b1b",
    }
    return colors.get(band, "#64748b")


# ══════════════════════════════════════════════
# Public API
# ══════════════════════════════════════════════

def render_template(template_name: str, context: Dict[str, Any]) -> str:
    """Render a Jinja2 template with the given context.

    Args:
        template_name: Template file name (e.g. 'cam_report.html')
        context: Dict of variables available in the template

    Returns:
        Rendered string (HTML or plain text)
    """
    env = _get_env()
    template = env.get_template(template_name)
    rendered = template.render(**context)
    logger.info("[Templates] Rendered '%s' (%d chars)", template_name, len(rendered))
    return rendered


def list_templates() -> list:
    """List available template files."""
    env = _get_env()
    return env.loader.list_templates()


def template_exists(template_name: str) -> bool:
    """Check if a template exists."""
    env = _get_env()
    try:
        env.get_template(template_name)
        return True
    except Exception:
        return False
