"""growpy.structure reference store, per-species score and realism gate."""

import numpy as np
import pandas as pd
import pytest

from growpy.structure.gate import gate, growth_consistency, series_of, verdict
from growpy.structure.reference import (
    CATALOG_SPECIES,
    QUANTILES,
    build_reference,
    coverage,
    default_reference_dir,
    height_bin,
    load_core_set,
    load_manifest,
    load_reference,
    normalise_by_height,
    write_reference,
)
from growpy.structure.score import descriptor_gaps, score_cells, species_summary


def _real(n=60, species="european_beech", tier="A", seed=1):
    rng = np.random.default_rng(seed)
    height = rng.uniform(10, 30, n)
    return pd.DataFrame(
        {
            "tree_uid": [f"r{seed}:{i}" for i in range(n)],
            "source": "biodiv",
            "source_kind": "scan",
            "tier": tier,
            "species_key": species,
            "height_class": [
                f"h{int(h // 10) * 10}-{int(h // 10) * 10 + 10}" for h in height
            ],
            "L1.height_m": height,
            "L1.crown_base_m": 0.4 * height + rng.normal(0, 0.5, n),  # unit m
            "L1.crown_ratio": rng.normal(0.65, 0.05, n),
            "L4.chord_angle_deg_middle": rng.normal(60, 6, n),
        }
    )


def _generated(n_series=5, angle=60.0, angle_sd=6.0, species="european_beech"):
    rng = np.random.default_rng(7)
    rows = []
    for s in range(n_series):
        for h in (10, 15, 20, 25):
            height = h + rng.normal(0, 0.3)
            rows.append(
                {
                    "tree_uid": f"growpy:{species}:T_r07_h{h:02d}m_d20cm_full",
                    "dataset": f"seed{s}",
                    "source": "growpy",
                    "source_tree_id": f"T_r07_h{h:02d}m_d20cm_full",
                    "source_kind": "generated",
                    "tier": None,
                    "species_key": species,
                    "height_class": f"h{h // 10 * 10}-{h // 10 * 10 + 10}",
                    "L1.height_m": height,
                    "dbh_m": 0.01 * h,
                    "trunk_length_m": height,
                    "L1.crown_base_m": 0.4 * height,
                    "L1.crown_ratio": 0.65,
                    "L4.chord_angle_deg_middle": rng.normal(angle, angle_sd),
                }
            )
    return pd.DataFrame(rows)


def test_height_normalisation_divides_lengths_only():
    t = _real(5)
    n = normalise_by_height(t)
    assert "L1.height_m" not in n
    np.testing.assert_allclose(
        n["L1.crown_base_m"], t["L1.crown_base_m"] / t["L1.height_m"]
    )
    np.testing.assert_allclose(n["L1.crown_ratio"], t["L1.crown_ratio"])
    assert height_bin(19.99) == "h15-20" and height_bin(20.0) == "h20-25"


def test_reference_pools_by_tier_and_fills_bins_with_enough_trees(tmp_path):
    table = pd.concat(
        [
            _real(60, tier="A"),
            _real(30, tier="C", seed=2),
            _real(8, "wild_cherry", "C", 3),
        ],
        ignore_index=True,
    )
    ref = build_reference(table, min_n=10)
    beech = ref[ref["species_key"] == "european_beech"]
    pooled = beech[beech["height_bin"] == "all"].set_index("descriptor")
    assert pooled.loc["L1.crown_base_m", "tiers"] == "A/B"  # tier C stays out
    assert pooled.loc["L1.crown_base_m", "n"] == 60
    assert pooled.loc["L1.crown_base_m", "p50"] == pytest.approx(0.4, abs=0.03)
    assert "L1.height_m" not in pooled.index
    assert (beech.groupby("height_bin")["n"].min() >= 10).all()
    assert "wild_cherry" not in set(ref["species_key"])  # 8 trees < min_n
    q = beech[list(QUANTILES)].to_numpy()
    assert (np.diff(q, axis=1) >= 0).all()

    write_reference(ref, coverage(table), tmp_path, {"note": "test"})
    back = load_reference(tmp_path)
    assert len(back) == len(ref) and load_manifest(tmp_path)["note"] == "test"
    assert load_core_set(tmp_path) is None


def test_committed_reference_store_loads():
    ref_dir = default_reference_dir()
    ref = load_reference(ref_dir)
    assert set(ref["species_key"]) <= set(CATALOG_SPECIES)
    beech = ref[ref["species_key"] == "european_beech"]
    bins = set(beech["height_bin"])
    assert "all" in bins and {"h10-15", "h20-25", "h30-35"} <= bins
    assert (beech["n"] >= load_manifest(ref_dir)["min_n"]).all()
    assert (ref["p5"] <= ref["p95"]).all()


def test_score_maps_proxies_and_reports_the_share_within_one_spread():
    real = pd.concat([_real(40), _real(40, "norway_spruce", seed=4)], ignore_index=True)
    gen = pd.concat(
        [_generated(angle=20.0, angle_sd=1.0), _generated(species="silver_fir")],
        ignore_index=True,
    )
    cells = score_cells(pd.concat([real, gen], ignore_index=True))
    fir = cells[cells["species_key"] == "silver_fir"]
    assert (fir["reference"] == "norway_spruce").all() and fir["proxy"].all()
    gaps = descriptor_gaps(cells).set_index(["species_key", "descriptor"])
    # beech branches 40 degrees too steep: that robust descriptor falls outside one spread
    angle = "L4.chord_angle_deg_middle"
    assert gaps.loc[("european_beech", angle), "abs_z"] > 2
    assert gaps.loc[("silver_fir", angle), "abs_z"] < 1
    assert "L1.crown_base_m" not in gaps.index.get_level_values(1)  # weak, not robust
    summary = species_summary(cells).set_index("species_key")
    within = (gaps["abs_z"] < 1).groupby(level=0).mean()
    np.testing.assert_allclose(summary["within_one_spread"], within[summary.index])


def test_gate_passes_matching_trees_and_flags_regular_ones():
    real = _real(200)
    ref = build_reference(real, min_n=10)
    core = {"european_beech": {"L1.crown_ratio", "L4.chord_angle_deg_middle"}}

    good = gate(_generated(), ref, core)
    pooled = good[good["height_bin"] == "all"].set_index("descriptor")
    assert pooled.loc["L4.chord_angle_deg_middle", "pass"]
    assert pooled.loc["L1.crown_ratio", "too_regular"]  # identical crowns, IQR ratio 0
    assert pooled.loc["L1.crown_ratio", "pass"]  # spread is reported, not gated
    v = verdict(good).set_index("height_bin")
    assert v.loc["all", "verdict"] == "pass" and v.loc["all", "enough_seeds"]

    steep = gate(_generated(angle=25.0), ref, core)
    row = steep[steep["height_bin"] == "all"].set_index("descriptor")
    assert not row.loc["L4.chord_angle_deg_middle", "pass"]
    v = verdict(steep).set_index("height_bin")
    assert v.loc["all", "failing"] == "L4.chord_angle_deg_middle"
    assert not verdict(gate(_generated(n_series=3), ref, core))["enough_seeds"].any()
    small = _generated()
    small["L1.height_m"] = 4.0  # below 5 m: reported elsewhere, never gated
    assert gate(small, ref, core).empty


def test_growth_consistency_catches_a_falling_crown_base():
    gen = _generated(n_series=2)
    assert series_of(gen).nunique() == 2
    ok = growth_consistency(gen)
    assert ok["consistent"].all() and (ok["stages"] == "h10 h15 h20 h25").all()

    bad = gen.copy()
    mask = (bad["dataset"] == "seed1") & bad["source_tree_id"].str.contains("_h20m")
    bad.loc[mask, "L1.crown_base_m"] = 0.5
    out = growth_consistency(bad).set_index("series")
    assert out["crown_base_drops"].sum() == 1
    assert out["consistent"].sum() == 1


def test_balanced_effect_size_ignores_group_imbalance_and_chance():
    from growpy.structure.adequacy import epsilon_squared

    rng = np.random.default_rng(3)
    same = [rng.normal(0, 1, 1500), rng.normal(0, 1, 30)]
    apart = [rng.normal(0, 1, 1500), rng.normal(3, 1, 30)]
    assert epsilon_squared(same) < 0.03
    assert epsilon_squared(apart) > 0.5  # 30 trees against 1,500 still separate
    assert np.isnan(epsilon_squared([rng.normal(0, 1, 50), rng.normal(0, 1, 5)]))


def test_adequacy_keeps_a_species_trait_and_drops_its_duplicate():
    from growpy.structure.adequacy import adequacy, candidates

    rng = np.random.default_rng(5)
    frames = []
    for species, angle in (("european_beech", 60), ("european_oak", 40)):
        t = _real(80, species, seed=angle)
        t["L4.chord_angle_deg_middle"] = rng.normal(angle, 5, 80)
        t["L4.initial_angle_deg_middle"] = t["L4.chord_angle_deg_middle"] + 1
        frames.append(t)
    real = pd.concat(frames, ignore_index=True)
    adeq = adequacy(real).set_index("descriptor")
    assert adeq.loc["L4.chord_angle_deg_middle", "species_eps2"] > 0.5
    assert adeq.loc["L1.crown_ratio", "species_eps2"] < 0.06
    cand = candidates(adeq.reset_index(), real).set_index("descriptor")
    pair = cand.loc[["L4.chord_angle_deg_middle", "L4.initial_angle_deg_middle"]]
    assert pair["kept"].sum() == 1  # the same trait twice: one stays
    assert set(pair.loc[~pair["kept"], "redundant_with"]) <= set(pair.index)
    assert "L1.crown_ratio" not in cand.index


def test_strata_gate_a_stout_tree_against_stout_real_trees():
    from growpy.structure.reference import assign_strata, strata_edges

    rng = np.random.default_rng(9)
    real = _real(600)
    hd = rng.uniform(50, 110, len(real))  # slenderness: stout 50 .. slender 110
    real["dbh_m_reported"] = real["L1.height_m"] / hd
    real["L1.crown_ratio"] = 0.9 - 0.004 * hd + rng.normal(0, 0.01, len(real))
    edges = strata_edges(real, min_n=10)
    assert {"hd_p33", "hd_p67"} <= set(edges.columns) and len(edges) >= 3
    strata = assign_strata(real, edges)
    assert (strata[hd < 55] == "stout").all() and (strata[hd > 105] == "slender").all()

    ref = build_reference(real, min_n=10, edges=edges)
    assert {"all", "stout", "medium", "slender"} <= set(ref["stratum"])
    gen = _generated()
    gen["dbh_m_reported"] = gen["L1.height_m"] / 60.0  # a stout, free-crowned tree
    gen["L1.crown_ratio"] = 0.9 - 0.004 * 60.0
    core = {"european_beech": {"L1.crown_ratio"}}

    flat = gate(gen, ref[ref["stratum"] == "all"], core)
    flat_row = flat[(flat["height_bin"] == "all")].set_index("descriptor")
    assert not flat_row.loc["L1.crown_ratio", "median_in_iqr"]

    strat = gate(gen, ref, core, edges)
    pooled = strat[strat["height_bin"] == "all"]
    assert set(pooled["stratum"]) <= {"stout", "all"}  # "all": bins without edges
    row = pooled[pooled["stratum"] == "stout"].set_index("descriptor")
    assert row.loc["L1.crown_ratio", "reference_stratum"] == "stout"
    assert row.loc["L1.crown_ratio", "median_in_iqr"]
