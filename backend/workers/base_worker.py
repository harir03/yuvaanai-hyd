"""
Intelli-Credit — Base Document Worker

Abstract base for all 8 document workers. Each worker:
1. Receives a file path + session_id
2. Reads and parses the document
3. Extracts structured data into a WorkerOutput
4. Emits ThinkingEvents throughout
5. Stages its output in Redis for the Consolidator

Subclasses must implement `_extract()`.
"""

import os
import time
import logging
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from backend.models.schemas import DocumentType, EventType
from backend.graph.state import WorkerOutput
from backend.thinking.event_emitter import ThinkingEventEmitter
from backend.storage.redis_client import get_redis_client

logger = logging.getLogger(__name__)


class BaseDocumentWorker(ABC):
    """
    Abstract base class for document workers.

    Each worker:
    - Is bound to one DocumentType
    - Extracts structured data from a file
    - Emits ThinkingEvents (READ, FOUND, FLAGGED, etc.)
    - Stages output in Redis for the Consolidator
    """

    # Subclasses must set these
    worker_id: str = ""
    document_type: DocumentType = DocumentType.ANNUAL_REPORT
    display_name: str = ""

    def __init__(self, session_id: str, file_path: str):
        self.session_id = session_id
        self.file_path = file_path
        self.emitter = ThinkingEventEmitter(session_id, self.display_name)

    async def process(self) -> WorkerOutput:
        """
        Full processing pipeline for a document.

        1. Validate file exists
        2. Emit READ event
        3. Call _extract() (subclass-specific)
        4. Build WorkerOutput
        5. Stage output in Redis
        6. Emit completion event

        Returns:
            WorkerOutput with extracted data
        """
        start_time = time.time()

        try:
            # 1. Validate file
            if not os.path.exists(self.file_path):
                await self.emitter.flagged(
                    f"File not found: {os.path.basename(self.file_path)}",
                )
                return WorkerOutput(
                    worker_id=self.worker_id,
                    document_type=self.document_type.value,
                    status="failed",
                    errors=[f"File not found: {self.file_path}"],
                )

            file_size = os.path.getsize(self.file_path)
            filename = os.path.basename(self.file_path)

            # 2. Emit READ event
            await self.emitter.read(
                f"Opening {filename} ({file_size / 1024:.0f} KB)",
                source_document=filename,
            )

            # 3. Call subclass extraction
            extracted_data, pages_processed, confidence = await self._extract()

            elapsed = time.time() - start_time

            # 4. Build output
            output = WorkerOutput(
                worker_id=self.worker_id,
                document_type=self.document_type.value,
                status="completed",
                extracted_data=extracted_data,
                confidence=confidence,
                pages_processed=pages_processed,
                errors=[],
                metadata={
                    "filename": filename,
                    "file_size": file_size,
                    "processing_time_seconds": round(elapsed, 2),
                },
            )

            # 5. Stage in Redis
            await self._stage_output(output)

            # 6. Emit completion
            await self.emitter.accepted(
                f"Completed {filename}: {pages_processed} pages, "
                f"confidence {confidence:.0%}, {elapsed:.1f}s",
                source_document=filename,
                confidence=confidence,
            )

            return output

        except Exception as e:
            elapsed = time.time() - start_time
            logger.error(f"[{self.worker_id}] Failed: {e}")
            await self.emitter.critical(
                f"Worker {self.worker_id} failed: {str(e)}",
            )
            return WorkerOutput(
                worker_id=self.worker_id,
                document_type=self.document_type.value,
                status="failed",
                errors=[str(e)],
                metadata={"processing_time_seconds": round(elapsed, 2)},
            )

    @abstractmethod
    async def _extract(self) -> tuple:
        """
        Extract structured data from the document.

        Must return a tuple of:
            (extracted_data: Dict[str, Any], pages_processed: int, confidence: float)

        Subclasses implement document-type-specific parsing here.
        This is where OCR, table extraction, LLM calls happen.
        """
        ...

    async def _stage_output(self, output: WorkerOutput) -> None:
        """Stage worker output in Redis for the Consolidator to collect."""
        try:
            redis = get_redis_client()
            if not redis.is_initialized:
                await redis.initialize()
            output_dict = output.model_dump(mode="json")
            await redis.stage_worker_output(self.session_id, self.worker_id, output_dict)
            logger.info(f"[{self.worker_id}] Output staged in Redis for session {self.session_id}")
        except Exception as e:
            logger.warning(f"[{self.worker_id}] Failed to stage output: {e}")
            # Non-fatal — consolidator can still get output from return value


    # ──────────────────────────────────────────────
    # Helper methods for subclasses
    # ──────────────────────────────────────────────

    def _file_extension(self) -> str:
        """Get the file extension (lowercase)."""
        _, ext = os.path.splitext(self.file_path)
        return ext.lower()

    def _read_text_file(self) -> str:
        """Read a text/CSV file. For PDFs/Excel, subclasses use specialized parsers."""
        with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
            return f.read()
