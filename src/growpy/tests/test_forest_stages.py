"""Tests for growpy.pipelines.forest_stages constants and helpers.

The per-species height ceiling and milestone shortfall reporting are covered in
test_milestone_ceiling.py: the ceiling now comes from the authored
tree_asset_lookup.csv Max Height rather than from a simulated growth model.

TestTreeExportContextStages covers the per-tree/per-variant stage functions
extracted in XRFF-289 (resolve_target_dbh, compute_radial_scale,
export_assembly, write_wind_json, write_pve_json, write_previews,
write_icons, derive_static). Each uses a stub TreeExportContext with mocked
I/O -- no bpy, no Grove.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from growpy.config.core import GrowPyConfig
from growpy.pipelines.forest_stages import (
    GROWTH_CYCLE_LIMIT,
    SMOOTH_ITERATIONS,
    STAGES,
    compute_radial_scale,
    derive_static,
    export_assembly,
    resolve_target_dbh,
    write_icons,
    write_previews,
    write_pve_json,
    write_wind_json,
)
from growpy.pipelines.tree_export_context import TreeExportContext


class TestForestStagesConstants:
    """Tests for pipeline constants."""

    def test_growth_cycle_limit(self):
        assert isinstance(GROWTH_CYCLE_LIMIT, int)
        assert GROWTH_CYCLE_LIMIT > 0

    def test_smooth_iterations(self):
        assert isinstance(SMOOTH_ITERATIONS, int)
        assert SMOOTH_ITERATIONS >= 0


def _make_ctx(**overrides) -> TreeExportContext:
    """A stub TreeExportContext with sensible defaults, no bpy/Grove required."""
    defaults = {
        "cfg": GrowPyConfig(),
        "species_name": "European beech",
        "species_clean": "european_beech",
        "fid": 1,
        "tree_idx": 0,
        "height": 10.0,
        "grove_dbh": 0.15,
        "skeleton": MagicMock(name="skeleton"),
        "bones_info": ["bone0"],
        "twig_usd_map": {"twig_a": Path("twig_a.usda")},
        "instances_dir": Path("Instances"),
        "timer": MagicMock(),
        "grove": MagicMock(name="grove"),
        "use_skeletal": True,
        "use_static_only": False,
        "skip_validation": False,
        "include_grove_attributes": False,
        "skip_pve_json": False,
        "model": MagicMock(name="model"),
        "variant_name": None,
        "variant_idx": 0,
        "twig_density": 1.0,
        "tree_dir": Path("out/european_beech/tree_0001"),
        "file_prefix": "european_beech_h10m_d15cm",
    }
    defaults.update(overrides)
    ctx = TreeExportContext(**{k: v for k, v in defaults.items() if k in _CTX_FIELDS})
    for k, v in defaults.items():
        if k not in _CTX_FIELDS:
            setattr(ctx, k, v)
    return ctx


_CTX_FIELDS = {
    "cfg", "species_name", "species_clean", "fid", "tree_idx", "height",
    "grove_dbh", "skeleton", "bones_info", "twig_usd_map", "instances_dir",
    "timer", "grove", "use_skeletal", "use_static_only", "skip_validation",
    "include_grove_attributes", "skip_pve_json",
}


class TestResolveTargetDbh:
    """Tests for resolve_target_dbh (XRFF-289)."""

    def _patches(self, h_dbh_model=None):
        return patch.multiple(
            "growpy.pipelines.forest_stages",
            get_height_dbh_model=MagicMock(return_value=h_dbh_model),
            load_target_dbh_from_preset=MagicMock(return_value=[]),
            predict_dbh_from_height_model=MagicMock(return_value=0.2),
        )

    def test_no_model_no_csv_keeps_grove_dbh(self):
        ctx = _make_ctx(grove_dbh=0.12)
        with self._patches(h_dbh_model=None):
            resolve_target_dbh(
                ctx, cycle=1, h_dbh_model_cache={}, target_dbh_cache={}, csv_dbh_map={}
            )
        assert ctx.target_dbh_m is None
        assert ctx.dbh_from_csv is False
        assert ctx.filename_dbh == 0.12

    def test_height_dbh_model_sets_target(self):
        ctx = _make_ctx(height=10.0)
        with self._patches(h_dbh_model={"a": 1}):
            resolve_target_dbh(
                ctx, cycle=1, h_dbh_model_cache={}, target_dbh_cache={}, csv_dbh_map={}
            )
        assert ctx.target_dbh_m == 0.2
        assert ctx.filename_dbh == 0.2
        assert ctx.dbh_from_csv is False

    def test_csv_override_wins(self):
        ctx = _make_ctx(fid=7, height=10.0)
        with self._patches(h_dbh_model={"a": 1}):
            resolve_target_dbh(
                ctx, cycle=1, h_dbh_model_cache={}, target_dbh_cache={},
                csv_dbh_map={7: 0.33},
            )
        assert ctx.target_dbh_m == 0.33
        assert ctx.filename_dbh == 0.33
        assert ctx.dbh_from_csv is True

    def test_legacy_cache_fallback_used_when_no_height_model(self):
        """species already resolved (in h_dbh_model_cache) to 'no model', so the
        pre-populated target_dbh_cache fallback is used instead of being
        recomputed."""
        ctx = _make_ctx(species_name="oak")
        with self._patches(h_dbh_model=None):
            resolve_target_dbh(
                ctx, cycle=2,
                h_dbh_model_cache={"oak": None},
                target_dbh_cache={"oak": [0.1, 0.25, 0.4]},
                csv_dbh_map={},
            )
        assert ctx.target_dbh_m == 0.25
        assert ctx.filename_dbh == 0.25


class TestComputeRadialScale:
    """Tests for compute_radial_scale (XRFF-289)."""

    def test_no_target_dbh_keeps_scale_one(self):
        ctx = _make_ctx(target_dbh_m=None, grove_dbh=0.1)
        compute_radial_scale(ctx)
        assert ctx.radial_scale == 1.0

    def test_csv_dbh_clamps_wider_range(self):
        ctx = _make_ctx(target_dbh_m=1.0, grove_dbh=0.1, dbh_from_csv=True)
        ctx.cfg.export_dbh_from_allometry = True
        compute_radial_scale(ctx)
        assert ctx.radial_scale == pytest.approx(5.0)  # clamped at 5.0, not 10x
        assert ctx.filename_dbh == pytest.approx(0.1 * 5.0)

    def test_non_csv_clamps_narrower_range_with_correction_weight(self):
        ctx = _make_ctx(target_dbh_m=1.0, grove_dbh=0.1, dbh_from_csv=False)
        ctx.cfg.export_dbh_from_allometry = True
        with patch(
            "growpy.pipelines.forest_stages.correction_weight", return_value=1.0
        ):
            compute_radial_scale(ctx)
        assert ctx.radial_scale == pytest.approx(2.0)  # clamped at 2.0

    def test_allometry_disabled_keeps_scale_one(self):
        ctx = _make_ctx(target_dbh_m=1.0, grove_dbh=0.1)
        ctx.cfg.export_dbh_from_allometry = False
        compute_radial_scale(ctx)
        assert ctx.radial_scale == 1.0


class TestExportAssembly:
    """Tests for export_assembly (XRFF-289)."""

    def test_success_sets_usd_path_and_flag(self):
        ctx = _make_ctx(dims_suffix="h10m_d15cm")
        with patch(
            "growpy.pipelines.forest_stages.export_tree_as_nanite_assembly",
            return_value=True,
        ) as mock_export:
            export_assembly(ctx)
        assert ctx.export_success is True
        expected_path = ctx.tree_dir / f"{ctx.file_prefix}_assembly{ctx.cfg.usd_ext}"
        assert ctx.usd_path == expected_path
        mock_export.assert_called_once()
        assert mock_export.call_args.kwargs["model"] is ctx.model
        assert mock_export.call_args.kwargs["twig_density"] == ctx.twig_density

    def test_failure_sets_flag_false(self):
        ctx = _make_ctx()
        with patch(
            "growpy.pipelines.forest_stages.export_tree_as_nanite_assembly",
            return_value=False,
        ):
            export_assembly(ctx)
        assert ctx.export_success is False

    def test_bone_limit_error_handled_then_reraised(self):
        ctx = _make_ctx()
        err = ValueError("bone limit exceeded")
        with (
            patch(
                "growpy.pipelines.forest_stages.export_tree_as_nanite_assembly",
                side_effect=err,
            ),
            patch(
                "growpy.pipelines.forest_stages._is_bone_limit_error",
                return_value=True,
            ),
            patch(
                "growpy.pipelines.forest_stages._handle_bone_limit_error"
            ) as mock_handle,
            pytest.raises(ValueError),
        ):
            export_assembly(ctx)
        mock_handle.assert_called_once_with(err)


class TestWriteWindJson:
    """Tests for write_wind_json (XRFF-289)."""

    def test_skipped_when_not_skeletal(self):
        ctx = _make_ctx(use_skeletal=False)
        with patch("growpy.io.unreal.wind_json.generate_wind_json") as mock_gen:
            write_wind_json(ctx)
        mock_gen.assert_not_called()

    def test_skipped_when_config_disables_wind(self):
        ctx = _make_ctx(use_skeletal=True)
        ctx.cfg.unreal_generate_wind_data = False
        with patch("growpy.io.unreal.wind_json.generate_wind_json") as mock_gen:
            write_wind_json(ctx)
        mock_gen.assert_not_called()

    def test_generates_when_gated_on(self):
        ctx = _make_ctx(use_skeletal=True, dims_suffix="h10m_d15cm")
        ctx.cfg.unreal_generate_wind_data = True
        with patch("growpy.io.unreal.wind_json.generate_wind_json") as mock_gen:
            write_wind_json(ctx)
        mock_gen.assert_called_once()
        assert mock_gen.call_args.kwargs["skeleton"] is ctx.skeleton

    def test_exception_logged_not_raised(self):
        ctx = _make_ctx(use_skeletal=True)
        ctx.cfg.unreal_generate_wind_data = True
        with patch(
            "growpy.io.unreal.wind_json.generate_wind_json",
            side_effect=RuntimeError("boom"),
        ):
            write_wind_json(ctx)  # must not raise


class TestWritePveJson:
    """Tests for write_pve_json (XRFF-289)."""

    def test_skipped_when_not_skeletal(self):
        ctx = _make_ctx(use_skeletal=False)
        with patch(
            "growpy.io.unreal.pve_grove_mapper.generate_pve_from_grove"
        ) as mock_gen:
            write_pve_json(ctx)
        mock_gen.assert_not_called()

    def test_skipped_when_skip_pve_json(self):
        ctx = _make_ctx(use_skeletal=True, skip_pve_json=True)
        with patch(
            "growpy.io.unreal.pve_grove_mapper.generate_pve_from_grove"
        ) as mock_gen:
            write_pve_json(ctx)
        mock_gen.assert_not_called()

    def test_generates_when_gated_on(self):
        ctx = _make_ctx(use_skeletal=True, skip_pve_json=False, tree_idx=3)
        with patch(
            "growpy.io.unreal.pve_grove_mapper.generate_pve_from_grove"
        ) as mock_gen:
            write_pve_json(ctx)
        mock_gen.assert_called_once()
        assert mock_gen.call_args.kwargs["tree_index"] == 3
        assert mock_gen.call_args.kwargs["grove"] is ctx.grove


class TestWritePreviews:
    """Tests for write_previews (XRFF-289)."""

    def test_generates_preview_and_export_control(self):
        ctx = _make_ctx(dims_suffix="h10m_d15cm")
        with (
            patch(
                "growpy.pipelines.forest_stages._generate_preview_image",
                return_value="bounds",
            ) as mock_preview,
            patch(
                "growpy.pipelines.forest_stages._generate_export_control_image"
            ) as mock_control,
        ):
            write_previews(ctx)
        mock_preview.assert_called_once()
        mock_control.assert_called_once()
        assert mock_control.call_args.kwargs["view_bounds"] == "bounds"


class TestWriteIcons:
    """Tests for write_icons (XRFF-289)."""

    def test_generates_three_views(self):
        ctx = _make_ctx()
        with patch(
            "growpy.pipelines.forest_stages._generate_icon_image"
        ) as mock_icon:
            write_icons(ctx)
        assert mock_icon.call_count == 3
        views = {c.kwargs["view"] for c in mock_icon.call_args_list}
        assert views == {"front", "side", "top"}


class TestDeriveStatic:
    """Tests for derive_static (XRFF-289)."""

    def test_skipped_when_not_skeletal(self):
        ctx = _make_ctx(use_skeletal=False)
        with patch(
            "growpy.pipelines.forest_stages._derive_static_from_skeletal"
        ) as mock_derive:
            derive_static(ctx)
        mock_derive.assert_not_called()
        assert ctx.static_path is None

    def test_skipped_when_export_static_disabled(self):
        ctx = _make_ctx(use_skeletal=True)
        ctx.cfg.export_static = False
        with patch(
            "growpy.pipelines.forest_stages._derive_static_from_skeletal"
        ) as mock_derive:
            derive_static(ctx)
        mock_derive.assert_not_called()

    def test_sets_static_path_when_gated_on(self):
        ctx = _make_ctx(use_skeletal=True)
        ctx.cfg.export_static = True
        with patch(
            "growpy.pipelines.forest_stages._derive_static_from_skeletal",
            return_value="out/static.usdc",
        ):
            derive_static(ctx)
        assert ctx.static_path == "out/static.usdc"


class TestStagesRegistry:
    """Tests for the STAGES registry (XRFF-290).

    generate_forest_stages() drives once-per-tree gating and ordering by
    iterating STAGES directly; that loop itself needs bpy/Grove to exercise
    end-to-end, so it's covered by a real before/after generation run (see
    the XRFF-290 Linear comment) rather than here. These tests cover the
    registry's own structure and gate functions, which are pure.
    """

    def test_stage_names_and_order(self):
        names = [name for name, *_ in STAGES]
        assert names == ["wind_json", "pve_json", "preview", "icons", "static_derive"]

    def test_all_stages_are_once_per_tree(self):
        """None of these run per density variant -- only for variant_idx == 0."""
        for name, _gate, _fn, once_per_tree in STAGES:
            assert once_per_tree is True, f"{name} should be once_per_tree"

    def test_stage_functions_match_extracted_functions(self):
        expected = {
            "wind_json": write_wind_json,
            "pve_json": write_pve_json,
            "preview": write_previews,
            "icons": write_icons,
            "static_derive": derive_static,
        }
        for name, _gate, fn, _once in STAGES:
            assert fn is expected[name]

    def _gate_for(self, name):
        for stage_name, gate, _fn, _once in STAGES:
            if stage_name == name:
                return gate
        raise AssertionError(f"no stage named {name!r}")

    def test_wind_json_gate_follows_config(self):
        gate = self._gate_for("wind_json")
        ctx = _make_ctx()
        ctx.cfg.unreal_generate_wind_data = True
        assert gate(ctx) is True
        ctx.cfg.unreal_generate_wind_data = False
        assert gate(ctx) is False

    def test_pve_json_gate_follows_skip_flag(self):
        gate = self._gate_for("pve_json")
        ctx = _make_ctx(skip_pve_json=False)
        assert gate(ctx) is True
        ctx.skip_pve_json = True
        assert gate(ctx) is False

    def test_preview_gate_follows_config(self):
        gate = self._gate_for("preview")
        ctx = _make_ctx()
        ctx.cfg.export_previews = True
        assert gate(ctx) is True
        ctx.cfg.export_previews = False
        assert gate(ctx) is False

    def test_icons_gate_follows_config(self):
        gate = self._gate_for("icons")
        ctx = _make_ctx()
        ctx.cfg.export_icons = True
        assert gate(ctx) is True
        ctx.cfg.export_icons = False
        assert gate(ctx) is False

    def test_static_derive_gate_follows_config(self):
        gate = self._gate_for("static_derive")
        ctx = _make_ctx()
        ctx.cfg.export_static = True
        assert gate(ctx) is True
        ctx.cfg.export_static = False
        assert gate(ctx) is False
