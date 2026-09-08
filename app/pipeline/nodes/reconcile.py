"""
Node: reconcile_contradictions
Attempts to reconcile apparent contradictions using explicit contextual evidence.
Only invoked for relations classified as 'contradicts'.
"""

import logging
from pathlib import Path

from app.pipeline.state import PipelineState, RelationData, CandidatePair
from app.services.llm_service import get_llm_service
from app.schemas.llm_outputs import ReconciliationResult

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "reconciliation.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""


def reconcile_contradictions(state: PipelineState) -> PipelineState:
    """Attempt to reconcile contradictions using explicit contextual evidence."""
    errors = state.get("errors", [])
    relations: list[RelationData] = state.get("relations", [])
    candidates: list[CandidatePair] = state.get("candidates", [])

    if state.get("is_duplicate") or not relations:
        return {**state, "status": "reconciled", "errors": errors}

    # Only process contradictions
    contradictions = [r for r in relations if r.relation_type == "contradicts"]
    if not contradictions:
        logger.info("No contradictions to reconcile")
        return {**state, "status": "reconciled", "errors": errors}

    llm = get_llm_service()

    # Build lookup for candidate data
    candidate_map = {}
    for pair in candidates:
        key = (pair.new_claim.claim_id, pair.existing_claim_id)
        candidate_map[key] = pair

    reconciled_count = 0

    for rel in contradictions:
        pair = candidate_map.get((rel.source_claim_id, rel.target_claim_id))
        if not pair:
            continue

        try:
            result = _reconcile_pair(llm, pair)
            if result and result.get("reconciled"):
                rel.relation_type = "contradicts_reconciled"
                rel.reconciling_factor = result.get("reconciling_factor")
                rel.reconciliation_explanation = result.get("explanation", "")
                reconciled_count += 1
                logger.info(
                    "Reconciled contradiction: %s.%s — factor: %s",
                    pair.new_claim.entity_text[:20],
                    pair.new_claim.attribute_raw[:20],
                    result.get("reconciling_factor"),
                )
            elif result:
                rel.reconciliation_explanation = result.get("explanation", "Could not reconcile")

        except Exception as e:
            logger.warning("Reconciliation failed: %s", e)
            errors.append({
                "stage": "reconcile",
                "error": str(e),
                "source_claim_id": rel.source_claim_id,
                "target_claim_id": rel.target_claim_id,
            })

    logger.info(
        "Reconciliation: %d/%d contradictions reconciled",
        reconciled_count, len(contradictions),
    )

    return {
        **state,
        "relations": relations,
        "status": "reconciled",
        "errors": errors,
    }


def _reconcile_pair(llm, pair: CandidatePair) -> dict | None:
    """Attempt to reconcile a single contradiction pair."""
    new = pair.new_claim
    existing = pair.existing_claim_data

    time_scope_a = ""
    if new.time_scope and new.time_scope.get("text"):
        time_scope_a = new.time_scope["text"]

    time_scope_b = ""
    if existing.get("time_scope") and existing["time_scope"].get("text"):
        time_scope_b = existing["time_scope"]["text"]

    prompt = _PROMPT_TEMPLATE.format(
        entity_a=new.entity_text,
        attribute_a=new.attribute_canonical or new.attribute_raw,
        value_a=new.value,
        unit_a=new.unit or "",
        time_scope_a=time_scope_a or "not specified",
        scope_a=new.scope or "not specified",
        evidence_a=new.evidence_text,
        entity_b=existing.get("entity_text", ""),
        attribute_b=existing.get("attribute_canonical", existing.get("attribute_raw", "")),
        value_b=existing.get("value", ""),
        unit_b=existing.get("unit", ""),
        time_scope_b=time_scope_b or "not specified",
        scope_b=existing.get("scope", "not specified"),
        evidence_b=existing.get("evidence_text", ""),
    )

    system_prompt = (
        "You are a contradiction reconciliation system. "
        "Determine if an apparent contradiction is explained by explicit contextual differences. "
        "Return ONLY valid JSON."
    )

    raw = llm.generate_json(prompt, system_prompt=system_prompt)
    if not raw:
        return None

    try:
        result = ReconciliationResult.model_validate(raw)
        return {
            "reconciled": result.reconciled,
            "reconciling_factor": result.reconciling_factor,
            "explanation": result.explanation,
            "confidence": result.confidence,
        }
    except Exception as e:
        logger.warning("Failed to validate reconciliation: %s", e)
        return None
