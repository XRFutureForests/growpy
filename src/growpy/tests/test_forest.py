"""Tests for growpy.core.forest pure-logic functions."""

from unittest.mock import MagicMock, patch

import pandas as pd
import pytest

try:
    import the_grove_23_core as _gc

    from growpy.core.forest import (
        _compute_grove_offsets,
        split_bones_by_tree,
        build_density_variant_model_sets,
        create_forest,
    )
    from growpy.core.grove import enable_surround

    _IMPORT_OK = True
except (ImportError, OSError):
    _IMPORT_OK = False
    _gc = None
    split_bones_by_tree = None
    _compute_grove_offsets = None
    create_forest = None
    enable_surround = None

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK,
    reason="growpy.core.forest requires The Grove API",
)


class TestSplitBonesByTree:
    """Tests for splitting combined bone list into per-tree lists."""

    def _bone(self, is_root, parent_id=0):
        """Create a minimal bone tuple: (is_tree_root, parent_id, ...)."""
        return (is_root, parent_id, (0, 0, 0), (0, 1, 0), 0.1, 1.0, False, 0)

    def test_single_tree(self):
        bones = [self._bone(True), self._bone(False), self._bone(False)]
        result = split_bones_by_tree(bones, 1)
        assert len(result) == 1
        assert len(result[0]) == 3

    def test_two_trees(self):
        bones = [
            self._bone(True), self._bone(False),  # tree 1
            self._bone(True), self._bone(False), self._bone(False),  # tree 2
        ]
        result = split_bones_by_tree(bones, 2)
        assert len(result) == 2
        assert len(result[0]) == 2
        assert len(result[1]) == 3

    def test_three_trees_different_sizes(self):
        bones = [
            self._bone(True),  # tree 1: 1 bone
            self._bone(True), self._bone(False), self._bone(False),  # tree 2: 3
            self._bone(True), self._bone(False),  # tree 3: 2
        ]
        result = split_bones_by_tree(bones, 3)
        assert len(result) == 3
        assert len(result[0]) == 1
        assert len(result[1]) == 3
        assert len(result[2]) == 2

    def test_empty_bones(self):
        result = split_bones_by_tree([], 3)
        assert len(result) == 3
        assert all(b == [] for b in result)

    def test_zero_trees(self):
        result = split_bones_by_tree([], 0)
        assert result == []

    def test_fewer_trees_than_expected_pads(self):
        bones = [self._bone(True), self._bone(False)]
        result = split_bones_by_tree(bones, 3)
        assert len(result) >= 1
        assert len(result[0]) == 2


class TestComputeGroveOffsets:
    """Tests for _compute_grove_offsets."""

    def _grove_entry(self, species_name, tree_count):
        """Create a minimal forest entry tuple: (grove, species_name, tree_count, fids)."""
        return (None, species_name, tree_count, [])

    def test_single_grove(self):
        forest = [self._grove_entry("spruce", 5)]
        offsets = _compute_grove_offsets(forest)
        assert offsets == [0]

    def test_different_species(self):
        forest = [
            self._grove_entry("spruce", 3),
            self._grove_entry("beech", 4),
        ]
        offsets = _compute_grove_offsets(forest)
        assert offsets == [0, 0]

    def test_same_species_multiple_groves(self):
        forest = [
            self._grove_entry("spruce", 3),
            self._grove_entry("spruce", 4),
            self._grove_entry("spruce", 2),
        ]
        offsets = _compute_grove_offsets(forest)
        assert offsets == [0, 3, 7]

    def test_mixed_species(self):
        forest = [
            self._grove_entry("spruce", 3),
            self._grove_entry("beech", 2),
            self._grove_entry("spruce", 4),
        ]
        offsets = _compute_grove_offsets(forest)
        assert offsets == [0, 0, 3]

    def test_empty_forest(self):
        assert _compute_grove_offsets([]) == []



class TestEnableSurround:
    """Tests for enabling Grove's Surround shell on a grove."""

    def test_sets_surround_properties(self):
        grove = _gc.Grove()
        grove.clear_trees()
        applied = enable_surround(
            grove, density=0.6, distance=10.0, height=5.0, grow=True
        )
        assert applied is True
        props = grove.get_properties()
        assert props.surround_enabled is True
        assert props.surround_density == pytest.approx(0.6)
        assert props.surround_distance == pytest.approx(10.0)
        assert props.surround_height == pytest.approx(5.0)
        assert props.surround_grow is True

    def test_surround_reduces_branch_count(self):
        # A tree grown with Surround competes for light and self-prunes, so it
        # should end up with fewer branches than the same tree grown open.
        def grow(surround):
            g = _gc.Grove()
            g.clear_trees()
            g.set_random_seed(42)
            if surround:
                enable_surround(g, density=0.7, distance=7.0, height=5.0, grow=True)
            g.add_new_tree(_gc.Vector(0, 0, 0), _gc.Vector(0, 0, 1), 0)
            for _ in range(12):
                g.weigh_and_bend()
                g.simulate(1)
            return g.number_of_branches

        assert grow(surround=True) < grow(surround=False)


class TestCreateForestSurroundRadius:
    """Tests for create_forest's per-row surround_radius dispatch.

    Surround is a pure runtime parameter: the radius must reach
    enable_surround() and never create_grove(), since a species has one preset
    regardless of which competition variant is being grown.
    """

    def _run(self, rows):
        df = pd.DataFrame(rows)
        mock_grove = MagicMock()
        with (
            patch(
                "growpy.core.forest.create_grove", return_value=mock_grove
            ) as mock_create,
            patch("growpy.core.forest.enable_surround") as mock_enable,
        ):
            create_forest(df)
        return mock_create, mock_enable

    def test_zero_radius_skips_surround(self):
        mock_create, mock_enable = self._run(
            [{"fid": 1, "species": "spruce", "x": 0.0, "y": 0.0, "surround_radius": 0.0}]
        )
        mock_create.assert_called_once_with("spruce")
        mock_enable.assert_not_called()

    def test_nonzero_radius_enables_surround(self):
        mock_create, mock_enable = self._run(
            [{"fid": 1, "species": "spruce", "x": 0.0, "y": 0.0, "surround_radius": 7.0}]
        )
        mock_create.assert_called_once_with("spruce")
        mock_enable.assert_called_once()
        _, kwargs = mock_enable.call_args
        assert kwargs["distance"] == 7.0

    def test_radius_never_reaches_create_grove(self):
        """Preset selection must not depend on the competition variant."""
        mock_create, _ = self._run(
            [{"fid": 1, "species": "spruce", "x": 0.0, "y": 0.0, "surround_radius": 7.0}]
        )
        _, kwargs = mock_create.call_args
        assert "radius" not in kwargs

    def test_missing_column_defaults_to_open_grown(self):
        mock_create, mock_enable = self._run(
            [{"fid": 1, "species": "spruce", "x": 0.0, "y": 0.0}]
        )
        mock_create.assert_called_once_with("spruce")
        mock_enable.assert_not_called()

    def test_multi_tree_group_skips_surround_even_if_nonzero(self):
        # enable_surround only applies to single-tree groves (Grove disables
        # Surround once several trees share a grove).
        mock_create, mock_enable = self._run(
            [
                {"fid": 1, "species": "spruce", "x": 0.0, "y": 0.0, "surround_radius": 7.0},
                {"fid": 2, "species": "spruce", "x": 1.0, "y": 0.0, "surround_radius": 7.0},
            ]
        )
        mock_create.assert_called_once_with("spruce")
        mock_enable.assert_not_called()


class TestBuildDensityVariantModelSets:
    """Tests for the shared cutoff-keyed model cache (XRFF-288).

    Shared by Pipeline A (core/forest.py's _build_models_for_grove) and
    Pipeline B (io/forest_export.py) so both honour a variant's
    build_cutoff_* overrides identically.
    """

    BASE_OPTS = {
        "resolution": 24,
        "resolution_reduce": 0.8,
        "build_cutoff_age": 0,
        "build_cutoff_thickness": 0.01,
        "build_blend": True,
        "build_end_cap": True,
    }

    def _make_grove(self, build_models_results):
        grove = MagicMock()
        grove.build_models.side_effect = build_models_results
        return grove

    def test_variant_matching_base_cutoff_reuses_base_models(self):
        base_models = ["base_model_0", "base_model_1"]
        grove = self._make_grove([])
        variants = [("full", {"twig_density": 1.5})]  # no cutoff override

        result = build_density_variant_model_sets(
            grove, base_models, self.BASE_OPTS, variants
        )

        assert result == {"full": base_models}
        grove.build_models.assert_not_called()

    def test_distinct_cutoff_triggers_exactly_one_extra_build(self):
        base_models = ["base0", "base1"]
        variant_models = ["variant0", "variant1"]
        grove = self._make_grove([variant_models])
        variants = [("bare", {"twig_density": 0.25, "build_cutoff_thickness": 0.02})]

        result = build_density_variant_model_sets(
            grove, base_models, self.BASE_OPTS, variants
        )

        assert grove.build_models.call_count == 1
        assert result["bare"] == variant_models

    def test_two_variants_sharing_cutoff_share_one_model_set(self):
        base_models = ["base0"]
        shared_models = ["shared0"]
        grove = self._make_grove([shared_models])
        variants = [
            ("reduced", {"twig_density": 0.75, "build_cutoff_thickness": 0.02}),
            ("bare", {"twig_density": 0.25, "build_cutoff_thickness": 0.02}),
        ]

        result = build_density_variant_model_sets(
            grove, base_models, self.BASE_OPTS, variants
        )

        assert grove.build_models.call_count == 1
        assert result["reduced"] is shared_models
        assert result["bare"] is shared_models

    def test_extra_build_uses_variant_cutoff_not_base(self):
        grove = self._make_grove([["variant_model"]])
        variants = [("bare", {"build_cutoff_age": 5, "build_cutoff_thickness": 0.02})]

        build_density_variant_model_sets(grove, ["base"], self.BASE_OPTS, variants)

        called_opts = grove.build_models.call_args[0][0]
        assert called_opts["build_cutoff_age"] == 5
        assert called_opts["build_cutoff_thickness"] == 0.02
        # Non-cutoff options pass through unchanged from the base options.
        assert called_opts["resolution"] == self.BASE_OPTS["resolution"]
