"""Tests for claim extraction schema validation."""

import pytest
from app.schemas.llm_outputs import (
    ExtractionOutput,
    ExtractedClaim,
    EntityOutput,
    ValueOutput,
    TimeScopeOutput,
    EvidenceOutput,
)


def _make_claim(**overrides):
    """Create a valid extracted claim with defaults."""
    base = {
        "entity": {"text": "TestCorp", "type": "company"},
        "attribute_raw": "annual revenue",
        "value": {"type": "number", "value": "1000"},
        "unit": "USD million",
        "time_scope": {"text": "FY2023", "start": "2023-04-01", "end": "2024-03-31"},
        "scope": None,
        "qualifiers": [],
        "evidence": {"text": "TestCorp reported annual revenue of 1000 USD million.", "page": 1, "char_start": 0, "char_end": 50},
        "confidence": 0.85,
    }
    base.update(overrides)
    return base


class TestExtractionSchema:
    def test_valid_extraction_output(self):
        data = {"claims": [_make_claim()]}
        output = ExtractionOutput.model_validate(data)
        assert len(output.claims) == 1
        assert output.claims[0].entity.text == "TestCorp"
        assert output.claims[0].attribute_raw == "annual revenue"

    def test_empty_claims_list(self):
        data = {"claims": []}
        output = ExtractionOutput.model_validate(data)
        assert output.claims == []

    def test_missing_claims_key(self):
        data = {}
        output = ExtractionOutput.model_validate(data)
        assert output.claims == []

    def test_confidence_clamped_high(self):
        claim = _make_claim(confidence=1.5)
        data = {"claims": [claim]}
        output = ExtractionOutput.model_validate(data)
        assert output.claims[0].confidence == 1.0

    def test_confidence_clamped_low(self):
        claim = _make_claim(confidence=-0.5)
        data = {"claims": [claim]}
        output = ExtractionOutput.model_validate(data)
        assert output.claims[0].confidence == 0.0

    def test_open_ended_entity_type(self):
        """Entity type must be open-ended, not restricted."""
        for etype in ["company", "person", "city", "chemical_compound", "satellite"]:
            claim = _make_claim(entity={"text": "X", "type": etype})
            data = {"claims": [claim]}
            output = ExtractionOutput.model_validate(data)
            assert output.claims[0].entity.type == etype

    def test_open_ended_attribute(self):
        """Attribute must be open-ended, not from a fixed list."""
        for attr in ["revenue", "boiling point", "orbital period", "population density"]:
            claim = _make_claim(attribute_raw=attr)
            data = {"claims": [claim]}
            output = ExtractionOutput.model_validate(data)
            assert output.claims[0].attribute_raw == attr

    def test_multiple_value_types(self):
        """Value type must support all defined types."""
        for vtype in ["number", "string", "boolean", "date", "range", "entity", "unknown"]:
            claim = _make_claim(value={"type": vtype, "value": "test"})
            data = {"claims": [claim]}
            output = ExtractionOutput.model_validate(data)
            assert output.claims[0].value.type == vtype

    def test_null_optional_fields(self):
        claim = _make_claim(unit=None, time_scope=None, scope=None, qualifiers=[])
        data = {"claims": [claim]}
        output = ExtractionOutput.model_validate(data)
        assert output.claims[0].unit is None
        assert output.claims[0].time_scope is None

    def test_qualifiers_list(self):
        claim = _make_claim(qualifiers=["consolidated", "audited", "restated"])
        data = {"claims": [claim]}
        output = ExtractionOutput.model_validate(data)
        assert len(output.claims[0].qualifiers) == 3

    def test_evidence_required(self):
        """Evidence text is required."""
        claim = _make_claim()
        claim["evidence"]["text"] = "Actual evidence text"
        data = {"claims": [claim]}
        output = ExtractionOutput.model_validate(data)
        assert output.claims[0].evidence.text == "Actual evidence text"

    def test_multiple_claims(self):
        data = {"claims": [_make_claim(), _make_claim(attribute_raw="employee count")]}
        output = ExtractionOutput.model_validate(data)
        assert len(output.claims) == 2
