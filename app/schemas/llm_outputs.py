"""
Pydantic models for validating LLM JSON outputs.
Catches malformed responses safely without crashing the pipeline.
"""

from typing import Optional, Any
from pydantic import BaseModel, Field, field_validator


# ── Extraction Output ────────────────────────────────────────

class EntityOutput(BaseModel):
    text: str
    type: Optional[str] = None


class ValueOutput(BaseModel):
    type: str = "unknown"  # number, string, boolean, date, range, entity, unknown
    value: Any = None


class TimeScopeOutput(BaseModel):
    text: Optional[str] = None
    start: Optional[str] = None
    end: Optional[str] = None


class EvidenceOutput(BaseModel):
    text: str
    page: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None


class ExtractedClaim(BaseModel):
    entity: EntityOutput
    attribute_raw: str
    value: ValueOutput
    unit: Optional[str] = None
    time_scope: Optional[TimeScopeOutput] = None
    scope: Optional[str] = None
    qualifiers: list[str] = Field(default_factory=list)
    evidence: EvidenceOutput
    confidence: float = 0.0

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v):
        return max(0.0, min(1.0, float(v)))


class ExtractionOutput(BaseModel):
    """Top-level extraction output from LLM."""
    claims: list[ExtractedClaim] = Field(default_factory=list)


# ── Grounding Output ────────────────────────────────────────

class GroundingResult(BaseModel):
    """Result of grounding validation for a single claim."""
    is_grounded: bool = False
    confidence: float = 0.0
    issues: list[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v):
        return max(0.0, min(1.0, float(v)))


class GroundingOutput(BaseModel):
    """Grounding validation results."""
    results: list[GroundingResult] = Field(default_factory=list)


# ── Classification Output ───────────────────────────────────

class ClassificationResult(BaseModel):
    """Relation classification for a candidate pair."""
    relation: str = "neutral"  # corroborates, contradicts, neutral
    confidence: float = 0.0
    explanation: str = ""
    reasoning_factors: list[str] = Field(default_factory=list)

    @field_validator("relation")
    @classmethod
    def validate_relation(cls, v):
        allowed = {"corroborates", "contradicts", "neutral"}
        if v not in allowed:
            return "neutral"
        return v

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v):
        return max(0.0, min(1.0, float(v)))


# ── Reconciliation Output ───────────────────────────────────

class ReconciliationResult(BaseModel):
    """Result of contradiction reconciliation."""
    reconciled: bool = False
    reconciling_factor: Optional[str] = None
    explanation: str = ""
    confidence: float = 0.0

    @field_validator("confidence")
    @classmethod
    def clamp_confidence(cls, v):
        return max(0.0, min(1.0, float(v)))
