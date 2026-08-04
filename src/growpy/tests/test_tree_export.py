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

