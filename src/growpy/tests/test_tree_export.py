"""Tests for growpy.io.usd.tree_export utility functions."""

from types import SimpleNamespace

import pytest

from growpy.core.skeleton import Vector3
from growpy.io.usd.tree_export import (
    build_tree_mesh,
    handle_bone_limit_error,
    is_bone_limit_error,
)


class TestIsBoneLimitError:
    """Tests for is_bone_limit_error."""

    def test_matches_bone_limit_message(self):
        err = ValueError("Tree has 300 bones which exceeds the limit of 256")
        assert is_bone_limit_error(err) is True

    def test_rejects_unrelated_error(self):
        err = ValueError("Invalid mesh data")
        assert is_bone_limit_error(err) is False

    def test_rejects_partial_match_bones_only(self):
        err = ValueError("Too many bones in skeleton")
        assert is_bone_limit_error(err) is False

    def test_rejects_partial_match_limit_only(self):
        err = ValueError("Exceeded the limit of faces")
        assert is_bone_limit_error(err) is False


class TestHandleBoneLimitError:
    """Tests for handle_bone_limit_error."""

    def test_raises_system_exit(self):
        err = ValueError("300 bones exceeds limit of 256")
        with pytest.raises(SystemExit, match="1"):
            handle_bone_limit_error(err)


class TestBuildTreeMeshJunctionContinuity:
    """Regression test for the trunk/branch radial-scale junction blend.

    Two vertices at the *same* physical position — one weighted to a trunk
    bone, one weighted to a branch bone attached to it — must scale to the
    same output position. Historically only the branch-owned vertex blended
    its scaling axis toward the trunk near the junction; the trunk-owned
    vertex always used its own axis unconditionally, so radial scaling tore
    the mesh apart right at branch connection points.
    """

    def _bones(self):
        trunk = (
            True,
            -1,
            Vector3(0.0, 0.0, 0.0),
            Vector3(0.0, 2.0, 0.0),
            0.15,
            1.0,
            False,
            0,
        )
        branch = (
            False,
            100,
            Vector3(0.05, 1.0, 0.05),
            Vector3(0.6, 1.3, 0.2),
            0.05,
            0.2,
            True,
            1,
        )
        return [trunk, branch]

    def _model(self):
        seam = Vector3(0.1, 1.0, 0.02)
        filler = Vector3(0.0, 0.0, 0.0)
        return SimpleNamespace(
            points=[seam, seam, filler],
            faces=[[0, 1, 2]],
            uvs=[],
            point_attribute_bone_id=[100, 101, 100],
        )

    def test_trunk_and_branch_owned_seam_vertices_scale_identically(self, tmp_path):
        scaled_points: list = []
        ok = build_tree_mesh(
            model=self._model(),
            skeleton=None,
            output_path=tmp_path / "seam_test.usda",
            bones_info=self._bones(),
            species_name="test_species",
            tree_id="0001",
            include_skeleton=False,
            include_grove_attributes=False,
            radial_scale=1.5,
            scaled_points_out=scaled_points,
        )

        assert ok is True
        assert len(scaled_points) == 3

        trunk_owned = scaled_points[0]
        branch_owned = scaled_points[1]
        for a, b in zip(trunk_owned, branch_owned, strict=True):
            assert a == pytest.approx(b, abs=1e-5)



class TestBuildTreeMeshFailureHandling:
    """Regression tests for how a failed export reports and cleans up.

    `Usd.Stage.CreateNew` writes the file the moment it is called, so every
    failure path between it and `stage.Save()` used to leave a 0-byte .usdc
    behind while the step still reported OK (XRFF-331). A `MemoryError` was
    additionally reported as whatever USD call came next, which pointed
    debugging at the UV handling instead of at the host's memory (XRFF-333).
    """

    def _model(self, uvs_exc=None):
        pt = Vector3(0.0, 0.0, 0.0)

        class _Model:
            points = [pt, pt, pt]
            faces = [[0, 1, 2]]
            point_attribute_bone_id = [0, 0, 0]

            @property
            def uvs(self):
                if uvs_exc is not None:
                    raise uvs_exc
                return []

        return _Model()

    def test_memory_error_is_reported_as_memory(self, tmp_path, caplog):
        out = tmp_path / "oom_tree.usda"

        ok = build_tree_mesh(
            model=self._model(uvs_exc=MemoryError()),
            skeleton=None,
            output_path=out,
            species_name="silver_fir",
            tree_id="0001",
            include_skeleton=False,
        )

        assert ok is False
        text = caplog.text
        assert "Out of memory" in text
        assert "silver_fir" in text
        # The counts bound before the failure are reported, so the log says how
        # big the mesh was when the host ran out.
        assert "3 points" in text
        # And it must not blame USD, which is what sent the original
        # investigation into this module's primvar handling.
        assert "USD export failed" not in text

    def test_memory_error_leaves_no_partial_artifact(self, tmp_path):
        out = tmp_path / "oom_tree.usda"

        build_tree_mesh(
            model=self._model(uvs_exc=MemoryError()),
            skeleton=None,
            output_path=out,
            species_name="silver_fir",
            tree_id="0001",
            include_skeleton=False,
        )

        assert not out.exists()

    def test_generic_failure_leaves_no_partial_artifact(self, tmp_path):
        out = tmp_path / "broken_tree.usda"

        ok = build_tree_mesh(
            model=self._model(uvs_exc=RuntimeError("boom")),
            skeleton=None,
            output_path=out,
            species_name="common_ash",
            tree_id="0001",
            include_skeleton=False,
        )

        assert ok is False
        # A consumer globbing *_stems_skeletal.usdc must not find an empty file
        # sitting where a real asset should be.
        assert not out.exists()

    def test_successful_export_keeps_its_file(self, tmp_path):
        out = tmp_path / "good_tree.usda"

        ok = build_tree_mesh(
            model=self._model(),
            skeleton=None,
            output_path=out,
            species_name="common_ash",
            tree_id="0001",
            include_skeleton=False,
        )

        assert ok is True
        assert out.exists()
        assert out.stat().st_size > 0
