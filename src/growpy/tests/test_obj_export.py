"""Tests for growpy.io.helios.obj_export utility functions."""

import numpy as np

from growpy.io.helios.obj_export import (
    WOOD_MATERIAL_KEYWORDS,
    _bake_twig_instances,
    _classified_twig_cache,
    _find_assembly_files,
    _fmt_vert,
    _quat_to_rotation_matrix,
    _resolve_to_static,
    _write_helios_mtl,
    clear_twig_cache,
)


class TestResolveToStatic:
    """Tests for _resolve_to_static filename conversion."""

    def test_converts_skeletal_to_static(self):
        assert _resolve_to_static("tree_skeletal.usda") == "tree_static.usda"

    def test_no_match_returns_unchanged(self):
        assert _resolve_to_static("tree_static.usda") == "tree_static.usda"

    def test_handles_complex_name(self):
        result = _resolve_to_static("norway_spruce_foliage_a_skeletal.usda")
        assert result == "norway_spruce_foliage_a_static.usda"


class TestClearTwigCache:
    """Tests for clear_twig_cache."""

    def test_clears_populated_cache(self):
        _classified_twig_cache["dummy"] = (None, None, None)
        clear_twig_cache()
        assert len(_classified_twig_cache) == 0

    def test_clears_empty_cache(self):
        clear_twig_cache()
        assert len(_classified_twig_cache) == 0


class TestWoodMaterialKeywords:
    """Tests for the WOOD_MATERIAL_KEYWORDS constant."""

    def test_contains_bark(self):
        assert "bark" in WOOD_MATERIAL_KEYWORDS

    def test_contains_branch(self):
        assert "branch" in WOOD_MATERIAL_KEYWORDS

    def test_is_tuple(self):
        assert isinstance(WOOD_MATERIAL_KEYWORDS, tuple)


class TestQuatToRotationMatrix:
    """Tests for _quat_to_rotation_matrix."""

    def test_identity_quaternion(self):
        mat = _quat_to_rotation_matrix(1.0, 0.0, 0.0, 0.0)
        np.testing.assert_allclose(mat, np.eye(3), atol=1e-10)

    def test_90_deg_around_z(self):
        # 90 degrees around Z: w=cos(45)=sqrt(2)/2, z=sin(45)=sqrt(2)/2
        s = np.sqrt(2) / 2
        mat = _quat_to_rotation_matrix(s, 0.0, 0.0, s)
        # Expected: x->y, y->-x, z->z
        expected = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=np.float64)
        np.testing.assert_allclose(mat, expected, atol=1e-10)

    def test_180_deg_around_x(self):
        # 180 degrees around X: w=0, x=1
        mat = _quat_to_rotation_matrix(0.0, 1.0, 0.0, 0.0)
        expected = np.array([[1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float64)
        np.testing.assert_allclose(mat, expected, atol=1e-10)

    def test_returns_3x3(self):
        mat = _quat_to_rotation_matrix(0.5, 0.5, 0.5, 0.5)
        assert mat.shape == (3, 3)

    def test_orthogonal(self):
        mat = _quat_to_rotation_matrix(0.5, 0.5, 0.5, 0.5)
        product = mat @ mat.T
        np.testing.assert_allclose(product, np.eye(3), atol=1e-10)


class TestFmtVert:
    """Tests for _fmt_vert."""

    def test_z_up(self):
        v = np.array([1.0, 2.0, 3.0])
        result = _fmt_vert(v, "z")
        assert result == "v 1.000000 2.000000 3.000000\n"

    def test_y_up_swaps_axes(self):
        v = np.array([1.0, 2.0, 3.0])
        result = _fmt_vert(v, "y")
        # Z-up to Y-up: x, z, -y
        assert result == "v 1.000000 3.000000 -2.000000\n"

    def test_negative_values(self):
        v = np.array([-1.5, 0.0, 2.5])
        result = _fmt_vert(v, "z")
        assert result.startswith("v -1.500000")


class TestBakeTwigInstances:
    """Tests for _bake_twig_instances."""

    def test_single_instance_identity(self):
        proto_verts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        proto_faces = np.array([[0, 1, 2]])
        proto_meshes = {0: (proto_verts, proto_faces)}
        positions = np.array([[0.0, 0.0, 0.0]])
        orientations = np.array([[1.0, 0.0, 0.0, 0.0]])  # identity quat
        scales = np.array([[1.0, 1.0, 1.0]])
        proto_indices = np.array([0])

        verts, faces = _bake_twig_instances(
            proto_meshes, positions, orientations, scales, proto_indices
        )
        np.testing.assert_allclose(verts, proto_verts, atol=1e-6)
        np.testing.assert_array_equal(faces, proto_faces)

    def test_translation(self):
        proto_verts = np.array([[0.0, 0.0, 0.0]])
        proto_faces = np.array([[0, 0, 0]])
        proto_meshes = {0: (proto_verts, proto_faces)}
        positions = np.array([[5.0, 3.0, 1.0]])
        orientations = np.array([[1.0, 0.0, 0.0, 0.0]])
        scales = np.array([[1.0, 1.0, 1.0]])
        proto_indices = np.array([0])

        verts, _ = _bake_twig_instances(
            proto_meshes, positions, orientations, scales, proto_indices
        )
        np.testing.assert_allclose(verts[0], [5.0, 3.0, 1.0], atol=1e-6)

    def test_missing_proto_index_skipped(self):
        proto_meshes = {0: (np.array([[0, 0, 0]]), np.array([[0, 0, 0]]))}
        positions = np.array([[0.0, 0.0, 0.0]])
        orientations = np.array([[1.0, 0.0, 0.0, 0.0]])
        scales = np.array([[1.0, 1.0, 1.0]])
        proto_indices = np.array([99])  # Not in proto_meshes

        verts, faces = _bake_twig_instances(
            proto_meshes, positions, orientations, scales, proto_indices
        )
        assert len(verts) == 0
        assert len(faces) == 0

    def test_multiple_instances_face_offset(self):
        proto_verts = np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
        proto_faces = np.array([[0, 1, 2]])
        proto_meshes = {0: (proto_verts, proto_faces)}
        positions = np.array([[0.0, 0.0, 0.0], [10.0, 0.0, 0.0]])
        orientations = np.array([[1.0, 0.0, 0.0, 0.0], [1.0, 0.0, 0.0, 0.0]])
        scales = np.array([[1.0, 1.0, 1.0], [1.0, 1.0, 1.0]])
        proto_indices = np.array([0, 0])

        verts, faces = _bake_twig_instances(
            proto_meshes, positions, orientations, scales, proto_indices
        )
        assert len(verts) == 6
        assert len(faces) == 2
        # Second face should have offset indices
        np.testing.assert_array_equal(faces[1], [3, 4, 5])


class _FakeConfig:
    """Minimal stand-in for GrowPyConfig -- resolvers only read export_usd_format."""

    def __init__(self, export_usd_format: str):
        self.export_usd_format = export_usd_format


class TestFindAssemblyFiles:
    """Tests for _find_assembly_files layout/extension discovery (XRFF-281)."""

    def test_discovers_tree_layout_usdc(self, tmp_path):
        target = tmp_path / "european_beech" / "tree_0001"
        target.mkdir(parents=True)
        (target / "european_beech_assembly_static.usdc").touch()

        found = _find_assembly_files(tmp_path, _FakeConfig("usdc"))
        assert found == [target / "european_beech_assembly_static.usdc"]

    def test_discovers_tree_layout_usda(self, tmp_path):
        target = tmp_path / "european_beech" / "tree_0001"
        target.mkdir(parents=True)
        (target / "european_beech_assembly_static.usda").touch()

        found = _find_assembly_files(tmp_path, _FakeConfig("usda"))
        assert found == [target / "european_beech_assembly_static.usda"]

    def test_wrong_extension_not_matched(self, tmp_path):
        target = tmp_path / "european_beech" / "tree_0001"
        target.mkdir(parents=True)
        (target / "european_beech_assembly_static.usda").touch()

        # Config says usdc, only a .usda file exists on disk -- must not match.
        assert _find_assembly_files(tmp_path, _FakeConfig("usdc")) == []

    def test_ignores_dataset_mode_layout(self, tmp_path):
        # Dataset mode writes species/rNN/, not species/tree_NNNN/ -- the
        # decided scope for XRFF-281 is layout mode only (see module docstring
        # on _find_assembly_files), so these must not be discovered.
        target = tmp_path / "european_beech" / "r00"
        target.mkdir(parents=True)
        (target / "european_beech_assembly_static.usdc").touch()

        assert _find_assembly_files(tmp_path, _FakeConfig("usdc")) == []



class TestExportForestObjEmptyDiagnostic:
    """Empty discovery must name the searched pattern, not fail silently (XRFF-297)."""

    def test_empty_result_names_pattern(self, tmp_path, caplog):
        import logging

        import pandas as pd

        from growpy.io.helios.obj_export import export_forest_obj

        forest_data = pd.DataFrame({"fid": [], "x": [], "y": [], "z": []})
        with caplog.at_level(logging.WARNING):
            result = export_forest_obj(tmp_path, forest_data)

        assert result == []
        messages = " ".join(r.message for r in caplog.records)
        assert "assembly_static" in messages
        assert str(tmp_path) in messages


class TestWriteHeliosMtl:
    """Tests for _write_helios_mtl, including the classification regression guard."""

    def test_default_args_unchanged_from_pre_classification_output(self, tmp_path):
        """With classification_codes=None and mat_prefix="" (the defaults),
        output must be identical to before per-tree classification existed.
        """
        mtl_path = tmp_path / "tree.mtl"
        _write_helios_mtl(mtl_path, bark_texture=None, helios_spectra_leaves="deciduous")
        content = mtl_path.read_text()

        assert "newmtl bark\n" in content
        assert "newmtl twig_wood\n" in content
        assert "newmtl twig_leaf\n" in content
        assert content.count("helios_classification 4\n") == 3
        assert "t01_" not in content

    def test_classification_codes_applied_per_material(self, tmp_path):
        mtl_path = tmp_path / "tree.mtl"
        codes = {"bark": 23, "wood": 23, "leaf": 13, "fruit": 23}
        _write_helios_mtl(
            mtl_path,
            bark_texture=None,
            helios_spectra_leaves="deciduous",
            classification_codes=codes,
            mat_prefix="t03_",
        )
        content = mtl_path.read_text()

        assert "newmtl t03_bark\n" in content
        assert "newmtl t03_twig_wood\n" in content
        assert "newmtl t03_twig_leaf\n" in content
        assert content.count("helios_classification 23\n") == 2
        assert content.count("helios_classification 13\n") == 1

    def test_missing_material_in_codes_falls_back_to_four(self, tmp_path):
        mtl_path = tmp_path / "tree.mtl"
        _write_helios_mtl(
            mtl_path,
            bark_texture=None,
            helios_spectra_leaves="deciduous",
            classification_codes={},
            mat_prefix="t01_",
        )
        content = mtl_path.read_text()
        assert content.count("helios_classification 4\n") == 3
