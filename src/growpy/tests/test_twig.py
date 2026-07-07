"""Tests for growpy.core.twig module."""

import math

import pytest

from growpy.core.twig import (
    TwigPlacement,
    extract_twig_placements_from_model,
    get_face_center_and_normal,
    normal_to_rotation_matrix,
    rotation_matrix_to_quaternion,
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
        assert tp.orientation == (0.0, 0.0, 1.0)

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

    def __init__(self, faces, points, twig_long, twig_dead, num_twigs):
        self.faces = faces
        self.points = points
        self.face_attribute_twig_long = twig_long
        self.face_attribute_twig_dead = twig_dead
        self._num_twigs = num_twigs

    def get_twig_locations(self):
        return [0.0, 0.0, 0.0] * self._num_twigs

    def get_twig_directions(self):
        return [0.0, 0.0, 1.0] * self._num_twigs

    def get_twig_orientations(self):
        return [0.0, 0.0, 1.0] * self._num_twigs


def _build_model(num_dead_faces, num_living_faces, num_twigs_placed):
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
    return _FakeModel(faces, points, twig_long, twig_dead, num_twigs_placed)


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
