"""Catalog against real trees per species: the gap table and the share within one spread.

The 2026-10-26 re-score (hub ``04-LOGIC-TIER/tree-skeleton-budget-2026-10``) in tracked
form. Each generated species is compared with the real trees of its reference species
(``compare.compare`` within species x height class), restricted to the scan-robust
descriptors. Silver fir and Douglas fir have no QSM of their own and use Norway spruce as
a declared proxy. For conifer references the descriptors the 2026-10-12 conifer fit
excluded (forks, second order, all-branch means) are flagged ``conifer_unsafe``: a conifer
QSM merges whorls into forks and misses most second-order branches.

"Within one spread" is the share of descriptors whose median robust z over the cells lies
inside +-1, i.e. whose generated median sits within one real standard deviation (IQR /
1.349). Higher is better; it is a summary to rank species, not the gate (``gate.py``).
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from growpy.structure.compare import compare
from growpy.structure.descriptors import definitions_table

# generated species -> real reference species; absent = itself
REFERENCE_OF = {
    "silver_fir": "norway_spruce",  # no Abies QSM exists: proxy, as on 2026-10-12
    "douglas_fir": "norway_spruce",  # no Pseudotsuga QSM: proxy, weak
}
CONIFERS = {"norway_spruce", "silver_fir", "douglas_fir", "scots_pine"}
CONIFER_UNSAFE = ("fork", "k1", "order 2", "second", "2nd", "bifurcation", "_all")


def robust_keys() -> set[str]:
    defs = definitions_table()
    return set(defs.loc[defs["robust"].astype(str).str.startswith("yes"), "key"])


def is_conifer_unsafe(species_key: str, descriptor: str) -> bool:
    lowered = descriptor.lower()
    return species_key in CONIFERS and any(s in lowered for s in CONIFER_UNSAFE)


def score_cells(table: pd.DataFrame, min_real: int = 5) -> pd.DataFrame:
    """``compare`` per generated species against its reference species, with the
    ``reference``, ``proxy``, ``robust``, ``conifer_unsafe`` and ``desc`` columns."""
    generated = table[table["source_kind"] == "generated"]
    real = table[table["source_kind"] == "scan"]
    defs = definitions_table().set_index("key")
    robust = robust_keys()
    out = []
    for species, gen in generated.groupby("species_key"):
        ref = REFERENCE_OF.get(species, species)
        ref_trees = real[real["species_key"] == ref].copy()
        if ref_trees.empty:
            print(f"{species}: no real trees for reference {ref}")
            continue
        ref_trees["species_key"] = species
        cells = compare(pd.concat([gen, ref_trees], ignore_index=True), min_real)
        if cells.empty:
            print(f"{species}: no cell with >= {min_real} real trees")
            continue
        cells["reference"] = ref
        cells["proxy"] = ref != species
        out.append(cells)
    if not out:
        return pd.DataFrame()
    cells = pd.concat(out, ignore_index=True)
    cells["robust"] = cells["descriptor"].isin(robust)
    cells["desc"] = cells["descriptor"].map(defs["description"])
    cells["conifer_unsafe"] = [
        is_conifer_unsafe(s, d)
        for s, d in zip(cells["species_key"], cells["descriptor"], strict=True)
    ]
    return cells


def descriptor_gaps(cells: pd.DataFrame) -> pd.DataFrame:
    """Per species and descriptor (robust, conifer-safe, finite z only): cells, median
    robust z, median percentile, real and generated medians; sorted by |z| per species."""
    usable = cells[
        cells["robust"]
        & ~cells["conifer_unsafe"]
        & cells["robust_z"].notna()
        & np.isfinite(cells["robust_z"])
    ]
    out = (
        usable.groupby(["species_key", "descriptor"])
        .agg(
            reference=("reference", "first"),
            proxy=("proxy", "first"),
            cells=("robust_z", "size"),
            z_med=("robust_z", "median"),
            z_absmax=("robust_z", lambda s: s.abs().max()),
            pct_med=("percentile", "median"),
            real_med=("real_median", "median"),
            gen_med=("generated_median", "median"),
            real_n=("real_n", "sum"),
            desc=("desc", "first"),
        )
        .reset_index()
    )
    out["abs_z"] = out["z_med"].abs()
    return out.sort_values(["species_key", "abs_z"], ascending=[True, False])


def species_summary(cells: pd.DataFrame) -> pd.DataFrame:
    """One row per species: robust descriptors scored, share |z| < 1 ("within one
    spread"), share |z| >= 2, height classes and real tiers used."""
    gaps_ = descriptor_gaps(cells)
    rows = []
    for species, g in gaps_.groupby("species_key"):
        c = cells[cells["species_key"] == species]
        rows.append(
            {
                "species_key": species,
                "reference": g["reference"].iloc[0],
                "proxy": bool(g["proxy"].iloc[0]),
                "descriptors": len(g),
                "within_one_spread": float((g["abs_z"] < 1).mean()),
                "beyond_two_spreads": float((g["abs_z"] >= 2).mean()),
                "height_classes": " ".join(sorted(c["height_class"].unique())),
                "real_tiers": " ".join(sorted(c["real_tiers"].unique())),
            }
        )
    return pd.DataFrame(rows)


FORM_KEYS = [
    "L1.crown_ratio",
    "L1.crown_base_m",
    "F.crown_m_per_dbh_cm",
    "L4.top5_chord_angle_deg_middle",
    "L4.chord_angle_deg_middle",
    "L4.straightness_middle",
    "F.length_cv_p50",
    "F.whorl_gap_cv_p50",
    "F.crown_offset_rel",
    "F.crown_holes_share",
    "F.lower_hang_len_frac",
    "F.wave_sag_rel_p50",
    "F.leader_m",
    "G.fork_asymmetry_p50",
    "G.k1.fork_share",
    "T.bifurcation_ratio",
]


def form_table(
    table: pd.DataFrame, keys: list[str] | None = None, lo: float = 10, hi: float = 30
) -> pd.DataFrame:
    """Medians of visible-trait descriptors, generated / real, for trees of ``lo``-``hi``
    m. Real side: tier A/B when a species has at least five, else A/B/C."""
    keys = [k for k in (keys or FORM_KEYS) if k in table.columns]
    h = table["L1.height_m"]
    t = table[(h >= lo) & (h < hi)]
    gen = t[t["source_kind"] == "generated"]
    real = t[t["source_kind"] == "scan"]
    wide = {}
    for species, g in gen.groupby("species_key"):
        ref = REFERENCE_OF.get(species, species)
        r = real[real["species_key"] == ref]
        good = r[r["tier"].isin(["A", "B"])]
        r, tier = (good, "A/B") if len(good) >= 5 else (r, "A/B/C")
        g_med, r_med = g[keys].median(), r[keys].median()
        label = f"{species} (n {len(g)} / {len(r)}, {ref} {tier})"
        wide[label] = {
            k: f"{g_med[k]:.3g} / {r_med[k]:.3g}" if len(r) else f"{g_med[k]:.3g} / -"
            for k in keys
        }
    return pd.DataFrame(wide).T
