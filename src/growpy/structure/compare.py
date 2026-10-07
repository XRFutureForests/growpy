"""Generated against real trees, descriptor by descriptor, within species x height class.

For every cell (species, height class) with enough real trees and at least one generated
tree, and every descriptor:

* where the generated median falls in the real distribution: percentile rank, and a robust
  z (difference of medians over the real spread, IQR / 1.349);
* with three or more generated trees, a Mann-Whitney U test and Cliff's delta (the
  probability a generated value exceeds a real one minus the reverse, -1 .. 1), with a
  Benjamini-Hochberg false discovery rate over every test run.

Real trees come from tiers A and B when a cell has at least ``min_real`` of them, otherwise
tier C is admitted and the row says so; tiers are never pooled silently. The robust z is
the number to read first: it does not depend on the generated sample size, which is small
(the Grove catalog has one to five trees per cell).
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import mannwhitneyu

from growpy.structure.descriptors import DEFINITIONS

CELL = ["species_key", "height_class"]


def cliffs_delta(a: np.ndarray, b: np.ndarray) -> float:
    """P(a > b) - P(a < b) over all pairs."""
    diff = np.subtract.outer(a, b)
    return float((np.sign(diff)).mean())


def benjamini_hochberg(p: pd.Series) -> pd.Series:
    """FDR-adjusted p values (NaN stays NaN)."""
    valid = p.dropna().sort_values()
    m = len(valid)
    if not m:
        return p * np.nan
    adjusted = valid * m / np.arange(1, m + 1)
    adjusted = np.minimum.accumulate(adjusted[::-1])[::-1].clip(upper=1.0)
    return adjusted.reindex(p.index)


def compare(table: pd.DataFrame, min_real: int = 5) -> pd.DataFrame:
    """One row per cell x descriptor (``table`` is ``growpy-qsm-descriptors`` output)."""
    keys = [k for k in DEFINITIONS if k in table.columns]
    generated = table[table["source_kind"] == "generated"]
    real_all = table[(table["source_kind"] == "scan") & table["species_key"].notna()]
    rows = []
    for (species, hclass), gen in generated.groupby(CELL):
        real = real_all[
            (real_all["species_key"] == species) & (real_all["height_class"] == hclass)
        ]
        good = real[real["tier"].isin(["A", "B"])]
        used, tiers = (good, "A/B") if len(good) >= min_real else (real, "A/B/C")
        if len(used) < min_real:
            continue
        for key in keys:
            r = used[key].dropna().to_numpy(dtype=float)
            g = gen[key].dropna().to_numpy(dtype=float)
            if len(r) < min_real or not len(g):
                continue
            q1, med, q3 = np.quantile(r, [0.25, 0.5, 0.75])
            spread = (q3 - q1) / 1.349
            g_med = float(np.median(g))
            row = {
                "species_key": species,
                "height_class": hclass,
                "descriptor": key,
                "real_tiers": tiers,
                "real_sources": ",".join(sorted(used["source"].unique())),
                "real_n": len(r),
                "real_p10": float(np.quantile(r, 0.1)),
                "real_median": float(med),
                "real_p90": float(np.quantile(r, 0.9)),
                "generated_n": len(g),
                "generated_median": g_med,
                "percentile": float(
                    (r < g_med).mean() * 100 + (r == g_med).mean() * 50
                ),
                "robust_z": (g_med - med) / spread if spread > 0 else np.nan,
                "cliffs_delta": cliffs_delta(g, r),
                "p": np.nan,
            }
            if len(g) >= 3 and len(np.unique(np.concatenate([g, r]))) > 1:
                row["p"] = float(mannwhitneyu(g, r, alternative="two-sided").pvalue)
            rows.append(row)
    out = pd.DataFrame(rows)
    if len(out):
        out["p_fdr"] = benjamini_hochberg(out["p"])
    return out


def gaps(cells: pd.DataFrame) -> pd.DataFrame:
    """Per descriptor across cells: how far and how often generated trees miss real ones."""
    if cells.empty:
        return cells
    grouped = cells.groupby("descriptor")
    out = pd.DataFrame(
        {
            "cells": grouped.size(),
            "median_robust_z": grouped["robust_z"].median(),
            "median_abs_robust_z": grouped["robust_z"].apply(
                lambda z: z.abs().median()
            ),
            "share_abs_z_over_1": grouped["robust_z"].apply(
                lambda z: (z.abs() > 1).mean()
            ),
            "median_cliffs_delta": grouped["cliffs_delta"].median(),
            "share_fdr_below_0_05": grouped["p_fdr"].apply(
                lambda p: (p < 0.05).sum() / max(p.notna().sum(), 1)
            ),
        }
    )
    return out.sort_values("median_abs_robust_z", ascending=False).reset_index()
