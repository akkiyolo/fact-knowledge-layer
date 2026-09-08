"""
Relations API endpoints.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.repositories import RelationRepository
from app.schemas.relation import RelationResponse, RelationListResponse

router = APIRouter(prefix="/api/relations", tags=["relations"])


@router.get("", response_model=RelationListResponse)
def list_relations(
    relation_type: str = None,
    skip: int = 0,
    limit: int = 500,
    db: Session = Depends(get_db),
):
    """List all relations with optional filtering by type."""
    rel_repo = RelationRepository(db)
    relations = rel_repo.list_all(
        relation_type=relation_type,
        skip=skip,
        limit=limit,
    )
    return RelationListResponse(
        relations=[
            RelationResponse.from_orm_relation(r, include_claims=True)
            for r in relations
        ],
        total=len(relations),
    )
