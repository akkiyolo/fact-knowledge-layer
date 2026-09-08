"""
Node: retrieve_candidates
Queries pgvector for top-k similar EXISTING claims for each new claim.
CRITICAL: Only compares against existing claims, NOT all-pairs.
"""

import logging

from app.pipeline.state import PipelineState, ClaimData, CandidatePair
from app.db.database import get_session_factory
from app.db.repositories import ClaimRepository
from app.config import get_settings

logger = logging.getLogger(__name__)


def retrieve_candidates(state: PipelineState) -> PipelineState:
    """Retrieve top-k similar existing claims for each new usable claim."""
    errors = state.get("errors", [])
    claims: list[ClaimData] = state.get("claims", [])
    document_id = state.get("document_id", "")

    if state.get("is_duplicate") or not claims:
        return state

    usable_claims = [c for c in claims if c.status == "usable" and c.embedding]
    if not usable_claims:
        logger.info("No usable claims with embeddings for retrieval")
        return {**state, "candidates": [], "status": "retrieved", "errors": errors}

    settings = get_settings()
    candidates: list[CandidatePair] = []

    factory = get_session_factory()
    session = factory()

    try:
        claim_repo = ClaimRepository(session)
        total_retrieved = 0

        for claim in usable_claims:
            try:
                # Query pgvector for similar EXISTING claims
                similar = claim_repo.find_similar_existing(
                    embedding=claim.embedding,
                    exclude_document_id=document_id,
                    top_k=settings.candidate_top_k,
                    similarity_threshold=settings.candidate_similarity_threshold,
                )

                for existing_claim, similarity in similar:
                    pair = CandidatePair(
                        new_claim=claim,
                        existing_claim_id=existing_claim.id,
                        existing_claim_data={
                            "id": existing_claim.id,
                            "entity_text": existing_claim.entity_text,
                            "entity_type": existing_claim.entity_type,
                            "attribute_raw": existing_claim.attribute_raw,
                            "attribute_canonical": existing_claim.attribute_canonical,
                            "value_type": existing_claim.value_type,
                            "value": existing_claim.value,
                            "unit": existing_claim.unit,
                            "time_scope": existing_claim.time_scope,
                            "scope": existing_claim.scope,
                            "qualifiers": existing_claim.qualifiers,
                            "evidence_text": existing_claim.evidence_text,
                            "evidence_page": existing_claim.evidence_page,
                            "document_id": existing_claim.document_id,
                            "document_filename": existing_claim.document.filename if existing_claim.document else "",
                        },
                        similarity_score=similarity,
                    )
                    candidates.append(pair)
                    total_retrieved += 1

            except Exception as e:
                logger.warning(
                    "Retrieval failed for claim %s: %s", claim.claim_id, e
                )
                errors.append({
                    "stage": "retrieve",
                    "error": str(e),
                    "claim_id": claim.claim_id,
                })

        logger.info(
            "Retrieved %d candidate pairs for %d new claims",
            total_retrieved, len(usable_claims),
        )

    except Exception as e:
        logger.error("Candidate retrieval failed: %s", e)
        errors.append({"stage": "retrieve", "error": str(e)})
    finally:
        session.close()

    return {
        **state,
        "candidates": candidates,
        "status": "retrieved",
        "errors": errors,
    }
