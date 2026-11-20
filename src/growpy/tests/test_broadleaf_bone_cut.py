"""Broadleaf bone cut (owner 2026-11-20): about 2,000 bones per exported mesh at h20.

The cut is config only: ``[unreal.growth_data_json]`` fraction, absolute bound and
point spacing per species. These tests read the SHIPPED ``config/unreal.toml`` and run
the exporter's own cut functions on one real h20 growth JSON per broadleaf, the tree
that kept the most bones under the cut (E121 / E132 regrow arms, seeds 512/1/2/3/4,
r07/r10). Each fixture is that tree pre-cut at
radius 6 mm, the loosest cut any species uses; that step is exact for any cut at or
above it, so the counts below are the real ones. ``tests/data/bonecut/`` holds gzipped
JSON of branch polylines and radii only (positions rounded to mm).
"""

import gzip
import json
import tomllib
from pathlib import Path

import pytest

from growpy.io.unreal.pve_growth_data_exporter import (
    _decimate_growth_data,
    _resample_growth_data,
    _trunk_base_radius,
)
from growpy.pipelines.forest_stages import (
    _min_branch_radius_fraction_for,
    _min_point_spacing_for,
    _per_species_setting,
)

REPO = Path(__file__).resolve().parents[3]
FIXTURES = Path(__file__).parent / "data" / "bonecut"
BONE_BUDGET = 2200
BROADLEAVES = [
    "common_ash",
    "european_oak",
    "silver_birch",
    "small_leaved_linden",
    "sycamore_maple",
    "wild_cherry",
]


@pytest.fixture(scope="module")
def settings() -> dict:
    with open(REPO / "config" / "unreal.toml", "rb") as fh:
        return tomllib.load(fh)["unreal"]["growth_data_json"]


def _cut(data: dict, settings: dict, species: str) -> tuple[int, float]:
    """Bones and cut diameter (mm) as ``build_growth_data_json`` applies them."""
    cap = _per_species_setting(settings, "max_branch_cut_radius", species, 0) or None
    cut = _trunk_base_radius(data) * _min_branch_radius_fraction_for(settings, species)
    if cap is not None:
        cut = min(cut, cap)
    cut = max(float(settings["min_branch_radius"]), cut)
    out = _decimate_growth_data(data, cut)
    out = _resample_growth_data(out, _min_point_spacing_for(settings, species))
    return len(out["points"]["positions"]), 2000 * cut


@pytest.mark.parametrize("species", BROADLEAVES)
def test_h20_bones_within_budget(settings, species):
    with gzip.open(FIXTURES / f"{species}_h20.json.gz", "rt", encoding="utf-8") as fh:
        data = json.load(fh)
    bones, cut_mm = _cut(data, settings, species)
    assert bones <= BONE_BUDGET
    # Guards the other direction: a cut that wipes out the crown is not a fix.
    assert bones >= 1500
    assert cut_mm >= 25.0  # the beech cut is the floor for every broadleaf


def test_beech_and_conifers_keep_their_shipped_cut(settings):
    """Release 1.2 (beech, conifers) must not move with the broadleaf rule."""
    expected = {
        # species: (fraction, cap radius m or 0, spacing m)
        "european_beech": (0.20, 0.0125, 0.2),
        "norway_spruce": (0.06, 0, 0.0),
        "silver_fir": (0.06, 0, 0.0),
        "scots_pine": (0.06, 0, 0.0),
        "douglas_fir": (0.06, 0, 0.0),
    }
    for species, (frac, cap, spacing) in expected.items():
        got = (
            _min_branch_radius_fraction_for(settings, species),
            _per_species_setting(settings, "max_branch_cut_radius", species, 0),
            _min_point_spacing_for(settings, species),
        )
        assert got == (frac, cap, spacing), species
    margins = settings["crown_base_cut_margin_per_species"]
    assert margins == {"norway_spruce": 0.0, "silver_fir": 0.0, "scots_pine": 0.0}
