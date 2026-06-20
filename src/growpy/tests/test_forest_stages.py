"""Tests for growpy.pipelines.forest_stages constants and helpers."""

import json
from unittest.mock import patch

from growpy.pipelines.forest_stages import (
    GROWTH_CYCLE_LIMIT,
    SMOOTH_ITERATIONS,
    _load_species_max_heights,
)


class TestForestStagesConstants:
    """Tests for pipeline constants."""

    def test_growth_cycle_limit(self):
        assert isinstance(GROWTH_CYCLE_LIMIT, int)
        assert GROWTH_CYCLE_LIMIT > 0

    def test_smooth_iterations(self):
        assert isinstance(SMOOTH_ITERATIONS, int)
        assert SMOOTH_ITERATIONS >= 0


class TestLoadSpeciesMaxHeights:
    """Tests for the per-species growth-model height ceiling lookup."""

    def _patch_assets_dir(self, tmp_path):
        return patch(
            "growpy.config.paths.get_assets_directory", return_value=tmp_path
        )

    def test_prefers_chapman_richards_asymptote_over_truncated_metadata(self, tmp_path):
        species_dir = tmp_path / "growth_models" / "common_ash"
        species_dir.mkdir(parents=True)
        (species_dir / "growth_model_params.json").write_text(
            json.dumps({"model_type": "chapman_richards", "A": 62.0})
        )
        (species_dir / "metadata.json").write_text(
            json.dumps({"max_height": 12.4})
        )

        with self._patch_assets_dir(tmp_path):
            result = _load_species_max_heights(["Common ash"])

        assert result == {"Common ash": 62.0}

    def test_falls_back_to_metadata_for_piecewise_model(self, tmp_path):
        species_dir = tmp_path / "growth_models" / "common_ash"
        species_dir.mkdir(parents=True)
        (species_dir / "growth_model_params.json").write_text(
            json.dumps({"model_type": "piecewise_linear"})
        )
        (species_dir / "metadata.json").write_text(
            json.dumps({"max_height": 18.0})
        )

        with self._patch_assets_dir(tmp_path):
            result = _load_species_max_heights(["Common ash"])

        assert result == {"Common ash": 18.0}

    def test_omits_species_with_no_readable_model(self, tmp_path):
        with self._patch_assets_dir(tmp_path):
            result = _load_species_max_heights(["Common ash"])

        assert result == {}
