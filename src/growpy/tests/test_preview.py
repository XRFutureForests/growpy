"""Tests for growpy.io.usd.preview image generation."""

import logging
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from growpy.io.usd.preview import generate_preview_image


class TestGeneratePreviewImage:
    """Tests for skeleton preview image generation."""

    def _mock_timer(self):
        timer = MagicMock()
        timer.track = MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=None),
            __exit__=MagicMock(return_value=False),
        ))
        return timer

    def test_returns_none_for_none_skeleton(self, tmp_path):
        result = generate_preview_image(
            tmp_path, "test_tree", "test_h10m", None, self._mock_timer()
        )
        assert result is None

    def test_returns_none_for_empty_skeleton(self, tmp_path):
        skeleton = MagicMock()
        skeleton.points = []
        result = generate_preview_image(
            tmp_path, "test_tree", "test_h10m", skeleton, self._mock_timer()
        )
        assert result is None

    def test_returns_view_bounds_for_valid_skeleton(self, tmp_path):
        skeleton = MagicMock()
        skeleton.points = [
            (0.0, 0.0, 0.0), (0.0, 0.0, 5.0), (1.0, 0.0, 3.0),
        ]
        skeleton.poly_lines = [[0, 1], [0, 2]]
        skeleton.point_attribute_radius = [0.1, 0.05, 0.03]

        result = generate_preview_image(
            tmp_path, "test_tree", "test_h10m", skeleton, self._mock_timer()
        )
        assert result is not None
        assert isinstance(result, list)
