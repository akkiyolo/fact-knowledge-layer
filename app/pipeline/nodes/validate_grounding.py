"""
Node: validate_grounding
Verifies extracted claims against their source text.
Separate LLM stage — NOT combined with extraction.
"""

import json
import logging
from pathlib import Path

from app.pipeline.state import PipelineState, ClaimData, ChunkData
from app.services.llm_service import get_llm_service
from app.schemas.llm_outputs import GroundingOutput
from app.config import get_settings

logger = logging.getLogger(__name__)

_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "grounding.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""


def validate_grounding(state: PipelineState) -> PipelineState:
    """Validate grounding of extracted claims against source chunks."""
    errors = state.get("errors", [])
    claims: list[ClaimData] = state.get("claims", [])
    chunks: list[ChunkData] = state.get("chunks", [])

    if state.get("is_duplicate") or not claims:
        return state

    settings = get_settings()
    llm = get_llm_service()

    # Group claims by chunk_id
    chunk_map = {c.chunk_id: c for c in chunks}
    claims_by_chunk: dict[str, list[int]] = {}
    for i, claim in enumerate(claims):
        claims_by_chunk.setdefault(claim.chunk_id, []).append(i)

    # Validate per chunk
    for chunk_id, claim_indices in claims_by_chunk.items():
        chunk = chunk_map.get(chunk_id)
        if not chunk:
            for idx in claim_indices:
                claims[idx].status = "unresolved"
                claims[idx].grounding_confidence = 0.0
            continue

        chunk_claims = [claims[i] for i in claim_indices]

        try:
            results = _validate_chunk_claims(llm, chunk, chunk_claims)

            for i, (idx, result) in enumerate(zip(claim_indices, results)):
                claims[idx].grounding_confidence = result.get("confidence", 0.0)
                if not result.get("is_grounded", False):
                    claims[idx].status = "unresolved"
                    issues = result.get("issues", [])
                    logger.info(
                        "Claim unresolved (page %d): %s — %s = %s | Issues: %s",
                        claims[idx].evidence_page,
                        claims[idx].entity_text,
                        claims[idx].attribute_raw,
                        claims[idx].value,
                        issues,
                    )
                elif result.get("confidence", 0.0) < settings.grounding_confidence_threshold:
                    claims[idx].status = "unresolved"

        except Exception as e:
            logger.error("Grounding validation failed for chunk %s: %s", chunk_id, e)
            errors.append({
                "stage": "validate_grounding",
                "error": str(e),
                "chunk_id": chunk_id,
            })
            # Don't crash — mark these claims as unresolved
            for idx in claim_indices:
                claims[idx].status = "unresolved"
                claims[idx].grounding_confidence = 0.0

    usable = sum(1 for c in claims if c.status == "usable")
    unresolved = sum(1 for c in claims if c.status == "unresolved")
    logger.info("Grounding: %d usable, %d unresolved out of %d total", usable, unresolved, len(claims))

    return {
        **state,
        "claims": claims,
        "status": "grounded",
        "errors": errors,
    }


def _validate_chunk_claims(llm, chunk: ChunkData, claims: list[ClaimData]) -> list[dict]:
    """Validate a batch of claims against their source chunk."""
    claims_json = json.dumps([
        {
            "entity": claim.entity_text,
            "attribute": claim.attribute_raw,
            "value": claim.value,
            "unit": claim.unit,
            "time_scope": claim.time_scope,
            "scope": claim.scope,
            "evidence": claim.evidence_text,
        }
        for claim in claims
    ], indent=2)

    prompt = _PROMPT_TEMPLATE.format(
        page_number=chunk.page_number,
        chunk_text=chunk.text,
        claims_json=claims_json,
    )

    system_prompt = (
        "You are a grounding validation system. "
        "Verify whether extracted claims are properly supported by source text. "
        "Return ONLY valid JSON."
    )

    raw = llm.generate_json(prompt, system_prompt=system_prompt)

    if not raw:
        return [{"is_grounded": False, "confidence": 0.0, "issues": ["LLM returned empty"]}] * len(claims)

    try:
        output = GroundingOutput.model_validate(raw)
        results = [
            {
                "is_grounded": r.is_grounded,
                "confidence": r.confidence,
                "issues": r.issues,
            }
            for r in output.results
        ]
        # Pad if LLM returned fewer results
        while len(results) < len(claims):
            results.append({"is_grounded": False, "confidence": 0.0, "issues": ["missing from LLM output"]})
        return results[:len(claims)]
    except Exception as e:
        logger.warning("Failed to parse grounding output: %s", e)
        return [{"is_grounded": False, "confidence": 0.0, "issues": [str(e)]}] * len(claims)
