"""
In-memory assessment store for hackathon.

Will be replaced by PostgreSQL in T0.4.
All route modules import from here for shared state.
"""

from typing import Dict
from backend.models.schemas import AssessmentSummary

# Session-ID → AssessmentSummary
assessments_store: Dict[str, AssessmentSummary] = {}
