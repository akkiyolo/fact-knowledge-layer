"""Pydantic schemas for Relation API."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel

from app.schemas.claim import ClaimResponse


class RelationResponse(BaseModel):
    id: str
    source_claim_id: str
    target_claim_id: str
    relation_type: str
    confidence: Optional[float] = None
    explanation: Optional[str] = None
    reasoning_factors: Optional[list[str]] = None
    reconciling_factor: Optional[str] = None
    reconciliation_explanation: Optional[str] = None
    created_at: datetime

    # Optionally include full claim details
    source_claim: Optional[ClaimResponse] = None
    target_claim: Optional[ClaimResponse] = None

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_relation(cls, rel, include_claims: bool = False):
        source = None
        target = None
        if include_claims:
            if rel.source_claim:
                source = ClaimResponse.from_orm_claim(rel.source_claim, include_doc_name=True)
            if rel.target_claim:
                target = ClaimResponse.from_orm_claim(rel.target_claim, include_doc_name=True)

        return cls(
            id=rel.id,
            source_claim_id=rel.source_claim_id,
            target_claim_id=rel.target_claim_id,
            relation_type=rel.relation_type,
            confidence=rel.confidence,
            explanation=rel.explanation,
            reasoning_factors=rel.reasoning_factors,
            reconciling_factor=rel.reconciling_factor,
            reconciliation_explanation=rel.reconciliation_explanation,
            created_at=rel.created_at,
            source_claim=source,
            target_claim=target,
        )


class RelationListResponse(BaseModel):
    relations: list[RelationResponse]
    total: int
