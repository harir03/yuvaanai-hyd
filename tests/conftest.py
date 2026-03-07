"""Shared fixtures for the test suite."""

import httpx
import pytest

BASE = "http://localhost:8001"


@pytest.fixture(scope="session")
def session_id():
    """Create a test assessment via upload and return the session_id.

    This is a session-scoped fixture so the upload only happens once
    across all tests that need the session_id.
    """
    r = httpx.post(f"{BASE}/api/upload", data={
        "company_name": "XYZ Steel Ltd",
        "sector": "Steel Manufacturing",
        "loan_type": "Working Capital",
        "loan_amount": "50,00,00,000",
        "loan_amount_numeric": 500000000,
        "cin": "L27100MH2005PLC123456",
        "gstin": "27AABCU9603R1ZM",
        "pan": "AABCU9603R",
        "incorporation_year": 2005,
        "promoter_name": "Rajesh K. Agarwal",
    })
    assert r.status_code == 201, f"Upload failed: {r.status_code}: {r.text}"
    return r.json()["session_id"]
