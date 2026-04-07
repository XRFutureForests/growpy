"""Tests for growpy.io.usd.twig_export functions."""

import pytest

from growpy.io.usd.twig_export import classify_texture_from_name, export_blender_mesh_to_usd


class TestTwigExportModule:
    """Verify module loads and key functions are accessible."""

    def test_export_function_exists(self):
        assert callable(export_blender_mesh_to_usd)


class TestClassifyTextureFromName:
    """Tests for classify_texture_from_name."""

    @pytest.mark.parametrize(
        "name,expected",
        [
            ("leaf_alpha.png", "alpha"),
            ("opacity_mask.png", "alpha"),
            ("OakAlpha.png", "alpha"),
            ("leaf_normal.png", "normal"),
            ("OakNorm.png", "normal"),
            ("Leaf_nrm.png", "normal"),
            ("leaf_bump.png", "bump"),
            ("Height_Map.png", "bump"),
            ("displacement.exr", "bump"),
            ("oak_bark.png", "bark"),
            ("BarkTop.png", "bark_top"),
            ("bark_upper_face.jpg", "bark_top"),
            ("bark_bottom.png", "bark_bottom"),
            ("bark_lower.png", "bark_bottom"),
            ("bark_back.png", "bark_bottom"),
            ("OakTop.png", "diffuse_top"),
            ("leaf_upper.png", "diffuse_top"),
            ("face_texture.png", "diffuse_top"),
            ("OakBottom.png", "diffuse_bottom"),
            ("leaf_lower.png", "diffuse_bottom"),
            ("back_side.png", "diffuse_bottom"),
            ("leaf_translucent.png", "translucent"),
            ("sss_map.png", "translucent"),
            ("transmission.png", "translucent"),
            ("leaf_roughness.png", "roughness"),
            ("metallic.png", "metallic"),
            ("ambient_occlusion.png", "ao"),
            ("leaf_diffuse.png", "diffuse"),
            ("OakLeaf.png", "diffuse"),
            ("some_texture.png", "diffuse"),
        ],
    )
    def test_classification(self, name, expected):
        assert classify_texture_from_name(name) == expected

    def test_case_insensitive(self):
        assert classify_texture_from_name("LEAF_ALPHA.PNG") == "alpha"
        assert classify_texture_from_name("OAK_NORMAL.PNG") == "normal"

    def test_alpha_takes_precedence_over_top_bottom(self):
        assert classify_texture_from_name("top_alpha.png") == "alpha"

    def test_normal_takes_precedence_over_top_bottom(self):
        assert classify_texture_from_name("top_normal.png") == "normal"
