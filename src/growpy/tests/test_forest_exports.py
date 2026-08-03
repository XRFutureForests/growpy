"""Tests for growpy.pipelines.forest_exports constants."""

import logging

import pandas as pd

from growpy.config.core import GrowPyConfig
from growpy.pipelines.forest_exports import (
    GROWTH_CYCLE_LIMIT,
    SMOOTH_ITERATIONS,
    generate_forest_exports,
)


class TestForestExportsConstants:
    """Tests for pipeline constants."""

    def test_growth_cycle_limit(self):
        assert isinstance(GROWTH_CYCLE_LIMIT, int)
        assert GROWTH_CYCLE_LIMIT > 0

    def test_smooth_iterations(self):
        assert isinstance(SMOOTH_ITERATIONS, int)
        assert SMOOTH_ITERATIONS >= 0


class TestExportModeHeliosGuard:
    """export_mode = "helios" is only implemented for the multi-stage
    pipeline (forest_stages.py); this pipeline (Pipeline B, selected by
    [forest] height_interval = 0) must refuse it explicitly rather than
    silently running the unreal/USD path (XRFF-311)."""

    def test_helios_mode_logs_error_and_returns_without_exporting(self, tmp_path, caplog):
        config = GrowPyConfig()
        config.export_mode = "helios"
        forest_data = pd.DataFrame(
            {"species": ["European beech"], "x": [0.0], "y": [0.0], "height": [10.0]}
        )

        with caplog.at_level(logging.ERROR):
            generate_forest_exports(forest_data, tmp_path, config)

        assert any("helios" in r.message for r in caplog.records)
        assert list(tmp_path.iterdir()) == []
