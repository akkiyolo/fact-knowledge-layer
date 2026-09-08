"""Pydantic schemas for Claim API and pipeline data."""

from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel


class ClaimResponse(BaseModel):
    id: str
    document_id: str
    chunk_id: str
    entity_text: str
    entity_type: Optional[str] = None
    attribute_raw: str
    attribute_canonical: Optional[str] = None
    value_type: Optional[str] = None
    value: Optional[str] = None
    unit: Optional[str] = None
    time_scope: Optional[dict] = None
    scope: Optional[str] = None
    qualifiers: Optional[list[str]] = None
    evidence_text: Optional[str] = None
    evidence_page: Optional[int] = None
    evidence_char_start: Optional[int] = None
    evidence_char_end: Optional[int] = None
    extraction_confidence: Optional[float] = None
    grounding_confidence: Optional[float] = None
    status: str
    created_at: datetime
    document_filename: Optional[str] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_claim(cls, claim, include_doc_name: bool = False):
        return cls(
            id=claim.id,
            document_id=claim.document_id,
            chunk_id=claim.chunk_id,
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
            created_at=claim.created_at,
            document_filename=claim.document.filename if include_doc_name and claim.document else None,
        )


class ClaimListResponse(BaseModel):
    claims: list[ClaimResponse]
    total: int
