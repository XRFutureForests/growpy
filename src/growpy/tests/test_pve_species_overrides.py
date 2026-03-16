"""Tests for growpy.config.pve_species_overrides module."""

import json

import pytest

from growpy.config.pve_species_overrides import (
    apply_species_overrides,
    create_example_pve_config,
    create_null_placeholder_config,
    load_species_pve_config,
)


class TestLoadSpeciesPveConfig:
    """Tests for load_species_pve_config."""

    def test_loads_from_config_dir(self, tmp_path):
        config = {"globalAttributes": {"cycle": {"value": 10}}}
        config_file = tmp_path / "european_beech_pve.json"
        config_file.write_text(json.dumps(config))
        result = load_species_pve_config("European beech", config_dir=tmp_path)
        assert result is not None
        assert result["globalAttributes"]["cycle"]["value"] == 10

    def test_normalizes_species_name(self, tmp_path):
        config_file = tmp_path / "norway_spruce_pve.json"
        config_file.write_text(json.dumps({"test": True}))
        result = load_species_pve_config("Norway Spruce", config_dir=tmp_path)
        assert result is not None
        assert result["test"] is True

    def test_returns_none_when_not_found(self, tmp_path):
        result = load_species_pve_config("nonexistent", config_dir=tmp_path)
        assert result is None

    def test_returns_none_with_no_config_dir(self):
        result = load_species_pve_config("nonexistent_species_xyz")
        assert result is None


class TestCreateExamplePveConfig:
    """Tests for create_example_pve_config."""

    def test_creates_file(self, tmp_path):
        output = tmp_path / "example_pve.json"
        create_example_pve_config(output, "test_species")
        assert output.exists()

    def test_valid_json(self, tmp_path):
        output = tmp_path / "example_pve.json"
        create_example_pve_config(output, "test_species")
        data = json.loads(output.read_text())
        assert "globalAttributes" in data
        assert "plantProfile_1" in data["globalAttributes"]

    def test_creates_parent_dirs(self, tmp_path):
        output = tmp_path / "subdir" / "deep" / "config.json"
        create_example_pve_config(output, "species")
        assert output.exists()


class TestApplySpeciesOverrides:
    """Tests for apply_species_overrides."""

    def _make_preset(self):
        return {
            "globalAttributes": {
                "cycle": {"isArray": False, "size": 1, "type": "int", "value": 5},
                "maxBranchNumber": {
                    "isArray": False,
                    "size": 1,
                    "type": "int",
                    "value": 10,
                },
            }
        }

    def test_no_config_returns_unchanged(self, tmp_path):
        preset = self._make_preset()
        result = apply_species_overrides(preset, "nonexistent", config_dir=tmp_path)
        assert result["globalAttributes"]["cycle"]["value"] == 5

    def test_override_replaces_value(self, tmp_path):
        config = {
            "globalAttributes": {
                "cycle": {"isArray": False, "size": 1, "type": "int", "value": 20},
            }
        }
        (tmp_path / "test_species_pve.json").write_text(json.dumps(config))
        preset = self._make_preset()
        result = apply_species_overrides(preset, "test_species", config_dir=tmp_path)
        assert result["globalAttributes"]["cycle"]["value"] == 20

    def test_null_value_skipped(self, tmp_path):
        config = {
            "globalAttributes": {
                "cycle": {"isArray": False, "size": 1, "type": "int", "value": None},
            }
        }
        (tmp_path / "test_species_pve.json").write_text(json.dumps(config))
        preset = self._make_preset()
        result = apply_species_overrides(preset, "test_species", config_dir=tmp_path)
        # Original value should be preserved since override is None
        assert result["globalAttributes"]["cycle"]["value"] == 5

    def test_new_attribute_added(self, tmp_path):
        config = {
            "globalAttributes": {
                "newAttr": {"isArray": False, "size": 1, "type": "float", "value": 1.5},
            }
        }
        (tmp_path / "test_species_pve.json").write_text(json.dumps(config))
        preset = self._make_preset()
        result = apply_species_overrides(preset, "test_species", config_dir=tmp_path)
        assert result["globalAttributes"]["newAttr"]["value"] == 1.5

    def test_unrelated_attributes_preserved(self, tmp_path):
        config = {
            "globalAttributes": {
                "cycle": {"isArray": False, "size": 1, "type": "int", "value": 99},
            }
        }
        (tmp_path / "test_species_pve.json").write_text(json.dumps(config))
        preset = self._make_preset()
        result = apply_species_overrides(preset, "test_species", config_dir=tmp_path)
        assert result["globalAttributes"]["maxBranchNumber"]["value"] == 10


class TestCreateNullPlaceholderConfig:
    """Tests for create_null_placeholder_config."""

    def test_creates_file(self, tmp_path):
        output = tmp_path / "beech_pve.json"
        create_null_placeholder_config(output, "european_beech", "European Beech")
        assert output.exists()

    def test_all_values_are_null(self, tmp_path):
        output = tmp_path / "config.json"
        create_null_placeholder_config(output, "test", "Test")
        data = json.loads(output.read_text())
        for key, attr in data["globalAttributes"].items():
            assert attr["value"] is None, f"{key} should have null value"

    def test_contains_species_metadata(self, tmp_path):
        output = tmp_path / "config.json"
        create_null_placeholder_config(output, "norway_spruce", "Norway Spruce")
        data = json.loads(output.read_text())
        assert data["_species"] == "norway_spruce"
        assert "Norway Spruce" in data["_comment"]
