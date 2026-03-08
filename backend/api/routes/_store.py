"""
In-memory assessment store for hackathon.

Will be replaced by PostgreSQL in T0.4.
All route modules import from here for shared state.
"""

from typing import Dict, List
from backend.models.schemas import AssessmentSummary, OfficerNote
from backend.agents.evidence.compliance_engine import ComplianceResult

# Session-ID → AssessmentSummary
assessments_store: Dict[str, AssessmentSummary] = {}

# Session-ID → List[OfficerNote]
officer_notes_store: Dict[str, List[OfficerNote]] = {}

# Session-ID → ComplianceResult
compliance_store: Dict[str, ComplianceResult] = {}

# Session-ID → interview answers (Dict[str, str])
interview_store: Dict[str, Dict[str, str]] = {}
