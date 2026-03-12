"""
Intelli-Credit — End-to-End Pipeline Test Script

1. Authenticates via /api/auth/login with real JWT
2. Uploads 8 dummy PDF documents 
3. Triggers the pipeline via /api/pipeline/{session_id}/run
4. Polls pipeline status until completion
5. Fetches final assessment results

Run: .venv\\Scripts\\python.exe tests/test_pipeline_e2e.py
"""

import os
import sys
import json
import time
import requests

# ── Config ──
API_BASE = "http://localhost:8000"
USERNAME = "admin"
PASSWORD = "admin123"
DOCS_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "test_docs")

# Company Info for the test
COMPANY_INFO = {
    "company_name": "Rajesh Steel Industries Pvt Ltd",
    "cin": "L27100MH2005PTC198765",
    "sector": "Steel Manufacturing",
    "loan_type": "Term Loan",
    "loan_amount": "₹50,00,00,000",
    "loan_amount_numeric": 5000000000,
    "promoter_name": "Rajesh Kumar Agarwal",
}

# Document type mapping (matches backend DOCUMENT_TYPE_MAP keys)
DOC_FILES = [
    ("annual_report_rajesh_steel_fy2025.pdf", "annual_report"),
    ("bank_statement_rajesh_steel_12m.pdf", "bank_statement"),
    ("gst_returns_rajesh_steel_fy2025.pdf", "gst_returns"),
    ("itr_rajesh_steel_ay2025.pdf", "itr"),
    ("legal_notices_rajesh_steel.pdf", "legal_notice"),
    ("board_minutes_rajesh_steel_fy2025.pdf", "board_minutes"),
    ("shareholding_rajesh_steel_fy2025.pdf", "shareholding_pattern"),
    ("rating_report_rajesh_steel.pdf", "rating_report"),
]


def print_step(step_num, msg):
    print(f"\n{'='*60}")
    print(f"  STEP {step_num}: {msg}")
    print(f"{'='*60}")


def print_result(key, value):
    print(f"  {key}: {value}")


def main():
    print("\n" + "="*60)
    print("  INTELLI-CREDIT — End-to-End Pipeline Test")
    print("="*60)
    print(f"  API: {API_BASE}")
    print(f"  Company: {COMPANY_INFO['company_name']}")
    print(f"  Documents: {len(DOC_FILES)} PDFs")

    # ──────────────────────────────────────────────
    # STEP 1: Health Check
    # ──────────────────────────────────────────────
    print_step(1, "Health Check")
    try:
        resp = requests.get(f"{API_BASE}/health", timeout=60)
        if resp.status_code == 200:
            health = resp.json()
            print_result("Status", health.get("status"))
            print_result("Version", health.get("version"))
            infra = health.get("infrastructure", {})
            for svc, status in infra.items():
                print_result(f"  {svc}", status)
        else:
            print(f"  ❌ Health check failed: {resp.status_code}")
            sys.exit(1)
    except requests.ConnectionError:
        print(f"  ❌ Cannot connect to {API_BASE}")
        print("  Make sure the backend is running:")
        print("    python -m uvicorn backend.api.main:app --reload --port 8000")
        sys.exit(1)

    # ──────────────────────────────────────────────
    # STEP 2: Login (real JWT auth)
    # ──────────────────────────────────────────────
    print_step(2, f"Login as '{USERNAME}'")
    resp = requests.post(
        f"{API_BASE}/api/auth/login",
        json={"username": USERNAME, "password": PASSWORD},
        timeout=60,
    )
    if resp.status_code != 200:
        print(f"  ❌ Login failed: {resp.status_code} — {resp.text}")
        sys.exit(1)

    auth_data = resp.json()
    token = auth_data["access_token"]
    print_result("Token", f"{token[:30]}...{token[-10:]}")
    print_result("Expires", f"{auth_data.get('expires_in', 0)} seconds")
    print("  ✅ Login successful!")

    headers = {"Authorization": f"Bearer {token}"}

    # Verify token with /api/auth/me
    resp = requests.get(f"{API_BASE}/api/auth/me", headers=headers, timeout=60)
    if resp.status_code == 200:
        me = resp.json()
        print_result("Verified User", f"{me['username']} ({me['role']})")
    else:
        print(f"  ⚠️ /api/auth/me failed: {resp.status_code}")

    # ──────────────────────────────────────────────
    # STEP 3: Upload Documents
    # ──────────────────────────────────────────────
    print_step(3, "Upload Documents")

    # Prepare multipart form data
    files_to_upload = []
    doc_types = []
    for filename, doc_type in DOC_FILES:
        filepath = os.path.join(DOCS_DIR, filename)
        if not os.path.exists(filepath):
            print(f"  ⚠️ Skipping {filename} — file not found")
            continue
        file_size = os.path.getsize(filepath) / 1024
        print(f"  📄 {filename} ({file_size:.1f} KB) → {doc_type}")
        files_to_upload.append(
            ("files", (filename, open(filepath, "rb"), "application/pdf"))
        )
        doc_types.append(doc_type)

    if not files_to_upload:
        print("  ❌ No files to upload!")
        sys.exit(1)

    form_data = {
        "company_name": COMPANY_INFO["company_name"],
        "cin": COMPANY_INFO["cin"],
        "sector": COMPANY_INFO["sector"],
        "loan_type": COMPANY_INFO["loan_type"],
        "loan_amount": COMPANY_INFO["loan_amount"],
        "loan_amount_numeric": str(COMPANY_INFO["loan_amount_numeric"]),
        "promoter_name": COMPANY_INFO["promoter_name"],
        "document_types": json.dumps(doc_types),
        "auto_run": "false",  # We'll trigger manually
    }

    resp = requests.post(
        f"{API_BASE}/api/upload",
        data=form_data,
        files=files_to_upload,
        headers=headers,
        timeout=30,
    )

    # Close the file handles
    for _, (_, fh, _) in [(None, f[1]) for f in files_to_upload]:
        fh.close()

    if resp.status_code not in (200, 201):
        print(f"  ❌ Upload failed: {resp.status_code} — {resp.text[:500]}")
        sys.exit(1)

    upload_result = resp.json()
    session_id = upload_result["session_id"]
    print(f"\n  ✅ Upload successful!")
    print_result("Session ID", session_id)
    print_result("Documents Uploaded", upload_result.get("documents_analyzed", len(doc_types)))
    print_result("Outcome", upload_result.get("outcome", "pending"))

    # Print worker statuses
    workers = upload_result.get("workers", [])
    if workers:
        print("\n  Workers initialized:")
        for w in workers:
            wid = w.get("worker_id", "?")
            dtype = w.get("document_type", "?")
            wstatus = w.get("status", "?")
            print(f"    {wid}: {dtype} — {wstatus}")

    # ──────────────────────────────────────────────
    # STEP 4: Trigger Pipeline
    # ──────────────────────────────────────────────
    print_step(4, "Trigger Pipeline")
    resp = requests.post(
        f"{API_BASE}/api/pipeline/{session_id}/run",
        headers=headers,
        timeout=60,
    )
    if resp.status_code not in (200, 202):
        print(f"  ❌ Pipeline trigger failed: {resp.status_code} — {resp.text[:500]}")
        sys.exit(1)

    trigger_result = resp.json()
    print_result("Status", trigger_result.get("status"))
    print_result("Message", trigger_result.get("message"))
    print("  ✅ Pipeline triggered!")

    # ──────────────────────────────────────────────
    # STEP 5: Poll Pipeline Status
    # ──────────────────────────────────────────────
    print_step(5, "Polling Pipeline Status")
    max_polls = 120  # Max 10 minutes
    poll_interval = 5  # 5 seconds

    for poll in range(max_polls):
        time.sleep(poll_interval)
        resp = requests.get(
            f"{API_BASE}/api/pipeline/{session_id}/status",
            headers=headers,
            timeout=60,
        )
        if resp.status_code != 200:
            print(f"  ⚠️ Status check failed: {resp.status_code}")
            continue

        status_data = resp.json()
        is_running = status_data.get("is_running", False)
        progress = status_data.get("progress", {})
        pct = progress.get("percent", 0)
        completed = progress.get("completed", 0)
        total = progress.get("total", 0)
        current = status_data.get("current_stage")
        outcome = status_data.get("outcome")
        score = status_data.get("score")
        band = status_data.get("score_band")

        # Progress bar
        bar_len = 30
        filled = int(bar_len * pct / 100) if pct else 0
        bar = "█" * filled + "░" * (bar_len - filled)
        print(f"\r  [{bar}] {pct}% ({completed}/{total}) "
              f"{'→ ' + current if current else ''}"
              f"{'  Score: ' + str(score) if score else ''}"
              f"{'  Band: ' + str(band) if band else ''}", end="", flush=True)

        if not is_running and (completed == total or outcome not in (None, "pending")):
            print()  # newline
            break

    # Final status
    print(f"\n  Pipeline finished!")
    print_result("Outcome", outcome)
    print_result("Score", score)
    print_result("Band", band)
    
    # Print all stage statuses
    stages = status_data.get("stages", [])
    if stages:
        print("\n  Stage Results:")
        for s in stages:
            stage_name = s.get("stage", "?")
            stage_status = s.get("status", "?")
            stage_msg = s.get("message", "")
            icon = "✅" if stage_status == "completed" else "❌" if stage_status == "failed" else "⬜"
            print(f"    {icon} {stage_name}: {stage_status} {('— ' + stage_msg) if stage_msg else ''}")

    error = status_data.get("error")
    if error:
        print(f"\n  ⚠️ Error: {error}")

    # ──────────────────────────────────────────────
    # STEP 6: Fetch Assessment Results
    # ──────────────────────────────────────────────
    print_step(6, "Fetch Assessment Results")
    resp = requests.get(
        f"{API_BASE}/api/assessment/{session_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 200:
        assessment = resp.json()
        print_result("Company", assessment.get("company", {}).get("name"))
        print_result("Score", assessment.get("score"))
        print_result("Band", assessment.get("score_band"))
        print_result("Outcome", assessment.get("outcome"))
        print_result("Documents", assessment.get("documents_analyzed"))
        print_result("Processing Time", assessment.get("processing_time"))
    else:
        print(f"  ⚠️ Assessment fetch failed: {resp.status_code}")

    # ──────────────────────────────────────────────
    # STEP 7: Fetch Score Details
    # ──────────────────────────────────────────────
    print_step(7, "Fetch Score Breakdown")
    resp = requests.get(
        f"{API_BASE}/api/score/{session_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 200:
        score_data = resp.json()
        print(f"  Score data retrieved successfully")
        # Print key fields if available
        if isinstance(score_data, dict):
            for key in ["total_score", "max_score", "band", "recommendation", "modules"]:
                if key in score_data:
                    val = score_data[key]
                    if key == "modules" and isinstance(val, list):
                        print(f"  Modules:")
                        for m in val:
                            mname = m.get("name", "?")
                            mscore = m.get("score", "?")
                            print(f"    {mname}: {mscore}")
                    else:
                        print_result(f"  {key}", val)
    else:
        print(f"  ⚠️ Score fetch: {resp.status_code} (may require pipeline completion)")

    # ──────────────────────────────────────────────
    # STEP 8: Fetch Tickets
    # ──────────────────────────────────────────────
    print_step(8, "Fetch Tickets")
    resp = requests.get(
        f"{API_BASE}/api/tickets/{session_id}",
        headers=headers,
        timeout=10,
    )
    if resp.status_code == 200:
        tickets = resp.json()
        if isinstance(tickets, list):
            print(f"  {len(tickets)} tickets found")
            for t in tickets:
                severity = t.get("severity", "?")
                title = t.get("title", t.get("description", "?"))[:80]
                print(f"    [{severity}] {title}")
        elif isinstance(tickets, dict):
            ticket_list = tickets.get("tickets", [])
            print(f"  {len(ticket_list)} tickets found")
            for t in ticket_list:
                severity = t.get("severity", "?")
                title = t.get("title", t.get("description", "?"))[:80]
                print(f"    [{severity}] {title}")
    else:
        print(f"  ⚠️ Tickets fetch: {resp.status_code}")

    # ──────────────────────────────────────────────
    # SUMMARY
    # ──────────────────────────────────────────────
    print("\n" + "="*60)
    print("  TEST SUMMARY")
    print("="*60)
    print(f"  Session ID: {session_id}")
    print(f"  Company: {COMPANY_INFO['company_name']}")
    print(f"  Documents: {len(DOC_FILES)} uploaded")
    print(f"  Score: {score} / Band: {band}")
    print(f"  Outcome: {outcome}")
    print(f"\n  Use this session_id in the frontend to view results:")
    print(f"  http://localhost:3000/processing")
    print("="*60)
    print()


if __name__ == "__main__":
    main()
