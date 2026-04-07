"""Tests for growpy.io.unreal.pve_grove_mapper template creation."""

import json

import pytest

from growpy.io.unreal.pve_grove_mapper import (
    _create_empty_global_attributes,
    _create_empty_point_attributes,
    _create_empty_primitive_attributes,
    create_pve_template_from_reference,
)

SAMPLE_REFERENCE = {
    "globalAttributes": {
        "height": {"isArray": False, "size": 1, "type": "float", "value": 12.5},
        "tags": {"isArray": True, "size": 3, "type": "string", "value": ["a", "b", "c"]},
    },
    "points": {
        "attributes": {
            "P": {"isArray": False, "size": 3, "type": "float", "values": [1, 2, 3]},
            "radius": {"isArray": False, "size": 1, "type": "float", "value": [0.1]},
        },
        "positions": [[0, 0, 0], [1, 1, 1]],
    },
    "primitives": {
        "attributes": {
            "depth": {"isArray": False, "size": 1, "type": "int", "values": [0, 1]},
            "branch_id": {"isArray": False, "size": 1, "type": "int", "value": [10]},
        },
        "points": [[0, 1], [1, 2]],
    },
}


class TestCreateEmptyGlobalAttributes:
    """Tests for global attributes template creation."""

    def test_preserves_keys(self):
        result = _create_empty_global_attributes(SAMPLE_REFERENCE["globalAttributes"])
        assert "height" in result
        assert "tags" in result

    def test_preserves_types(self):
        result = _create_empty_global_attributes(SAMPLE_REFERENCE["globalAttributes"])
        assert result["height"]["type"] == "float"
        assert result["tags"]["type"] == "string"

    def test_clears_scalar_value(self):
        result = _create_empty_global_attributes(SAMPLE_REFERENCE["globalAttributes"])
        assert result["height"]["value"] == 0

    def test_clears_array_value(self):
        result = _create_empty_global_attributes(SAMPLE_REFERENCE["globalAttributes"])
        assert result["tags"]["value"] == []


class TestCreateEmptyPointAttributes:
    """Tests for point attributes template creation."""

    def test_preserves_values_key(self):
        result = _create_empty_point_attributes(SAMPLE_REFERENCE["points"]["attributes"])
        assert "values" in result["P"]

    def test_preserves_value_key(self):
        result = _create_empty_point_attributes(SAMPLE_REFERENCE["points"]["attributes"])
        assert "value" in result["radius"]

    def test_clears_data(self):
        result = _create_empty_point_attributes(SAMPLE_REFERENCE["points"]["attributes"])
        assert result["P"]["values"] == []
        assert result["radius"]["value"] == []

    def test_preserves_size(self):
        result = _create_empty_point_attributes(SAMPLE_REFERENCE["points"]["attributes"])
        assert result["P"]["size"] == 3
        assert result["radius"]["size"] == 1


class TestCreateEmptyPrimitiveAttributes:
    """Tests for primitive attributes template creation."""

    def test_preserves_values_key(self):
        result = _create_empty_primitive_attributes(SAMPLE_REFERENCE["primitives"]["attributes"])
        assert "values" in result["depth"]

    def test_preserves_value_key(self):
        result = _create_empty_primitive_attributes(SAMPLE_REFERENCE["primitives"]["attributes"])
        assert "value" in result["branch_id"]

    def test_clears_data(self):
        result = _create_empty_primitive_attributes(SAMPLE_REFERENCE["primitives"]["attributes"])
        assert result["depth"]["values"] == []


class TestCreatePveTemplateFromReference:
    """Tests for full PVE template creation from reference JSON."""

    def test_creates_template(self, tmp_path):
        ref_path = tmp_path / "reference.json"
        ref_path.write_text(json.dumps(SAMPLE_REFERENCE))
        template = create_pve_template_from_reference(ref_path)
        assert "globalAttributes" in template
        assert "points" in template
        assert "primitives" in template

    def test_clears_positions(self, tmp_path):
        ref_path = tmp_path / "reference.json"
        ref_path.write_text(json.dumps(SAMPLE_REFERENCE))
        template = create_pve_template_from_reference(ref_path)
        assert template["points"]["positions"] == []

    def test_clears_primitive_points(self, tmp_path):
        ref_path = tmp_path / "reference.json"
        ref_path.write_text(json.dumps(SAMPLE_REFERENCE))
        template = create_pve_template_from_reference(ref_path)
        assert template["primitives"]["points"] == []
