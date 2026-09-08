"""
Document API endpoints.
"""

import logging
from fastapi import APIRouter, UploadFile, File, HTTPException, Depends, BackgroundTasks
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repositories import DocumentRepository, ClaimRepository
from app.schemas.document import DocumentResponse, DocumentListResponse, UploadResponse
from app.schemas.claim import ClaimResponse, ClaimListResponse
from app.pipeline.graph import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/documents", tags=["documents"])


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    """Upload a PDF document for processing."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    # Read file content
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Empty file")

    # Check for duplicate
    from app.services.document_service import DocumentService
    content_hash = DocumentService.compute_content_hash(content)
    doc_repo = DocumentRepository(db)
    existing = doc_repo.find_by_content_hash(content_hash)

    if existing:
        # If existing document has 0 claims (failed previously), delete stale record and allow re-ingest
        from app.db.repositories import ClaimRepository
        claim_repo = ClaimRepository(db)
        claims = claim_repo.get_by_document(existing.id, limit=1)
        if len(claims) == 0:
            logger.info("Existing document %s has 0 claims. Removing stale record to re-process.", existing.filename)
            db.delete(existing)
            db.commit()
        else:
            return UploadResponse(
                document_id=existing.id,
                filename=existing.filename,
                status="duplicate",
                message="This document has already been ingested",
                is_duplicate=True,
            )

    # Run pipeline in background
    filename = file.filename
    background_tasks.add_task(_run_pipeline_task, filename, content)

    return UploadResponse(
        document_id="pending",
        filename=filename,
        status="processing",
        message="Document accepted for processing. Check /api/documents for results.",
        is_duplicate=False,
    )


def _run_pipeline_task(filename: str, content: bytes):
    """Background task to run the full pipeline."""
    try:
        result = run_pipeline(filename, content)
        status = result.get("status", "unknown")
        errors = result.get("errors", [])
        if errors:
            logger.warning(
                "Pipeline completed with %d errors for %s", len(errors), filename
            )
    except Exception as e:
        logger.error("Pipeline task failed for %s: %s", filename, e, exc_info=True)


@router.get("", response_model=DocumentListResponse)
def list_documents(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
):
    """List all ingested documents."""
    doc_repo = DocumentRepository(db)
    docs = doc_repo.list_all(skip=skip, limit=limit)
    return DocumentListResponse(
        documents=[DocumentResponse.from_orm_doc(d) for d in docs],
        total=len(docs),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(
    document_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific document by ID."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    return DocumentResponse.from_orm_doc(doc)


@router.get("/{document_id}/claims", response_model=ClaimListResponse)
def get_document_claims(
    document_id: str,
    status: str = None,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    """Get all claims for a specific document."""
    doc_repo = DocumentRepository(db)
    doc = doc_repo.get_by_id(document_id)
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")

    claim_repo = ClaimRepository(db)
    claims = claim_repo.get_by_document(document_id, status=status, skip=skip, limit=limit)

    return ClaimListResponse(
        claims=[ClaimResponse.from_orm_claim(c) for c in claims],
        total=len(claims),
    )
