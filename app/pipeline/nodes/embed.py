"""
Node: embed_claims
Generates embeddings for all usable claims using local sentence transformers.
"""

import logging

from app.pipeline.state import PipelineState, ClaimData
from app.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


def embed_claims(state: PipelineState) -> PipelineState:
    """Generate embeddings for usable claims."""
    errors = state.get("errors", [])
    claims: list[ClaimData] = state.get("claims", [])

    if state.get("is_duplicate") or not claims:
        return state

    usable_claims = [c for c in claims if c.status == "usable"]
    if not usable_claims:
        logger.info("No usable claims to embed")
        return {**state, "status": "embedded", "errors": errors}

    try:
        embedding_service = get_embedding_service()

        # Build semantic text for each claim
        texts = [_claim_to_embedding_text(c) for c in usable_claims]

        # Batch embed
        embeddings = embedding_service.embed(texts)

        for claim, emb in zip(usable_claims, embeddings):
            claim.embedding = emb

        logger.info("Embedded %d usable claims (dim=%d)", len(usable_claims), embedding_service.dimension)

    except Exception as e:
        logger.error("Embedding generation failed: %s", e)
        errors.append({"stage": "embed", "error": str(e)})

    return {
        **state,
        "claims": claims,
        "status": "embedded",
        "errors": errors,
    }


def _claim_to_embedding_text(claim: ClaimData) -> str:
    """
    Convert a claim to a text representation suitable for embedding.
    Captures the semantic content of the claim.
    """
    parts = [claim.entity_text]

    if claim.attribute_canonical:
        parts.append(claim.attribute_canonical)
    elif claim.attribute_raw:
        parts.append(claim.attribute_raw)

    if claim.value:
        parts.append(str(claim.value))

    if claim.unit:
        parts.append(claim.unit)

    if claim.time_scope and claim.time_scope.get("text"):
        parts.append(claim.time_scope["text"])

    if claim.scope:
        parts.append(claim.scope)

    return " | ".join(parts)
