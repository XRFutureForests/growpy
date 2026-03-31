"""Tests for growpy.cli.dataset_pipeline._parse_steps.

Uses importlib to import only the function, avoiding transitive imports
that pull in Blender/Grove dependencies.
"""

import argparse
import importlib
import types

import pytest


def _get_parse_steps():
    """Import _parse_steps without triggering heavy transitive imports."""
    import growpy.cli.dataset_pipeline as mod

    return mod._parse_steps


try:
    _parse_steps = _get_parse_steps()
    _IMPORT_OK = True
except Exception:
    _IMPORT_OK = False
    _parse_steps = None

pytestmark = pytest.mark.skipif(
    not _IMPORT_OK,
    reason="dataset_pipeline imports unavailable (Blender/Grove deps)",
)


class TestParseSteps:
    """Tests for --steps argument parsing."""

    def test_all_keyword(self):
        assert _parse_steps("all") == [1, 2, 3, 4]

    def test_all_case_insensitive(self):
        assert _parse_steps("ALL") == [1, 2, 3, 4]
        assert _parse_steps("All") == [1, 2, 3, 4]

    def test_single_step(self):
        assert _parse_steps("3") == [3]

    def test_comma_separated(self):
        assert _parse_steps("1,3,4") == [1, 3, 4]

    def test_sorted_output(self):
        assert _parse_steps("4,1,2") == [1, 2, 4]

    def test_deduplicates(self):
        assert _parse_steps("2,2,3") == [2, 3]

    def test_whitespace_handling(self):
        assert _parse_steps("  1 , 2 , 3  ") == [1, 2, 3]

    def test_invalid_step_number(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid step numbers"):
            _parse_steps("1,5")

    def test_non_integer(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid --steps"):
            _parse_steps("abc")

    def test_zero_step(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Invalid step numbers"):
            _parse_steps("0")
