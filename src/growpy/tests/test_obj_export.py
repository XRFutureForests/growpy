"""Tests for growpy.io.helios.obj_export utility functions."""

from growpy.io.helios.obj_export import (
    WOOD_MATERIAL_KEYWORDS,
    _classified_twig_cache,
    _resolve_to_static,
    clear_twig_cache,
)


class TestResolveToStatic:
    """Tests for _resolve_to_static filename conversion."""

    def test_converts_skeletal_to_static(self):
        assert _resolve_to_static("tree_skeletal.usda") == "tree_static.usda"

    def test_no_match_returns_unchanged(self):
        assert _resolve_to_static("tree_static.usda") == "tree_static.usda"

    def test_handles_complex_name(self):
        result = _resolve_to_static("norway_spruce_foliage_a_skeletal.usda")
        assert result == "norway_spruce_foliage_a_static.usda"


class TestClearTwigCache:
    """Tests for clear_twig_cache."""

    def test_clears_populated_cache(self):
        _classified_twig_cache["dummy"] = (None, None, None)
        clear_twig_cache()
        assert len(_classified_twig_cache) == 0

    def test_clears_empty_cache(self):
        clear_twig_cache()
        assert len(_classified_twig_cache) == 0


class TestWoodMaterialKeywords:
    """Tests for the WOOD_MATERIAL_KEYWORDS constant."""

    def test_contains_bark(self):
        assert "bark" in WOOD_MATERIAL_KEYWORDS

    def test_contains_branch(self):
        assert "branch" in WOOD_MATERIAL_KEYWORDS

    def test_is_tuple(self):
        assert isinstance(WOOD_MATERIAL_KEYWORDS, tuple)
