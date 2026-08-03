"""Tests for growpy.io.helios.classification (Helios++ point-cloud labeling)."""

import json

import pytest

from growpy.io.helios.classification import (
    MAX_TREES,
    build_classification_codes,
    build_material_prefix,
    compute_classification_code,
    validate_classification_fids,
    validate_classification_materials,
    validate_classification_species,
)


class TestComputeClassificationCode:
    """Tests for the 2-digit [material][fid] code."""

    def test_leaf_code(self):
        assert compute_classification_code("leaf", 3) == 13

    def test_wood_code(self):
        assert compute_classification_code("wood", 3) == 23

    def test_bark_code(self):
        assert compute_classification_code("bark", 3) == 23

    def test_fruit_code(self):
        assert compute_classification_code("fruit", 3) == 23

    def test_fid_zero_raises(self):
        with pytest.raises(ValueError):
            compute_classification_code("leaf", 0)

    def test_fid_above_max_raises(self):
        with pytest.raises(ValueError):
            compute_classification_code("leaf", MAX_TREES + 1)

    def test_all_codes_within_las_range(self):
        for fid in range(1, MAX_TREES + 1):
            for material_class in ("leaf", "wood", "bark", "fruit"):
                code = compute_classification_code(material_class, fid)
                assert 11 <= code <= 29


class TestBuildClassificationCodes:
    def test_returns_all_material_classes(self):
        codes = build_classification_codes(3)
        assert codes == {"leaf": 13, "wood": 23, "bark": 23, "fruit": 23}


class TestBuildMaterialPrefix:
    def test_zero_padded_two_digit(self):
        assert build_material_prefix(3) == "t03_"

    def test_double_digit_fid(self):
        assert build_material_prefix(12) == "t12_"


class TestValidateClassificationSpecies:
    def test_supported_species_returns_no_errors(self):
        assert validate_classification_species(["selected_european_beech"]) == []

    def test_unsupported_species_returns_one_error_naming_it(self):
        errors = validate_classification_species(["not_a_real_species"])
        assert len(errors) == 1
        assert "not_a_real_species" in errors[0]

    def test_mixed_supported_and_unsupported(self):
        errors = validate_classification_species(
            ["selected_european_beech", "bogus_species"]
        )
        assert len(errors) == 1
        assert "bogus_species" in errors[0]


class TestValidateClassificationFids:
    def test_within_range_no_errors_no_warnings(self):
        errors, warnings = validate_classification_fids(list(range(1, MAX_TREES + 1)))
        assert errors == []
        assert warnings == []

    def test_zero_fid_is_error(self):
        errors, warnings = validate_classification_fids([0])
        assert len(errors) == 1
        assert "0" in errors[0]

    def test_negative_fid_is_error(self):
        errors, warnings = validate_classification_fids([-1])
        assert len(errors) == 1

    def test_above_max_trees_warns_not_errors(self):
        errors, warnings = validate_classification_fids(list(range(1, 48)))
        assert errors == []
        assert len(warnings) == 1
        assert "47 trees" in warnings[0]
        assert str(MAX_TREES) in warnings[0]

    def test_below_max_trees_no_warning(self):
        errors, warnings = validate_classification_fids(list(range(1, MAX_TREES + 1)))
        assert warnings == []


class TestValidateClassificationMaterials:
    def test_missing_twig_dir_returns_error(self, tmp_path):
        errors = validate_classification_materials(
            "selected_european_beech", tmp_path / "does_not_exist"
        )
        assert len(errors) == 1
        assert "not found" in errors[0].lower()

    def test_no_sidecar_files_returns_error(self, tmp_path):
        errors = validate_classification_materials("selected_european_beech", tmp_path)
        assert len(errors) == 1
        assert "face_materials.json" in errors[0]

    def test_has_leaf_and_wood_returns_no_errors(self, tmp_path):
        sidecar = tmp_path / "twig_a_face_materials.json"
        sidecar.write_text(json.dumps({"materials": ["bark", "leaf_top"]}))

        errors = validate_classification_materials("selected_european_beech", tmp_path)
        assert errors == []

    def test_missing_leaf_material_is_error(self, tmp_path):
        sidecar = tmp_path / "twig_a_face_materials.json"
        sidecar.write_text(json.dumps({"materials": ["bark", "twig_wood"]}))

        errors = validate_classification_materials("selected_european_beech", tmp_path)
        assert len(errors) == 1
        assert "leaf" in errors[0]

    def test_missing_wood_material_is_error(self, tmp_path):
        sidecar = tmp_path / "twig_a_face_materials.json"
        sidecar.write_text(json.dumps({"materials": ["leaf_top", "leaf_bottom"]}))

        errors = validate_classification_materials("selected_european_beech", tmp_path)
        assert len(errors) == 1
        assert "twig (wood)" in errors[0]
