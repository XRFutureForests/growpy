"""Adequacy checks for gate descriptors: which descriptors may decide a verdict (XRFF-576).

A descriptor gates only if it (1) separates species and tracks height among real trees,
(2) moves under known knob changes, (3) is stable across fitters and sources, and (4)
agrees with the owner's ranking by eye (hub ``04-LOGIC-TIER/tree-structure-realism-plan-
2026-10``). This module covers what the real QSMs alone can answer:

* **species**: Kruskal-Wallis epsilon squared across species inside one source and tier
  (BioDiv tier A: beech, oak, ash, sycamore), on height-normalised values, so a species
  effect is not a source or height effect;
* **height**: Spearman rho with tree height inside one species (raw values), i.e. whether
  the descriptor needs the per-bin rows rather than the pooled one;
* **source**: epsilon squared across sources for one species (beech: BioDiv A, Belgium B,
  Kew C), 10-35 m, height-normalised: a first robustness proxy (different scans, fitters
  and radius corrections) until the fitter (XRFF-575) and stand-scan (XRFF-344) checks
  exist;
* **sensitivity**: median |robust z| shift between knob arms and their baseline, from
  ``growpy-qsm-gate`` runs of the C1 sweep (XRFF-579).

``candidates`` keeps the scan-robust descriptors whose species effect is at least
``MIN_SPECIES_EFFECT``, then drops near-duplicates (|Spearman| above ``MAX_REDUNDANCY``
with a better-ranked one). The source effect is reported as ``source_stable`` (species
effect above ``SOURCE_RATIO`` times the source effect) but does not filter yet: the three
beech sources differ in site and stand as well as in scanner and fitter (first pass
2026-10-27: they differ about as much as species do), so they cannot isolate scan
robustness. The fitter comparison on the same clouds (XRFF-575) can.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import kruskal, spearmanr

from growpy.structure.descriptors import DEFINITIONS
from growpy.structure.reference import normalise_by_height
from growpy.structure.score import robust_keys

MIN_GROUP = 10
DRAWS = 30
MIN_SPECIES_EFFECT = 0.06  # epsilon squared: 0.01 small, 0.06 medium, 0.14 large
SOURCE_RATIO = 2.0
MAX_REDUNDANCY = 0.8


def epsilon_squared(groups: list[np.ndarray], draws: int = DRAWS) -> float:
    """Kruskal-Wallis (H - (k - 1)) / (n - k), the share of rank variance between the
    groups beyond chance, on
    balanced draws: every group subsampled to the smallest one, averaged over ``draws``.
    Unbalanced groups (1,658 BioDiv beech against 36 ash) would otherwise hide a
    separation the small groups show."""
    groups = [g[np.isfinite(g)] for g in groups]
    groups = [g for g in groups if len(g) >= MIN_GROUP]
    if len(groups) < 2 or len(np.unique(np.concatenate(groups))) < 2:
        return np.nan
    m = min(len(g) for g in groups)
    rng = np.random.default_rng(0)
    values = []
    for _ in range(draws if any(len(g) > m for g in groups) else 1):
        sample = [rng.choice(g, m, replace=False) for g in groups]
        if len(np.unique(np.concatenate(sample))) > 1:
            k, n = len(sample), m * len(sample)
            # H has expectation k - 1 without any effect; subtract it so small
            # balanced groups do not read as an effect
            values.append(max(kruskal(*sample).statistic - (k - 1), 0.0) / (n - k))
    return float(np.mean(values)) if values else np.nan


def _effect(table: pd.DataFrame, by: str, keys: list[str]) -> pd.Series:
    out = {}
    for key in keys:
        groups = [g[key].to_numpy(dtype=float) for _, g in table.groupby(by)]
        out[key] = epsilon_squared(groups)
    return pd.Series(out)


def adequacy(real: pd.DataFrame) -> pd.DataFrame:
    """One row per descriptor (``real`` = descriptor rows of scanned trees)."""
    real = real[(real["source_kind"] == "scan") & (real["L1.height_m"] > 0)]
    keys = [k for k in DEFINITIONS if k in real.columns and k != "L1.height_m"]
    norm = normalise_by_height(real)

    biodiv_a = norm[(norm["source"] == "biodiv") & (norm["tier"] == "A")]
    species = _effect(biodiv_a, "species_key", keys)

    beech = real[real["species_key"] == "european_beech"]
    height = {}
    for key in keys:
        v = beech[[key, "L1.height_m"]].dropna()
        height[key] = (
            float(spearmanr(v[key], v["L1.height_m"]).statistic)
            if len(v) >= MIN_GROUP and v[key].nunique() > 1
            else np.nan
        )

    h = real["L1.height_m"]
    mid = norm[(h >= 10) & (h < 35)]
    beech_sources = _effect(mid[mid["species_key"] == "european_beech"], "source", keys)
    ash_sources = _effect(mid[mid["species_key"] == "common_ash"], "source", keys)

    robust = robust_keys()
    out = pd.DataFrame(
        {
            "descriptor": keys,
            "unit": [DEFINITIONS[k][0] for k in keys],
            "robust": [DEFINITIONS[k][2] for k in keys],
            "species_eps2": species.reindex(keys).to_numpy(),
            "height_rho_beech": [height[k] for k in keys],
            "source_eps2_beech": beech_sources.reindex(keys).to_numpy(),
            "source_eps2_ash": ash_sources.reindex(keys).to_numpy(),
            "meaning": [DEFINITIONS[k][3] for k in keys],
        }
    )
    source = out[["source_eps2_beech", "source_eps2_ash"]].max(axis=1)
    out["discriminates"] = out["species_eps2"] >= MIN_SPECIES_EFFECT
    out["source_stable"] = out["species_eps2"] > SOURCE_RATIO * source.fillna(0)
    out["eligible"] = out["descriptor"].isin(robust) & out["discriminates"]
    return out.sort_values("species_eps2", ascending=False).reset_index(drop=True)


def candidates(adeq: pd.DataFrame, real: pd.DataFrame) -> pd.DataFrame:
    """Eligible descriptors, best species effect first, near-duplicates dropped."""
    eligible = adeq[adeq["eligible"]].copy()
    norm = normalise_by_height(real[real["source_kind"] == "scan"])
    corr = norm[eligible["descriptor"].tolist()].corr(method="spearman").abs()
    kept: list[str] = []
    shadowed: dict[str, str] = {}
    for key in eligible["descriptor"]:
        twin = next((k for k in kept if corr.loc[key, k] > MAX_REDUNDANCY), None)
        if twin:
            shadowed[key] = twin
        else:
            kept.append(key)
    eligible["kept"] = eligible["descriptor"].isin(kept)
    eligible["redundant_with"] = eligible["descriptor"].map(shadowed).fillna("")
    return eligible


def sensitivity(arms: dict[str, pd.DataFrame], baseline: str) -> pd.DataFrame:
    """Per descriptor and arm: shift of the generated median against the baseline, in
    real IQRs (``gate.csv`` of each arm, pooled rows)."""
    base = arms[baseline]
    base = base[base["height_bin"] == "all"].set_index(["species_key", "descriptor"])
    rows = []
    for arm, g in arms.items():
        if arm == baseline:
            continue
        g = g[g["height_bin"] == "all"].set_index(["species_key", "descriptor"])
        joined = g.join(base, rsuffix="_base", how="inner")
        iqr = (joined["p75"] - joined["p25"]).replace(0, np.nan)
        shift = (joined["gen_median"] - joined["gen_median_base"]) / iqr
        rows.append(shift.rename(arm))
    return pd.concat(rows, axis=1).reset_index() if rows else pd.DataFrame()
