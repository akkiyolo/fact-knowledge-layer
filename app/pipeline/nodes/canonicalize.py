"""
Node: canonicalize_attributes
Dynamically canonicalizes claim attributes using embedding similarity.
No fixed vocabulary.
"""

import logging

from app.pipeline.state import PipelineState, ClaimData
from app.services.attribute_service import AttributeService
from app.db.database import get_session_factory
from app.db.repositories import ClaimRepository

logger = logging.getLogger(__name__)


def canonicalize_attributes(state: PipelineState) -> PipelineState:
    """Canonicalize raw attributes for all extracted claims."""
    errors = state.get("errors", [])
    claims: list[ClaimData] = state.get("claims", [])

    if state.get("is_duplicate") or not claims:
        return state

    try:
        attr_service = AttributeService()

        # Load existing canonical attributes from DB
        factory = get_session_factory()
        session = factory()
        try:
            claim_repo = ClaimRepository(session)
            existing_attrs = claim_repo.get_canonical_attributes()
            attr_service.load_existing_attributes(existing_attrs)
        finally:
            session.close()

        # Canonicalize each claim's attribute
        for claim in claims:
            if claim.status != "usable":
                # Still canonicalize unresolved claims for inspection
                pass
            try:
                canonical = attr_service.canonicalize(claim.attribute_raw)
                claim.attribute_canonical = canonical
            except Exception as e:
                logger.warning(
                    "Failed to canonicalize '%s': %s", claim.attribute_raw, e
                )
                claim.attribute_canonical = claim.attribute_raw

        logger.info(
            "Canonicalized %d claims. Known attributes: %d",
            len(claims),
            len(attr_service.known_attributes),
        )

    except Exception as e:
        logger.error("Attribute canonicalization failed: %s", e)
        errors.append({"stage": "canonicalize", "error": str(e)})
        # Fallback: use raw as canonical
        for claim in claims:
            if not claim.attribute_canonical:
                claim.attribute_canonical = claim.attribute_raw

    return {
        **state,
        "claims": claims,
        "status": "canonicalized",
        "errors": errors,
    }
