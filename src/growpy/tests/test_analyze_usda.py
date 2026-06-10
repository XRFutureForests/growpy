"""Tests for growpy.tools.analyze_usda parsing functions."""

import pytest

from growpy.tools.analyze_usda import parse_int_array, parse_vec3f_array


class TestParseVec3fArray:
    """Tests for USD point3f[] array parsing."""

    def test_single_point(self):
        text = "point3f[] points = [(1.0, 2.0, 3.0)]"
        result = parse_vec3f_array(text)
        assert len(result) == 1
        assert result[0] == pytest.approx((1.0, 2.0, 3.0))

    def test_multiple_points(self):
        text = "[(1.0, 2.0, 3.0), (4.0, 5.0, 6.0), (7.0, 8.0, 9.0)]"
        result = parse_vec3f_array(text)
        assert len(result) == 3
        assert result[2] == pytest.approx((7.0, 8.0, 9.0))

    def test_negative_values(self):
        text = "[(-1.5, -2.5, 0.0)]"
        result = parse_vec3f_array(text)
        assert result[0] == pytest.approx((-1.5, -2.5, 0.0))

    def test_empty_string(self):
        result = parse_vec3f_array("")
        assert result == []

    def test_no_parentheses(self):
        result = parse_vec3f_array("[]")
        assert result == []

    def test_multiline_format(self):
        text = """point3f[] points = [
            (1.0, 2.0, 3.0),
            (4.0, 5.0, 6.0),
        ]"""
        result = parse_vec3f_array(text)
        assert len(result) == 2


class TestParseIntArray:
    """Tests for USD int[] array parsing."""

    def test_basic(self):
        text = "[3, 3, 3]"
        result = parse_int_array(text)
        assert result == [3, 3, 3]

    def test_with_prefix(self):
        # Note: int[] in "int[] name =" contains brackets that match first,
        # so extract_array_line is used to isolate the data line before parsing.
        text = "faceVertexCounts = [3, 3, 3]"
        result = parse_int_array(text)
        assert result == [3, 3, 3]

    def test_single_value(self):
        text = "[42]"
        result = parse_int_array(text)
        assert result == [42]

    def test_empty_array(self):
        text = "int[] arr = []"
        result = parse_int_array(text)
        assert result == []

    def test_no_brackets(self):
        result = parse_int_array("no brackets here")
        assert result == []

    def test_negative_values(self):
        text = "[-1, 0, 1]"
        result = parse_int_array(text)
        assert result == [-1, 0, 1]

    def test_whitespace_handling(self):
        text = "[  1 , 2 ,  3  ]"
        result = parse_int_array(text)
        assert result == [1, 2, 3]
