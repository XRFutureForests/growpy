"""Tests for growpy.io.usd.assembly_export utility functions."""

import shutil
from pathlib import Path

from growpy.io.usd.assembly_export import (
    _build_joint_parent_indices,
    _copied_twig_cache,
    _copy_twig_file_cached,
    _extract_species_from_twig_stem,
    clear_twig_copy_cache,
)


class TestBuildJointParentIndices:
    """Tests for _build_joint_parent_indices."""

    def test_single_root(self):
        result = _build_joint_parent_indices(["root"])
        assert result == [-1]

    def test_simple_hierarchy(self):
        names = ["root", "root/joint_1", "root/joint_1/joint_2"]
        result = _build_joint_parent_indices(names)
        assert result == [-1, 0, 1]

    def test_branching_hierarchy(self):
        names = ["root", "root/a", "root/b", "root/a/c"]
        result = _build_joint_parent_indices(names)
        assert result == [-1, 0, 0, 1]

    def test_missing_parent_returns_neg1(self):
        names = ["root/orphan"]
        result = _build_joint_parent_indices(names)
        assert result == [-1]


class TestExtractSpeciesFromTwigStem:
    """Tests for _extract_species_from_twig_stem."""

    def test_foliage_underscore(self):
        assert _extract_species_from_twig_stem("norway_spruce_foliage_a") == "norway_spruce"

    def test_foliage_suffix(self):
        assert _extract_species_from_twig_stem("silver_birch_foliage") == "silver_birch"

    def test_no_foliage(self):
        assert _extract_species_from_twig_stem("plain_stem") == "plain_stem"


class TestClearTwigCopyCache:
    """Tests for clear_twig_copy_cache."""

    def test_clears_cache(self):
        _copied_twig_cache[("a", "b")] = Path("c")
        clear_twig_copy_cache()
        assert len(_copied_twig_cache) == 0


class TestCopyTwigFileCached:
    """Tests for _copy_twig_file_cached."""

    def test_copies_file(self, tmp_path):
        src = tmp_path / "src" / "twig.usda"
        src.parent.mkdir()
        src.write_text("test")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        clear_twig_copy_cache()
        result = _copy_twig_file_cached(src, dest_dir)
        assert result.exists()
        assert result.parent == dest_dir

    def test_skips_second_copy(self, tmp_path):
        src = tmp_path / "src" / "twig.usda"
        src.parent.mkdir()
        src.write_text("test")
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        clear_twig_copy_cache()
        result1 = _copy_twig_file_cached(src, dest_dir)
        # Delete destination file, second call should still return cached path
        result1.unlink()
        result2 = _copy_twig_file_cached(src, dest_dir)
        assert result2 == result1
        assert not result2.exists()  # Was not re-copied
