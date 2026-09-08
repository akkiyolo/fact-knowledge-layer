"""
Node: persist_results
Writes document, chunks, claims, and relations to the database.
"""

import logging

from app.pipeline.state import PipelineState, ClaimData, RelationData, ChunkData
from app.db.database import get_session_factory
from app.db.repositories import DocumentRepository, ChunkRepository, ClaimRepository, RelationRepository

logger = logging.getLogger(__name__)


def persist_results(state: PipelineState) -> PipelineState:
    """Persist all extracted data to the database."""
    errors = state.get("errors", [])

    # If duplicate, nothing to persist
    if state.get("is_duplicate"):
        return {**state, "status": "complete"}

    factory = get_session_factory()
    session = factory()

    try:
        doc_repo = DocumentRepository(session)
        chunk_repo = ChunkRepository(session)
        claim_repo = ClaimRepository(session)
        rel_repo = RelationRepository(session)

        # 1. Create document
        document = doc_repo.create(
            filename=state.get("filename", "unknown.pdf"),
            content_hash=state.get("content_hash", ""),
            page_count=state.get("page_count"),
            metadata_={
                "errors": len(errors),
                "total_chunks": len(state.get("chunks", [])),
                "total_claims": len(state.get("claims", [])),
                "total_relations": len(state.get("relations", [])),
            },
            status="completed",
        )
        document_id = document.id

        # Update state with the actual document_id
        state["document_id"] = document_id

        # 2. Create chunks
        chunks: list[ChunkData] = state.get("chunks", [])
        chunk_id_map = {}  # pipeline chunk_id → db chunk_id

        for chunk in chunks:
            db_chunk_data = {
                "document_id": document_id,
                "page_number": chunk.page_number,
                "char_start": chunk.char_start,
                "char_end": chunk.char_end,
                "text": chunk.text,
                "metadata_": chunk.metadata,
            }
            db_chunks = chunk_repo.bulk_create([db_chunk_data])
            if db_chunks:
                chunk_id_map[chunk.chunk_id] = db_chunks[0].id

        # 3. Create claims
        claims: list[ClaimData] = state.get("claims", [])
        claim_id_map = {}  # pipeline claim_id → db claim_id

        for claim in claims:
            db_chunk_id = chunk_id_map.get(claim.chunk_id, None)
            if not db_chunk_id:
                continue

            db_claim = claim_repo.create(
                document_id=document_id,
                chunk_id=db_chunk_id,
                entity_text=claim.entity_text,
                entity_type=claim.entity_type,
                attribute_raw=claim.attribute_raw,
                attribute_canonical=claim.attribute_canonical,
                value_type=claim.value_type,
                value=claim.value,
                unit=claim.unit,
                time_scope=claim.time_scope,
                scope=claim.scope,
                qualifiers=claim.qualifiers,
                evidence_text=claim.evidence_text,
                evidence_page=claim.evidence_page,
                evidence_char_start=claim.evidence_char_start,
                evidence_char_end=claim.evidence_char_end,
                extraction_confidence=claim.extraction_confidence,
                grounding_confidence=claim.grounding_confidence,
                status=claim.status,
                embedding=claim.embedding,
            )
            claim_id_map[claim.claim_id] = db_claim.id

        # 4. Create relations
        relations: list[RelationData] = state.get("relations", [])
        persisted_relations = 0

        for rel in relations:
            source_id = claim_id_map.get(rel.source_claim_id)
            target_id = rel.target_claim_id  # Already a DB ID (from existing claims)

            if not source_id or not target_id:
                continue

            rel_repo.create(
                source_claim_id=source_id,
                target_claim_id=target_id,
                relation_type=rel.relation_type,
                confidence=rel.confidence,
                explanation=rel.explanation,
                reasoning_factors=rel.reasoning_factors,
                reconciling_factor=rel.reconciling_factor,
                reconciliation_explanation=rel.reconciliation_explanation,
            )
            persisted_relations += 1

        session.commit()

        logger.info(
            "Persisted: doc=%s, chunks=%d, claims=%d, relations=%d",
            document_id,
            len(chunk_id_map),
            len(claim_id_map),
            persisted_relations,
        )

        return {
            **state,
            "document_id": document_id,
            "status": "complete",
            "errors": errors,
        }

    except Exception as e:
        session.rollback()
        logger.error("Persist failed: %s", e)
        errors.append({"stage": "persist", "error": str(e)})
        return {**state, "errors": errors, "status": "failed"}
    finally:
        session.close()
