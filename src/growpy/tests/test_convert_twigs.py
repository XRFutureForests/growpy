"""Tests for growpy.cli.convert_twigs pure-logic functions.

Covers classify_texture_type and find_textures_for_material (with real
temp directories). Does not test process_twig_directory which requires Blender.
"""


import pytest

from growpy.cli.convert_twigs import classify_texture_type, find_textures_for_material


class TestClassifyTextureType:
    """Tests for PBR texture type classification from filename."""

    @pytest.mark.parametrize(
        "stem,expected",
        [
            ("leaf_diffuse", "diffuse"),
            ("bark_albedo", "diffuse"),
            ("color_basecolor", "diffuse"),
        ],
    )
    def test_diffuse_variants(self, stem, expected, tmp_path):
        p = tmp_path / f"{stem}.png"
        assert classify_texture_type(p) == expected

    @pytest.mark.parametrize(
        "stem,expected",
        [
            ("leaf_alpha", "alpha"),
            ("opacity_mask", "alpha"),
        ],
    )
    def test_alpha_variants(self, stem, expected, tmp_path):
        p = tmp_path / f"{stem}.png"
        assert classify_texture_type(p) == expected

    @pytest.mark.parametrize(
        "stem,expected",
        [
            ("bark_normal", "normal"),
            ("leaf_nrm", "normal"),
            ("bump_map", "normal"),
        ],
    )
    def test_normal_variants(self, stem, expected, tmp_path):
        p = tmp_path / f"{stem}.png"
        assert classify_texture_type(p) == expected

    def test_top_modifier(self, tmp_path):
        p = tmp_path / "leaf_top.png"
        assert classify_texture_type(p) == "diffuse_top"

    def test_bottom_modifier(self, tmp_path):
        p = tmp_path / "leaf_bottom.png"
        assert classify_texture_type(p) == "diffuse_bottom"

    def test_translucent(self, tmp_path):
        p = tmp_path / "leaf_translucent.png"
        assert classify_texture_type(p) == "translucent"

    def test_unknown_defaults_to_diffuse(self, tmp_path):
        p = tmp_path / "random_texture.png"
        assert classify_texture_type(p) == "diffuse"


class TestFindTexturesForMaterial:
    """Tests for texture file discovery and matching."""

    def test_finds_textures_in_directory(self, tmp_path):
        tex_dir = tmp_path / "textures"
        tex_dir.mkdir()
        (tex_dir / "oak_diffuse.png").touch()
        (tex_dir / "oak_normal.png").touch()
        (tex_dir / "oak_alpha.png").touch()

        result = find_textures_for_material(tmp_path, "oak", search_parent=False)

        assert "diffuse" in result
        assert "normal" in result
        assert "alpha" in result

    def test_empty_directory(self, tmp_path):
        result = find_textures_for_material(tmp_path, "oak", search_parent=False)
        assert result == {}

    def test_scores_by_name_overlap(self, tmp_path):
        tex_dir = tmp_path / "textures"
        tex_dir.mkdir()
        (tex_dir / "beech_diffuse.png").touch()
        (tex_dir / "oak_diffuse.png").touch()

        result = find_textures_for_material(tmp_path, "oak", search_parent=False)
        assert "diffuse" in result
        assert "oak" in result["diffuse"].stem

    def test_searches_parent_when_enabled(self, tmp_path):
        parent_tex = tmp_path / "textures"
        parent_tex.mkdir()
        (parent_tex / "leaf_diffuse.png").touch()
        child_dir = tmp_path / "child"
        child_dir.mkdir()

        result = find_textures_for_material(child_dir, "leaf", search_parent=True)
        assert "diffuse" in result

    def test_no_parent_search_when_disabled(self, tmp_path):
        parent_tex = tmp_path / "textures"
        parent_tex.mkdir()
        (parent_tex / "leaf_diffuse.png").touch()
        child_dir = tmp_path / "child"
        child_dir.mkdir()

        result = find_textures_for_material(child_dir, "leaf", search_parent=False)
        assert result == {}
