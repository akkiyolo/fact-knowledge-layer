"""
Node: extract_claims
Calls LLM to extract atomic claims from each chunk.
This is a dedicated LLM stage — NOT combined with relation classification.
"""

import json
import logging
import uuid
from pathlib import Path

from app.pipeline.state import PipelineState, ClaimData, ChunkData
from app.services.llm_service import get_llm_service
from app.schemas.llm_outputs import ExtractionOutput, ExtractedClaim
from app.config import get_settings

logger = logging.getLogger(__name__)

# Load prompt template
_PROMPT_PATH = Path(__file__).parent.parent.parent / "prompts" / "extraction.txt"
_PROMPT_TEMPLATE = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""


def extract_claims(state: PipelineState) -> PipelineState:
    """Extract atomic claims from each chunk using LLM."""
    errors = state.get("errors", [])
    warnings = state.get("warnings", [])

    if state.get("is_duplicate"):
        return state

    chunks: list[ChunkData] = state.get("chunks", [])
    if not chunks:
        errors.append({"stage": "extract_claims", "error": "No chunks to process"})
        return {**state, "errors": errors, "status": "failed"}

    settings = get_settings()
    llm = get_llm_service()
    all_claims: list[ClaimData] = []

    for i, chunk in enumerate(chunks):
        try:
            claims = _extract_from_chunk(llm, chunk, settings)
            all_claims.extend(claims)
            logger.info(
                "Chunk %d/%d (page %d): extracted %d claims",
                i + 1, len(chunks), chunk.page_number, len(claims),
            )
        except Exception as e:
            logger.error("Claim extraction failed for chunk %d: %s", i, e)
            errors.append({
                "stage": "extract_claims",
                "error": str(e),
                "chunk_id": chunk.chunk_id,
                "page": chunk.page_number,
            })
            # Continue with other chunks — don't crash the whole pipeline

    logger.info("Total claims extracted: %d from %d chunks", len(all_claims), len(chunks))

    return {
        **state,
        "claims": all_claims,
        "status": "claims_extracted",
        "errors": errors,
        "warnings": warnings,
    }


def _extract_from_chunk(llm, chunk: ChunkData, settings) -> list[ClaimData]:
    """Extract claims from a single chunk."""
    if not chunk.text.strip():
        return []

    # Build prompt
    prompt = _PROMPT_TEMPLATE.format(
        page_number=chunk.page_number,
        char_start=chunk.char_start,
        char_end=chunk.char_end,
        chunk_text=chunk.text,
    )

    system_prompt = (
        "You are a precise fact extraction system. "
        "Extract atomic, verifiable claims from source text. "
        "Return ONLY valid JSON. Do not include any explanation outside the JSON."
    )

    # Call LLM
    raw_response = llm.generate_json(prompt, system_prompt=system_prompt)

    if not raw_response:
        logger.warning("Empty LLM response for chunk (page %d)", chunk.page_number)
        return []

    # Parse through Pydantic schema
    try:
        if isinstance(raw_response, dict):
            output = ExtractionOutput.model_validate(raw_response)
        else:
            return []
    except Exception as e:
        logger.warning("Failed to validate extraction output: %s", e)
        return []

    # Convert to ClaimData
    claims = []
    for extracted in output.claims[:settings.max_claims_per_chunk]:
        claim = _extracted_to_claim_data(extracted, chunk)
        if claim:
            claims.append(claim)

    return claims


def _extracted_to_claim_data(extracted: ExtractedClaim, chunk: ChunkData) -> ClaimData | None:
    """Convert an ExtractedClaim to a ClaimData object."""
    try:
        # Validate evidence exists in chunk
        evidence_text = extracted.evidence.text
        evidence_char_start = chunk.char_start
        evidence_char_end = chunk.char_end

        # Try to find exact evidence location within chunk
        idx = chunk.text.find(evidence_text)
        if idx >= 0:
            evidence_char_start = chunk.char_start + idx
            evidence_char_end = evidence_char_start + len(evidence_text)

        value_str = str(extracted.value.value) if extracted.value.value is not None else ""

        time_scope = None
        if extracted.time_scope:
            time_scope = {
                "text": extracted.time_scope.text,
                "start": extracted.time_scope.start,
                "end": extracted.time_scope.end,
            }

        return ClaimData(
            claim_id=str(uuid.uuid4()),
            chunk_id=chunk.chunk_id,
            entity_text=extracted.entity.text,
            entity_type=extracted.entity.type or "",
            attribute_raw=extracted.attribute_raw,
            value_type=extracted.value.type,
            value=value_str,
            unit=extracted.unit or "",
            time_scope=time_scope,
            scope=extracted.scope or "",
            qualifiers=extracted.qualifiers,
            evidence_text=evidence_text,
            evidence_page=extracted.evidence.page or chunk.page_number,
            evidence_char_start=evidence_char_start,
            evidence_char_end=evidence_char_end,
            extraction_confidence=extracted.confidence,
            status="usable",
        )
    except Exception as e:
        logger.warning("Failed to convert extracted claim: %s", e)
        return None
