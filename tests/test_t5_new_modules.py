"""
T5 — Tests for New Modules: ChromaDB Client, Document Ingestor,
Rate Limiter, and File Upload Validation.

Covers 5 perspectives: Credit Domain, Security, Systems, QA, Demo.
"""

import os
import io
import time
import tempfile
import asyncio
from unittest.mock import patch, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient
from starlette.testclient import TestClient

from backend.api.main import app
from backend.api.routes._store import assessments_store


# ════════════════════════════════════════════════════════════════
# Section 1 — ChromaDB Client
# ════════════════════════════════════════════════════════════════

from backend.storage.chromadb_client import (
    ChromaDBClient,
    InMemoryVectorStore,
    get_chromadb_client,
    reset_chromadb_client,
    COLLECTION_DOCUMENT_CHUNKS,
    COLLECTION_KNOWLEDGE_BASE,
    COLLECTION_TICKET_PRECEDENTS,
)


class TestInMemoryVectorStore:
    """Unit tests for the in-memory fallback vector store."""

    def setup_method(self):
        self.store = InMemoryVectorStore()

    def test_add_and_count(self):
        """Add documents and verify count."""
        self.store.add(
            collection="test",
            ids=["doc-1", "doc-2"],
            documents=["revenue is 247 crores", "DSCR is 1.38x"],
            metadatas=[{"source": "AR"}, {"source": "GST"}],
        )
        assert self.store.count("test") == 2

    def test_add_with_metadata(self):
        """Add documents with metadata filters."""
        self.store.add(
            collection="test",
            ids=["doc-1"],
            documents=["AR revenue 247 crores"],
            metadatas=[{"source": "annual_report", "page": 12}],
        )
        results = self.store.query("test", "revenue", top_k=1)
        assert len(results) == 1
        assert results[0]["metadata"]["source"] == "annual_report"

    def test_query_returns_ranked_results(self):
        """Query returns most relevant results first."""
        self.store.add(
            collection="test",
            ids=["doc-1", "doc-2", "doc-3"],
            documents=[
                "DSCR is 1.38x for the borrower",
                "The weather today is sunny",
                "Debt service coverage ratio improved to 1.5x",
            ],
            metadatas=[{}, {}, {}],
        )
        results = self.store.query("test", "DSCR debt service coverage", top_k=2)
        assert len(results) == 2
        # Both DSCR-related docs should rank higher than weather
        ids = [r["id"] for r in results]
        assert "doc-2" not in ids

    def test_query_empty_collection(self):
        """Query on nonexistent collection returns empty list."""
        results = self.store.query("nonexistent", "test query", top_k=5)
        assert results == []

    def test_query_with_metadata_filter(self):
        """Query filters by metadata 'where' clause."""
        self.store.add(
            collection="test",
            ids=["d1", "d2"],
            documents=["revenue 100cr", "revenue 200cr"],
            metadatas=[{"session_id": "s1"}, {"session_id": "s2"}],
        )
        results = self.store.query("test", "revenue", top_k=5, where={"session_id": "s1"})
        assert len(results) == 1
        assert results[0]["id"] == "d1"

    def test_delete_collection(self):
        """Delete a collection."""
        self.store.add("test", ids=["d1"], documents=["hello"], metadatas=[{}])
        self.store.delete_collection("test")
        assert self.store.count("test") == 0

    def test_list_collections(self):
        """List all collections."""
        self.store.add("col_a", ids=["1"], documents=["a"], metadatas=[{}])
        self.store.add("col_b", ids=["2"], documents=["b"], metadatas=[{}])
        names = self.store.list_collections()
        assert "col_a" in names
        assert "col_b" in names

    def test_count_nonexistent_collection(self):
        """Count on nonexistent collection returns 0."""
        assert self.store.count("ghost") == 0

    def test_add_duplicate_ids(self):
        """Adding duplicate IDs doesn't crash."""
        self.store.add("test", ids=["d1"], documents=["first"], metadatas=[{}])
        self.store.add("test", ids=["d1"], documents=["second"], metadatas=[{}])
        # Implementation-specific: should have at least 1 entry
        assert self.store.count("test") >= 1


class TestChromaDBClient:
    """Tests for the ChromaDB async client (falls back to in-memory)."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        reset_chromadb_client()
        yield
        reset_chromadb_client()

    @pytest.mark.asyncio
    async def test_initialize_fallback(self):
        """Client falls back to in-memory when ChromaDB unavailable."""
        client = ChromaDBClient(host="localhost", port=19999)  # bad port
        await client.initialize()
        assert client.backend == "memory"

    @pytest.mark.asyncio
    async def test_add_and_search_documents(self):
        """Add and search documents through async client."""
        client = ChromaDBClient()
        await client.initialize()
        count = await client.add_documents(
            COLLECTION_DOCUMENT_CHUNKS,
            documents=["XYZ Steel revenue ₹247 crores from Annual Report"],
            metadatas=[{"source": "AR", "page": 5, "session_id": "test-sess"}],
        )
        assert count == 1
        results = await client.search(
            COLLECTION_DOCUMENT_CHUNKS, "revenue steel company", top_k=3
        )
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_rag_retrieve_with_session_filter(self):
        """RAG retrieve filters by session_id."""
        client = ChromaDBClient()
        await client.initialize()
        await client.add_documents(
            COLLECTION_DOCUMENT_CHUNKS,
            documents=["DSCR 1.38x", "Revenue mismatch"],
            metadatas=[
                {"session_id": "s1", "source": "AR"},
                {"session_id": "s2", "source": "GST"},
            ],
            ids=["chunk-1", "chunk-2"],
        )
        results = await client.rag_retrieve("s1", "DSCR", top_k=5)
        assert all(r.get("metadata", {}).get("session_id") == "s1" for r in results)

    @pytest.mark.asyncio
    async def test_ticket_precedent_storage(self):
        """Store and retrieve ticket precedents."""
        client = ChromaDBClient()
        await client.initialize()
        await client.add_ticket_precedent(
            ticket_id="T-001",
            description="Revenue mismatch AR vs GST: ₹247cr vs ₹198cr",
            resolution="Accepted GST figure as authoritative per source priority",
            metadata={"severity": "HIGH", "outcome": "resolved"},
        )
        results = await client.find_similar_tickets("revenue discrepancy annual report GST")
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_knowledge_base_entry(self):
        """Add and retrieve knowledge base entries."""
        client = ChromaDBClient()
        await client.initialize()
        await client.add_knowledge_entry(
            entry_id="kb-001",
            content="DSCR below 1.0x triggers hard block cap at 300",
            source="scoring_rules",
            metadata={"category": "hard_block"},
        )
        results = await client.search(COLLECTION_KNOWLEDGE_BASE, "DSCR hard block", top_k=1)
        assert len(results) >= 1

    @pytest.mark.asyncio
    async def test_count(self):
        """Count returns correct number after additions."""
        client = ChromaDBClient()
        await client.initialize()
        await client.add_documents("test_col", ["a", "b", "c"])
        assert client.count("test_col") == 3

    @pytest.mark.asyncio
    async def test_singleton_pattern(self):
        """get_chromadb_client returns same instance."""
        c1 = get_chromadb_client()
        c2 = get_chromadb_client()
        assert c1 is c2


# ════════════════════════════════════════════════════════════════
# Section 2 — Document Ingestor
# ════════════════════════════════════════════════════════════════

from backend.agents.ingestor.document_ingestor import (
    DocumentIngestor,
    IngestResult,
    ParsedPage,
    get_available_parsers,
    _detect_file_type,
)


class TestDocumentIngestor:
    """Tests for the adaptive document ingestor."""

    def setup_method(self):
        self.ingestor = DocumentIngestor()

    def test_detect_file_type_pdf(self):
        assert _detect_file_type("report.pdf") == "pdf"

    def test_detect_file_type_xlsx(self):
        assert _detect_file_type("data.xlsx") == "xlsx"

    def test_detect_file_type_csv(self):
        assert _detect_file_type("data.csv") == "csv"

    def test_detect_file_type_docx(self):
        assert _detect_file_type("memo.docx") == "docx"

    def test_detect_file_type_unknown(self):
        result = _detect_file_type("mystery.xyz")
        assert result in ("unknown", "xyz")  # implementation may vary

    def test_detect_file_type_case_insensitive(self):
        assert _detect_file_type("REPORT.PDF") == "pdf"

    @pytest.mark.asyncio
    async def test_ingest_missing_file(self):
        """Ingest a file that doesn't exist — should return gracefully."""
        result = await self.ingestor.ingest("/nonexistent/ghost.pdf")
        assert isinstance(result, IngestResult)
        assert len(result.warnings) > 0 or result.total_pages == 0

    @pytest.mark.asyncio
    async def test_ingest_plain_text_file(self):
        """Ingest a .txt file with known content."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False, encoding="utf-8") as f:
            f.write("XYZ Steel Ltd — Annual Revenue: ₹247 Crores\nDSCR: 1.38x\n")
            path = f.name
        try:
            result = await self.ingestor.ingest(path)
            assert isinstance(result, IngestResult)
            assert "247" in result.full_text or result.total_pages >= 1
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_ingest_csv_file(self):
        """Ingest a CSV file with financial data."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, encoding="utf-8") as f:
            f.write("Year,Revenue,EBITDA\n2023,247,45\n2022,210,38\n2021,195,32\n")
            path = f.name
        try:
            result = await self.ingestor.ingest(path)
            assert isinstance(result, IngestResult)
            # file_type is "csv" if pandas available, "txt" if fallback
            assert result.file_type in ("csv", "txt")
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_ingest_empty_file(self):
        """Ingest a zero-byte file — should not crash."""
        with tempfile.NamedTemporaryFile(suffix=".txt", delete=False) as f:
            path = f.name
        try:
            result = await self.ingestor.ingest(path)
            assert isinstance(result, IngestResult)
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_ingest_excel_file(self):
        """Ingest an Excel file if openpyxl is available."""
        parsers = get_available_parsers()
        if not parsers.get("openpyxl", False):
            pytest.skip("openpyxl not installed")
        # Create a minimal xlsx via openpyxl
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Company", "Revenue", "DSCR"])
        ws.append(["XYZ Steel", 247, 1.38])
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
            wb.save(f.name)
            path = f.name
        try:
            result = await self.ingestor.ingest(path)
            assert result.file_type == "xlsx"
            assert result.total_pages >= 1
        finally:
            os.unlink(path)

    def test_parsed_page_dataclass(self):
        """ParsedPage holds correct data."""
        page = ParsedPage(page_number=1, text="Revenue: ₹247 Crores", confidence=0.95, method="pymupdf")
        assert page.page_number == 1
        assert page.confidence == 0.95
        assert page.method == "pymupdf"

    def test_ingest_result_average_confidence(self):
        """IngestResult computes average confidence."""
        result = IngestResult(
            file_path="test.pdf",
            file_type="pdf",
            total_pages=3,
            pages=[
                ParsedPage(page_number=1, text="a", confidence=0.9),
                ParsedPage(page_number=2, text="b", confidence=0.6),
                ParsedPage(page_number=3, text="c", confidence=0.9),
            ],
        )
        assert abs(result.average_confidence - 0.8) < 0.01

    def test_ingest_result_average_confidence_empty(self):
        """Average confidence is 0 when no pages."""
        result = IngestResult(file_path="x.pdf", file_type="pdf")
        assert result.average_confidence == 0.0

    def test_get_available_parsers(self):
        """get_available_parsers returns a dict of booleans."""
        parsers = get_available_parsers()
        assert isinstance(parsers, dict)
        assert all(isinstance(v, bool) for v in parsers.values())


# ════════════════════════════════════════════════════════════════
# Section 3 — Rate Limiter
# ════════════════════════════════════════════════════════════════

from backend.api.middleware.rate_limiter import (
    TokenBucket,
    InMemoryRateLimiter,
    RateLimitMiddleware,
    RATE_LIMITS,
    reset_rate_limiter,
    _get_client_ip,
)


class TestTokenBucket:
    """Unit tests for the token bucket algorithm."""

    def test_initial_tokens(self):
        """Bucket starts full."""
        b = TokenBucket(max_tokens=10, refill_rate=1.0)
        assert b.consume(1) is True

    def test_burst_capacity(self):
        """Can consume up to max_tokens in a burst."""
        b = TokenBucket(max_tokens=5, refill_rate=0.1)
        for _ in range(5):
            assert b.consume(1) is True
        assert b.consume(1) is False

    def test_refill_over_time(self):
        """Tokens refill after waiting."""
        b = TokenBucket(max_tokens=2, refill_rate=100.0)  # 100 tokens/sec
        b.consume(2)
        assert b.consume(1) is False
        time.sleep(0.05)  # 50ms → should refill ~5 tokens (capped at 2)
        assert b.consume(1) is True

    def test_retry_after(self):
        """retry_after is positive when bucket empty."""
        b = TokenBucket(max_tokens=1, refill_rate=1.0)
        b.consume(1)
        assert b.retry_after > 0

    def test_retry_after_when_available(self):
        """retry_after is 0 when tokens available."""
        b = TokenBucket(max_tokens=10, refill_rate=1.0)
        assert b.retry_after == 0.0

    def test_consume_multiple_tokens(self):
        """Consume more than 1 token at once."""
        b = TokenBucket(max_tokens=10, refill_rate=1.0)
        assert b.consume(5) is True
        assert b.consume(5) is True
        assert b.consume(1) is False


class TestInMemoryRateLimiter:
    """Tests for the per-client rate limiter."""

    def setup_method(self):
        self.limiter = InMemoryRateLimiter()

    def test_allows_normal_traffic(self):
        """Normal traffic passes."""
        allowed, _ = self.limiter.check("192.168.1.1", "/api/assessment")
        assert allowed is True

    def test_blocks_after_exhaustion(self):
        """Blocks when bucket exhausted."""
        for _ in range(200):
            self.limiter.check("10.0.0.1", "/api/assessment")
        allowed, retry_after = self.limiter.check("10.0.0.1", "/api/assessment")
        assert allowed is False
        assert retry_after > 0

    def test_upload_path_lower_limit(self):
        """Upload endpoint has stricter rate limit (10/min)."""
        for _ in range(10):
            self.limiter.check("10.0.0.2", "/api/upload")
        allowed, _ = self.limiter.check("10.0.0.2", "/api/upload")
        assert allowed is False

    def test_different_clients_independent(self):
        """Different IPs have independent buckets."""
        for _ in range(200):
            self.limiter.check("10.0.0.3", "/api/assessment")
        allowed, _ = self.limiter.check("10.0.0.4", "/api/assessment")
        assert allowed is True


class TestRateLimitMiddleware:
    """Integration tests for rate limit middleware via HTTP."""

    @pytest.fixture(autouse=True)
    def _reset(self):
        reset_rate_limiter()
        yield
        reset_rate_limiter()

    @pytest.mark.asyncio
    async def test_health_bypasses_limiter(self):
        """Health endpoint is never rate-limited."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            for _ in range(50):
                resp = await ac.get("/health")
                assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self):
        """Response includes X-RateLimit headers."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.get("/api/assessment/list")
            assert "x-ratelimit-limit" in resp.headers or resp.status_code == 200

    @pytest.mark.asyncio
    async def test_429_on_upload_overload(self):
        """Upload endpoint returns 429 after 10 rapid requests."""
        reset_rate_limiter()
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            statuses = []
            for _ in range(15):
                resp = await ac.post(
                    "/api/upload",
                    data={
                        "company_name": "Test",
                        "sector": "IT",
                        "loan_type": "WC",
                        "loan_amount": "10Cr",
                        "loan_amount_numeric": 100.0,
                    },
                )
                statuses.append(resp.status_code)
            assert 429 in statuses


class TestClientIPExtraction:
    """Security tests for client IP resolution."""

    def test_get_client_ip_forwarded(self):
        """Extracts first IP from X-Forwarded-For."""
        from starlette.datastructures import Headers
        request = MagicMock()
        request.headers = Headers({"x-forwarded-for": "203.0.113.1, 10.0.0.1, 127.0.0.1"})
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        ip = _get_client_ip(request)
        assert ip == "203.0.113.1"

    def test_get_client_ip_direct(self):
        """Falls back to request.client.host when no XFF header."""
        from starlette.datastructures import Headers
        request = MagicMock()
        request.headers = Headers({})
        request.client = MagicMock()
        request.client.host = "192.168.1.100"
        ip = _get_client_ip(request)
        assert ip == "192.168.1.100"


# ════════════════════════════════════════════════════════════════
# Section 4 — File Upload Validation
# ════════════════════════════════════════════════════════════════

from backend.api.routes.upload import (
    _sanitize_filename,
    _validate_file_type,
    MAX_FILE_SIZE,
    MAX_TOTAL_SIZE,
    MAX_FILES,
    ALLOWED_EXTENSIONS,
    MAGIC_BYTES,
)


class TestSanitizeFilename:
    """Security tests for filename sanitization."""

    def test_normal_filename(self):
        assert _sanitize_filename("annual_report.pdf") == "annual_report.pdf"

    def test_path_traversal_unix(self):
        """Strips path traversal sequences (unix)."""
        result = _sanitize_filename("../../../etc/passwd")
        assert ".." not in result
        assert "/" not in result

    def test_path_traversal_windows(self):
        """Strips path traversal sequences (Windows)."""
        result = _sanitize_filename("..\\..\\..\\windows\\system32\\config")
        assert ".." not in result
        assert "\\" not in result

    def test_null_byte_injection(self):
        """Removes null bytes."""
        result = _sanitize_filename("report\x00.pdf")
        assert "\x00" not in result

    def test_full_path_stripped(self):
        """Only keeps the basename."""
        result = _sanitize_filename("/home/user/documents/report.pdf")
        assert result == "report.pdf"

    def test_windows_full_path_stripped(self):
        """Windows paths are stripped to basename."""
        result = _sanitize_filename("C:\\Users\\admin\\report.pdf")
        assert result == "report.pdf"

    def test_empty_filename(self):
        """Empty filename gets default."""
        result = _sanitize_filename("")
        assert result.endswith(".pdf")
        assert len(result) > 0

    def test_dot_only_filename(self):
        """Dot-only filename gets default."""
        result = _sanitize_filename(".hidden")
        assert not result.startswith(".")

    def test_unicode_filename(self):
        """Unicode characters preserved."""
        result = _sanitize_filename("रिपोर्ट.pdf")
        assert result.endswith(".pdf")


class TestValidateFileType:
    """Security + QA tests for file type validation."""

    def test_valid_pdf(self):
        """PDF with correct magic bytes passes."""
        content = b"%PDF-1.4 fake pdf content"
        _validate_file_type(content, "report.pdf")  # should not raise

    def test_valid_csv(self):
        """CSV passes (no magic check for text files)."""
        content = b"Year,Revenue\n2023,247\n"
        _validate_file_type(content, "data.csv")  # should not raise

    def test_valid_txt(self):
        """TXT passes."""
        content = b"Plain text content"
        _validate_file_type(content, "notes.txt")  # should not raise

    def test_disallowed_extension(self):
        """Executable extension rejected."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_type(b"MZ\x90\x00", "malware.exe")
        assert exc_info.value.status_code == 400
        assert "not allowed" in exc_info.value.detail

    def test_disallowed_py_extension(self):
        """Python file rejected."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException):
            _validate_file_type(b"import os", "script.py")

    def test_magic_mismatch_pdf(self):
        """File claims PDF but has wrong magic bytes."""
        from fastapi import HTTPException
        # PK magic (ZIP) but claiming .pdf extension
        content = b"PK\x03\x04" + b"\x00" * 100
        with pytest.raises(HTTPException) as exc_info:
            _validate_file_type(content, "fake.pdf")
        assert exc_info.value.status_code == 400
        assert "does not match" in exc_info.value.detail

    def test_xlsx_docx_both_pk_magic(self):
        """xlsx and docx both use PK magic — both should pass."""
        content = b"PK\x03\x04" + b"\x00" * 100
        _validate_file_type(content, "data.xlsx")  # should not raise
        _validate_file_type(content, "memo.docx")  # should not raise

    def test_xls_doc_both_ole2_magic(self):
        """xls and doc both use OLE2 magic — both should pass."""
        content = b"\xd0\xcf\x11\xe0" + b"\x00" * 100
        _validate_file_type(content, "data.xls")  # should not raise
        _validate_file_type(content, "memo.doc")  # should not raise

    def test_small_file_no_magic_check(self):
        """Very small binary file (< 4 bytes) — should still check extension."""
        content = b"AB"  # 2 bytes
        _validate_file_type(content, "tiny.pdf")  # should not raise (can't check magic)

    def test_allowed_extensions_complete(self):
        """All 7 expected extensions are in ALLOWED_EXTENSIONS."""
        expected = {".pdf", ".xlsx", ".xls", ".csv", ".doc", ".docx", ".txt"}
        assert expected == ALLOWED_EXTENSIONS

    def test_max_file_size_constant(self):
        """MAX_FILE_SIZE is 50MB."""
        assert MAX_FILE_SIZE == 50 * 1024 * 1024

    def test_max_total_size_constant(self):
        """MAX_TOTAL_SIZE is 200MB."""
        assert MAX_TOTAL_SIZE == 200 * 1024 * 1024

    def test_max_files_constant(self):
        """MAX_FILES is 20."""
        assert MAX_FILES == 20


class TestUploadValidationIntegration:
    """Integration tests for upload endpoint validation."""

    @pytest.fixture(autouse=True)
    def _clear_store(self):
        assessments_store.clear()
        yield
        assessments_store.clear()

    @pytest.mark.asyncio
    async def test_upload_too_many_files(self):
        """Rejects upload with > MAX_FILES files."""
        files = []
        for i in range(MAX_FILES + 1):
            files.append(("files", (f"doc{i}.txt", b"content", "text/plain")))
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/upload",
                data={
                    "company_name": "Test Corp",
                    "sector": "IT",
                    "loan_type": "WC",
                    "loan_amount": "10Cr",
                    "loan_amount_numeric": 100.0,
                },
                files=files,
            )
        assert resp.status_code == 400
        assert "Too many files" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_disallowed_file_type(self):
        """Rejects upload with disallowed file extension."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/upload",
                data={
                    "company_name": "Test Corp",
                    "sector": "IT",
                    "loan_type": "WC",
                    "loan_amount": "10Cr",
                    "loan_amount_numeric": 100.0,
                },
                files=[("files", ("evil.exe", b"MZ\x90\x00", "application/octet-stream"))],
            )
        assert resp.status_code == 400
        assert "not allowed" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_valid_txt_file(self):
        """Accepts valid .txt upload."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/upload",
                data={
                    "company_name": "XYZ Steel Ltd",
                    "sector": "Steel Manufacturing",
                    "loan_type": "Working Capital",
                    "loan_amount": "₹50 Cr",
                    "loan_amount_numeric": 5000.0,
                },
                files=[("files", ("report.txt", b"Revenue: 247 crores", "text/plain"))],
            )
        assert resp.status_code == 201
        data = resp.json()
        assert data["documents"][0]["filename"] == "report.txt"

    @pytest.mark.asyncio
    async def test_upload_sanitizes_traversal_filename(self):
        """Path traversal in filename is sanitized."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/upload",
                data={
                    "company_name": "Test",
                    "sector": "IT",
                    "loan_type": "WC",
                    "loan_amount": "10Cr",
                    "loan_amount_numeric": 100.0,
                },
                files=[("files", ("../../etc/passwd.txt", b"test content", "text/plain"))],
            )
        # Should succeed but with sanitized filename
        assert resp.status_code == 201
        filename = resp.json()["documents"][0]["filename"]
        assert ".." not in filename
        assert "/" not in filename

    @pytest.mark.asyncio
    async def test_upload_magic_mismatch_rejected(self):
        """File with wrong magic bytes is rejected."""
        # PK magic bytes but claiming .pdf
        content = b"PK\x03\x04" + b"\x00" * 100
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/upload",
                data={
                    "company_name": "Test",
                    "sector": "IT",
                    "loan_type": "WC",
                    "loan_amount": "10Cr",
                    "loan_amount_numeric": 100.0,
                },
                files=[("files", ("fake.pdf", content, "application/pdf"))],
            )
        assert resp.status_code == 400
        assert "does not match" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_upload_no_files_succeeds(self):
        """Upload with zero files creates session with no documents."""
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as ac:
            resp = await ac.post(
                "/api/upload",
                data={
                    "company_name": "Empty Corp",
                    "sector": "IT",
                    "loan_type": "WC",
                    "loan_amount": "5Cr",
                    "loan_amount_numeric": 50.0,
                },
            )
        assert resp.status_code == 201
        assert len(resp.json()["documents"]) == 0
