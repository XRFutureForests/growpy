"""Tests for growpy.io.mesh_simplify module.

Covers classify_material and _extract_and_simplify (ratio=1.0 path only,
since _decimate_with_bpy requires Blender).
"""

import numpy as np
import pytest

from growpy.io.helios.mesh_simplify import (
    _extract_and_simplify,
    _simplify_proto_by_material,
    classify_material,
)


class TestClassifyMaterial:
    """Tests for material name classification."""

    def test_bark_literal(self):
        assert classify_material("bark") == "bark"

    def test_bark_not_partial(self):
        # "bark" must be exact match for "bark" class; partial triggers wood
        assert classify_material("bark_base") == "wood"

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("twig_wood", "wood"),
            ("branch_material", "wood"),
            ("stem_base", "wood"),
            ("Twig_Wood_01", "wood"),
            ("WOOD_texture", "wood"),
        ],
    )
    def test_wood_keywords(self, name, expected):
        assert classify_material(name) == expected

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("EuropeanOakFruits", "fruit"),
            ("fruit_cluster", "fruit"),
        ],
    )
    def test_fruit_keywords(self, name, expected):
        assert classify_material(name) == expected

    @pytest.mark.parametrize(
        "name",
        ["leaf_top", "needle_mat", "foliage", "SomeMaterial"],
    )
    def test_leaf_default(self, name):
        assert classify_material(name) == "leaf"

    def test_empty_string(self):
        assert classify_material("") == "leaf"


class TestExtractAndSimplify:
    """Tests for vertex extraction and reindexing (ratio=1.0, no Blender)."""

    def test_basic_reindex(self):
        verts = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
            [99, 99, 99],  # unused vertex
        ], dtype=np.float64)
        faces = np.array([[0, 1, 2]], dtype=np.int64)

        out_verts, out_faces = _extract_and_simplify(verts, faces, ratio=1.0)

        assert out_verts.shape == (3, 3)
        assert out_faces.shape == (1, 3)
        # Reindexed faces should be 0-based
        np.testing.assert_array_equal(out_faces[0], [0, 1, 2])

    def test_sparse_indices(self):
        verts = np.zeros((10, 3), dtype=np.float64)
        verts[3] = [1, 0, 0]
        verts[7] = [0, 1, 0]
        verts[9] = [0, 0, 1]
        faces = np.array([[3, 7, 9]], dtype=np.int64)

        out_verts, out_faces = _extract_and_simplify(verts, faces, ratio=1.0)

        assert out_verts.shape == (3, 3)
        assert out_faces.shape == (1, 3)
        # Check vertex values are preserved
        np.testing.assert_array_equal(out_verts[out_faces[0, 0]], [1, 0, 0])
        np.testing.assert_array_equal(out_verts[out_faces[0, 1]], [0, 1, 0])
        np.testing.assert_array_equal(out_verts[out_faces[0, 2]], [0, 0, 1])

    def test_multiple_faces(self):
        verts = np.array([
            [0, 0, 0],
            [1, 0, 0],
            [0, 1, 0],
            [1, 1, 0],
        ], dtype=np.float64)
        faces = np.array([[0, 1, 2], [1, 3, 2]], dtype=np.int64)

        out_verts, out_faces = _extract_and_simplify(verts, faces, ratio=1.0)

        assert out_verts.shape == (4, 3)
        assert out_faces.shape == (2, 3)


class TestSimplifyProtoByMaterial:
    """Tests for per-material simplification (ratio=1.0, no Blender)."""

    def test_splits_by_material(self):
        verts = np.array([
            [0, 0, 0], [1, 0, 0], [0, 1, 0],  # face 0
            [2, 0, 0], [3, 0, 0], [2, 1, 0],  # face 1
        ], dtype=np.float64)
        faces = np.array([[0, 1, 2], [3, 4, 5]], dtype=np.int64)
        face_mats = np.array([0, 1], dtype=np.int32)
        mat_names = ["bark", "leaf_top"]

        out_verts, out_faces, out_mats = _simplify_proto_by_material(
            verts, faces, face_mats, mat_names,
            wood_ratio=1.0, leaf_ratio=1.0, fruit_ratio=1.0,
            global_offset=0,
        )

        assert out_verts.shape[0] == 6
        assert out_faces.shape[0] == 2
        assert len(out_mats) == 2
        assert set(out_mats.tolist()) == {0, 1}

    def test_empty_faces(self):
        verts = np.array([[0, 0, 0]], dtype=np.float64)
        faces = np.empty((0, 3), dtype=np.int64)
        face_mats = np.empty(0, dtype=np.int32)

        out_verts, out_faces, out_mats = _simplify_proto_by_material(
            verts, faces, face_mats, ["bark"],
            wood_ratio=1.0, leaf_ratio=1.0, fruit_ratio=1.0,
            global_offset=0,
        )

        assert out_verts.shape[0] == 0
        assert out_faces.shape[0] == 0

    def test_global_offset_applied(self):
        verts = np.array([
            [0, 0, 0], [1, 0, 0], [0, 1, 0],
        ], dtype=np.float64)
        faces = np.array([[0, 1, 2]], dtype=np.int64)
        face_mats = np.array([0], dtype=np.int32)

        _, out_faces, _ = _simplify_proto_by_material(
            verts, faces, face_mats, ["leaf_mat"],
            wood_ratio=1.0, leaf_ratio=1.0, fruit_ratio=1.0,
            global_offset=100,
        )

        assert out_faces.min() >= 100
