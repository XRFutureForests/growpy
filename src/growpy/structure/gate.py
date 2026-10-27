"""The realism gate: generated trees against the real reference store, per descriptor.

Provisional thresholds (XRFF-549, owner decisions 2026-10-27, hub
``04-LOGIC-TIER/tree-structure-realism-plan-2026-10``), per species and descriptor:

* at least ``INSIDE_SHARE`` (80 %) of the generated trees inside the real p5-p95;
* the generated median inside the real p25-p75.

Spread is reported, not gated: the real spread includes growth conditions a generator
does not simulate. Generated IQR / real IQR below ``TOO_REGULAR`` (0.25) raises a "too
regular" flag for the owner's eye (only with ``MIN_SERIES`` or more generated trees in
the row). A cell needs ``MIN_SERIES`` (5) seeds; fewer is scored but marked.

Rows come in two kinds, matching the store: ``height_bin == "all"`` compares
height-normalised values with every real tree of the species; a 5 m bin compares raw
values where the store has that bin. Only the core descriptors decide a verdict; until
XRFF-576 fixes the core set it defaults to the scan-robust descriptors (minus the
conifer-unsafe ones on conifers), and every other descriptor is reported alongside.

``growth_consistency`` checks one tree grown over time (the height-keyed snapshots of one
run): height and DBH never fall, the crown base only rises, the stem persists.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from growpy.structure.reference import POOLED, height_bin, normalise_by_height
from growpy.structure.score import REFERENCE_OF, is_conifer_unsafe, robust_keys

INSIDE_SHARE = 0.8
TOO_REGULAR = 0.25
MIN_SERIES = 5
# growth-over-time tolerances (measurement noise of a standardised skeleton)
HEIGHT_TOL_M = 0.05
DBH_TOL_REL = 0.01
CROWN_BASE_TOL_M = 0.25
TRUNK_TOL_REL = 0.05

_STAGE = re.compile(r"_h(?P<h>\d+)m")


def series_of(table: pd.DataFrame) -> pd.Series:
    """One id per grown individual: dataset + species + tree id without the height stage
    (``European_Beech_r07_h20m_d28cm_full`` -> ``European_Beech_r07_full``)."""
    base = (
        table["source_tree_id"]
        .astype(str)
        .str.replace(r"_h\d+m_d\d+cm", "", regex=True)
    )
    dataset = table["dataset"] if "dataset" in table else table["source"]
    return dataset.astype(str) + ":" + table["species_key"].astype(str) + ":" + base


def stage_of(table: pd.DataFrame) -> pd.Series:
    return table["source_tree_id"].astype(str).str.extract(_STAGE)["h"].astype(float)


def default_core(species_key: str) -> set[str]:
    return {k for k in robust_keys() if not is_conifer_unsafe(species_key, k)}


def _row(values: np.ndarray, ref: pd.Series) -> dict:
    g_med = float(np.median(values))
    q1, q3 = np.quantile(values, [0.25, 0.75])
    real_iqr = float(ref["p75"] - ref["p25"])
    inside = float(((values >= ref["p5"]) & (values <= ref["p95"])).mean())
    median_ok = bool(ref["p25"] <= g_med <= ref["p75"])
    # an IQR of one to four trees says nothing about regularity
    enough = len(values) >= MIN_SERIES and real_iqr > 0
    ratio = (q3 - q1) / real_iqr if enough else np.nan
    return {
        "gen_n": len(values),
        "gen_median": g_med,
        "gen_iqr": float(q3 - q1),
        "real_n": int(ref["n"]),
        "real_tiers": ref.get("tiers"),
        **{p: float(ref[p]) for p in ("p5", "p25", "p50", "p75", "p95")},
        "inside_p5_p95": inside,
        "median_in_iqr": median_ok,
        "iqr_ratio": ratio,
        "too_regular": bool(ratio < TOO_REGULAR) if np.isfinite(ratio) else False,
        "pass": bool(inside >= INSIDE_SHARE and median_ok),
    }


def gate(
    table: pd.DataFrame,
    reference: pd.DataFrame,
    core: dict[str, set[str]] | None = None,
) -> pd.DataFrame:
    """One row per generated species x height bin ("all" + 5 m bins) x descriptor.

    ``table`` is ``growpy-qsm-descriptors`` output (its generated rows are scored);
    ``reference`` is ``load_reference()``; ``core`` maps species to its core descriptors
    (default: ``default_core``)."""
    generated = table[table["source_kind"] == "generated"].copy()
    generated = generated[generated["L1.height_m"] > 0]
    generated["series"] = series_of(generated)
    ref_index = reference.set_index(["species_key", "height_bin", "descriptor"])
    rows = []
    for species, gen in generated.groupby("species_key"):
        ref_sp = REFERENCE_OF.get(species, species)
        core_set = (core or {}).get(species) or default_core(species)
        groups = [(POOLED, normalise_by_height(gen), gen["series"])]
        bins = gen["L1.height_m"].map(height_bin)
        groups += [(b, g, g["series"]) for b, g in gen.groupby(bins)]
        for hbin, values_table, series in groups:
            for key in values_table.columns:
                if (ref_sp, hbin, key) not in ref_index.index:
                    continue
                values = values_table[key].to_numpy(dtype=float)
                values = values[np.isfinite(values)]
                if not len(values):
                    continue
                row = {
                    "species_key": species,
                    "reference": ref_sp,
                    "proxy": ref_sp != species,
                    "height_bin": hbin,
                    "descriptor": key,
                    "core": key in core_set,
                    "series": series.nunique(),
                }
                row.update(_row(values, ref_index.loc[(ref_sp, hbin, key)]))
                rows.append(row)
    return pd.DataFrame(rows)


def verdict(gated: pd.DataFrame) -> pd.DataFrame:
    """Per species x height bin, over the core descriptors: how many pass, how many are
    too regular, whether there are enough seeds, and the verdict (all core pass)."""
    if gated.empty:
        return gated
    core = gated[gated["core"]]
    out = (
        core.groupby(["species_key", "reference", "height_bin"])
        .agg(
            core_scored=("pass", "size"),
            core_pass=("pass", "sum"),
            too_regular=("too_regular", "sum"),
            gen_n=("gen_n", "max"),
            series=("series", "max"),
            real_n_min=("real_n", "min"),
        )
        .reset_index()
    )
    out["pass_share"] = out["core_pass"] / out["core_scored"]
    out["enough_seeds"] = out["series"] >= MIN_SERIES
    out["verdict"] = np.where(out["core_pass"] == out["core_scored"], "pass", "fail")
    failing = (
        core[~core["pass"]]
        .groupby(["species_key", "height_bin"])["descriptor"]
        .apply(lambda s: " ".join(sorted(s)))
    )
    out["failing"] = [
        failing.get((s, b), "")
        for s, b in zip(out["species_key"], out["height_bin"], strict=True)
    ]
    return out


def _drops(values: pd.Series, tol_abs: float = 0.0, tol_rel: float = 0.0) -> int:
    """How often a snapshot series falls by more than the tolerance."""
    v = values.to_numpy(dtype=float)
    allowed = tol_abs + tol_rel * np.abs(v[:-1])
    return int((np.diff(v) < -allowed).sum())


def growth_consistency(table: pd.DataFrame) -> pd.DataFrame:
    """Per grown individual (``series_of``), snapshots ordered by height stage: height
    and DBH never fall, the crown base never drops, the trunk never shortens.

    Needs ``source_tree_id`` (the stage is read from ``_hNNm``), ``L1.height_m``,
    ``dbh_m``, ``L1.crown_base_m`` and ``trunk_length_m``."""
    gen = table[table["source_kind"] == "generated"].copy()
    gen["series"] = series_of(gen)
    gen["stage"] = stage_of(gen)
    rows = []
    for series, s in gen.sort_values("stage").groupby("series"):
        if s["stage"].isna().any():
            continue
        rows.append(
            {
                "series": series,
                "species_key": s["species_key"].iloc[0],
                "stages": " ".join(f"h{h:02.0f}" for h in s["stage"]),
                "height_drops": _drops(s["L1.height_m"], HEIGHT_TOL_M),
                "dbh_drops": _drops(s["dbh_m"], tol_rel=DBH_TOL_REL),
                "crown_base_drops": _drops(s["L1.crown_base_m"], CROWN_BASE_TOL_M),
                "trunk_drops": _drops(s["trunk_length_m"], tol_rel=TRUNK_TOL_REL),
                "trunk_top_frac_min": float(
                    (s["trunk_length_m"] / s["L1.height_m"]).min()
                ),
            }
        )
    out = pd.DataFrame(rows)
    if len(out):
        out["consistent"] = (
            out[["height_drops", "dbh_drops", "crown_base_drops", "trunk_drops"]].sum(
                axis=1
            )
            == 0
        )
    return out
