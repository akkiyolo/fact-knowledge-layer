"""
Repository pattern for database operations.
Provides clean data access methods for documents, claims, and relations.
"""

import logging
from typing import Optional
from sqlalchemy import text, select, func
from sqlalchemy.orm import Session, joinedload

from app.db.models import Document, Chunk, Claim, Relation
from app.config import get_settings

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Data access for Document entities."""

    def __init__(self, session: Session):
        self.session = session

    def find_by_content_hash(self, content_hash: str) -> Optional[Document]:
        return self.session.query(Document).filter(
            Document.content_hash == content_hash
        ).first()

    def create(self, **kwargs) -> Document:
        doc = Document(**kwargs)
        self.session.add(doc)
        self.session.flush()
        return doc

    def get_by_id(self, doc_id: str) -> Optional[Document]:
        return self.session.query(Document).filter(Document.id == doc_id).first()

    def list_all(self, skip: int = 0, limit: int = 100) -> list[Document]:
        return (
            self.session.query(Document)
            .order_by(Document.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )

    def update_status(self, doc_id: str, status: str):
        doc = self.get_by_id(doc_id)
        if doc:
            doc.status = status
            self.session.flush()


class ChunkRepository:
    """Data access for Chunk entities."""

    def __init__(self, session: Session):
        self.session = session

    def bulk_create(self, chunks: list[dict]) -> list[Chunk]:
        chunk_objs = [Chunk(**c) for c in chunks]
        self.session.add_all(chunk_objs)
        self.session.flush()
        return chunk_objs

    def get_by_document(self, doc_id: str) -> list[Chunk]:
        return (
            self.session.query(Chunk)
            .filter(Chunk.document_id == doc_id)
            .order_by(Chunk.page_number, Chunk.char_start)
            .all()
        )


class ClaimRepository:
    """Data access for Claim entities."""

    def __init__(self, session: Session):
        self.session = session

    def bulk_create(self, claims: list[dict]) -> list[Claim]:
        claim_objs = [Claim(**c) for c in claims]
        self.session.add_all(claim_objs)
        self.session.flush()
        return claim_objs

    def create(self, **kwargs) -> Claim:
        claim = Claim(**kwargs)
        self.session.add(claim)
        self.session.flush()
        return claim

    def get_by_id(self, claim_id: str) -> Optional[Claim]:
        return self.session.query(Claim).filter(Claim.id == claim_id).first()

    def get_by_document(
        self,
        doc_id: str,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 500,
    ) -> list[Claim]:
        q = self.session.query(Claim).filter(Claim.document_id == doc_id)
        if status:
            q = q.filter(Claim.status == status)
        return q.order_by(Claim.evidence_page, Claim.evidence_char_start).offset(skip).limit(limit).all()

    def list_all(
        self,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 500,
    ) -> list[Claim]:
        q = self.session.query(Claim)
        if status:
            q = q.filter(Claim.status == status)
        return q.order_by(Claim.created_at.desc()).offset(skip).limit(limit).all()

    def find_similar_existing(
        self,
        embedding: list[float],
        exclude_document_id: str,
        top_k: int = 10,
        similarity_threshold: float = 0.70,
    ) -> list[tuple[Claim, float]]:
        """
        Find top-k semantically similar EXISTING claims (from other documents).
        Uses pgvector cosine distance. Returns (claim, similarity_score) pairs.
        """
        settings = get_settings()

        # pgvector cosine distance: <=> operator returns distance (0 = identical)
        # similarity = 1 - distance
        embedding_str = f"[{','.join(str(x) for x in embedding)}]"
        distance_threshold = 1.0 - similarity_threshold

        stmt = (
            select(
                Claim,
                (1 - Claim.embedding.cosine_distance(embedding_str)).label("similarity"),
            )
            .where(Claim.document_id != exclude_document_id)
            .where(Claim.status == "usable")
            .where(Claim.embedding.isnot(None))
            .where(
                (1 - Claim.embedding.cosine_distance(embedding_str)) >= similarity_threshold
            )
            .order_by(Claim.embedding.cosine_distance(embedding_str))
            .limit(top_k)
        )

        results = self.session.execute(stmt).all()
        return [(row[0], float(row[1])) for row in results]

    def get_canonical_attributes(self) -> list[str]:
        """Get all distinct canonical attributes."""
        results = (
            self.session.query(Claim.attribute_canonical)
            .filter(Claim.attribute_canonical.isnot(None))
            .distinct()
            .all()
        )
        return [r[0] for r in results]

    def update_embedding(self, claim_id: str, embedding: list[float]):
        claim = self.get_by_id(claim_id)
        if claim:
            claim.embedding = embedding
            self.session.flush()


class RelationRepository:
    """Data access for Relation entities."""

    def __init__(self, session: Session):
        self.session = session

    def create(self, **kwargs) -> Relation:
        rel = Relation(**kwargs)
        self.session.add(rel)
        self.session.flush()
        return rel

    def bulk_create(self, relations: list[dict]) -> list[Relation]:
        rel_objs = [Relation(**r) for r in relations]
        self.session.add_all(rel_objs)
        self.session.flush()
        return rel_objs

    def get_by_claim(self, claim_id: str) -> list[Relation]:
        return (
            self.session.query(Relation)
            .filter(
                (Relation.source_claim_id == claim_id)
                | (Relation.target_claim_id == claim_id)
            )
            .order_by(Relation.created_at.desc())
            .all()
        )

    def list_all(
        self,
        relation_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 500,
    ) -> list[Relation]:
        q = self.session.query(Relation)
        if relation_type:
            q = q.filter(Relation.relation_type == relation_type)
        return q.order_by(Relation.created_at.desc()).offset(skip).limit(limit).all()
