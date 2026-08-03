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
    simplify_trunk_mesh,
)
import growpy.io.helios.mesh_simplify as mesh_simplify_module


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
            bark_ratio=1.0, wood_ratio=1.0, leaf_ratio=1.0, fruit_ratio=1.0,
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
            bark_ratio=1.0, wood_ratio=1.0, leaf_ratio=1.0, fruit_ratio=1.0,
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
            bark_ratio=1.0, wood_ratio=1.0, leaf_ratio=1.0, fruit_ratio=1.0,
            global_offset=100,
        )

        assert out_faces.min() >= 100


class TestChunkedTrunkDecimation:
    """Tests for chunked decimation on very large trunk meshes.

    _decimate_with_bpy is monkeypatched throughout -- these tests exercise
    the chunking/reassembly logic, not Blender's actual decimation, so they
    run without bpy/The Grove installed.
    """

    @staticmethod
    def _make_stacked_mesh(num_faces):
        """Build num_faces disjoint triangles stacked along Z (one per integer z)."""
        verts = []
        faces = []
        for i in range(num_faces):
            base = len(verts)
            verts.extend([[0.0, 0.0, float(i)], [1.0, 0.0, float(i)], [0.0, 1.0, float(i)]])
            faces.append([base, base + 1, base + 2])
        return np.array(verts, dtype=np.float64), np.array(faces, dtype=np.int64)

    @staticmethod
    def _fake_decimate(calls):
        def _decimate(vertices, faces_in, ratio):
            calls.append(len(faces_in))
            keep = max(1, int(len(faces_in) * ratio))
            return vertices, faces_in[:keep]
        return _decimate

    def test_below_chunk_limit_calls_decimate_once(self, monkeypatch):
        monkeypatch.setattr(mesh_simplify_module, "CHUNK_FACE_LIMIT", 10)
        verts, faces = self._make_stacked_mesh(10)
        calls = []
        monkeypatch.setattr(
            mesh_simplify_module, "_decimate_with_bpy", self._fake_decimate(calls)
        )

        _, dec_faces, dec_uvs = simplify_trunk_mesh(verts, faces, None, 0.5)

        assert len(calls) == 1
        assert dec_uvs is None

    def test_above_chunk_limit_splits_into_multiple_chunks(self, monkeypatch):
        monkeypatch.setattr(mesh_simplify_module, "CHUNK_FACE_LIMIT", 10)
        verts, faces = self._make_stacked_mesh(30)
        calls = []
        monkeypatch.setattr(
            mesh_simplify_module, "_decimate_with_bpy", self._fake_decimate(calls)
        )

        _, dec_faces, dec_uvs = simplify_trunk_mesh(verts, faces, None, 0.5)

        assert len(calls) > 1
        # Roughly ratio * input (30 * 0.5 = 15), allowing for per-chunk rounding.
        assert 10 <= len(dec_faces) <= 20
        assert dec_uvs is None


class TestBarkWoodRatioSplit:
    """Tests that bark and wood take independent simplification ratios."""

    def test_distinct_ratios_produce_different_face_counts(self, monkeypatch):
        def fake_decimate(vertices, faces_in, ratio):
            keep = max(1, int(len(faces_in) * ratio))
            return vertices, faces_in[:keep]
        monkeypatch.setattr(mesh_simplify_module, "_decimate_with_bpy", fake_decimate)

        num_bark, num_wood = 4, 4
        verts = []
        faces = []
        face_mats = []
        for i in range(num_bark):
            base = len(verts)
            verts.extend([[0, 0, i], [1, 0, i], [0, 1, i]])
            faces.append([base, base + 1, base + 2])
            face_mats.append(0)
        for i in range(num_wood):
            base = len(verts)
            verts.extend([[10, 0, i], [11, 0, i], [10, 1, i]])
            faces.append([base, base + 1, base + 2])
            face_mats.append(1)

        verts = np.array(verts, dtype=np.float64)
        faces = np.array(faces, dtype=np.int64)
        face_mats = np.array(face_mats, dtype=np.int32)
        mat_names = ["bark", "twig_wood"]

        _, _, out_mats = _simplify_proto_by_material(
            verts, faces, face_mats, mat_names,
            bark_ratio=0.25, wood_ratio=0.75, leaf_ratio=1.0, fruit_ratio=1.0,
            global_offset=0,
        )

        bark_kept = int(np.sum(out_mats == 0))
        wood_kept = int(np.sum(out_mats == 1))
        assert bark_kept == 1
        assert wood_kept == 3
        assert bark_kept != wood_kept
