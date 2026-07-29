"""Tests for growpy.pipelines.forest_stages constants and helpers.

The per-species height ceiling and milestone shortfall reporting are covered in
test_milestone_ceiling.py: the ceiling now comes from the authored
tree_asset_lookup.csv Max Height rather than from a simulated growth model.
"""

from growpy.pipelines.forest_stages import GROWTH_CYCLE_LIMIT, SMOOTH_ITERATIONS


class TestForestStagesConstants:
    """Tests for pipeline constants."""

    def test_growth_cycle_limit(self):
        assert isinstance(GROWTH_CYCLE_LIMIT, int)
        assert GROWTH_CYCLE_LIMIT > 0

    def test_smooth_iterations(self):
        assert isinstance(SMOOTH_ITERATIONS, int)
        assert SMOOTH_ITERATIONS >= 0
