"""Tests for growpy.io.usd.preview image generation."""

from unittest.mock import MagicMock

import pytest

from growpy.io.usd.preview import generate_export_control_image, generate_preview_image


class TestGeneratePreviewImage:
    """Tests for skeleton preview image generation."""

    def _mock_timer(self):
        timer = MagicMock()
        timer.track = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=None),
            __exit__=MagicMock(return_value=False),
        ))
        return timer

    def test_returns_none_for_none_skeleton(self, tmp_path):
        result = generate_preview_image(
            tmp_path, "test_tree", "test_h10m", None, self._mock_timer()
        )
        assert result is None

    def test_returns_none_for_empty_skeleton(self, tmp_path):
        skeleton = MagicMock()
        skeleton.points = []
        result = generate_preview_image(
            tmp_path, "test_tree", "test_h10m", skeleton, self._mock_timer()
        )
        assert result is None

    def test_returns_view_bounds_for_valid_skeleton(self, tmp_path):
        skeleton = MagicMock()
        skeleton.points = [
            (0.0, 0.0, 0.0), (0.0, 0.0, 5.0), (1.0, 0.0, 3.0),
        ]
        skeleton.poly_lines = [[0, 1], [0, 2]]
        skeleton.point_attribute_radius = [0.1, 0.05, 0.03]

        result = generate_preview_image(
            tmp_path, "test_tree", "test_h10m", skeleton, self._mock_timer()
        )
        assert result is not None
        assert isinstance(result, list)


class TestGenerateExportControlImage:
    """Regression: must read the stems USD via the pxr API (works for both
    '.usda' and '.usdc'), not via read_text()+regex which cannot parse the
    binary '.usdc' crate format.
    """

    def _mock_timer(self):
        timer = MagicMock()
        timer.track = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=None),
            __exit__=MagicMock(return_value=False),
        ))
        return timer

    def _write_stems_usd(self, path):
        from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

        ensure_pxr_with_unreal_schema()
        from pxr import Gf, UsdGeom, UsdSkel, Vt
        from pxr import Usd as _Usd

        stage = _Usd.Stage.CreateNew(str(path))
        mesh = UsdGeom.Mesh.Define(stage, "/tree/mesh")
        mesh.CreatePointsAttr(
            Vt.Vec3fArray([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 2)])
        )
        mesh.CreateFaceVertexCountsAttr(Vt.IntArray([3, 3]))
        mesh.CreateFaceVertexIndicesAttr(Vt.IntArray([0, 1, 2, 0, 2, 3]))

        skel = UsdSkel.Skeleton.Define(stage, "/tree/skeleton")
        skel.CreateJointsAttr(Vt.TokenArray(["root", "root/child"]))
        m0 = Gf.Matrix4d(1.0)
        m0.SetTranslateOnly(Gf.Vec3d(0, 0, 0))
        m1 = Gf.Matrix4d(1.0)
        m1.SetTranslateOnly(Gf.Vec3d(0, 0, 1))
        skel.CreateBindTransformsAttr(Vt.Matrix4dArray([m0, m1]))
        stage.GetRootLayer().Save()

    @pytest.fixture(autouse=True)
    def _reset_global_config(self):
        from growpy.config.core import set_global_config

        yield
        set_global_config(None)

    @pytest.mark.parametrize("fmt", ["usda", "usdc"])
    def test_renders_control_image_for_both_formats(self, tmp_path, fmt):
        from growpy.config.core import GrowPyConfig, set_global_config

        set_global_config(GrowPyConfig(export_usd_format=fmt))

        self._write_stems_usd(tmp_path / f"test_h10m_stems_skeletal.{fmt}")

        generate_export_control_image(
            tmp_path,
            "test_tree",
            "test_h10m",
            self._mock_timer(),
            stems_file_base="test_h10m",
        )

        assert (tmp_path / "test_h10m_export_control.png").exists()

    def test_returns_silently_when_stems_file_missing(self, tmp_path):
        from growpy.config.core import GrowPyConfig, set_global_config

        set_global_config(GrowPyConfig(export_usd_format="usda"))

        generate_export_control_image(
            tmp_path,
            "test_tree",
            "test_h10m",
            self._mock_timer(),
            stems_file_base="test_h10m",
        )

        assert not (tmp_path / "test_h10m_export_control.png").exists()
