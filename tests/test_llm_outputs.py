"""Tests for the LLM output validation schemas."""

import pytest
from app.schemas.llm_outputs import (
    ExtractionOutput,
    GroundingResult,
    ClassificationResult,
    ReconciliationResult,
)


def test_extraction_output_validation():
    """Test valid extraction JSON parsing with confidence clamping."""
    data = {
        "claims": [
            {
                "entity": {"text": "Acme Corp", "type": "company"},
                "attribute_raw": "annual revenue",
                "value": {"type": "number", "value": "1000"},
                "unit": "USD million",
                "time_scope": {"text": "FY2023", "start": "2023-04-01", "end": "2024-03-31"},
                "scope": "Global",
                "qualifiers": ["audited"],
                "evidence": {"text": "Acme Corp reported $1B revenue.", "page": 1, "char_start": 0, "char_end": 30},
                "confidence": 1.5,  # Should be clamped to 1.0
            }
        ]
    }
    result = ExtractionOutput.model_validate(data)
    assert len(result.claims) == 1
    assert result.claims[0].entity.text == "Acme Corp"
    assert result.claims[0].confidence == 1.0  # Clamped


def test_grounding_output_validation():
    """Test grounding validation with proper clamping."""
    data = {
        "is_grounded": True,
        "issues": ["Explicitly stated in the text."],
        "confidence": -0.5,  # Should be clamped to 0.0
    }
    result = GroundingResult.model_validate(data)
    assert result.is_grounded is True
    assert result.confidence == 0.0  # Clamped


def test_classification_output_validation():
    """Test relation classification validation."""
    data = {
        "relation": "corroborates",
        "explanation": "Both sources confirm the same revenue.",
        "reasoning_factors": ["Same entity", "Same value", "Same time scope"],
        "confidence": 0.95,
    }
    result = ClassificationResult.model_validate(data)
    assert result.relation == "corroborates"
    assert len(result.reasoning_factors) == 3


def test_reconciliation_result_validation():
    """Test reconciliation result validation."""
    data = {
        "reconciled": True,
        "reconciling_factor": "Different accounting standards (GAAP vs IFRS)",
        "explanation": "Source A uses GAAP while Source B uses IFRS, explaining the difference in reported revenue.",
        "confidence": 0.88,
    }
    result = ReconciliationResult.model_validate(data)
    assert result.reconciled is True
    assert result.reconciling_factor == "Different accounting standards (GAAP vs IFRS)"
