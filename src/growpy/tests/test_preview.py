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

    def _skeleton(self):
        skeleton = MagicMock()
        skeleton.points = [
            (0.0, 0.0, 0.0), (0.0, 0.0, 5.0), (1.0, 0.0, 3.0),
        ]
        skeleton.poly_lines = [[0, 1], [0, 2]]
        skeleton.point_attribute_radius = [0.1, 0.05, 0.03]
        return skeleton

    def _placements(self, n):
        return {"twig_long": [MagicMock(position=(0.1 * i, 0.0, 1.0 + 0.1 * i))
                              for i in range(n)]}

    def test_twig_row_adds_a_second_row_of_views(self, tmp_path):
        """Twig placements must change the image; without them density is invisible."""
        (tmp_path / "bare").mkdir(parents=True, exist_ok=True)
        (tmp_path / "withtwigs").mkdir(parents=True, exist_ok=True)
        bare = generate_preview_image(
            tmp_path / "bare", "test_tree", "t_h10m", self._skeleton(),
            self._mock_timer(),
        )
        withtwigs = generate_preview_image(
            tmp_path / "withtwigs", "test_tree", "t_h10m", self._skeleton(),
            self._mock_timer(), twig_placements=self._placements(20),
        )
        # Contract preserved: three branch-row bounds either way, so the
        # export-control render still frames itself identically.
        assert len(bare) == 3
        assert len(withtwigs) == 3
        b = (tmp_path / "bare" / "t_h10m_preview.png").read_bytes()
        w = (tmp_path / "withtwigs" / "t_h10m_preview.png").read_bytes()
        assert b != w, "twig row did not change the rendered image"
        assert len(w) > len(b), "twig row should add content, not replace it"

    def test_density_changes_the_image(self, tmp_path):
        """The whole point: two densities must not render identically."""
        for name, n in (("sparse", 5), ("dense", 400)):
            (tmp_path / name).mkdir(parents=True, exist_ok=True)
            generate_preview_image(
                tmp_path / name, "test_tree", "t_h10m", self._skeleton(),
                self._mock_timer(), twig_placements=self._placements(n),
            )
        sparse = (tmp_path / "sparse" / "t_h10m_preview.png").read_bytes()
        dense = (tmp_path / "dense" / "t_h10m_preview.png").read_bytes()
        assert sparse != dense

    def test_empty_placements_fall_back_to_single_row(self, tmp_path):
        for name, tp in (("none", None), ("empty", {}), ("emptylist", {"twig_long": []})):
            (tmp_path / name).mkdir(parents=True, exist_ok=True)
            generate_preview_image(
                tmp_path / name, "test_tree", "t_h10m", self._skeleton(),
                self._mock_timer(), twig_placements=tp,
            )
        ref = (tmp_path / "none" / "t_h10m_preview.png").read_bytes()
        for name in ("empty", "emptylist"):
            assert (tmp_path / name / "t_h10m_preview.png").read_bytes() == ref


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
