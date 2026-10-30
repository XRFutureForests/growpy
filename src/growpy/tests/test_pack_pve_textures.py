"""Tests for the leaf Normal map growpy-pack-pve-textures writes.

MA_Foliage_Trees rebuilds the leaf normal from R/G and reads translucency from B
(MF_TwoSided_Leaves, 2026-09-25). Translucency in alpha, as the packer wrote it
until then, was never sampled: the material took normal Z (~0.95) instead, so
every leaf glowed alike and the real translucency maps went unused. A twig
without a real normal map takes its relief from its colour, as The Grove bumps
cherry and sycamore maple.
"""

from __future__ import annotations

import numpy as np
import pytest
from PIL import Image

from growpy.tools.pack_pve_textures import (
    TRANSLUCENCY_TARGETS,
    is_flat_normal,
    pack_normal_map,
    relief_from_colour,
    translucency_channel,
    twig_growth_habit,
)


def _leaf(size=64, blade=80, vein=160):
    """A leaf cutout: dark blade, one pale vein, transparent border."""
    rgb = np.zeros((size, size, 3), dtype=np.uint8)
    rgb[8:56, 8:56] = blade
    rgb[8:56, 30:34] = vein
    alpha = np.zeros((size, size), dtype=np.uint8)
    alpha[8:56, 8:56] = 255
    return Image.fromarray(rgb), Image.fromarray(alpha)


def _ramp_leaf(size=64):
    """A leaf whose brightness runs 60 -> 140 across it: no pixel near a clip."""
    ramp = np.linspace(60, 140, size, dtype=np.float32).astype(np.uint8)
    rgb = np.repeat(np.tile(ramp, (size, 1))[..., None], 3, axis=2)
    alpha = np.zeros((size, size), dtype=np.uint8)
    alpha[8:56, :] = 255
    return Image.fromarray(rgb), Image.fromarray(alpha)


def _inside(image, alpha):
    return np.asarray(image, dtype=float)[np.asarray(alpha) > 128]


class TestNormalLayout:
    def test_translucency_goes_to_blue_and_there_is_no_alpha(self):
        normal = Image.new("RGB", (8, 8), (100, 150, 250))
        packed = pack_normal_map(normal, Image.new("L", (8, 8), 77))
        assert packed.mode == "RGB"
        assert packed.getpixel((3, 3)) == (100, 150, 77)

    def test_a_translucency_map_of_another_size_is_resampled(self):
        packed = pack_normal_map(
            Image.new("RGB", (16, 16), (128, 128, 255)), Image.new("L", (4, 4), 200)
        )
        assert packed.size == (16, 16)
        assert packed.getpixel((10, 10))[2] == 200


class TestTranslucency:
    @pytest.mark.parametrize("habit", ["broadleaf", "conifer"])
    def test_the_leaf_matches_the_plugin_sample_level(self, habit):
        diffuse, alpha = _ramp_leaf()
        values = _inside(translucency_channel(diffuse, alpha, habit), alpha)
        mean, spread, _ = TRANSLUCENCY_TARGETS[habit]
        assert values.mean() == pytest.approx(mean, abs=1.0)
        assert values.std() == pytest.approx(spread, abs=1.5)

    def test_a_broadleaf_transmits_least_through_its_pale_veins(self):
        diffuse, alpha = _leaf()
        t = translucency_channel(diffuse, alpha, "broadleaf")
        assert t.getpixel((31, 30)) < t.getpixel((15, 30))

    def test_a_conifer_transmits_most_where_the_needle_is_bright(self):
        diffuse, alpha = _leaf()
        t = translucency_channel(diffuse, alpha, "conifer")
        assert t.getpixel((31, 30)) > t.getpixel((15, 30))

    def test_a_translucency_map_sets_the_pattern_not_the_level(self):
        # The Grove maps sit at 0.14-0.21 of full scale; as authored they would
        # make the three species that have one the dimmest in the set.
        diffuse, alpha = _leaf()
        dim = np.full((64, 64), 30, dtype=np.uint8)
        dim[8:56, 8:20] = 50
        t = translucency_channel(diffuse, alpha, "broadleaf", Image.fromarray(dim))
        assert _inside(t, alpha).mean() == pytest.approx(
            TRANSLUCENCY_TARGETS["broadleaf"][0], abs=1.0
        )
        assert t.getpixel((12, 30)) > t.getpixel((40, 30))

    def test_outside_the_leaf_holds_the_mean_so_mips_do_not_darken_the_edge(self):
        diffuse, alpha = _leaf()
        t = translucency_channel(diffuse, alpha, "broadleaf")
        assert t.getpixel((2, 2)) == round(TRANSLUCENCY_TARGETS["broadleaf"][0])

    def test_a_flat_leaf_gets_the_flat_mean(self):
        diffuse, alpha = _leaf(vein=80)
        values = _inside(translucency_channel(diffuse, alpha, "conifer"), alpha)
        assert set(values) == {round(TRANSLUCENCY_TARGETS["conifer"][0])}


class TestHabit:
    @pytest.mark.parametrize(
        ("twig", "habit"),
        [
            ("pacific_silver_fir_twig", "conifer"),
            ("scots_pine_twig", "conifer"),
            ("european_beech_twig", "broadleaf"),
            ("one_leaved_ash_twig", "broadleaf"),
            ("no_such_twig", "broadleaf"),
        ],
    )
    def test_the_habit_comes_from_the_species_using_the_twig(self, twig, habit):
        assert twig_growth_habit(twig) == habit


class TestRelief:
    def test_a_placeholder_normal_counts_as_no_relief(self):
        assert is_flat_normal(Image.new("RGB", (32, 32), (128, 128, 255)))
        bumpy = np.full((32, 32, 3), 128, dtype=np.uint8)
        bumpy[:, ::4, 0] = 160
        assert not is_flat_normal(Image.fromarray(bumpy))

    def test_the_colour_raises_relief_along_the_vein(self):
        diffuse, alpha = _leaf()
        normal = np.asarray(relief_from_colour(diffuse, alpha), dtype=int)
        # the pale vein (x 30..33) is a ridge: X tilts one way on its left
        # flank and the other way on its right, and not at all mid-blade
        left, right, blade = normal[30, 29, 0], normal[30, 34, 0], normal[30, 15, 0]
        assert left > 128 > right or left < 128 < right
        assert abs(blade - 128) <= 1
        assert normal[30, 15, 2] > 250  # flat blade faces straight out

    def test_the_leaf_edge_raises_no_cliff(self):
        # Outside the cutout the height is the leaf's mean, so the transparent
        # atlas border (black here) does not tilt every edge texel.
        diffuse, alpha = _leaf(vein=80)
        normal = np.asarray(relief_from_colour(diffuse, alpha), dtype=int)
        assert abs(normal[30, 8, 0] - 128) <= 1
        assert abs(normal[8, 30, 1] - 128) <= 1
