"""Tests for baking a Grove subtree into one welded USD prototype (XRFF-357).

The geometry functions here are deliberately pxr-free -- `pxr` is imported
inside the two USD functions only -- so everything except the writer runs
without USD installed.
"""

import math
from types import SimpleNamespace

import pytest

from growpy.io.usd.compound_part_export import (
    PartMesh,
    align_to_forward_quat,
    extract_subtree_mesh,
    merge_mesh,
    normalise_part_frame,
    quat_multiply,
    subtree_branch_ids,
)


def _vec(x, y, z):
    """Stand-in for a Grove Vector, which exposes .x/.y/.z and is not indexable."""
    return SimpleNamespace(x=x, y=y, z=z)


class TestSubtreeBranchIds:
    """`face_attribute_branch_id == walker_index + 1`, verified on a real beech."""

    def test_single_branch(self):
        assert subtree_branch_ids([[]], 0) == {1}

    def test_collects_the_whole_subtree_and_adds_one(self):
        # 0 -> 1 -> 3, and 0 -> 2
        children = [[1, 2], [3], [], []]
        assert subtree_branch_ids(children, 0) == {1, 2, 3, 4}
        assert subtree_branch_ids(children, 1) == {2, 4}
        assert subtree_branch_ids(children, 2) == {3}

    def test_deep_chain_does_not_recurse(self):
        depth = 20000
        children = [[i + 1] for i in range(depth - 1)] + [[]]
        assert len(subtree_branch_ids(children, 0)) == depth


class TestExtractSubtreeMesh:
    """Selecting a subtree's woody faces out of a built Grove model."""

    def _model(self):
        # Two quads on branch id 1, one triangle on branch id 2.
        points = [_vec(float(i), 0.0, 0.0) for i in range(8)]
        faces = [[0, 1, 2, 3], [4, 5, 6, 7], [0, 1, 4]]
        # Face-varying: one (u, v) per FACE-CORNER -- 4 + 4 + 3 = 11.
        uvs = [(float(i), float(i) * 2) for i in range(11)]
        face_branch_ids = [1, 1, 2]
        return faces, points, uvs, face_branch_ids

    def test_selects_only_the_requested_branches(self):
        faces, points, uvs, ids = self._model()
        part = extract_subtree_mesh(faces, points, uvs, ids, {1})
        # Two quads fan-triangulate to two triangles each.
        assert len(part.faces) == 4
        assert len(part.points) == 8

    def test_remaps_point_indices_into_the_part(self):
        faces, points, uvs, ids = self._model()
        part = extract_subtree_mesh(faces, points, uvs, ids, {2})
        assert len(part.points) == 3
        assert all(0 <= i < 3 for face in part.faces for i in face)

    def test_slices_face_varying_uvs_by_corner_offset_not_face_index(self):
        # The triangle is face 2 but its corners start at offset 8, so slicing
        # by face index would hand it UVs 2..4 instead of 8..10.
        faces, points, uvs, ids = self._model()
        part = extract_subtree_mesh(faces, points, uvs, ids, {2})
        assert part.uvs == [(8.0, 16.0), (9.0, 18.0), (10.0, 20.0)]

    def test_uv_count_matches_triangulated_corners(self):
        faces, points, uvs, ids = self._model()
        part = extract_subtree_mesh(faces, points, uvs, ids, {1, 2})
        assert len(part.uvs) == len(part.faces) * 3
        part.validate()

    def test_drops_grove_twig_marker_faces(self):
        # The part bakes real twig assets at those placements, so keeping the
        # markers buries a flat quad inside every leaf cluster.
        faces, points, uvs, ids = self._model()
        part = extract_subtree_mesh(
            faces, points, uvs, ids, {1, 2}, twig_face_mask=[False, True, False]
        )
        assert len(part.faces) == 3  # one quad (2 tris) + one triangle

    def test_keeps_twig_faces_when_no_mask_is_given(self):
        faces, points, uvs, ids = self._model()
        part = extract_subtree_mesh(faces, points, uvs, ids, {1, 2})
        assert len(part.faces) == 5

    def test_empty_selection_yields_an_empty_part(self):
        faces, points, uvs, ids = self._model()
        part = extract_subtree_mesh(faces, points, uvs, ids, set())
        assert part.faces == [] and part.points == []
        part.validate()

    def test_names_the_woody_material(self):
        faces, points, uvs, ids = self._model()
        part = extract_subtree_mesh(
            faces, points, uvs, ids, {1}, material="european_beech_bark"
        )
        assert part.materials == ["european_beech_bark"]
        assert set(part.face_materials) == {0}


class TestAlignToForwardQuat:
    """+X is the forward axis: `core.twig._quat_forward` rotates +X."""

    def _rotate(self, quat, vector):
        w, x, y, z = quat
        px, py, pz = vector
        tx = 2.0 * (y * pz - z * py)
        ty = 2.0 * (z * px - x * pz)
        tz = 2.0 * (x * py - y * px)
        return (
            px + w * tx + (y * tz - z * ty),
            py + w * ty + (z * tx - x * tz),
            pz + w * tz + (x * ty - y * tx),
        )

    @pytest.mark.parametrize(
        "direction",
        [
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, -1.0),
            (-1.0, 0.0, 0.0),
            (0.3, -0.7, 0.65),
            (2.0, 2.0, 2.0),
        ],
    )
    def test_rotates_the_direction_onto_plus_x(self, direction):
        quat = align_to_forward_quat(direction)
        length = math.sqrt(sum(c * c for c in direction))
        unit = tuple(c / length for c in direction)
        result = self._rotate(quat, unit)
        assert result[0] == pytest.approx(1.0, abs=1e-6)
        assert result[1] == pytest.approx(0.0, abs=1e-6)
        assert result[2] == pytest.approx(0.0, abs=1e-6)

    def test_returns_a_unit_quaternion(self):
        for direction in ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.1, 0.2, -0.9)):
            quat = align_to_forward_quat(direction)
            assert math.sqrt(sum(c * c for c in quat)) == pytest.approx(1.0, abs=1e-6)

    def test_already_forward_is_the_identity(self):
        assert align_to_forward_quat((1.0, 0.0, 0.0)) == (1.0, 0.0, 0.0, 0.0)

    def test_zero_direction_does_not_divide_by_zero(self):
        assert align_to_forward_quat((0.0, 0.0, 0.0)) == (1.0, 0.0, 0.0, 0.0)


class TestQuatMultiply:
    def test_identity(self):
        q = (0.5, 0.5, 0.5, 0.5)
        assert quat_multiply((1.0, 0.0, 0.0, 0.0), q) == pytest.approx(q)

    def test_stays_unit_length(self):
        a = align_to_forward_quat((0.0, 1.0, 0.0))
        b = align_to_forward_quat((0.0, 0.0, 1.0))
        product = quat_multiply(a, b)
        assert math.sqrt(sum(c * c for c in product)) == pytest.approx(1.0, abs=1e-6)

    def test_matches_the_quaternion_units(self):
        # i*j = k pins both the argument order and every sign; unit-length and
        # identity checks pass under a swapped order or a flipped sign.
        i = (0.0, 1.0, 0.0, 0.0)
        j = (0.0, 0.0, 1.0, 0.0)
        k = (0.0, 0.0, 0.0, 1.0)
        assert quat_multiply(i, j) == pytest.approx(k)
        assert quat_multiply(j, i) == pytest.approx((0.0, 0.0, 0.0, -1.0))
        assert quat_multiply(i, i) == pytest.approx((-1.0, 0.0, 0.0, 0.0))

    def test_is_not_commutative(self):
        a = align_to_forward_quat((0.0, 1.0, 0.0))
        b = align_to_forward_quat((0.0, 0.0, 1.0))
        assert quat_multiply(a, b) != pytest.approx(quat_multiply(b, a))

    def test_composing_a_rotation_with_its_conjugate_is_the_identity(self):
        w, x, y, z = align_to_forward_quat((0.3, -0.5, 0.81))
        assert quat_multiply((w, x, y, z), (w, -x, -y, -z)) == pytest.approx(
            (1.0, 0.0, 0.0, 0.0), abs=1e-6
        )


class TestNormalisePartFrame:
    """Base at the origin, own axis on +X -- the twig prototype convention."""

    def _part_along(self, direction, base):
        points = [
            (
                base[0] + direction[0] * t,
                base[1] + direction[1] * t,
                base[2] + direction[2] * t,
            )
            for t in (0.0, 0.5, 1.0)
        ]
        return PartMesh(
            points=points,
            faces=[(0, 1, 2)],
            uvs=[(0.0, 0.0)] * 3,
            face_materials=[0],
            materials=["bark"],
        )

    def test_moves_the_base_to_the_origin(self):
        part = self._part_along((0.0, 0.0, 1.0), (3.0, -2.0, 7.0))
        normalise_part_frame(part, (3.0, -2.0, 7.0), (0.0, 0.0, 1.0))
        assert part.points[0] == pytest.approx((0.0, 0.0, 0.0), abs=1e-6)

    def test_puts_the_branch_axis_on_plus_x(self):
        part = self._part_along((0.0, 0.0, 1.0), (3.0, -2.0, 7.0))
        normalise_part_frame(part, (3.0, -2.0, 7.0), (0.0, 0.0, 1.0))
        assert part.points[-1] == pytest.approx((1.0, 0.0, 0.0), abs=1e-6)

    def test_preserves_lengths(self):
        part = self._part_along((0.4, -0.5, 0.766), (1.0, 1.0, 1.0))
        before = [
            math.dist(p, part.points[0]) for p in part.points
        ]
        normalise_part_frame(part, (1.0, 1.0, 1.0), (0.4, -0.5, 0.766))
        after = [math.dist(p, part.points[0]) for p in part.points]
        assert after == pytest.approx(before, abs=1e-6)

    def test_returns_the_quaternion_it_applied(self):
        part = self._part_along((0.0, 1.0, 0.0), (0.0, 0.0, 0.0))
        quat = normalise_part_frame(part, (0.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        assert quat == align_to_forward_quat((0.0, 1.0, 0.0))


class TestMergeMesh:
    """Leaves are welded in, never nested: Nanite allows one layer of instancing."""

    def _leaf(self):
        return PartMesh(
            points=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
            faces=[(0, 1, 2)],
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)],
            face_materials=[0],
            materials=["leaf"],
        )

    def _base(self):
        return PartMesh(
            points=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0)],
            faces=[(0, 1, 2)],
            uvs=[(0.0, 0.0)] * 3,
            face_materials=[0],
            materials=["bark"],
        )

    def test_offsets_the_welded_face_indices(self):
        base = self._base()
        merge_mesh(base, self._leaf())
        assert base.faces == [(0, 1, 2), (3, 4, 5)]
        assert len(base.points) == 6

    def test_translates_the_welded_copy(self):
        base = self._base()
        merge_mesh(base, self._leaf(), translation=(10.0, 0.0, 0.0))
        assert base.points[3] == pytest.approx((10.0, 0.0, 0.0))

    def test_rotates_the_welded_copy(self):
        base = self._base()
        # 90 deg about +Z sends +X to +Y.
        half = math.sqrt(0.5)
        merge_mesh(base, self._leaf(), rotation=(half, 0.0, 0.0, half))
        assert base.points[4] == pytest.approx((0.0, 1.0, 0.0), abs=1e-6)

    def test_scales_the_welded_copy(self):
        base = self._base()
        merge_mesh(base, self._leaf(), scale=3.0)
        assert base.points[4] == pytest.approx((3.0, 0.0, 0.0))

    def test_composes_scale_then_rotate_then_translate(self):
        # Each of the three above is exercised with the other two at identity,
        # so none of them pins the ORDER -- and rotate-before-scale or
        # translate-before-rotate give different answers.
        base = self._base()
        half = math.sqrt(0.5)
        merge_mesh(
            base,
            self._leaf(),
            translation=(1.0, 2.0, 3.0),
            rotation=(half, 0.0, 0.0, half),  # 90 deg about +Z: +X -> +Y
            scale=2.0,
        )
        # local (1,0,0) -> scale 2 -> (2,0,0) -> rotate -> (0,2,0) -> +t
        assert base.points[4] == pytest.approx((1.0, 4.0, 3.0), abs=1e-6)
        # local (0,1,0) -> scale 2 -> (0,2,0) -> rotate -> (-2,0,0) -> +t
        assert base.points[5] == pytest.approx((-1.0, 2.0, 3.0), abs=1e-6)

    def test_unions_material_names_and_remaps_ids(self):
        base = self._base()
        merge_mesh(base, self._leaf())
        assert base.materials == ["bark", "leaf"]
        assert base.face_materials == [0, 1]

    def test_reuses_a_material_already_present(self):
        base = self._base()
        merge_mesh(base, self._base())
        assert base.materials == ["bark"]
        assert base.face_materials == [0, 0]

    def test_stays_valid_after_many_welds(self):
        base = self._base()
        for i in range(25):
            merge_mesh(base, self._leaf(), translation=(float(i), 0.0, 0.0))
        base.validate()
        assert len(base.faces) == 26


class TestPartMeshValidate:
    def test_rejects_a_uv_count_that_is_not_three_per_triangle(self):
        part = PartMesh(
            points=[(0.0, 0.0, 0.0)] * 3,
            faces=[(0, 1, 2)],
            uvs=[(0.0, 0.0)] * 2,
            face_materials=[0],
            materials=["bark"],
        )
        with pytest.raises(ValueError, match="face-varying UV count"):
            part.validate()

    def test_rejects_an_out_of_range_face_index(self):
        part = PartMesh(
            points=[(0.0, 0.0, 0.0)] * 2,
            faces=[(0, 1, 2)],
            uvs=[(0.0, 0.0)] * 3,
            face_materials=[0],
            materials=["bark"],
        )
        with pytest.raises(ValueError, match="out of range"):
            part.validate()

    def test_rejects_a_material_id_with_no_material(self):
        part = PartMesh(
            points=[(0.0, 0.0, 0.0)] * 3,
            faces=[(0, 1, 2)],
            uvs=[(0.0, 0.0)] * 3,
            face_materials=[7],
            materials=["bark"],
        )
        with pytest.raises(ValueError, match="material id"):
            part.validate()

    def test_bounds_of_an_empty_mesh(self):
        assert PartMesh().bounds() == ((0.0, 0.0, 0.0), (0.0, 0.0, 0.0))

    def test_bounds_span_every_point(self):
        # This value is written straight out as the USD extent.
        part = PartMesh(
            points=[(-1.0, 2.0, 0.5), (3.0, -4.0, 0.0), (0.0, 0.0, 7.0)],
            faces=[(0, 1, 2)],
            uvs=[(0.0, 0.0)] * 3,
            face_materials=[0],
            materials=["bark"],
        )
        lo, hi = part.bounds()
        assert lo == pytest.approx((-1.0, -4.0, 0.0))
        assert hi == pytest.approx((3.0, 2.0, 7.0))


class TestCompoundConversionProfile:
    """The coarser profile for twigs destined to be welded (XRFF-359).

    Ordering matters: this selects settings for the per-twig Blender conversion
    (densify -> alpha contour cut -> planar dissolve), which still runs BEFORE
    any welding. It is not a simplification applied to a finished part -- a
    welded part has lost the per-leaf alpha association the contour cut needs.
    """

    def _config(self, **overrides):
        from growpy.config.core import GrowPyConfig

        return GrowPyConfig(**overrides)

    def test_twig_role_is_the_close_range_settings(self):
        config = self._config(twigs_boundary_edge_mm=0.25, twigs_planar_angle=0.1)
        profile = config.get_twig_conversion_profile("twig")
        assert profile["boundary_edge_mm"] == 0.25
        assert profile["planar_angle"] == 0.1

    def test_compound_falls_back_to_close_range_when_unset(self):
        # Adding the role must change nothing until the profile is configured.
        config = self._config(twigs_boundary_edge_mm=0.25, twigs_planar_angle=0.1)
        assert config.get_twig_conversion_profile(
            "compound"
        ) == config.get_twig_conversion_profile("twig")

    def test_compound_overrides_only_the_keys_that_are_set(self):
        config = self._config(
            twigs_boundary_edge_mm=0.25,
            twigs_planar_angle=0.1,
            twigs_compound_boundary_edge_mm=1.0,
        )
        profile = config.get_twig_conversion_profile("compound")
        assert profile["boundary_edge_mm"] == 1.0
        assert profile["planar_angle"] == 0.1

    def test_default_role_is_twig(self):
        config = self._config(twigs_compound_boundary_edge_mm=1.0)
        assert config.get_twig_conversion_profile() == (
            config.get_twig_conversion_profile("twig")
        )

    def test_rejects_an_unknown_role(self):
        with pytest.raises(ValueError, match="unknown twig conversion role"):
            self._config().get_twig_conversion_profile("part")

    def test_covers_every_shared_knob(self):
        profile = self._config().get_twig_conversion_profile("compound")
        assert set(profile) == {
            "boundary_edge_mm",
            "planar_angle",
            "alpha_trim",
            "interior_edge_mm",
        }


class TestPlacementRoundTrip:
    """Author then place must return the part to where it was cut.

    This is the check XRFF-329 is the precedent for: a frame convention that is
    wrong in a self-consistent way renders nothing obviously broken until it is
    imported, so it is pinned numerically here.
    """

    def _rotate(self, quat, vector):
        w, x, y, z = quat
        px, py, pz = vector
        tx = 2.0 * (y * pz - z * py)
        ty = 2.0 * (z * px - x * pz)
        tz = 2.0 * (x * py - y * px)
        return (
            px + w * tx + (y * tz - z * ty),
            py + w * ty + (z * tx - x * tz),
            pz + w * tz + (x * ty - y * tx),
        )

    @pytest.mark.parametrize(
        "direction",
        [
            (0.0, 0.0, 1.0),
            (1.0, 0.0, 0.0),
            (-1.0, 0.0, 0.0),
            (0.0, -1.0, 0.0),
            (0.31, 0.62, -0.72),
        ],
    )
    def test_placement_quat_restores_the_branch_direction(self, direction):
        from growpy.io.usd.compound_part_export import placement_quat_for_direction

        length = math.sqrt(sum(c * c for c in direction))
        unit = tuple(c / length for c in direction)
        # The prototype's own axis is +X by construction.
        quat = placement_quat_for_direction(direction)
        restored = self._rotate(quat, (1.0, 0.0, 0.0))
        assert restored == pytest.approx(unit, abs=1e-6)

    def test_a_normalised_part_placed_back_lands_on_its_original_points(self):
        from growpy.io.usd.compound_part_export import placement_quat_for_direction

        base = (2.0, -1.0, 5.0)
        direction = (0.0, 0.0, 1.0)
        original = [(2.0, -1.0, 5.0), (2.0, -1.0, 5.5), (2.2, -1.0, 6.0)]
        part = PartMesh(
            points=list(original),
            faces=[(0, 1, 2)],
            uvs=[(0.0, 0.0)] * 3,
            face_materials=[0],
            materials=["bark"],
        )
        normalise_part_frame(part, base, direction)
        placed = [
            tuple(
                c + o
                for c, o in zip(
                    self._rotate(placement_quat_for_direction(direction), p),
                    base,
                    strict=True,
                )
            )
            for p in part.points
        ]
        for got, want in zip(placed, original, strict=True):
            assert got == pytest.approx(want, abs=1e-6)


class TestCompoundProfileCannotClobberDatasetAssets:
    """`process_twig_directory` writes beside the .blend under fixed names.

    Both profiles therefore produce `<twig>_static.usda`, so running the coarse
    one over `data/assets/twigs` would silently replace the close-range assets
    the dataset depends on. The CLI refuses rather than allowing that.
    """

    def _run(self, argv, monkeypatch):
        """Call the real CLI without leaking its side effects into the session.

        `main()` mutates the module-level GrowPyConfig singleton via
        `config.resolve(args)` and installs a stderr handler via
        `setup_logging`, so both are restored here.
        """
        import copy
        import logging
        import sys

        from growpy.cli import convert_twigs
        from growpy.config import core as config_core

        saved_config = copy.deepcopy(config_core.get_config())
        root = logging.getLogger()
        saved_handlers = list(root.handlers)
        saved_level = root.level
        try:
            monkeypatch.setattr(sys, "argv", argv)
            return convert_twigs.main()
        finally:
            config_core.set_global_config(saved_config)
            root.handlers[:] = saved_handlers
            root.setLevel(saved_level)

    def test_compound_profile_without_output_root_is_refused(
        self, monkeypatch, tmp_path
    ):
        # An EXISTING twig dir, so the only thing that can fail is the guard.
        # Relying on the default path would pass on any machine without
        # data/assets/twigs even with the guard deleted.
        twigs = tmp_path / "twigs"
        twigs.mkdir()
        code = self._run(
            [
                "convert_twigs",
                str(twigs),
                "--conversion-profile",
                "compound",
                "-q",
                "--csv",
                str(tmp_path / "absent.csv"),
            ],
            monkeypatch,
        )
        assert code == 1

    def test_compound_profile_with_output_root_is_allowed(self, monkeypatch, tmp_path):
        # A real but empty twig dir: nothing to convert, so a clean exit proves
        # the guard did not fire.
        twigs = tmp_path / "twigs"
        twigs.mkdir()
        code = self._run(
            [
                "convert_twigs",
                str(twigs),
                "--conversion-profile",
                "compound",
                "--output-root",
                str(tmp_path / "out"),
                "-q",
                "--csv",
                str(tmp_path / "absent.csv"),
            ],
            monkeypatch,
        )
        assert code == 0

    def test_default_profile_needs_no_output_root(self, monkeypatch, tmp_path):
        twigs = tmp_path / "twigs"
        twigs.mkdir()
        code = self._run(
            ["convert_twigs", str(twigs), "-q", "--csv", str(tmp_path / "absent.csv")],
            monkeypatch,
        )
        assert code == 0




class TestWriteCompoundPartUsd:
    """The pxr write path. It occupies the same prototype slot as a twig asset,
    so it has to satisfy the same contracts `assembly_export` and
    `utils.leaf_geometry` impose on one.
    """

    def _part(self):
        return PartMesh(
            points=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)],
            faces=[(0, 1, 2), (0, 1, 3)],
            uvs=[(0.0, 0.0), (1.0, 0.0), (0.0, 1.0)] * 2,
            face_materials=[0, 1],
            materials=["beech_bark", "beech_leaf"],
        )

    def _write(self, tmp_path, part=None, name="beech_compound_p00"):
        from growpy.io.usd.compound_part_export import write_compound_part_usd

        return write_compound_part_usd(
            part or self._part(), tmp_path / f"{name}_static.usda", part_name=name
        )

    def test_root_prim_matches_the_filename_assembly_export_derives(self, tmp_path):
        # assembly_export references /{stem minus _static} inside the file; a
        # mismatch resolves to nothing and renders silently empty.
        from pxr import Usd

        path = self._write(tmp_path)
        stage = Usd.Stage.Open(str(path))
        asset_name = path.stem.replace("_static", "")
        assert stage.GetPrimAtPath(f"/{asset_name}").IsValid()
        assert stage.GetDefaultPrim().GetName() == asset_name

    def test_stage_is_z_up_metres(self, tmp_path):
        from pxr import Usd, UsdGeom

        stage = Usd.Stage.Open(str(self._write(tmp_path)))
        assert UsdGeom.GetStageUpAxis(stage) == UsdGeom.Tokens.z
        assert UsdGeom.GetStageMetersPerUnit(stage) == 1.0

    def test_declares_the_foliage_mesh_attributes_every_twig_prototype_declares(
        self, tmp_path
    ):
        # USD's fallbacks are catmullClark and single-sided: the first would
        # subdivide a baked crown, the second makes every leaf vanish from
        # behind. All 48 shipped static twig prototypes declare both.
        from pxr import Usd, UsdGeom

        stage = Usd.Stage.Open(str(self._write(tmp_path)))
        prim = next(p for p in stage.Traverse() if p.GetTypeName() == "Mesh")
        mesh = UsdGeom.Mesh(prim)
        assert mesh.GetSubdivisionSchemeAttr().Get() == UsdGeom.Tokens.none
        assert mesh.GetDoubleSidedAttr().Get() is True

    def test_writes_only_triangles(self, tmp_path):
        # leaf_geometry.load_full_twig_mesh raises on any non-triangle.
        from pxr import Usd, UsdGeom

        stage = Usd.Stage.Open(str(self._write(tmp_path)))
        prim = next(p for p in stage.Traverse() if p.GetTypeName() == "Mesh")
        mesh = UsdGeom.Mesh(prim)
        assert set(mesh.GetFaceVertexCountsAttr().Get()) == {3}

    def test_uvs_are_face_varying_and_complete(self, tmp_path):
        from pxr import Usd, UsdGeom

        stage = Usd.Stage.Open(str(self._write(tmp_path)))
        prim = next(p for p in stage.Traverse() if p.GetTypeName() == "Mesh")
        primvar = UsdGeom.PrimvarsAPI(prim).GetPrimvar("st")
        counts = UsdGeom.Mesh(prim).GetFaceVertexCountsAttr().Get()
        assert primvar.GetInterpolation() == UsdGeom.Tokens.faceVarying
        assert len(primvar.Get()) == len(counts) * 3

    def test_one_geom_subset_per_material(self, tmp_path):
        from pxr import Usd

        stage = Usd.Stage.Open(str(self._write(tmp_path)))
        prim = next(p for p in stage.Traverse() if p.GetTypeName() == "Mesh")
        names = {
            c.GetName() for c in prim.GetChildren() if c.GetTypeName() == "GeomSubset"
        }
        assert names == {"beech_bark", "beech_leaf"}

    def test_a_single_material_part_writes_no_subsets(self, tmp_path):
        from pxr import Usd

        part = self._part()
        part.materials = ["beech_bark"]
        part.face_materials = [0, 0]
        stage = Usd.Stage.Open(str(self._write(tmp_path, part)))
        prim = next(p for p in stage.Traverse() if p.GetTypeName() == "Mesh")
        assert not [c for c in prim.GetChildren() if c.GetTypeName() == "GeomSubset"]

    def test_extent_matches_the_points(self, tmp_path):
        from pxr import Usd, UsdGeom

        stage = Usd.Stage.Open(str(self._write(tmp_path)))
        prim = next(p for p in stage.Traverse() if p.GetTypeName() == "Mesh")
        mesh = UsdGeom.Mesh(prim)
        lo, hi = mesh.GetExtentAttr().Get()
        assert tuple(lo) == pytest.approx((0.0, 0.0, 0.0))
        assert tuple(hi) == pytest.approx((1.0, 1.0, 1.0))

    def test_an_invalid_part_is_refused_before_anything_is_written(self, tmp_path):
        part = self._part()
        part.uvs = part.uvs[:-1]
        out = tmp_path / "broken_static.usda"
        with pytest.raises(ValueError):
            self._write(tmp_path, part, name="broken")
        assert not out.exists()

    def test_round_trips_through_load_prototype_mesh(self, tmp_path):
        from growpy.io.usd.compound_part_export import load_prototype_mesh

        written = self._part()
        back = load_prototype_mesh(self._write(tmp_path))
        assert len(back.points) == len(written.points)
        assert len(back.faces) == len(written.faces)
        assert set(back.materials) == set(written.materials)
        assert back.face_materials == written.face_materials


class TestStageTextures:
    """Relative `@./textures/...@` asset paths resolve against the layer that
    holds them, so a copied Materials scope needs its textures copied too.
    """

    def _source(self, tmp_path):
        source = tmp_path / "src"
        (source / "textures").mkdir(parents=True)
        (source / "textures" / "leaf_diffuse.png").write_bytes(b"png")
        (source / "textures" / "leaf_normal.png").write_bytes(b"png")
        return source / "twig_static.usda"

    def test_copies_the_textures_next_to_the_part(self, tmp_path):
        from growpy.io.usd.compound_part_export import _stage_textures

        out = tmp_path / "parts"
        out.mkdir()
        assert _stage_textures(self._source(tmp_path), out) == 2
        assert (out / "textures" / "leaf_diffuse.png").is_file()

    def test_is_idempotent(self, tmp_path):
        from growpy.io.usd.compound_part_export import _stage_textures

        source = self._source(tmp_path)
        out = tmp_path / "parts"
        out.mkdir()
        _stage_textures(source, out)
        assert _stage_textures(source, out) == 0

    def test_no_textures_dir_is_not_an_error(self, tmp_path):
        from growpy.io.usd.compound_part_export import _stage_textures

        bare = tmp_path / "bare"
        bare.mkdir()
        out = tmp_path / "parts"
        out.mkdir()
        assert _stage_textures(bare / "twig_static.usda", out) == 0

    def test_does_not_copy_a_directory_onto_itself(self, tmp_path):
        from growpy.io.usd.compound_part_export import _stage_textures

        source = self._source(tmp_path)
        assert _stage_textures(source, source.parent) == 0


class TestOutputRootMustLeaveTheSourceTree:
    """Requiring --output-root is not enough on its own.

    `process_twig_directory` writes to ``output_root / <twig folder>``, so
    ``--output-root data/assets/twigs`` reproduces the default "beside the
    .blend" path exactly -- the most natural-looking value defeats the guard.
    The coarse assets would also land inside the tree that `analyze_usda`,
    `leaf_geometry` and `twig_silhouette` discover twigs in by rglob, where a
    duplicate basename is resolved by filesystem order.
    """

    def _run(self, argv, monkeypatch):
        return TestCompoundProfileCannotClobberDatasetAssets()._run(argv, monkeypatch)

    def _argv(self, twigs, out, tmp_path):
        return [
            "convert_twigs",
            str(twigs),
            "--conversion-profile",
            "compound",
            "--output-root",
            str(out),
            "-q",
            "--csv",
            str(tmp_path / "absent.csv"),
        ]

    def test_output_root_equal_to_the_source_is_refused(self, monkeypatch, tmp_path):
        twigs = tmp_path / "twigs"
        twigs.mkdir()
        assert self._run(self._argv(twigs, twigs, tmp_path), monkeypatch) == 1

    def test_output_root_nested_under_the_source_is_refused(
        self, monkeypatch, tmp_path
    ):
        twigs = tmp_path / "twigs"
        (twigs / "compound").mkdir(parents=True)
        assert self._run(
            self._argv(twigs, twigs / "compound", tmp_path), monkeypatch
        ) == 1

    def test_a_sibling_output_root_is_allowed(self, monkeypatch, tmp_path):
        twigs = tmp_path / "twigs"
        twigs.mkdir()
        assert self._run(
            self._argv(twigs, tmp_path / "compound_twigs", tmp_path), monkeypatch
        ) == 0


class TestCompoundProfileTomlParsing:
    """The [twigs] compound_* keys, through the real loader.

    The profile tests above construct GrowPyConfig directly, so they never touch
    `from_toml` -- the parsing could be absent entirely and they would pass.
    """

    def _config(self, body, tmp_path):
        from growpy.config.core import GrowPyConfig

        (tmp_path / "twigs.toml").write_text(body, encoding="utf-8")
        return GrowPyConfig.from_toml(tmp_path / "twigs.toml", set_as_global=False)

    def test_reads_the_compound_keys(self, tmp_path):
        config = self._config(
            "[twigs]\n"
            "boundary_edge_mm = 0.25\n"
            "compound_boundary_edge_mm = 1.0\n"
            "compound_planar_angle = 1.0\n",
            tmp_path,
        )
        assert config.twigs_compound_boundary_edge_mm == 1.0
        profile = config.get_twig_conversion_profile("compound")
        assert profile["boundary_edge_mm"] == 1.0
        assert config.get_twig_conversion_profile("twig")["boundary_edge_mm"] == 0.25

    def test_absent_compound_keys_stay_none(self, tmp_path):
        # The shipped config comments the whole block out, so the default must
        # reproduce current behaviour exactly.
        config = self._config("[twigs]\nboundary_edge_mm = 0.25\n", tmp_path)
        assert config.twigs_compound_boundary_edge_mm is None
        assert config.get_twig_conversion_profile(
            "compound"
        ) == config.get_twig_conversion_profile("twig")

    def test_the_shipped_config_leaves_the_profile_inert(self):
        # config/twigs.toml ships the compound block commented out.
        from pathlib import Path

        from growpy.config.core import GrowPyConfig

        shipped = Path("config/twigs.toml")
        if not shipped.is_file():
            pytest.skip("config/twigs.toml not present")
        config = GrowPyConfig.from_toml(shipped, set_as_global=False)
        assert config.get_twig_conversion_profile(
            "compound"
        ) == config.get_twig_conversion_profile("twig")

    def test_the_per_twig_subtable_stays_last(self, tmp_path):
        # A TOML sub-table captures every key defined after it, so the compound
        # keys must sit above [twigs.planar_angle_per_twig].
        import tomllib
        from pathlib import Path

        shipped = Path("config/twigs.toml")
        if not shipped.is_file():
            pytest.skip("config/twigs.toml not present")
        data = tomllib.loads(shipped.read_text(encoding="utf-8"))
        assert "planar_angle_per_twig" in data["twigs"]
        assert isinstance(data["twigs"]["planar_angle_per_twig"], dict)
        # Every scalar key must have survived as a sibling, not been swallowed.
        assert isinstance(data["twigs"]["boundary_edge_mm"], float)

    def test_an_explicit_cli_value_beats_a_toml_compound_value(self, tmp_path):
        # Every other flag in this CLI wins over TOML; the compound profile
        # must not invert that.
        config = self._config(
            "[twigs]\nboundary_edge_mm = 0.25\ncompound_boundary_edge_mm = 1.0\n",
            tmp_path,
        )
        config.twigs_boundary_edge_mm = 0.5  # as resolve() would set it
        profile = config.get_twig_conversion_profile(
            "compound", explicit={"boundary_edge_mm"}
        )
        assert profile["boundary_edge_mm"] == 0.5
