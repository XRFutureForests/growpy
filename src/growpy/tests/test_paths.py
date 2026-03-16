"""Tests for growpy.config.paths module."""

import pytest

from growpy.config.paths import _normalize_grove_texture_name


class TestNormalizeGroveTextureName:
    """Tests for _normalize_grove_texture_name."""

    def test_simple_name_with_number(self):
        assert _normalize_grove_texture_name("Beech60.jpg") == ("beech_60", ".jpg")

    def test_multi_word_camel_case(self):
        stem, ext = _normalize_grove_texture_name("BaldCypress80.jpg")
        assert stem == "bald_cypress_80"
        assert ext == ".jpg"

    def test_no_number(self):
        stem, ext = _normalize_grove_texture_name("OakBark.png")
        assert stem == "oak_bark"
        assert ext == ".png"

    def test_single_word_lowercase(self):
        stem, ext = _normalize_grove_texture_name("birch.jpg")
        assert stem == "birch"
        assert ext == ".jpg"

    def test_png_extension(self):
        _, ext = _normalize_grove_texture_name("SomeTex.png")
        assert ext == ".png"

    def test_multiple_numbers(self):
        stem, ext = _normalize_grove_texture_name("Pine120Bark.jpg")
        assert "pine" in stem
        assert "120" in stem
        assert ext == ".jpg"

    def test_already_snake_case(self):
        stem, _ = _normalize_grove_texture_name("some_texture.jpg")
        assert stem == "some_texture"
