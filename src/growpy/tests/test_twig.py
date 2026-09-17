"""Tests for growpy.core.twig module."""

import math

import pytest

from growpy.core.twig import (
    IDENTITY_QUAT,
    TwigPlacement,
    _face_area,
    recover_cutoff_twig_placements,
    shortest_arc_quaternion,
    densify_twig_placements,
    direction_to_quaternion,
    extract_twig_placements_from_model,
    get_face_center_and_normal,
    normal_to_rotation_matrix,
    rotation_matrix_to_quaternion,
    thin_placements_to_limit,
)


class TestTwigPlacement:
    """Tests for TwigPlacement dataclass."""

    def test_default_values(self):
        tp = TwigPlacement(
            type="twig_long",
            position=(1.0, 2.0, 3.0),
            normal=(0.0, 0.0, 1.0),
        )
        assert tp.scale == 1.0
        assert tp.bone_id is None
        assert tp.branch_id is None
        assert tp.orientation == IDENTITY_QUAT

    def test_to_dict(self):
        tp = TwigPlacement(
            type="twig_short",
            position=(1.0, 2.0, 3.0),
            normal=(0.0, 1.0, 0.0),
            scale=0.5,
            bone_id=10,
            branch_id=3,
        )
        d = tp.to_dict()
        assert d["type"] == "twig_short"
        assert d["position"] == (1.0, 2.0, 3.0)
        assert d["normal"] == (0.0, 1.0, 0.0)
        assert d["scale"] == 0.5
        assert d["bone_id"] == 10
        assert d["branch_id"] == 3

    def test_to_dict_roundtrip(self):
        tp = TwigPlacement(
            type="twig_dead",
            position=(0.0, 0.0, 0.0),
            normal=(1.0, 0.0, 0.0),
        )
        d = tp.to_dict()
        tp2 = TwigPlacement(**d)
        assert tp2.type == tp.type
        assert tp2.position == tp.position
        assert tp2.normal == tp.normal


class TestGetFaceCenterAndNormal:
    """Tests for face center and normal calculation."""

    def test_triangle_center(self):
        vertices = [(0.0, 0.0, 0.0), (2.0, 0.0, 0.0), (1.0, 2.0, 0.0)]
        face = [0, 1, 2]
        center, normal = get_face_center_and_normal(vertices, face)
        assert center[0] == pytest.approx(1.0)
        assert center[1] == pytest.approx(2.0 / 3.0)
        assert center[2] == pytest.approx(0.0)

    def test_triangle_normal_z_up(self):
        vertices = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        face = [0, 1, 2]
        center, normal = get_face_center_and_normal(vertices, face)
        # Normal should point in Z direction for XY-plane triangle
        assert abs(normal[2]) == pytest.approx(1.0, abs=1e-6)

    def test_quad_center(self):
        vertices = [
            (0.0, 0.0, 0.0),
            (2.0, 0.0, 0.0),
            (2.0, 2.0, 0.0),
            (0.0, 2.0, 0.0),
        ]
        face = [0, 1, 2, 3]
        center, normal = get_face_center_and_normal(vertices, face)
        assert center[0] == pytest.approx(1.0)
        assert center[1] == pytest.approx(1.0)
        assert center[2] == pytest.approx(0.0)

    def test_degenerate_face_returns_default_normal(self):
        vertices = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
        face = [0, 1, 2]
        center, normal = get_face_center_and_normal(vertices, face)
        assert normal == (0.0, 0.0, 1.0)

    def test_normal_is_unit_length(self):
        vertices = [(0.0, 0.0, 0.0), (3.0, 0.0, 0.0), (0.0, 4.0, 0.0)]
        face = [0, 1, 2]
        center, normal = get_face_center_and_normal(vertices, face)
        length = math.sqrt(sum(n * n for n in normal))
        assert length == pytest.approx(1.0, abs=1e-6)


class TestNormalToRotationMatrix:
    """Tests for normal-to-rotation matrix conversion."""

    def test_z_up_normal(self):
        matrix = normal_to_rotation_matrix((0.0, 0.0, 1.0))
        assert len(matrix) == 3
        assert len(matrix[0]) == 3

    def test_x_axis_normal(self):
        matrix = normal_to_rotation_matrix((1.0, 0.0, 0.0))
        # X-axis of result should be the input normal
        assert matrix[0][0] == pytest.approx(1.0)
        assert matrix[1][0] == pytest.approx(0.0)
        assert matrix[2][0] == pytest.approx(0.0)

    def test_matrix_orthogonality(self):
        matrix = normal_to_rotation_matrix((0.577, 0.577, 0.577))
        # Columns should be orthogonal
        col0 = [matrix[i][0] for i in range(3)]
        col1 = [matrix[i][1] for i in range(3)]
        col2 = [matrix[i][2] for i in range(3)]
        dot_01 = sum(a * b for a, b in zip(col0, col1))
        dot_02 = sum(a * b for a, b in zip(col0, col2))
        dot_12 = sum(a * b for a, b in zip(col1, col2))
        assert dot_01 == pytest.approx(0.0, abs=1e-4)
        assert dot_02 == pytest.approx(0.0, abs=1e-4)
        assert dot_12 == pytest.approx(0.0, abs=1e-4)


class TestRotationMatrixToQuaternion:
    """Tests for rotation_matrix_to_quaternion conversion."""

    def test_identity_matrix(self):
        identity = [[1, 0, 0], [0, 1, 0], [0, 0, 1]]
        w, x, y, z = rotation_matrix_to_quaternion(identity)
        assert w == pytest.approx(1.0, abs=1e-6)
        assert x == pytest.approx(0.0, abs=1e-6)
        assert y == pytest.approx(0.0, abs=1e-6)
        assert z == pytest.approx(0.0, abs=1e-6)

    def test_90_degree_z_rotation(self):
        # 90 degrees around Z axis
        matrix = [[0, -1, 0], [1, 0, 0], [0, 0, 1]]
        w, x, y, z = rotation_matrix_to_quaternion(matrix)
        # q = (cos(45), 0, 0, sin(45))
        assert w == pytest.approx(math.cos(math.pi / 4), abs=1e-4)
        assert z == pytest.approx(math.sin(math.pi / 4), abs=1e-4)

    def test_quaternion_is_normalized(self):
        matrix = [[0, 0, 1], [1, 0, 0], [0, 1, 0]]
        w, x, y, z = rotation_matrix_to_quaternion(matrix)
        length = math.sqrt(w * w + x * x + y * y + z * z)
        assert length == pytest.approx(1.0, abs=1e-6)

    def test_180_degree_rotation(self):
        # 180 degrees around Z: negate x and y
        matrix = [[-1, 0, 0], [0, -1, 0], [0, 0, 1]]
        w, x, y, z = rotation_matrix_to_quaternion(matrix)
        length = math.sqrt(w * w + x * x + y * y + z * z)
        assert length == pytest.approx(1.0, abs=1e-6)
        assert w == pytest.approx(0.0, abs=1e-4)

    def test_roundtrip_with_normal_to_rotation(self):
        normal = (0.577, 0.577, 0.577)
        matrix = normal_to_rotation_matrix(normal)
        w, x, y, z = rotation_matrix_to_quaternion(matrix)
        length = math.sqrt(w * w + x * x + y * y + z * z)
        assert length == pytest.approx(1.0, abs=1e-6)


class TestGetFaceCenterAndNormalAdvanced:
    """Additional geometry tests for face center and normal."""

    def test_yz_plane_triangle_normal_x(self):
        vertices = [(0.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
        face = [0, 1, 2]
        _, normal = get_face_center_and_normal(vertices, face)
        assert abs(normal[0]) == pytest.approx(1.0, abs=1e-6)

    def test_xz_plane_triangle_normal_y(self):
        vertices = [(0.0, 0.0, 0.0), (0.0, 0.0, 1.0), (1.0, 0.0, 0.0)]
        face = [0, 1, 2]
        _, normal = get_face_center_and_normal(vertices, face)
        assert abs(normal[1]) == pytest.approx(1.0, abs=1e-6)

    def test_pentagon_center(self):
        import math as m

        vertices = [
            (m.cos(2 * m.pi * i / 5), m.sin(2 * m.pi * i / 5), 0.0) for i in range(5)
        ]
        face = [0, 1, 2, 3, 4]
        center, _ = get_face_center_and_normal(vertices, face)
        assert center[0] == pytest.approx(0.0, abs=1e-6)
        assert center[1] == pytest.approx(0.0, abs=1e-6)


class TestNormalToRotationMatrixAdvanced:
    """Additional rotation matrix tests."""

    def test_y_axis_normal(self):
        matrix = normal_to_rotation_matrix((0.0, 1.0, 0.0))
        assert matrix[1][0] == pytest.approx(1.0)

    def test_negative_z_normal(self):
        matrix = normal_to_rotation_matrix((0.0, 0.0, -1.0))
        assert matrix[2][0] == pytest.approx(-1.0)

    def test_columns_unit_length(self):
        matrix = normal_to_rotation_matrix((0.3, 0.4, 0.866))
        for c in range(3):
            col = [matrix[r][c] for r in range(3)]
            length = math.sqrt(sum(v * v for v in col))
            assert length == pytest.approx(1.0, abs=1e-4)

    def test_determinant_positive(self):
        matrix = normal_to_rotation_matrix((0.577, 0.577, 0.577))
        det = (
            matrix[0][0] * (matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1])
            - matrix[0][1] * (matrix[1][0] * matrix[2][2] - matrix[1][2] * matrix[2][0])
            + matrix[0][2] * (matrix[1][0] * matrix[2][1] - matrix[1][1] * matrix[2][0])
        )
        assert det == pytest.approx(1.0, abs=2e-3)


class _FakeModel:
    """Minimal Grove-model stand-in for extract_twig_placements_from_model.

    Living twigs expose ground-truth arrays (num_twigs placed); dead twigs only
    have face attributes. Faces are independent triangles indexing `points`.
    """

    def __init__(
        self, faces, points, twig_long, twig_dead, num_twigs, orientations=None
    ):
        self.faces = faces
        self.points = points
        self.face_attribute_twig_long = twig_long
        self.face_attribute_twig_dead = twig_dead
        self._num_twigs = num_twigs
        self._orientations = orientations

    def get_twig_locations(self):
        return [0.0, 0.0, 0.0] * self._num_twigs

    def get_twig_directions(self):
        return [0.0, 0.0, 1.0] * self._num_twigs

    def get_twig_orientations(self):
        # Grove returns a unit quaternion per twig: 4 floats, (w, x, y, z).
        if self._orientations is not None:
            return self._orientations
        return [1.0, 0.0, 0.0, 0.0] * self._num_twigs


def _build_model(num_dead_faces, num_living_faces, num_twigs_placed, orientations=None):
    """Dead faces first, then living faces, so dead ones are all extracted
    before the living array is exhausted."""
    faces = []
    points = []
    twig_long = []
    twig_dead = []
    for i in range(num_dead_faces + num_living_faces):
        base = i * 3
        points.extend([(base, 0.0, 0.0), (base + 1, 0.0, 0.0), (base, 1.0, 0.0)])
        faces.append([base, base + 1, base + 2])
        is_dead = i < num_dead_faces
        twig_dead.append(1 if is_dead else 0)
        twig_long.append(0 if is_dead else 1)
    return _FakeModel(
        faces, points, twig_long, twig_dead, num_twigs_placed, orientations
    )


class TestDeadTwigDensityMatch:
    """Dead twigs should be thinned to Grove's living-twig scatter density."""

    def test_dead_thinned_to_living_scatter_ratio(self):
        # 4 living candidate faces, Grove placed only 2 -> scatter ratio 0.5.
        # 4 dead faces should be kept at ~0.5 -> 2.
        model = _build_model(num_dead_faces=4, num_living_faces=4, num_twigs_placed=2)
        placements = extract_twig_placements_from_model(model)
        assert len(placements["twig_long"]) == 2
        assert len(placements["twig_dead"]) == 2

    def test_dead_unchanged_when_grove_places_all_living(self):
        # Grove placed one twig per living face -> scatter ratio 1.0 -> keep all dead.
        model = _build_model(num_dead_faces=3, num_living_faces=3, num_twigs_placed=3)
        placements = extract_twig_placements_from_model(model)
        assert len(placements["twig_dead"]) == 3

    def test_no_living_faces_leaves_dead_unchanged(self):
        # No living candidates -> ratio undefined -> dead placements untouched.
        model = _build_model(num_dead_faces=3, num_living_faces=0, num_twigs_placed=0)
        placements = extract_twig_placements_from_model(model)
        assert len(placements["twig_dead"]) == 3


class TestTwigOrientationQuaternion:
    """Grove's get_twig_orientations() is 4 floats per twig, not 3.

    Reading it at stride 3 silently hands each twig a misaligned slice of the
    next one's quaternion, so the values are not even unit-length.
    """

    def test_default_orientation_is_identity_quaternion(self):
        tp = TwigPlacement(
            type="twig_long", position=(0.0, 0.0, 0.0), normal=(0.0, 0.0, 1.0)
        )
        assert len(tp.orientation) == 4
        assert tp.orientation == IDENTITY_QUAT

    def test_orientation_read_at_stride_four(self):
        # Two twigs with distinguishable quaternions. At stride 3 the second
        # twig would receive (0.5, 0.5, 0.0) instead of its own quaternion.
        quats = [0.5, 0.5, 0.5, 0.5, 0.0, 0.0, 0.0, 1.0]
        model = _build_model(0, 2, 2, orientations=quats)
        placements = extract_twig_placements_from_model(model)
        got = [p.orientation for p in placements["twig_long"]]
        assert got == [(0.5, 0.5, 0.5, 0.5), (0.0, 0.0, 0.0, 1.0)]

    def test_stride_three_orientation_data_raises(self):
        # 2 twigs' worth of stride-3 data is 6 floats, not 2 quaternions.
        model = _build_model(0, 2, 2, orientations=[0.0, 0.0, 1.0] * 2)
        with pytest.raises(ValueError, match="twig_orientations"):
            extract_twig_placements_from_model(model)

    def test_missing_orientations_fall_back_to_identity(self):
        model = _build_model(0, 2, 2, orientations=[])
        placements = extract_twig_placements_from_model(model)
        assert all(p.orientation == IDENTITY_QUAT for p in placements["twig_long"])


class TestDirectionToQuaternion:
    """The quaternion must rotate +X (Grove's twig growth axis) onto direction."""

    @staticmethod
    def _rotate_x(q):
        w, x, y, z = q
        return (
            1 - 2 * (y * y + z * z),
            2 * (x * y + z * w),
            2 * (x * z - y * w),
        )

    @pytest.mark.parametrize(
        "direction",
        [
            (1.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
            (0.0, 0.0, 1.0),
            (0.0, 0.0, -1.0),
            (0.577, 0.577, 0.577),
            (-0.3, 0.6, -0.74),
        ],
    )
    def test_maps_x_axis_onto_direction(self, direction):
        q = direction_to_quaternion(direction)
        length = math.sqrt(sum(c * c for c in direction))
        expected = tuple(c / length for c in direction)
        assert self._rotate_x(q) == pytest.approx(expected, abs=1e-5)

    def test_result_is_unit_quaternion(self):
        q = direction_to_quaternion((0.3, -0.5, 0.81), (0.0, 0.0, 1.0))
        assert math.sqrt(sum(c * c for c in q)) == pytest.approx(1.0, abs=1e-6)

    def test_degenerate_direction_returns_identity(self):
        assert direction_to_quaternion((0.0, 0.0, 0.0)) == IDENTITY_QUAT

    def test_reference_parallel_to_direction_still_valid(self):
        # Gram-Schmidt degenerates here; must fall back rather than divide by ~0.
        q = direction_to_quaternion((0.0, 0.0, 1.0), (0.0, 0.0, 1.0))
        assert math.sqrt(sum(c * c for c in q)) == pytest.approx(1.0, abs=1e-6)
        assert self._rotate_x(q) == pytest.approx((0.0, 0.0, 1.0), abs=1e-5)


class TestFaceArea:
    """Face area drives twig density per unit bark, not per face."""

    def test_unit_right_triangle(self):
        verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
        assert _face_area(verts, [0, 1, 2]) == pytest.approx(0.5)

    def test_unit_square_quad(self):
        verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (1.0, 1.0, 0.0), (0.0, 1.0, 0.0)]
        assert _face_area(verts, [0, 1, 2, 3]) == pytest.approx(1.0)

    def test_degenerate_face_is_zero(self):
        verts = [(0.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]
        assert _face_area(verts, [0, 1, 2]) == pytest.approx(0.0)

    def test_face_with_too_few_vertices_is_zero(self):
        verts = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
        assert _face_area(verts, [0, 1]) == 0.0


class _CylinderModel:
    """One branch segment along +Z, for synthetic twig direction tests."""

    def __init__(self, segments=12, radius=0.1, length=2.0):
        self.points = []
        for z in (0.0, length):
            for k in range(segments):
                angle = 2 * math.pi * k / segments
                self.points.append(
                    (radius * math.cos(angle), radius * math.sin(angle), z)
                )
        self.faces = []
        for k in range(segments):
            nxt = (k + 1) % segments
            self.faces.append([k, nxt, segments + nxt, segments + k])
        n_faces = len(self.faces)
        self.face_attribute_twig_long = [0] * n_faces
        self.face_attribute_twig_short = [0] * n_faces
        self.face_attribute_twig_upward = [0] * n_faces
        self.face_attribute_twig_dead = [0] * n_faces
        self.point_attribute_bone_id = [0] * len(self.points)
        self.point_attribute_age = [0.0] * len(self.points)


class TestDensifiedTwigDirection:
    """Synthetic twigs must leave the bark at an angle, not lie along it.

    The previous implementation overwrote the face normal with the bone axis,
    which is TANGENT to the branch surface: every synthetic twig then lay flat
    along the bark and half of its leaf fan was driven inside the branch mesh.
    """

    BONES = [(True, 0, (0.0, 0.0, 0.0), (0.0, 0.0, 2.0), 0.1, 1.0, True, 0)]

    def _densify(self, branch_angle=None):
        model = _CylinderModel()
        seed = TwigPlacement(
            type="twig_long", position=(0.1, 0.0, 1.0), normal=(1.0, 0.0, 0.0)
        )
        placements = {
            "twig_long": [seed],
            "twig_short": [],
            "twig_upward": [],
            "twig_dead": [],
        }
        kwargs = {} if branch_angle is None else {"branch_angle": branch_angle}
        out = densify_twig_placements(
            model, placements, density=5.0, bones_info=self.BONES, **kwargs
        )
        return [p for p in out["twig_long"] if p is not seed]

    @staticmethod
    def _angle_to_axis(normal):
        # Branch axis is +Z for _CylinderModel.
        length = math.sqrt(sum(c * c for c in normal))
        return math.degrees(math.acos(max(-1.0, min(1.0, normal[2] / length))))

    def test_synthetic_twigs_were_added(self):
        assert len(self._densify()) > 0

    def test_direction_is_not_tangent_to_branch(self):
        # The old bug produced 0 deg (straight along the axis); a pure face
        # normal would give 90 deg. Both are tangent-or-edge-on failure modes.
        for placement in self._densify():
            angle = self._angle_to_axis(placement.normal)
            assert 15.0 < angle < 85.0

    def test_direction_matches_requested_branch_angle(self):
        for placement in self._densify(branch_angle=math.radians(30.0)):
            assert self._angle_to_axis(placement.normal) == pytest.approx(30.0, abs=1.0)

    def test_direction_has_outward_radial_component(self):
        # The twig must point away from the branch centreline, otherwise it is
        # buried inside the mesh.
        for placement in self._densify():
            px, py, _ = placement.position
            nx, ny, _ = placement.normal
            assert px * nx + py * ny > 0.0

    def test_orientation_is_unit_quaternion_matching_direction(self):
        for placement in self._densify():
            q = placement.orientation
            assert len(q) == 4
            assert math.sqrt(sum(c * c for c in q)) == pytest.approx(1.0, abs=1e-6)
            w, x, y, z = q
            rotated = (
                1 - 2 * (y * y + z * z),
                2 * (x * y + z * w),
                2 * (x * z - y * w),
            )
            assert rotated == pytest.approx(placement.normal, abs=1e-5)


class _PlaneModel:
    """Flat surviving surface in the z=0 plane, for twig recovery tests."""

    def __init__(self):
        self.points = [
            (-1.0, -1.0, 0.0),
            (1.0, -1.0, 0.0),
            (1.0, 1.0, 0.0),
            (-1.0, 1.0, 0.0),
        ]
        self.faces = [[0, 1, 2, 3]]
        self.point_attribute_bone_id = [7, 7, 7, 7]
        self.face_attribute_branch_id = [3]


def _twig(position, normal=(0.0, 0.0, 1.0), quat=(1.0, 0.0, 0.0, 0.0)):
    return TwigPlacement(
        type="twig_long", position=position, normal=normal, orientation=quat
    )


class TestShortestArcQuaternion:
    """Re-aiming a recovered twig must carry its roll along, not reset it."""

    @staticmethod
    def _rotate(q, v):
        w, x, y, z = q
        vx, vy, vz = v
        return (
            (1 - 2 * (y * y + z * z)) * vx
            + 2 * (x * y - z * w) * vy
            + 2 * (x * z + y * w) * vz,
            2 * (x * y + z * w) * vx
            + (1 - 2 * (x * x + z * z)) * vy
            + 2 * (y * z - x * w) * vz,
            2 * (x * z - y * w) * vx
            + 2 * (y * z + x * w) * vy
            + (1 - 2 * (x * x + y * y)) * vz,
        )

    def test_rotates_from_onto_to(self):
        q = shortest_arc_quaternion((1.0, 0.0, 0.0), (0.0, 1.0, 0.0))
        assert self._rotate(q, (1.0, 0.0, 0.0)) == pytest.approx(
            (0.0, 1.0, 0.0), abs=1e-6
        )

    def test_identical_vectors_give_identity(self):
        assert (
            shortest_arc_quaternion((0.0, 0.0, 1.0), (0.0, 0.0, 1.0)) == IDENTITY_QUAT
        )

    def test_antiparallel_vectors_rotate_180_degrees(self):
        q = shortest_arc_quaternion((0.0, 0.0, 1.0), (0.0, 0.0, -1.0))
        assert math.sqrt(sum(c * c for c in q)) == pytest.approx(1.0, abs=1e-6)
        assert self._rotate(q, (0.0, 0.0, 1.0)) == pytest.approx(
            (0.0, 0.0, -1.0), abs=1e-6
        )

    def test_degenerate_input_returns_identity(self):
        assert (
            shortest_arc_quaternion((0.0, 0.0, 0.0), (0.0, 0.0, 1.0)) == IDENTITY_QUAT
        )


class TestRecoverCutoffTwigPlacements:
    """build_cutoff_thickness deletes branches without redistributing their
    twigs; recovery restores exactly those, reattached to the surviving mesh.
    """

    def test_surviving_twigs_are_not_recovered(self):
        precut = {"twig_long": [_twig((0.1, 0.2, 0.001))]}
        out = recover_cutoff_twig_placements(precut, [(0.1, 0.2, 0.001)], _PlaneModel())
        assert out == {}

    def test_lost_twig_is_recovered(self):
        precut = {"twig_long": [_twig((0.1, 0.2, 0.001)), _twig((0.3, 0.4, 0.001))]}
        out = recover_cutoff_twig_placements(precut, [(0.1, 0.2, 0.001)], _PlaneModel())
        assert [p.position for p in out["twig_long"]] == [(0.3, 0.4, 0.001)]

    def test_empty_cut_set_recovers_everything(self):
        precut = {"twig_long": [_twig((0.1, 0.2, 0.001))]}
        out = recover_cutoff_twig_placements(precut, [], _PlaneModel())
        assert len(out["twig_long"]) == 1

    def test_near_surface_twig_keeps_position_and_orientation(self):
        quat = (0.5, 0.5, 0.5, 0.5)
        precut = {"twig_long": [_twig((0.1, 0.2, 0.002), (1.0, 0.0, 0.0), quat)]}
        out = recover_cutoff_twig_placements(
            precut, [], _PlaneModel(), reattach_threshold=0.01
        )
        got = out["twig_long"][0]
        assert got.position == pytest.approx((0.1, 0.2, 0.002), abs=1e-9)
        assert got.orientation == quat
        assert got.normal == (1.0, 0.0, 0.0)

    def test_far_orphan_is_pulled_onto_the_surface(self):
        # 50 mm above the plane, well beyond the 10 mm threshold.
        precut = {"twig_long": [_twig((0.1, 0.2, 0.05), (1.0, 0.0, 0.0))]}
        out = recover_cutoff_twig_placements(
            precut, [], _PlaneModel(), reattach_threshold=0.01
        )
        got = out["twig_long"][0]
        assert got.position == pytest.approx((0.1, 0.2, 0.0), abs=1e-6)
        # Re-aimed along the direction the deleted shoot ran (straight up).
        assert got.normal == pytest.approx((0.0, 0.0, 1.0), abs=1e-6)

    def test_recovered_twig_binds_to_the_host_face(self):
        precut = {"twig_long": [_twig((0.1, 0.2, 0.001))]}
        out = recover_cutoff_twig_placements(precut, [], _PlaneModel(), bones_info=None)
        got = out["twig_long"][0]
        assert got.bone_id == 7
        assert got.branch_id == 3

    def test_scaled_points_displace_the_recovered_twig(self):
        # Surface lifted 0.5 m by radial scaling; a near-surface twig must
        # follow it rather than staying behind inside the branch.
        model = _PlaneModel()
        scaled = [(x, y, z + 0.5) for (x, y, z) in model.points]
        precut = {"twig_long": [_twig((0.1, 0.2, 0.002))]}
        out = recover_cutoff_twig_placements(precut, [], model, scaled_points=scaled)
        assert out["twig_long"][0].position == pytest.approx(
            (0.1, 0.2, 0.502), abs=1e-6
        )

    def test_mismatched_scaled_points_are_ignored(self):
        model = _PlaneModel()
        precut = {"twig_long": [_twig((0.1, 0.2, 0.002))]}
        out = recover_cutoff_twig_placements(
            precut, [], model, scaled_points=[(0.0, 0.0, 0.0)]
        )
        assert out["twig_long"][0].position == pytest.approx(
            (0.1, 0.2, 0.002), abs=1e-9
        )

    def test_twig_type_is_preserved(self):
        precut = {
            "twig_long": [_twig((0.1, 0.2, 0.001))],
            "twig_short": [
                TwigPlacement(
                    type="twig_short",
                    position=(0.3, 0.1, 0.001),
                    normal=(0.0, 0.0, 1.0),
                )
            ],
        }
        out = recover_cutoff_twig_placements(precut, [], _PlaneModel())
        assert set(out) == {"twig_long", "twig_short"}

    def test_recovered_twig_crowding_a_survivor_is_skipped(self):
        survivors = [(0.0, 0.0, 0.001), (0.5, 0.0, 0.001), (1.0, 0.0, 0.001)]
        precut = {
            "twig_long": [
                _twig(survivors[0]),
                _twig(survivors[1]),
                _twig(survivors[2]),
                _twig((0.0001, 0.0, 0.001)),  # lost, crowds survivors[0]
                _twig((0.9, 0.9, 0.001)),  # lost, well clear of every survivor
            ]
        }
        out = recover_cutoff_twig_placements(precut, survivors, _PlaneModel())
        assert len(out["twig_long"]) == 1
        assert out["twig_long"][0].position == pytest.approx(
            (0.9, 0.9, 0.001), abs=1e-9
        )

    def test_recovered_twigs_are_thinned_when_they_crowd_each_other(self):
        survivors = [(0.0, 0.0, 0.001), (0.5, 0.0, 0.001), (1.0, 0.0, 0.001)]
        precut = {
            "twig_long": [
                _twig(survivors[0]),
                _twig(survivors[1]),
                _twig(survivors[2]),
                _twig((-0.9, -0.9, 0.001)),
                _twig((-0.85, -0.9, 0.001)),  # lost, crowds the twig above
            ]
        }
        out = recover_cutoff_twig_placements(precut, survivors, _PlaneModel())
        assert len(out["twig_long"]) == 1
        assert out["twig_long"][0].position == pytest.approx(
            (-0.9, -0.9, 0.001), abs=1e-9
        )

    def test_min_spacing_ratio_zero_disables_crowding_guard(self):
        survivors = [(0.0, 0.0, 0.001), (0.5, 0.0, 0.001), (1.0, 0.0, 0.001)]
        precut = {
            "twig_long": [
                _twig(survivors[0]),
                _twig(survivors[1]),
                _twig(survivors[2]),
                _twig((0.0001, 0.0, 0.001)),
            ]
        }
        out = recover_cutoff_twig_placements(
            precut, survivors, _PlaneModel(), min_spacing_ratio=0.0
        )
        assert len(out["twig_long"]) == 1


class TestThinPlacementsToLimit:
    """Tests for thin_placements_to_limit."""

    @staticmethod
    def _crowd(n, twig_type="twig_long", offset=0.0):
        return [
            TwigPlacement(
                type=twig_type,
                position=(float(i) + offset, 0.0, 0.0),
                normal=(0.0, 0.0, 1.0),
            )
            for i in range(n)
        ]

    def test_returns_input_untouched_when_under_limit(self):
        placements = {"twig_long": self._crowd(10)}
        assert thin_placements_to_limit(placements, 100) is placements

    def test_disabled_when_limit_is_zero(self):
        placements = {"twig_long": self._crowd(10)}
        assert thin_placements_to_limit(placements, 0) is placements

    def test_thins_to_the_limit(self):
        out = thin_placements_to_limit({"twig_long": self._crowd(100)}, 10)
        assert sum(len(v) for v in out.values()) == 10

    def test_does_not_mutate_the_input(self):
        placements = {"twig_long": self._crowd(100)}
        thin_placements_to_limit(placements, 10)
        assert len(placements["twig_long"]) == 100

    def test_preserves_type_keys_and_mix(self):
        placements = {
            "twig_long": self._crowd(80, "twig_long"),
            "twig_short": self._crowd(20, "twig_short", offset=0.5),
        }
        out = thin_placements_to_limit(placements, 50)
        assert set(out) == {"twig_long", "twig_short"}
        # Every type is thinned by the same ratio, so the mix is preserved.
        assert len(out["twig_long"]) == 40
        assert len(out["twig_short"]) == 10

    def test_empty_type_survives_as_empty(self):
        placements = {"twig_long": self._crowd(100), "twig_dead": []}
        out = thin_placements_to_limit(placements, 10)
        assert out["twig_dead"] == []

    def test_deterministic_for_a_given_seed(self):
        placements = {"twig_long": self._crowd(100)}
        a = thin_placements_to_limit(placements, 10)
        b = thin_placements_to_limit(placements, 10)
        assert [p.position for p in a["twig_long"]] == [
            p.position for p in b["twig_long"]
        ]
