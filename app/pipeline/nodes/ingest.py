"""
Node: ingest_document
Receives uploaded file, computes content hash, checks for duplicates.
"""

import logging
from app.pipeline.state import PipelineState
from app.services.document_service import DocumentService
from app.db.database import get_session_factory
from app.db.repositories import DocumentRepository

logger = logging.getLogger(__name__)


def ingest_document(state: PipelineState) -> PipelineState:
    """Ingest a document: save file, check for duplicates."""
    errors = state.get("errors", [])
    filename = state.get("filename", "unknown.pdf")

    try:
        file_content = state.get("file_content", b"")
        if not file_content:
            raise ValueError("No file content provided")

        # Compute content hash
        content_hash = DocumentService.compute_content_hash(file_content)

        # Check for duplicate
        factory = get_session_factory()
        session = factory()
        try:
            doc_repo = DocumentRepository(session)
            existing = doc_repo.find_by_content_hash(content_hash)
            if existing:
                from app.db.repositories import ClaimRepository
                claim_repo = ClaimRepository(session)
                claims = claim_repo.get_by_document(existing.id, limit=1)
                if len(claims) > 0:
                    logger.info("Duplicate document detected with %d+ claims: %s (existing: %s)", len(claims), filename, existing.id)
                    return {
                        **state,
                        "content_hash": content_hash,
                        "is_duplicate": True,
                        "existing_document_id": existing.id,
                        "document_id": existing.id,
                        "status": "duplicate",
                        "errors": errors,
                    }
                else:
                    logger.info("Document %s previously ingested with 0 claims. Removing stale record to re-ingest.", filename)
                    session.delete(existing)
                    session.commit()
        finally:
            session.close()

        # Save file
        doc_service = DocumentService()
        file_path = doc_service.save_upload(filename, file_content)

        logger.info("Document ingested: %s (hash: %s...)", filename, content_hash[:12])

        return {
            **state,
            "file_path": str(file_path),
            "content_hash": content_hash,
            "is_duplicate": False,
            "status": "ingested",
            "errors": errors,
        }

    except Exception as e:
        logger.error("Ingest failed for %s: %s", filename, e)
        errors.append({"stage": "ingest", "error": str(e), "filename": filename})
        return {**state, "errors": errors, "status": "failed"}
