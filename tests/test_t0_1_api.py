"""T0.1 — FastAPI Backend Skeleton Test Suite"""

import httpx
import json
import sys

BASE = "http://localhost:8001"

def test_root():
    r = httpx.get(f"{BASE}/")
    assert r.status_code == 200
    data = r.json()
    assert data["service"] == "Intelli-Credit API"
    print("  [PASS] Root endpoint")

def test_health():
    r = httpx.get(f"{BASE}/health")
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "healthy"
    print("  [PASS] Health check")

def test_upload():
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
    assert r.status_code == 201, f"Expected 201, got {r.status_code}: {r.text}"
    data = r.json()
    assert "session_id" in data
    assert data["company"]["name"] == "XYZ Steel Ltd"
    assert len(data["pipeline_stages"]) == 10
    assert data["outcome"] == "PENDING"
    print(f"  [PASS] Upload — session {data['session_id'][:8]}...")
    return data["session_id"]

def test_get_assessment(session_id):
    r = httpx.get(f"{BASE}/api/assessment/{session_id}")
    assert r.status_code == 200
    assert r.json()["session_id"] == session_id
    print("  [PASS] Get assessment")

def test_assessment_404():
    r = httpx.get(f"{BASE}/api/assessment/nonexistent-id")
    assert r.status_code == 404
    print("  [PASS] Assessment 404")

def test_tickets(session_id):
    r = httpx.get(f"{BASE}/api/tickets/{session_id}")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    print("  [PASS] Get tickets")

def test_history():
    r = httpx.get(f"{BASE}/api/history")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) >= 1
    print(f"  [PASS] History — {len(r.json())} records")

def test_analytics():
    r = httpx.get(f"{BASE}/api/analytics")
    assert r.status_code == 200
    data = r.json()
    assert data["total_assessments"] >= 1
    print(f"  [PASS] Analytics — {data['total_assessments']} assessments")

def test_list_assessments():
    r = httpx.get(f"{BASE}/api/assessments")
    assert r.status_code == 200
    assert len(r.json()) >= 1
    print(f"  [PASS] List assessments — {len(r.json())} total")

def test_openapi_docs():
    r = httpx.get(f"{BASE}/openapi.json")
    assert r.status_code == 200
    data = r.json()
    assert "paths" in data
    paths = list(data["paths"].keys())
    print(f"  [PASS] OpenAPI docs — {len(paths)} paths: {', '.join(paths)}")

if __name__ == "__main__":
    print("=" * 50)
    print("T0.1 — FastAPI Backend Skeleton Tests")
    print("=" * 50)
    
    passed = 0
    failed = 0
    
    try:
        test_root()
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Root: {e}")
        failed += 1
    
    try:
        test_health()
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Health: {e}")
        failed += 1
    
    session_id = None
    try:
        session_id = test_upload()
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Upload: {e}")
        failed += 1
    
    if session_id:
        try:
            test_get_assessment(session_id)
            passed += 1
        except Exception as e:
            print(f"  [FAIL] Get assessment: {e}")
            failed += 1
        
        try:
            test_tickets(session_id)
            passed += 1
        except Exception as e:
            print(f"  [FAIL] Tickets: {e}")
            failed += 1
    
    try:
        test_assessment_404()
        passed += 1
    except Exception as e:
        print(f"  [FAIL] 404: {e}")
        failed += 1
    
    try:
        test_history()
        passed += 1
    except Exception as e:
        print(f"  [FAIL] History: {e}")
        failed += 1
    
    try:
        test_analytics()
        passed += 1
    except Exception as e:
        print(f"  [FAIL] Analytics: {e}")
        failed += 1
    
    try:
        test_list_assessments()
        passed += 1
    except Exception as e:
        print(f"  [FAIL] List assessments: {e}")
        failed += 1
    
    try:
        test_openapi_docs()
        passed += 1
    except Exception as e:
        print(f"  [FAIL] OpenAPI: {e}")
        failed += 1
    
    print("=" * 50)
    print(f"Results: {passed} passed, {failed} failed")
    if failed > 0:
        print("SOME TESTS FAILED")
        sys.exit(1)
    else:
        print("ALL TESTS PASSED")
