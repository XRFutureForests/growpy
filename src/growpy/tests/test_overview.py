"""Tests for growpy.io.overview pure helper functions.

Does not test functions requiring filesystem, matplotlib, or pandas I/O.
"""

import pytest

from growpy.io.overview import (
    _snap_to_interval,
    _build_interval_columns,
    _height_label,
    _ICON_PATTERN,
)


class TestSnapToInterval:
    """Tests for height snapping to interval grid."""

    @pytest.mark.parametrize(
        "height,interval,expected",
        [
            (10, 5, 10),
            (12, 5, 10),
            (13, 5, 15),
            (7, 5, 5),
            (3, 5, 5),
            (1, 5, 0),
            (0, 5, 0),
            (25, 10, 20),
            (24, 10, 20),
        ],
    )
    def test_snapping(self, height, interval, expected):
        assert _snap_to_interval(height, interval) == expected

    def test_zero_interval_passthrough(self):
        assert _snap_to_interval(7, 0) == 7

    def test_negative_interval_passthrough(self):
        assert _snap_to_interval(7, -1) == 7


class TestBuildIntervalColumns:
    """Tests for building sorted interval column list from entries."""

    def test_basic(self):
        entries = {
            ("spruce", "comp"): {5: ("p1", "a1"), 10: ("p2", "a2"), 15: ("p3", "a3")},
        }
        result = _build_interval_columns(entries, 5)
        assert result == [5, 10, 15]

    def test_snaps_to_interval(self):
        entries = {
            ("spruce", "comp"): {7: ("p1", "a1"), 12: ("p2", "a2")},
        }
        result = _build_interval_columns(entries, 5)
        # 7 -> 5, 12 -> 10
        assert result == [5, 10]

    def test_deduplicates(self):
        entries = {
            ("spruce", "comp"): {6: ("p1", "a1"), 8: ("p2", "a2")},
        }
        # Both 6 and 8 snap to 10 with interval=10
        result = _build_interval_columns(entries, 10)
        assert result == [10]

    def test_excludes_zero(self):
        entries = {
            ("spruce", "comp"): {1: ("p1", "a1")},
        }
        # 1 snaps to 0 with interval=5; 0 < interval so excluded
        result = _build_interval_columns(entries, 5)
        assert result == []

    def test_empty_entries(self):
        result = _build_interval_columns({}, 5)
        assert result == []

    def test_multiple_species(self):
        entries = {
            ("spruce", "comp"): {5: ("p1", "a1")},
            ("beech", "open"): {10: ("p2", "a2"), 20: ("p3", "a3")},
        }
        result = _build_interval_columns(entries, 5)
        assert result == [5, 10, 20]


class TestHeightLabel:
    """Tests for height label formatting."""

    @pytest.mark.parametrize(
        "meters,expected",
        [
            (5, "h05m"),
            (10, "h10m"),
            (0, "h00m"),
            (100, "h100m"),
        ],
    )
    def test_format(self, meters, expected):
        assert _height_label(meters) == expected


class TestIconPattern:
    """Tests for the icon filename regex pattern."""

    def test_matches_valid_icon(self):
        m = _ICON_PATTERN.match("norway_spruce_comp_h10m_d15cm_high_icon.png")
        assert m is not None
        assert m.group(1) == "norway_spruce"
        assert m.group(2) == "comp"
        assert m.group(3) == "h10m"
        assert m.group(4) == "d15cm"
        assert m.group(5) == "high"

    def test_matches_open_context(self):
        m = _ICON_PATTERN.match("european_beech_open_h20m_d30cm_medium_icon.png")
        assert m is not None
        assert m.group(2) == "open"

    def test_no_match_without_icon_suffix(self):
        m = _ICON_PATTERN.match("norway_spruce_comp_h10m_d15cm_high.png")
        assert m is None

    def test_no_match_random_name(self):
        m = _ICON_PATTERN.match("some_random_file.png")
        assert m is None
