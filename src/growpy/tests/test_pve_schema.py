"""Tests for growpy.io.pve_schema module."""

import pytest

from growpy.io.pve_schema import create_empty_pve_preset, get_pve_schema


class TestGetPveSchema:
    """Tests for PVE schema structure."""

    def test_has_global_attributes(self):
        schema = get_pve_schema()
        assert "globalAttributes" in schema

    def test_has_points_section(self):
        schema = get_pve_schema()
        assert "points" in schema
        assert "attributes" in schema["points"]
        assert "positions" in schema["points"]

    def test_has_primitives_section(self):
        schema = get_pve_schema()
        assert "primitives" in schema
        assert "attributes" in schema["primitives"]

    def test_global_attribute_types(self):
        schema = get_pve_schema()
        ga = schema["globalAttributes"]
        assert ga["cycle"]["type"] == "int"
        assert ga["cycleTime"]["type"] == "float"
        assert ga["randomSeed"]["type"] == "int"

    def test_array_attributes_have_isarray_true(self):
        schema = get_pve_schema()
        ga = schema["globalAttributes"]
        assert ga["axialElongation"]["isArray"] is True
        assert ga["lateralElongation"]["isArray"] is True

    def test_scalar_attributes_have_isarray_false(self):
        schema = get_pve_schema()
        ga = schema["globalAttributes"]
        assert ga["cycle"]["isArray"] is False
        assert ga["gravitationalForce"]["isArray"] is False

    def test_plant_profiles_present(self):
        schema = get_pve_schema()
        ga = schema["globalAttributes"]
        for i in range(1, 6):
            assert f"plantProfile_{i}" in ga

    def test_point_attributes_include_position(self):
        schema = get_pve_schema()
        pa = schema["points"]["attributes"]
        assert "P" in pa
        assert pa["P"]["size"] == 3

    def test_primitive_attributes_include_hierarchy(self):
        schema = get_pve_schema()
        pa = schema["primitives"]["attributes"]
        assert "branchGeneration" in pa
        assert "branchParentNumber" in pa
        assert "children" in pa
        assert "parents" in pa


class TestCreateEmptyPvePreset:
    """Tests for empty PVE preset creation."""

    def test_has_all_sections(self):
        preset = create_empty_pve_preset()
        assert "globalAttributes" in preset
        assert "points" in preset
        assert "primitives" in preset

    def test_global_attributes_have_values(self):
        preset = create_empty_pve_preset()
        ga = preset["globalAttributes"]
        assert "cycle" in ga
        assert "value" in ga["cycle"]

    def test_array_attributes_have_empty_list(self):
        preset = create_empty_pve_preset()
        ga = preset["globalAttributes"]
        assert ga["axialElongation"]["value"] == []

    def test_scalar_int_attributes_default_zero(self):
        preset = create_empty_pve_preset()
        ga = preset["globalAttributes"]
        assert ga["cycle"]["value"] == 0

    def test_scalar_float_attributes_default_zero(self):
        preset = create_empty_pve_preset()
        ga = preset["globalAttributes"]
        assert ga["gravitationalForce"]["value"] == 0

    def test_point_attributes_have_empty_values(self):
        preset = create_empty_pve_preset()
        pa = preset["points"]["attributes"]
        assert pa["P"]["values"] == []

    def test_primitive_attributes_have_empty_values(self):
        preset = create_empty_pve_preset()
        pa = preset["primitives"]["attributes"]
        assert pa["branchGeneration"]["values"] == []

    def test_positions_empty(self):
        preset = create_empty_pve_preset()
        assert preset["points"]["positions"] == []
