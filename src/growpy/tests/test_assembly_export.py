"""Tests for growpy.io.usd.assembly_export utility functions."""

from pathlib import Path

from growpy.io.usd import assembly_export
from growpy.io.usd.assembly_export import (
    _build_joint_parent_indices,
    _copied_twig_cache,
    _copy_twig_file_cached,
    _extract_species_from_twig_stem,
    _sanitize_prim_name,
    clear_twig_copy_cache,
    create_assembly,
    create_combined_twig_usda,
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


class TestSanitizePrimName:
    """Tests for _sanitize_prim_name."""

    def test_replaces_invalid_chars(self):
        assert _sanitize_prim_name("European Oak") == "european_oak"

    def test_leading_digit_gets_underscore_prefix(self):
        assert _sanitize_prim_name("07_test") == "_07_test"

    def test_lowercases(self):
        assert (
            _sanitize_prim_name("Hornbeam_r00_H05M_D04CM_full_assembly")
            == "hornbeam_r00_h05m_d04cm_full_assembly"
        )


class TestCreateAssemblyUniqueNaming:
    """Regression test for the Unreal DataTable RowName collision bug.

    Every height/DBH/density/radius variant of a species used to get the
    SAME internal USD default-prim name (species only), which Unreal uses
    as the imported SkeletalMesh asset name -- so importing a second
    variant into the same destination folder overwrote the first. The
    default prim must now be unique per exported file (derived from
    output_path), not per species.
    """

    def test_default_prim_differs_across_variants_of_same_species(self, tmp_path):
        from pxr import Usd

        tree_usd = tmp_path / "european_oak_stems.usda"
        stems_stage = Usd.Stage.CreateNew(str(tree_usd))
        stems_stage.DefinePrim("/european_oak_stems", "Xform")
        stems_stage.GetRootLayer().Save()

        out_a = tmp_path / "European_Oak_r00_h05m_d04cm_full_assembly.usda"
        out_b = tmp_path / "European_Oak_r00_h12m_d18cm_full_assembly.usda"

        for out_path in (out_a, out_b):
            assert create_assembly(
                tree_usd_path=tree_usd,
                output_path=out_path,
                species_name="European Oak",
                use_skeletal_mesh=False,
                validate=False,
            )

        stage_a = Usd.Stage.Open(str(out_a))
        stage_b = Usd.Stage.Open(str(out_b))
        name_a = stage_a.GetDefaultPrim().GetName()
        name_b = stage_b.GetDefaultPrim().GetName()

        assert name_a != name_b
        assert name_a == "european_oak_r00_h05m_d04cm_full_assembly"
        assert name_b == "european_oak_r00_h12m_d18cm_full_assembly"



class TestCreateCombinedTwigUsda:
    """Regression: the wrapper glob must use the twig extension, not the
    configured tree extension -- twigs are always .usda regardless of
    [export] usd_format.
    """

    def test_finds_usda_twigs_when_tree_format_is_usdc(self, tmp_path, monkeypatch):
        class _FakeConfig:
            export_usd_format = "usdc"

        monkeypatch.setattr(assembly_export, "_get_config", lambda: _FakeConfig())

        instances_dir = tmp_path / "Instances"
        instances_dir.mkdir()
        (instances_dir / "european_beech_foliage_a_skeletal.usda").write_text(
            "#usda 1.0\n"
        )
        (instances_dir / "european_beech_foliage_b_skeletal.usda").write_text(
            "#usda 1.0\n"
        )

        result = create_combined_twig_usda(instances_dir)

        assert len(result) == 1
        assert result[0].name == "european_beech_twigs_combined_skeletal.usda"
        assert result[0].exists()
