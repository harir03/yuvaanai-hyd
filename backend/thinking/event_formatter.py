"""
Intelli-Credit — ThinkingEvent Formatter

Utility functions for formatting ThinkingEvents with consistent
styling, color coding, and metadata enrichment.
"""

from datetime import datetime
from typing import Optional, Dict, Any

from backend.models.schemas import EventType


# ──────────────────────────────────────────────
# Event Type → Display Properties
# ──────────────────────────────────────────────

EVENT_DISPLAY = {
    EventType.READ: {
        "icon": "📄",
        "color": "slate",
        "label": "Reading",
    },
    EventType.FOUND: {
        "icon": "🔍",
        "color": "blue",
        "label": "Found",
    },
    EventType.COMPUTED: {
        "icon": "🧮",
        "color": "indigo",
        "label": "Computed",
    },
    EventType.ACCEPTED: {
        "icon": "✅",
        "color": "green",
        "label": "Accepted",
    },
    EventType.REJECTED: {
        "icon": "❌",
        "color": "red",
        "label": "Rejected",
    },
    EventType.FLAGGED: {
        "icon": "⚠️",
        "color": "amber",
        "label": "Flagged",
    },
    EventType.CRITICAL: {
        "icon": "🚨",
        "color": "red",
        "label": "Critical",
    },
    EventType.CONNECTING: {
        "icon": "🔗",
        "color": "purple",
        "label": "Connecting",
    },
    EventType.CONCLUDING: {
        "icon": "💡",
        "color": "teal",
        "label": "Concluding",
    },
    EventType.QUESTIONING: {
        "icon": "💬",
        "color": "blue",
        "label": "Questioning",
    },
    EventType.DECIDED: {
        "icon": "⚖️",
        "color": "teal",
        "label": "Decided",
    },
}


def get_event_display(event_type: EventType) -> dict:
    """Get display properties (icon, color, label) for an event type."""
    return EVENT_DISPLAY.get(event_type, {
        "icon": "📌",
        "color": "slate",
        "label": "Info",
    })


def format_event_message(
    event_type: EventType,
    message: str,
    include_icon: bool = True,
) -> str:
    """
    Format a ThinkingEvent message with icon prefix.

    Example: "✅ Revenue cross-verified: AR ₹142cr matches GST ₹140cr (1.4% deviation)"
    """
    display = get_event_display(event_type)
    if include_icon:
        return f"{display['icon']} {message}"
    return message


def enrich_event_dict(event_dict: dict) -> dict:
    """
    Add display metadata to a serialized ThinkingEvent dict.

    Adds: icon, color, label for frontend rendering.
    Does NOT modify the original dict — returns a new one.
    """
    enriched = dict(event_dict)
    event_type_str = enriched.get("event_type", "")

    try:
        event_type = EventType(event_type_str)
        display = get_event_display(event_type)
    except (ValueError, KeyError):
        display = {"icon": "📌", "color": "slate", "label": "Info"}

    enriched["display"] = display
    return enriched


def format_agent_header(agent_name: str) -> str:
    """Format an agent name for display in the chatbot."""
    return f"🤖 {agent_name}"


def format_source_citation(
    document: Optional[str] = None,
    page: Optional[int] = None,
    excerpt: Optional[str] = None,
) -> Optional[str]:
    """
    Format a source citation string.

    Example: "Annual Report, p.42: 'Revenue for FY2023 was ₹142.3 crores'"
    """
    if not document:
        return None

    parts = [document]
    if page is not None:
        parts.append(f"p.{page}")

    citation = ", ".join(parts)

    if excerpt:
        # Truncate long excerpts
        truncated = excerpt[:150] + "..." if len(excerpt) > 150 else excerpt
        citation += f": '{truncated}'"

    return citation
