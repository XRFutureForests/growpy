"""Which Grove leaf texture becomes a twig's leaf colour and its underside.

The paper birch ships a Summer and a Fall pair. Directory order put Fall first,
and both the foliage copy (first file wins) and the standardizer (which read
"summer" as a top side and "fall" as an underside) left the birch leaves
autumn-yellow in summer (2026-09-25). The sycamore maple twig is itself the
Fall set, and the packer took "fall" in its name for an autumn variant, so its
top and bottom never reached the leaf material.
"""

from __future__ import annotations

import pytest
from PIL import Image

from growpy.io.usd.texture_utils import season_rank, standardize_twig_textures
from growpy.tools.pack_pve_textures import _foliage_maps

SUMMER_TOP, SUMMER_BOTTOM = (20, 90, 20), (60, 110, 60)
FALL_TOP, FALL_BOTTOM = (200, 150, 30), (170, 140, 60)


def _birch(tmp_path):
    textures = tmp_path / "paper_birch_twig" / "textures"
    textures.mkdir(parents=True)
    for name, colour in (
        ("PaperBirchFallBottom", FALL_BOTTOM),
        ("PaperBirchFallTop", FALL_TOP),
        ("PaperBirchSummerBottom", SUMMER_BOTTOM),
        ("PaperBirchSummerTop", SUMMER_TOP),
    ):
        Image.new("RGB", (4, 4), colour).save(textures / f"{name}.png")
    return textures.parent


def _colour(path):
    return Image.open(path).convert("RGB").getpixel((1, 1))


def test_summer_and_unmarked_textures_rank_first():
    assert season_rank("PaperBirchSummerTop") == season_rank("OakEuropeanTop") == 0
    assert season_rank("PaperBirchFallTop") == 1
    assert season_rank("SomethingSpring") == 2


def test_the_standardizer_keeps_the_summer_pair_and_its_sides(tmp_path):
    twig = _birch(tmp_path)
    standardize_twig_textures(twig)
    textures = twig / "textures"
    assert _colour(textures / "paper_birch_twig_diffuse_top.png") == SUMMER_TOP
    assert _colour(textures / "paper_birch_twig_diffuse_bottom.png") == SUMMER_BOTTOM


def test_the_foliage_copy_prefers_summer(tmp_path):
    bpy = pytest.importorskip("bpy")
    # As the twig export does: Blender's own pxr before the pip one, whose DLLs
    # clash with bpy's.
    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
    material_texture = pytest.importorskip("growpy.io.usd.material_texture")

    twig = _birch(tmp_path)
    out = tmp_path / "out"
    out.mkdir()
    material_texture.copy_opaque_textures_for_skeletal(
        twig, out, "paper_birch_foliage", {}
    )
    copied = out / "textures"
    assert _colour(copied / "paper_birch_foliage_diffuse_top.png") == SUMMER_TOP
    assert _colour(copied / "paper_birch_foliage_diffuse_bottom.png") == SUMMER_BOTTOM


def test_packed_maps_are_never_read_back_as_sources(tmp_path):
    # The packer writes _pve_ maps into the same folder; read back, its packed
    # Normal became the twig's normal map and its Base Color the twig diffuse.
    twig = _birch(tmp_path)
    textures = twig / "textures"
    packed = textures / "paper_birch_twig_pve_basecolor.png"
    Image.new("RGBA", (4, 4), (1, 2, 3, 4)).save(packed)
    packed = textures / "paper_birch_twig_pve_normal.png"
    Image.new("RGB", (4, 4), (90, 90, 186)).save(packed)
    standardize_twig_textures(twig)
    assert not (textures / "paper_birch_twig_normal.png").exists()
    assert not (textures / "paper_birch_twig_diffuse.png").exists()


def test_a_fall_twig_keeps_its_top_and_bottom(tmp_path):
    textures = tmp_path / "sycamore_maple_fall_twig" / "textures"
    textures.mkdir(parents=True)
    for name in (
        "SycamoreMapleFallTop",
        "SycamoreMapleFallBottom",
        "sycamore_maple_fall_foliage_diffuse_top",
        "sycamore_maple_fall_foliage_diffuse_bottom",
    ):
        Image.new("RGB", (4, 4)).save(textures / f"{name}.png")
    roles = {k: v.name for k, v in _foliage_maps(textures.parent).items()}
    assert roles == {
        "diffuse": "sycamore_maple_fall_foliage_diffuse_top.png",
        "bottom": "sycamore_maple_fall_foliage_diffuse_bottom.png",
    }


def test_a_real_autumn_variant_still_drives_the_season_colour(tmp_path):
    twig = _birch(tmp_path)
    for side, colour in (("top", SUMMER_TOP), ("bottom", SUMMER_BOTTOM)):
        Image.new("RGB", (4, 4), colour).save(
            twig / "textures" / f"paper_birch_foliage_diffuse_{side}.png"
        )
    roles = {k: v.name for k, v in _foliage_maps(twig).items()}
    assert roles["diffuse"] == "paper_birch_foliage_diffuse_top.png"
    assert roles["fall"] == "PaperBirchFallTop.png"
