"""
Node: classify_relations
Separate LLM stage for relation classification between candidate pairs.
"""

import logging
from pathlib import Path

from app.pipeline.state import PipelineState, CandidatePair, RelationData, ClaimData
from app.services.llm_service import get_llm_service
from app.schemas.llm_outputs import ClassificationResult
from app.config import get_settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "classification.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""


def classify_relations(state: PipelineState) -> PipelineState:
    """Classify relations for all candidate pairs."""
    errors = state.get("errors", [])
    candidates: list[CandidatePair] = state.get("candidates", [])

    if state.get("is_duplicate") or not candidates:
        return {**state, "relations": [], "status": "classified", "errors": errors}

    llm = get_llm_service()
    relations: list[RelationData] = []

    for i, pair in enumerate(candidates):
        try:
            result = _classify_pair(llm, pair)
            if result:
                relations.append(result)
                logger.info(
                    "Pair %d/%d: %s (conf=%.2f) — %s.%s vs %s.%s",
                    i + 1, len(candidates),
                    result.relation_type,
                    result.confidence,
                    pair.new_claim.entity_text[:20],
                    pair.new_claim.attribute_raw[:20],
                    pair.existing_claim_data.get("entity_text", "")[:20],
                    pair.existing_claim_data.get("attribute_raw", "")[:20],
                )
        except Exception as e:
            logger.warning("Classification failed for pair %d: %s", i, e)
            errors.append({
                "stage": "classify",
                "error": str(e),
                "new_claim_id": pair.new_claim.claim_id,
                "existing_claim_id": pair.existing_claim_id,
            })

    logger.info(
        "Classified %d relations from %d candidates", len(relations), len(candidates)
    )

    return {
        **state,
        "relations": relations,
        "status": "classified",
        "errors": errors,
    }


def _classify_pair(llm, pair: CandidatePair) -> RelationData | None:
    """Classify the relation between a new claim and an existing claim."""
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
        doc_a=f"current document",
        entity_b=existing.get("entity_text", ""),
        attribute_b=existing.get("attribute_canonical", existing.get("attribute_raw", "")),
        value_b=existing.get("value", ""),
        unit_b=existing.get("unit", ""),
        time_scope_b=time_scope_b or "not specified",
        scope_b=existing.get("scope", "not specified"),
        evidence_b=existing.get("evidence_text", ""),
        doc_b=existing.get("document_filename", "previous document"),
    )

    system_prompt = (
        "You are a relation classification system. "
        "Determine the relationship between two claims. "
        "Return ONLY valid JSON."
    )

    raw = llm.generate_json(prompt, system_prompt=system_prompt)
    if not raw:
        return None

    try:
        result = ClassificationResult.model_validate(raw)
    except Exception as e:
        logger.warning("Failed to validate classification: %s", e)
        return None

    return RelationData(
        source_claim_id=new.claim_id,
        target_claim_id=pair.existing_claim_id,
        relation_type=result.relation,
        confidence=result.confidence,
        explanation=result.explanation,
        reasoning_factors=result.reasoning_factors,
    )
