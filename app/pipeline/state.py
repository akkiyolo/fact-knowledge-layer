"""
Pipeline state definition.
Explicit, typed state flowing through the LangGraph pipeline.
"""

from typing import TypedDict, Optional, Any
from dataclasses import dataclass, field


@dataclass
class ChunkData:
    """A text chunk with page and offset metadata."""
    chunk_id: str = ""
    page_number: int = 0
    char_start: int = 0
    char_end: int = 0
    text: str = ""
    metadata: dict = field(default_factory=dict)


@dataclass
class ClaimData:
    """An extracted claim with all associated data."""
    claim_id: str = ""
    chunk_id: str = ""

    # Entity
    entity_text: str = ""
    entity_type: str = ""

    # Attribute
    attribute_raw: str = ""
    attribute_canonical: str = ""

    # Value
    value_type: str = "unknown"
    value: str = ""
    unit: str = ""

    # Temporal / Scope
    time_scope: Optional[dict] = None
    scope: str = ""
    qualifiers: list = field(default_factory=list)

    # Evidence
    evidence_text: str = ""
    evidence_page: int = 0
    evidence_char_start: int = 0
    evidence_char_end: int = 0

    # Confidence
    extraction_confidence: float = 0.0
    grounding_confidence: float = 0.0

    # Status
    status: str = "usable"

    # Embedding
    embedding: Optional[list[float]] = None


@dataclass
class CandidatePair:
    """A pair of claims for relation classification."""
    new_claim: ClaimData = field(default_factory=ClaimData)
    existing_claim_id: str = ""
    existing_claim_data: dict = field(default_factory=dict)
    similarity_score: float = 0.0


@dataclass
class RelationData:
    """A classified relation between two claims."""
    source_claim_id: str = ""
    target_claim_id: str = ""
    relation_type: str = "neutral"
    confidence: float = 0.0
    explanation: str = ""
    reasoning_factors: list = field(default_factory=list)
    reconciling_factor: Optional[str] = None
    reconciliation_explanation: Optional[str] = None


class PipelineState(TypedDict, total=False):
    """Typed state for the LangGraph pipeline."""

    # Input
    file_path: str
    file_content: bytes
    filename: str

    # Document
    document_id: str
    content_hash: str
    is_duplicate: bool
    existing_document_id: str

    # PDF content
    full_text: str
    page_count: int
    pages: list  # list of PageContent

    # Chunks
    chunks: list  # list of ChunkData

    # Claims
    claims: list  # list of ClaimData

    # Candidates
    candidates: list  # list of CandidatePair

    # Relations
    relations: list  # list of RelationData

    # Error tracking
    errors: list  # list of error dicts
    warnings: list

    # Status
    status: str
