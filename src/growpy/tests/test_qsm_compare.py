"""growpy.structure.compare: placement of generated trees in the real distribution."""

import numpy as np
import pandas as pd
import pytest

from growpy.structure.compare import benjamini_hochberg, cliffs_delta, compare, gaps


def _table():
    rng = np.random.default_rng(1)
    real = pd.DataFrame(
        {
            "source_kind": "scan",
            "source": "biodiv",
            "tier": ["A"] * 40,
            "species_key": "european_beech",
            "height_class": "h20-30",
            "T.path_fraction": rng.normal(0.70, 0.05, 40),
            "G.fork_asymmetry_p50": rng.normal(0.15, 0.05, 40),
        }
    )
    generated = pd.DataFrame(
        {
            "source_kind": "generated",
            "source": "growpy",
            "tier": None,
            "species_key": "european_beech",
            "height_class": "h20-30",
            "T.path_fraction": [0.69, 0.71, 0.70, 0.72],  # inside the real spread
            "G.fork_asymmetry_p50": [0.02, 0.03, 0.03, 0.04],  # far below it
        }
    )
    return pd.concat([real, generated], ignore_index=True)


def test_cliffs_delta_and_fdr():
    assert cliffs_delta(np.array([2, 3]), np.array([0, 1])) == 1.0
    assert cliffs_delta(np.array([1]), np.array([1])) == 0.0
    adjusted = benjamini_hochberg(pd.Series([0.01, 0.04, np.nan, 0.03]))
    assert adjusted.iloc[0] == pytest.approx(0.03)  # 0.01 * 3 / 1
    assert np.isnan(adjusted.iloc[2])


def test_generated_trees_are_placed_in_the_real_distribution():
    cells = compare(_table()).set_index("descriptor")
    near, far = cells.loc["T.path_fraction"], cells.loc["G.fork_asymmetry_p50"]
    assert abs(near["robust_z"]) < 1 and 20 < near["percentile"] < 80
    assert far["robust_z"] < -1.5 and far["percentile"] < 5
    assert far["cliffs_delta"] == pytest.approx(
        -1.0
    )  # every generated value lies below
    assert far["p_fdr"] < 0.05 and near["p_fdr"] > 0.05
    assert far["real_tiers"] == "A/B"


def test_gap_summary_ranks_the_worst_descriptor_first():
    summary = gaps(compare(_table()))
    assert summary.iloc[0]["descriptor"] == "G.fork_asymmetry_p50"
