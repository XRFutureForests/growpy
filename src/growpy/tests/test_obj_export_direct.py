"""Tests for growpy.io.helios.obj_export's direct (USD-free) trunk/twig path.

Covers _scale_trunk_points_radially, _twig_placements_to_instance_arrays,
_read_twig_prototypes_for_direct_export, and convert_tree_to_obj_direct
(export_mode = "helios", XRFF-311). Twig USD prototype files are built with
pxr directly -- these tests need no Grove, only bpy's bundled USD (already
a dependency of every other obj_export test in this suite).
"""

import numpy as np
import pytest

from growpy.core.twig import TwigPlacement

# obj_export imports bpy and calls bpy.utils.expose_bundled_modules(), which
# is what makes `pxr` importable at all in this environment -- import it
# first so the pxr import below succeeds.
from growpy.io.helios.obj_export import (  # noqa: F401
    _read_twig_prototypes_for_direct_export,
    _trunk_points_for_obj,
    _twig_placements_to_instance_arrays,
    convert_tree_to_obj_direct,
)

from pxr import Usd, UsdGeom, UsdShade  # noqa: E402


class _FakePoint:
    def __init__(self, x, y, z):
        self.x, self.y, self.z = x, y, z


class _FakeModel:
    """Stand-in for a Grove model: exposes only what convert_tree_to_obj_direct
    and extract_twig_placements_from_model actually read.
    """

    def __init__(
        self, points, faces, twig_locations, twig_directions, twig_orientations,
        point_attribute_bone_id=None,
    ):
        self.points = points
        self.faces = faces
        self._twig_locations = twig_locations
        self._twig_directions = twig_directions
        self._twig_orientations = twig_orientations
        if point_attribute_bone_id is not None:
            self.point_attribute_bone_id = point_attribute_bone_id

    def get_twig_locations(self):
        return self._twig_locations

    def get_twig_directions(self):
        return self._twig_directions

    def get_twig_orientations(self):
        return self._twig_orientations


def _write_minimal_twig_usd(path, material_names):
    """Write a minimal static twig USD: one triangle per material, bound
    via GeomSubset so _read_twig_mesh_classified can classify faces.
    """
    stage = Usd.Stage.CreateNew(str(path))
    mesh = UsdGeom.Mesh.Define(stage, "/twig")

    points = []
    face_indices = []
    face_counts = []
    for i, _ in enumerate(material_names):
        base = i * 3
        points.extend([(base, 0, 0), (base + 1, 0, 0), (base, 1, 0)])
        face_indices.extend([base, base + 1, base + 2])
        face_counts.append(3)

    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexIndicesAttr(face_indices)
    mesh.CreateFaceVertexCountsAttr(face_counts)

    for i, mat_name in enumerate(material_names):
        subset = UsdGeom.Subset.Define(stage, f"/twig/subset_{i}")
        subset.CreateIndicesAttr([i])
        subset.CreateElementTypeAttr("face")
        material = UsdShade.Material.Define(stage, f"/twig/{mat_name}")
        UsdShade.MaterialBindingAPI(subset.GetPrim()).Bind(material)

    stage.GetRootLayer().Save()
    return path


# A Z-up tree like Grove's: a 10 m trunk bone and a 5 m horizontal branch bone at
# 5 m. Bones are (id, parent_id, start, end, radius) as from grove.tag_bone_id().
_BONES = [
    (0, -1, _FakePoint(0.0, 0.0, 0.0), _FakePoint(0.0, 0.0, 10.0), 0.3),
    (1, 0, _FakePoint(0.0, 0.0, 5.0), _FakePoint(5.0, 0.0, 5.0), 0.1),
]
_TREE_POINTS = [
    _FakePoint(0.2, 0.0, 1.0),  # trunk surface at 1 m (below breast height)
    _FakePoint(0.0, 0.2, 1.0),
    _FakePoint(0.0, 0.0, 10.0),  # stem tip, on the trunk axis
    _FakePoint(3.0, 0.0, 5.2),  # branch surface, 3 m out, 0.2 m above its axis
]
_TREE_BONE_IDS = [0, 0, 0, 1]


def _branch_scale(radial_scale, z, tree_height=10.0):
    """Expected per-height scale: full at 1.3 m, 30 % of the correction at 0.85 h."""
    start, end = 1.3, max(2.3, 0.85 * tree_height)
    crown = 1.0 + (radial_scale - 1.0) * 0.3
    t = (z - start) / (end - start)
    t = t * t * (3.0 - 2.0 * t)
    return radial_scale + (crown - radial_scale) * t


class TestTrunkPointsForObj:
    def _model(self, with_bone_ids=True):
        return _FakeModel(
            points=_TREE_POINTS, faces=[[0, 1, 2], [0, 2, 3]],
            twig_locations=[], twig_directions=[], twig_orientations=[],
            point_attribute_bone_id=_TREE_BONE_IDS if with_bone_ids else None,
        )

    def test_identity_when_scale_is_one(self):
        pts = _trunk_points_for_obj(self._model(), _TREE_POINTS, _BONES, 1.0)
        assert pts == [(p.x, p.y, p.z) for p in _TREE_POINTS]

    def test_scales_radii_about_each_bone_and_keeps_positions(self):
        pts = np.array(_trunk_points_for_obj(self._model(), _TREE_POINTS, _BONES, 0.5))
        # trunk ring at 1 m: radius halved, height unchanged
        np.testing.assert_allclose(pts[0], [0.1, 0.0, 1.0], atol=1e-6)
        np.testing.assert_allclose(pts[1], [0.0, 0.1, 1.0], atol=1e-6)
        # stem tip on the axis: not moved, so the tree keeps its height
        np.testing.assert_allclose(pts[2], [0.0, 0.0, 10.0], atol=1e-6)
        # branch point: stays 3 m out along its branch (crown spread kept); only
        # its 0.2 m offset from the branch axis shrinks by the height-blended scale
        s = _branch_scale(0.5, 5.2)
        np.testing.assert_allclose(pts[3], [3.0, 0.0, 5.0 + 0.2 * s], atol=1e-5)

    def test_without_bone_data_points_are_unscaled(self):
        model = self._model(with_bone_ids=False)
        pts = _trunk_points_for_obj(model, _TREE_POINTS, _BONES, 0.5)
        assert pts == [(p.x, p.y, p.z) for p in _TREE_POINTS]
        assert _trunk_points_for_obj(self._model(), _TREE_POINTS, None, 0.5) == pts

    def test_returns_plain_floats_for_twig_placement(self):
        pts = _trunk_points_for_obj(self._model(), _TREE_POINTS, _BONES, 0.5)
        assert all(type(c) is float for p in pts for c in p)


class TestTwigPlacementsToInstanceArrays:
    def test_empty_placements_returns_empty_arrays(self):
        positions, orientations, scales, proto_indices = (
            _twig_placements_to_instance_arrays({}, {})
        )
        assert positions.shape == (0, 3)
        assert orientations.shape == (0, 4)
        assert scales.shape == (0,)
        assert proto_indices.shape == (0,)

    def test_single_placement_produces_one_instance(self):
        placement = TwigPlacement(
            type="twig_long",
            position=(1.0, 2.0, 3.0),
            normal=(0.0, 0.0, 1.0),
            scale=0.8,
        )
        twig_placements = {"twig_long": [placement]}
        type_to_proto_idx = {"twig_long": 0}

        positions, orientations, scales, proto_indices = (
            _twig_placements_to_instance_arrays(twig_placements, type_to_proto_idx)
        )

        assert positions.shape == (1, 3)
        np.testing.assert_allclose(positions[0], [1.0, 2.0, 3.0])
        assert orientations.shape == (1, 4)
        # Quaternion should be normalized (unit length).
        np.testing.assert_allclose(np.linalg.norm(orientations[0]), 1.0, atol=1e-6)
        assert scales[0] == 0.8
        assert proto_indices[0] == 0

    def test_unresolved_twig_type_is_skipped(self):
        placement = TwigPlacement(
            type="twig_dead", position=(0.0, 0.0, 0.0), normal=(0.0, 0.0, 1.0),
        )
        twig_placements = {"twig_dead": [placement]}
        # No matching entry in type_to_proto_idx (e.g. prototype mesh missing).
        positions, _, _, _ = _twig_placements_to_instance_arrays(twig_placements, {})
        assert positions.shape == (0, 3)

    def test_multiple_types_get_distinct_proto_indices(self):
        p1 = TwigPlacement(type="twig_long", position=(0, 0, 0), normal=(0, 0, 1))
        p2 = TwigPlacement(type="twig_short", position=(1, 0, 0), normal=(0, 0, 1))
        twig_placements = {"twig_long": [p1], "twig_short": [p2]}
        type_to_proto_idx = {"twig_long": 0, "twig_short": 1}

        _, _, _, proto_indices = _twig_placements_to_instance_arrays(
            twig_placements, type_to_proto_idx
        )
        assert set(proto_indices.tolist()) == {0, 1}


class TestReadTwigPrototypesForDirectExport:
    def test_resolves_first_file_per_type(self, tmp_path):
        twig_path = _write_minimal_twig_usd(
            tmp_path / "twig_long_static.usda", ["bark", "leaf_top"]
        )
        twig_placements = {"twig_long": [
            TwigPlacement(type="twig_long", position=(0, 0, 0), normal=(0, 0, 1))
        ]}
        twig_usd_map = {"twig_long": [twig_path]}

        classified_protos, type_to_proto_idx = _read_twig_prototypes_for_direct_export(
            twig_placements, twig_usd_map, "usda",
        )

        assert "twig_long" in type_to_proto_idx
        proto_idx = type_to_proto_idx["twig_long"]
        verts, wood_faces, leaf_faces = classified_protos[proto_idx]
        assert verts.shape[0] == 6  # 2 materials x 3 verts/triangle
        assert len(wood_faces) == 1
        assert len(leaf_faces) == 1

    def test_missing_file_skipped(self, tmp_path):
        twig_placements = {"twig_long": [
            TwigPlacement(type="twig_long", position=(0, 0, 0), normal=(0, 0, 1))
        ]}
        twig_usd_map = {"twig_long": [tmp_path / "does_not_exist.usda"]}

        classified_protos, type_to_proto_idx = _read_twig_prototypes_for_direct_export(
            twig_placements, twig_usd_map, "usda",
        )
        assert classified_protos == {}
        assert type_to_proto_idx == {}

    def test_empty_placement_list_skipped(self, tmp_path):
        twig_path = _write_minimal_twig_usd(tmp_path / "twig_long_static.usda", ["bark"])
        classified_protos, type_to_proto_idx = _read_twig_prototypes_for_direct_export(
            {"twig_long": []}, {"twig_long": [twig_path]}, "usda",
        )
        assert classified_protos == {}
        assert type_to_proto_idx == {}


class TestConvertTreeToObjDirect:
    def test_trunk_only_no_twigs(self, tmp_path):
        model = _FakeModel(
            points=[_FakePoint(0, 0, 0), _FakePoint(1, 0, 0), _FakePoint(0, 1, 0)],
            faces=[[0, 1, 2]],
            twig_locations=[],
            twig_directions=[],
            twig_orientations=[],
        )

        obj_path = convert_tree_to_obj_direct(
            model=model,
            twig_usd_map={},
            output_dir=tmp_path,
            species_name="Selected European beech",
            tree_id="1",
        )

        assert obj_path is not None
        assert obj_path.exists()
        content = obj_path.read_text()
        assert "usemtl bark" in content
        assert content.count("v ") == 3

    def test_empty_model_returns_none(self, tmp_path):
        model = _FakeModel(
            points=[], faces=[], twig_locations=[], twig_directions=[], twig_orientations=[],
        )
        result = convert_tree_to_obj_direct(
            model=model,
            twig_usd_map={},
            output_dir=tmp_path,
            species_name="Selected European beech",
            tree_id="1",
        )
        assert result is None

    def test_with_classification_applies_prefix_and_codes(self, tmp_path):
        model = _FakeModel(
            points=[_FakePoint(0, 0, 0), _FakePoint(1, 0, 0), _FakePoint(0, 1, 0)],
            faces=[[0, 1, 2]],
            twig_locations=[],
            twig_directions=[],
            twig_orientations=[],
        )

        obj_path = convert_tree_to_obj_direct(
            model=model,
            twig_usd_map={},
            output_dir=tmp_path,
            species_name="Selected European beech",
            tree_id="1",
            mat_prefix="t01_",
            classification_codes={"bark": 21, "wood": 21, "leaf": 11, "fruit": 21},
        )

        obj_content = obj_path.read_text()
        mtl_content = obj_path.with_suffix(".mtl").read_text()
        assert "usemtl t01_bark" in obj_content
        assert "newmtl t01_bark" in mtl_content
        assert "helios_classification 21" in mtl_content

    @staticmethod
    def _tall_model():
        return _FakeModel(
            points=_TREE_POINTS,
            faces=[[0, 1, 2], [0, 2, 3]],
            twig_locations=[],
            twig_directions=[],
            twig_orientations=[],
            point_attribute_bone_id=_TREE_BONE_IDS,
        )

    @staticmethod
    def _verts(obj_path):
        rows = [r for r in obj_path.read_text().splitlines() if r.startswith("v ")]
        return np.array([[float(x) for x in r.split()[1:4]] for r in rows])

    def _convert(self, tmp_path, up_axis):
        return convert_tree_to_obj_direct(
            model=self._tall_model(),
            twig_usd_map={},
            output_dir=tmp_path,
            species_name="Selected European beech",
            tree_id="1",
            radial_scale=0.5,
            bones_info=_BONES,
            up_axis=up_axis,
        )

    def test_radial_scale_per_bone_in_z_up_obj(self, tmp_path):
        v = self._verts(self._convert(tmp_path, "z"))
        np.testing.assert_allclose(v[:, 2].max(), 10.0)  # height unchanged
        np.testing.assert_allclose(v[0], [0.1, 0.0, 1.0], atol=1e-5)  # trunk radius halved
        np.testing.assert_allclose(v[3, :2], [3.0, 0.0], atol=1e-5)  # branch stays put

    def test_radial_scale_per_bone_in_y_up_obj(self, tmp_path):
        v = self._verts(self._convert(tmp_path, "y"))
        # Z-up height lands on OBJ y; the branch reach stays on OBJ x
        np.testing.assert_allclose(v[:, 1].max(), 10.0)
        np.testing.assert_allclose(v[0], [0.1, 1.0, 0.0], atol=1e-5)
        np.testing.assert_allclose(v[3, 0], 3.0, atol=1e-5)

    def test_name_sets_file_stem(self, tmp_path):
        obj_path = convert_tree_to_obj_direct(
            model=self._tall_model(),
            twig_usd_map={},
            output_dir=tmp_path,
            species_name="Selected European beech",
            tree_id="1",
            name="European_Beech_r07_h20m_d29cm_full",
        )
        assert obj_path.name == "European_Beech_r07_h20m_d29cm_full_helios.obj"
        assert obj_path.with_suffix(".mtl").exists()

    def test_two_stages_do_not_overwrite(self, tmp_path):
        paths = [
            convert_tree_to_obj_direct(
                model=self._tall_model(),
                twig_usd_map={},
                output_dir=tmp_path,
                species_name="Selected European beech",
                tree_id="1",
                name=f"European_Beech_r07_{stage}_full",
            )
            for stage in ("h15m_d22cm", "h20m_d29cm")
        ]
        assert paths[0] != paths[1]
        assert all(p.exists() for p in paths)
