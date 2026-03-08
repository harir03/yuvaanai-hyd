"""
Intelli-Credit — Upload Route

POST /api/upload — Accepts company info + document files, creates a session,
dispatches Celery workers for parallel document processing.
"""

import uuid
import os
import json
import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, UploadFile, File, Form, HTTPException, BackgroundTasks, status

from backend.models.schemas import (
    CompanyInfo,
    DocumentMeta,
    DocumentType,
    AssessmentSummary,
    PipelineStage,
    PipelineStageEnum,
    PipelineStageStatus,
    WorkerStatus,
    WorkerStatusEnum,
    AssessmentOutcome,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["upload"])

# In-memory store for hackathon (replaced by PostgreSQL in T0.4)
# Shared with other route modules via import
from backend.api.routes._store import assessments_store


DOCUMENT_TYPE_MAP = {
    "annual_report": DocumentType.ANNUAL_REPORT,
    "bank_statement": DocumentType.BANK_STATEMENT,
    "gst_returns": DocumentType.GST_RETURNS,
    "itr": DocumentType.ITR,
    "legal_notice": DocumentType.LEGAL_NOTICE,
    "board_minutes": DocumentType.BOARD_MINUTES,
    "shareholding_pattern": DocumentType.SHAREHOLDING_PATTERN,
    "rating_report": DocumentType.RATING_REPORT,
}

UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "..", "data", "uploads")


@router.post("/upload", response_model=AssessmentSummary, status_code=status.HTTP_201_CREATED)
async def upload_documents(
    background_tasks: BackgroundTasks,
    company_name: str = Form(...),
    sector: str = Form(...),
    loan_type: str = Form(...),
    loan_amount: str = Form(...),
    loan_amount_numeric: float = Form(...),
    cin: str = Form(default=""),
    gstin: str = Form(default=""),
    pan: str = Form(default=""),
    incorporation_year: int = Form(default=0),
    promoter_name: str = Form(default=""),
    annual_turnover: str = Form(default=""),
    files: List[UploadFile] = File(default=[]),
    document_types: str = Form(default="[]"),
    auto_run: bool = Form(default=False),
):
    """
    Create a new credit assessment session.

    Accepts company info as form fields and document files.
    Returns the initial AssessmentSummary with session_id.
    """
    session_id = str(uuid.uuid4())
    logger.info(f"[Upload] New session: {session_id} for {company_name}")

    # Build company info
    company = CompanyInfo(
        name=company_name,
        cin=cin or None,
        gstin=gstin or None,
        pan=pan or None,
        sector=sector,
        loan_type=loan_type,
        loan_amount=loan_amount,
        loan_amount_numeric=loan_amount_numeric,
        incorporation_year=incorporation_year if incorporation_year > 0 else None,
        promoter_name=promoter_name or None,
        annual_turnover=annual_turnover or None,
    )

    # Parse document type assignments
    try:
        doc_type_list = json.loads(document_types)
    except (json.JSONDecodeError, TypeError):
        doc_type_list = []

    # Save files and build document metadata
    documents: List[DocumentMeta] = []
    os.makedirs(os.path.join(UPLOAD_DIR, session_id), exist_ok=True)

    for i, file in enumerate(files):
        # Determine document type
        doc_type_str = doc_type_list[i] if i < len(doc_type_list) else "annual_report"
        doc_type = DOCUMENT_TYPE_MAP.get(doc_type_str, DocumentType.ANNUAL_REPORT)

        # Read file content
        content = await file.read()
        file_path = os.path.join(UPLOAD_DIR, session_id, file.filename)

        # Save to disk
        with open(file_path, "wb") as f:
            f.write(content)

        doc_meta = DocumentMeta(
            filename=file.filename,
            document_type=doc_type,
            file_size=len(content),
        )
        documents.append(doc_meta)
        logger.info(f"[Upload] Saved {file.filename} ({doc_type.value}) — {len(content)} bytes")

    # Initialize pipeline stages
    pipeline_stages = [
        PipelineStage(stage=PipelineStageEnum.UPLOAD, status=PipelineStageStatus.COMPLETED,
                       started_at=datetime.utcnow(), completed_at=datetime.utcnow(),
                       message="Documents uploaded successfully"),
        PipelineStage(stage=PipelineStageEnum.WORKERS, status=PipelineStageStatus.PENDING),
        PipelineStage(stage=PipelineStageEnum.CONSOLIDATION, status=PipelineStageStatus.PENDING),
        PipelineStage(stage=PipelineStageEnum.VALIDATION, status=PipelineStageStatus.PENDING),
        PipelineStage(stage=PipelineStageEnum.ORGANIZATION, status=PipelineStageStatus.PENDING),
        PipelineStage(stage=PipelineStageEnum.RESEARCH, status=PipelineStageStatus.PENDING),
        PipelineStage(stage=PipelineStageEnum.REASONING, status=PipelineStageStatus.PENDING),
        PipelineStage(stage=PipelineStageEnum.EVIDENCE, status=PipelineStageStatus.PENDING),
        PipelineStage(stage=PipelineStageEnum.TICKETS, status=PipelineStageStatus.PENDING),
        PipelineStage(stage=PipelineStageEnum.RECOMMENDATION, status=PipelineStageStatus.PENDING),
    ]

    # Initialize worker statuses for each uploaded document
    workers = [
        WorkerStatus(
            worker_id=f"W{i+1}",
            document_type=doc.document_type,
            status=WorkerStatusEnum.QUEUED,
            current_task="Queued for processing",
        )
        for i, doc in enumerate(documents)
    ]

    # Build assessment summary
    assessment = AssessmentSummary(
        session_id=session_id,
        company=company,
        documents=documents,
        pipeline_stages=pipeline_stages,
        workers=workers,
        outcome=AssessmentOutcome.PENDING,
        documents_analyzed=len(documents),
        created_at=datetime.utcnow(),
    )

    # Store in memory (will be PostgreSQL later)
    assessments_store[session_id] = assessment

    # Auto-trigger pipeline if requested
    if auto_run and documents:
        from backend.api.routes.pipeline import _execute_pipeline
        background_tasks.add_task(_execute_pipeline, session_id)
        logger.info(f"[Upload] Auto-triggered pipeline for {session_id}")

    logger.info(f"[Upload] Session {session_id} created with {len(documents)} documents")
    return assessment
