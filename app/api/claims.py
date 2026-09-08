"""
Claims API endpoints.
"""

from fastapi import APIRouter, HTTPException, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repositories import ClaimRepository, RelationRepository
from app.schemas.claim import ClaimResponse, ClaimListResponse
from app.schemas.relation import RelationResponse, RelationListResponse

router = APIRouter(prefix="/api/claims", tags=["claims"])


@router.get("", response_model=ClaimListResponse)
def list_claims(
    status: str = None,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    """List all claims with optional filtering."""
    claim_repo = ClaimRepository(db)
    claims = claim_repo.list_all(status=status, skip=skip, limit=limit)
    return ClaimListResponse(
        claims=[ClaimResponse.from_orm_claim(c, include_doc_name=True) for c in claims],
        total=len(claims),
    )


@router.get("/{claim_id}", response_model=ClaimResponse)
def get_claim(
    claim_id: str,
    db: Session = Depends(get_db),
):
    """Get a specific claim by ID."""
    claim_repo = ClaimRepository(db)
    claim = claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return ClaimResponse.from_orm_claim(claim, include_doc_name=True)


@router.get("/{claim_id}/relations", response_model=RelationListResponse)
def get_claim_relations(
    claim_id: str,
    db: Session = Depends(get_db),
):
    """Get all relations involving a specific claim."""
    claim_repo = ClaimRepository(db)
    claim = claim_repo.get_by_id(claim_id)
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    rel_repo = RelationRepository(db)
    relations = rel_repo.get_by_claim(claim_id)

    return RelationListResponse(
        relations=[RelationResponse.from_orm_relation(r, include_claims=True) for r in relations],
        total=len(relations),
    )
