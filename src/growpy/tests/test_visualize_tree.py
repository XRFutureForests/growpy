"""Tests for growpy.tools.visualize_tree USDA parsing functions."""

import numpy as np
import pytest

from growpy.tools.visualize_tree import parse_usda_faces, parse_usda_points

SAMPLE_USDA = """\
#usda 1.0
(
    defaultPrim = "Tree"
)

def Mesh "Stems"
{
    point3f[] points = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.5, 0.5, 2.0), (0.5, -0.5, 2.0)]
    int[] faceVertexCounts = [3, 3]
    int[] faceVertexIndices = [0, 1, 2, 0, 2, 3]
}
"""


class TestParseUsdaPoints:
    """Tests for USDA vertex parsing."""

    def test_parses_points(self, tmp_path):
        f = tmp_path / "tree.usda"
        f.write_text(SAMPLE_USDA, encoding="utf-8")
        points = parse_usda_points(f)
        assert points.shape == (4, 3)

    def test_correct_values(self, tmp_path):
        f = tmp_path / "tree.usda"
        f.write_text(SAMPLE_USDA, encoding="utf-8")
        points = parse_usda_points(f)
        np.testing.assert_allclose(points[0], [0.0, 0.0, 0.0])
        np.testing.assert_allclose(points[2], [0.5, 0.5, 2.0])

    def test_no_points_returns_empty(self, tmp_path):
        f = tmp_path / "empty.usda"
        f.write_text("#usda 1.0\ndef Mesh 'x' {}\n", encoding="utf-8")
        points = parse_usda_points(f)
        assert points.shape == (0, 3)

    def test_single_point(self, tmp_path):
        content = """\
def Mesh "X"
{
    point3f[] points = [(1.5, 2.5, 3.5)]
}
"""
        f = tmp_path / "single.usda"
        f.write_text(content, encoding="utf-8")
        points = parse_usda_points(f)
        assert points.shape == (1, 3)
        np.testing.assert_allclose(points[0], [1.5, 2.5, 3.5])


class TestParseUsdaFaces:
    """Tests for USDA face index parsing."""

    def test_parses_faces(self, tmp_path):
        f = tmp_path / "tree.usda"
        f.write_text(SAMPLE_USDA, encoding="utf-8")
        faces = parse_usda_faces(f)
        assert len(faces) == 2

    def test_correct_indices(self, tmp_path):
        f = tmp_path / "tree.usda"
        f.write_text(SAMPLE_USDA, encoding="utf-8")
        faces = parse_usda_faces(f)
        assert faces[0] == (0, 1, 2)
        assert faces[1] == (0, 2, 3)

    def test_no_faces_returns_empty(self, tmp_path):
        f = tmp_path / "empty.usda"
        f.write_text("#usda 1.0\ndef Mesh 'x' {}\n", encoding="utf-8")
        faces = parse_usda_faces(f)
        assert faces == []
