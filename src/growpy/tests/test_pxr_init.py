"""Tests for growpy.utils.pxr_init USD initialization."""

import os
from unittest.mock import MagicMock, patch

import pytest

from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema


class TestEnsurePxrWithUnrealSchema:
    """Tests for PXR initialization and schema registration."""

    def test_runs_without_error(self):
        ensure_pxr_with_unreal_schema()

    @patch.dict(os.environ, {"PXR_PLUGINPATH_NAME": ""}, clear=False)
    def test_empty_plugin_path_no_error(self):
        ensure_pxr_with_unreal_schema()

    @patch.dict(os.environ, {}, clear=False)
    def test_no_plugin_path_no_error(self):
        if "PXR_PLUGINPATH_NAME" in os.environ:
            del os.environ["PXR_PLUGINPATH_NAME"]
        ensure_pxr_with_unreal_schema()

    @patch("growpy.utils.pxr_init.os.path.exists", return_value=False)
    @patch.dict(os.environ, {"PXR_PLUGINPATH_NAME": "/fake/path"}, clear=False)
    def test_nonexistent_plugin_path_no_error(self, mock_exists):
        ensure_pxr_with_unreal_schema()
