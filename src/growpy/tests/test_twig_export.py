"""Tests for growpy.io.usd.twig_export import-level constants."""

from growpy.io.usd.twig_export import export_blender_mesh_to_usd


class TestTwigExportModule:
    """Verify module loads and key functions are accessible."""

    def test_export_function_exists(self):
        assert callable(export_blender_mesh_to_usd)
