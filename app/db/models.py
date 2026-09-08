"""
SQLAlchemy ORM models for the Fact Knowledge Layer.
Uses pgvector for claim embedding storage.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    String,
    Integer,
    Float,
    Text,
    DateTime,
    ForeignKey,
    Index,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector

from app.config import get_settings
from app.db.database import Base


def _now():
    return datetime.now(timezone.utc)


def _uuid():
    return str(uuid.uuid4())


class Document(Base):
    __tablename__ = "documents"

    id = Column(String(36), primary_key=True, default=_uuid)
    filename = Column(String(512), nullable=False)
    content_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)
    page_count = Column(Integer, nullable=True)
    status = Column(String(32), default="processing", nullable=False)

    # Relationships
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="document", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Document(id={self.id}, filename={self.filename})>"


class Chunk(Base):
    __tablename__ = "chunks"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number = Column(Integer, nullable=False)
    char_start = Column(Integer, nullable=False)
    char_end = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    metadata_ = Column("metadata", JSONB, default=dict)

    # Relationships
    document = relationship("Document", back_populates="chunks")
    claims = relationship("Claim", back_populates="chunk", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Chunk(id={self.id}, page={self.page_number})>"


class Claim(Base):
    __tablename__ = "claims"

    id = Column(String(36), primary_key=True, default=_uuid)
    document_id = Column(String(36), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True)
    chunk_id = Column(String(36), ForeignKey("chunks.id", ondelete="CASCADE"), nullable=False, index=True)

    # Entity
    entity_text = Column(String(1024), nullable=False)
    entity_type = Column(String(256), nullable=True)

    # Attribute
    attribute_raw = Column(String(1024), nullable=False)
    attribute_canonical = Column(String(1024), nullable=True)

    # Value
    value_type = Column(String(64), nullable=True)  # number, string, boolean, date, range, entity, unknown
    value = Column(Text, nullable=True)
    unit = Column(String(256), nullable=True)

    # Temporal / Scope
    time_scope = Column(JSONB, nullable=True)  # {text, start, end}
    scope = Column(Text, nullable=True)
    qualifiers = Column(JSONB, default=list)

    # Evidence / Grounding
    evidence_text = Column(Text, nullable=True)
    evidence_page = Column(Integer, nullable=True)
    evidence_char_start = Column(Integer, nullable=True)
    evidence_char_end = Column(Integer, nullable=True)

    # Confidence
    extraction_confidence = Column(Float, nullable=True)
    grounding_confidence = Column(Float, nullable=True)

    # Status: usable, unresolved
    status = Column(String(32), default="usable", nullable=False)

    # Embedding (pgvector)
    embedding = Column(Vector(get_settings().embedding_dimension), nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    # Relationships
    document = relationship("Document", back_populates="claims")
    chunk = relationship("Chunk", back_populates="claims")

    source_relations = relationship(
        "Relation",
        foreign_keys="Relation.source_claim_id",
        back_populates="source_claim",
        cascade="all, delete-orphan",
    )
    target_relations = relationship(
        "Relation",
        foreign_keys="Relation.target_claim_id",
        back_populates="target_claim",
        cascade="all, delete-orphan",
    )

    def __repr__(self):
        return f"<Claim(id={self.id}, entity={self.entity_text}, attr={self.attribute_raw})>"


class Relation(Base):
    __tablename__ = "relations"

    id = Column(String(36), primary_key=True, default=_uuid)
    source_claim_id = Column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)
    target_claim_id = Column(String(36), ForeignKey("claims.id", ondelete="CASCADE"), nullable=False, index=True)

    # corroborates, contradicts, neutral, contradicts_reconciled
    relation_type = Column(String(64), nullable=False)
    confidence = Column(Float, nullable=True)
    explanation = Column(Text, nullable=True)
    reasoning_factors = Column(JSONB, default=list)

    # Reconciliation (only for contradicts / contradicts_reconciled)
    reconciling_factor = Column(String(256), nullable=True)
    reconciliation_explanation = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_now, nullable=False)

    # Relationships
    source_claim = relationship("Claim", foreign_keys=[source_claim_id], back_populates="source_relations")
    target_claim = relationship("Claim", foreign_keys=[target_claim_id], back_populates="target_relations")

    def __repr__(self):
        return f"<Relation(id={self.id}, type={self.relation_type})>"


# ── Indexes ──────────────────────────────────────────────────

Index("ix_claims_status", Claim.status)
Index("ix_claims_entity_text", Claim.entity_text)
Index("ix_claims_attribute_canonical", Claim.attribute_canonical)
Index("ix_relations_type", Relation.relation_type)
