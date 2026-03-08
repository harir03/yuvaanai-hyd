"""
Intelli-Credit — Document Ingestor Orchestrator

Orchestrates document parsing by selecting the appropriate parsing library
based on document type and format:
- Unstructured.io for complex PDF spatial layout parsing
- Tesseract OCR for scanned pages  
- Camelot for PDF table extraction (financial statements)
- PyMuPDF (fitz) for fast text extraction from simple PDFs
- OpenPyXL for Excel files with formula support
- Pandas for CSV/Excel tabular data

Falls back to basic text extraction when specialized libraries are unavailable.

Usage:
    ingestor = DocumentIngestor()
    result = await ingestor.ingest("path/to/doc.pdf", DocumentType.ANNUAL_REPORT)
"""

import os
import io
import logging
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ParsedPage:
    """A single parsed page from a document."""
    page_number: int
    text: str
    tables: List[List[List[str]]] = field(default_factory=list)  # list of tables, each table is rows of cells
    confidence: float = 1.0
    method: str = "unknown"  # "pymupdf", "ocr", "unstructured", "camelot"


@dataclass
class IngestResult:
    """Result of document ingestion."""
    file_path: str
    file_type: str  # "pdf", "xlsx", "csv", "docx"
    total_pages: int = 0
    pages: List[ParsedPage] = field(default_factory=list)
    full_text: str = ""
    tables: List[List[List[str]]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    method: str = "fallback"
    warnings: List[str] = field(default_factory=list)

    @property
    def average_confidence(self) -> float:
        if not self.pages:
            return 0.0
        return sum(p.confidence for p in self.pages) / len(self.pages)


# ── Library availability flags ──
_HAS_PYMUPDF = False
_HAS_CAMELOT = False
_HAS_TESSERACT = False
_HAS_UNSTRUCTURED = False
_HAS_OPENPYXL = False
_HAS_PANDAS = False
_checked = False


def _check_libraries() -> None:
    """Check which parsing libraries are available."""
    global _HAS_PYMUPDF, _HAS_CAMELOT, _HAS_TESSERACT, _HAS_UNSTRUCTURED
    global _HAS_OPENPYXL, _HAS_PANDAS, _checked

    if _checked:
        return
    _checked = True

    try:
        import fitz  # PyMuPDF
        _HAS_PYMUPDF = True
        logger.info("[Ingestor] PyMuPDF available")
    except ImportError:
        logger.warning("[Ingestor] PyMuPDF not installed")

    try:
        import camelot
        _HAS_CAMELOT = True
        logger.info("[Ingestor] Camelot available")
    except ImportError:
        logger.warning("[Ingestor] Camelot not installed")

    try:
        import pytesseract
        _HAS_TESSERACT = True
        logger.info("[Ingestor] Tesseract OCR available")
    except ImportError:
        logger.warning("[Ingestor] Tesseract OCR not installed")

    try:
        from unstructured.partition.pdf import partition_pdf
        _HAS_UNSTRUCTURED = True
        logger.info("[Ingestor] Unstructured.io available")
    except ImportError:
        logger.warning("[Ingestor] Unstructured.io not installed")

    try:
        import openpyxl
        _HAS_OPENPYXL = True
        logger.info("[Ingestor] OpenPyXL available")
    except ImportError:
        logger.warning("[Ingestor] OpenPyXL not installed")

    try:
        import pandas
        _HAS_PANDAS = True
        logger.info("[Ingestor] Pandas available")
    except ImportError:
        logger.warning("[Ingestor] Pandas not installed")


def _detect_file_type(file_path: str) -> str:
    """Detect file type from extension."""
    ext = os.path.splitext(file_path)[1].lower()
    type_map = {
        ".pdf": "pdf",
        ".xlsx": "xlsx",
        ".xls": "xlsx",
        ".csv": "csv",
        ".docx": "docx",
        ".doc": "docx",
        ".txt": "txt",
    }
    return type_map.get(ext, "unknown")


async def _parse_pdf_pymupdf(file_path: str) -> IngestResult:
    """Parse PDF using PyMuPDF (fast text extraction)."""
    import fitz

    doc = fitz.open(file_path)
    pages: List[ParsedPage] = []
    full_text_parts = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        text = page.get_text()
        # Check if page has meaningful text (not just whitespace)
        is_text_rich = len(text.strip()) > 50
        pages.append(ParsedPage(
            page_number=page_num + 1,
            text=text,
            confidence=0.95 if is_text_rich else 0.3,
            method="pymupdf",
        ))
        full_text_parts.append(text)

    doc.close()

    return IngestResult(
        file_path=file_path,
        file_type="pdf",
        total_pages=len(pages),
        pages=pages,
        full_text="\n\n".join(full_text_parts),
        method="pymupdf",
        metadata={"parser": "PyMuPDF", "version": fitz.version[0]},
    )


async def _parse_pdf_unstructured(file_path: str) -> IngestResult:
    """Parse PDF using Unstructured.io (complex spatial layout)."""
    from unstructured.partition.pdf import partition_pdf

    elements = partition_pdf(
        filename=file_path,
        strategy="hi_res",
        infer_table_structure=True,
    )

    pages_dict: Dict[int, ParsedPage] = {}
    tables = []

    for element in elements:
        page_num = getattr(element.metadata, "page_number", 1) or 1
        if page_num not in pages_dict:
            pages_dict[page_num] = ParsedPage(
                page_number=page_num,
                text="",
                confidence=0.90,
                method="unstructured",
            )
        pages_dict[page_num].text += str(element) + "\n"

        # Extract tables
        if hasattr(element, "metadata") and hasattr(element.metadata, "text_as_html"):
            html = element.metadata.text_as_html
            if html and "<table" in str(html).lower():
                tables.append([[str(element)]])

    pages = sorted(pages_dict.values(), key=lambda p: p.page_number)
    full_text = "\n\n".join(p.text for p in pages)

    return IngestResult(
        file_path=file_path,
        file_type="pdf",
        total_pages=len(pages),
        pages=pages,
        full_text=full_text,
        tables=tables,
        method="unstructured",
        metadata={"parser": "Unstructured.io", "elements": len(elements)},
    )


async def _parse_pdf_ocr(file_path: str) -> IngestResult:
    """Parse scanned PDF pages using Tesseract OCR."""
    import fitz
    import pytesseract
    from PIL import Image

    doc = fitz.open(file_path)
    pages: List[ParsedPage] = []
    full_text_parts = []

    for page_num in range(len(doc)):
        page = doc[page_num]
        # Render page to image at 300 DPI
        mat = fitz.Matrix(300 / 72, 300 / 72)
        pix = page.get_pixmap(matrix=mat)
        img = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        # OCR the image
        text = pytesseract.image_to_string(img)
        confidence_data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
        # Average OCR confidence
        confs = [int(c) for c in confidence_data.get("conf", []) if str(c).isdigit() and int(c) > 0]
        avg_conf = (sum(confs) / len(confs) / 100.0) if confs else 0.5

        pages.append(ParsedPage(
            page_number=page_num + 1,
            text=text,
            confidence=avg_conf,
            method="ocr",
        ))
        full_text_parts.append(text)

    doc.close()

    return IngestResult(
        file_path=file_path,
        file_type="pdf",
        total_pages=len(pages),
        pages=pages,
        full_text="\n\n".join(full_text_parts),
        method="ocr",
        metadata={"parser": "Tesseract OCR"},
    )


async def _extract_tables_camelot(file_path: str) -> List[List[List[str]]]:
    """Extract tables from PDF using Camelot."""
    import camelot

    try:
        tables = camelot.read_pdf(file_path, pages="all", flavor="lattice")
        if len(tables) == 0:
            tables = camelot.read_pdf(file_path, pages="all", flavor="stream")
    except Exception as e:
        logger.warning(f"[Ingestor/Camelot] Table extraction failed: {e}")
        return []

    result = []
    for table in tables:
        df = table.df
        rows = df.values.tolist()
        result.append(rows)

    return result


async def _parse_excel(file_path: str) -> IngestResult:
    """Parse Excel file using OpenPyXL + Pandas."""
    import pandas as pd

    sheets_data = []
    full_text_parts = []
    tables = []

    try:
        xls = pd.ExcelFile(file_path)
        for sheet_name in xls.sheet_names:
            df = pd.read_excel(xls, sheet_name=sheet_name)
            text = f"Sheet: {sheet_name}\n{df.to_string()}"
            sheets_data.append(sheet_name)
            full_text_parts.append(text)
            tables.append(df.values.tolist())
    except Exception as e:
        logger.warning(f"[Ingestor/Excel] Parse failed: {e}")
        return IngestResult(
            file_path=file_path,
            file_type="xlsx",
            method="fallback",
            warnings=[f"Excel parse failed: {e}"],
        )

    pages = [
        ParsedPage(
            page_number=i + 1,
            text=full_text_parts[i],
            confidence=0.95,
            method="pandas",
        )
        for i in range(len(full_text_parts))
    ]

    return IngestResult(
        file_path=file_path,
        file_type="xlsx",
        total_pages=len(pages),
        pages=pages,
        full_text="\n\n".join(full_text_parts),
        tables=tables,
        method="pandas+openpyxl",
        metadata={"sheets": sheets_data},
    )


async def _parse_csv(file_path: str) -> IngestResult:
    """Parse CSV file using Pandas."""
    import pandas as pd

    try:
        df = pd.read_csv(file_path)
        text = df.to_string()
        table = df.values.tolist()
    except Exception as e:
        return IngestResult(
            file_path=file_path,
            file_type="csv",
            method="fallback",
            warnings=[f"CSV parse failed: {e}"],
        )

    return IngestResult(
        file_path=file_path,
        file_type="csv",
        total_pages=1,
        pages=[ParsedPage(page_number=1, text=text, confidence=0.99, method="pandas")],
        full_text=text,
        tables=[table],
        method="pandas",
    )


async def _fallback_text_read(file_path: str) -> IngestResult:
    """Last resort: read file as plain text."""
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()
    except Exception:
        text = ""

    return IngestResult(
        file_path=file_path,
        file_type="txt",
        total_pages=1,
        pages=[ParsedPage(page_number=1, text=text, confidence=0.5, method="fallback")],
        full_text=text,
        method="fallback",
        warnings=["No specialized parser available — used plain text fallback"],
    )


class DocumentIngestor:
    """Orchestrates document parsing using the best available libraries.

    Selection strategy:
    1. For PDFs:
       a. Try PyMuPDF first (fast text extraction)
       b. If low confidence (scanned pages), fall back to Tesseract OCR
       c. Use Unstructured.io for complex layouts if available
       d. Extract tables with Camelot if available
    2. For Excel: OpenPyXL + Pandas
    3. For CSV: Pandas
    4. Fallback: plain text read
    """

    def __init__(self):
        _check_libraries()

    async def ingest(
        self,
        file_path: str,
        document_type: Optional[str] = None,
        force_ocr: bool = False,
    ) -> IngestResult:
        """Ingest a document and return parsed content.

        Args:
            file_path: Path to the document file.
            document_type: Optional hint (e.g., "annual_report", "bank_statement").
            force_ocr: Force OCR even if text extraction succeeds.

        Returns:
            IngestResult with parsed text, tables, and metadata.
        """
        if not os.path.isfile(file_path):
            return IngestResult(
                file_path=file_path,
                file_type="unknown",
                warnings=[f"File not found: {file_path}"],
            )

        file_type = _detect_file_type(file_path)
        logger.info(f"[Ingestor] Parsing {file_path} (type={file_type}, doc_type={document_type})")

        if file_type == "pdf":
            return await self._ingest_pdf(file_path, force_ocr)
        elif file_type == "xlsx":
            return await self._ingest_excel(file_path)
        elif file_type == "csv":
            return await self._parse_csv(file_path)
        else:
            return await _fallback_text_read(file_path)

    async def _ingest_pdf(self, file_path: str, force_ocr: bool) -> IngestResult:
        """PDF ingestion with adaptive parser selection."""
        result = None

        # Step 1: Try fast text extraction with PyMuPDF
        if _HAS_PYMUPDF and not force_ocr:
            try:
                result = await _parse_pdf_pymupdf(file_path)
                # Check if pages have meaningful text
                low_conf_pages = [p for p in result.pages if p.confidence < 0.5]
                if len(low_conf_pages) > len(result.pages) * 0.5:
                    # More than half the pages are low confidence → likely scanned
                    logger.info("[Ingestor] PyMuPDF found mostly scanned pages, trying OCR")
                    result = None  # Fall through to OCR
            except Exception as e:
                logger.warning(f"[Ingestor/PyMuPDF] Failed: {e}")

        # Step 2: Try Unstructured.io for complex layouts
        if result is None and _HAS_UNSTRUCTURED:
            try:
                result = await _parse_pdf_unstructured(file_path)
            except Exception as e:
                logger.warning(f"[Ingestor/Unstructured] Failed: {e}")

        # Step 3: Try OCR for scanned pages
        if result is None and _HAS_TESSERACT and _HAS_PYMUPDF:
            try:
                result = await _parse_pdf_ocr(file_path)
            except Exception as e:
                logger.warning(f"[Ingestor/OCR] Failed: {e}")

        # Step 4: Fallback to plain text read
        if result is None:
            result = await _fallback_text_read(file_path)
            result.warnings.append("No PDF parser available — extracted as plain text")

        # Step 5: Extract tables with Camelot if available
        if _HAS_CAMELOT and result.file_type == "pdf":
            try:
                tables = await _extract_tables_camelot(file_path)
                if tables:
                    result.tables = tables
                    result.metadata["tables_extracted"] = len(tables)
            except Exception as e:
                logger.warning(f"[Ingestor/Camelot] Table extraction failed: {e}")

        return result

    async def _ingest_excel(self, file_path: str) -> IngestResult:
        """Excel ingestion."""
        if _HAS_PANDAS:
            return await _parse_excel(file_path)
        return await _fallback_text_read(file_path)

    async def _parse_csv(self, file_path: str) -> IngestResult:
        """CSV ingestion."""
        if _HAS_PANDAS:
            return await _parse_csv(file_path)
        return await _fallback_text_read(file_path)


def get_available_parsers() -> Dict[str, bool]:
    """Return which parsing libraries are available."""
    _check_libraries()
    return {
        "pymupdf": _HAS_PYMUPDF,
        "camelot": _HAS_CAMELOT,
        "tesseract": _HAS_TESSERACT,
        "unstructured": _HAS_UNSTRUCTURED,
        "openpyxl": _HAS_OPENPYXL,
        "pandas": _HAS_PANDAS,
    }
