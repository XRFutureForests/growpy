"""The real-tree reference store: percentiles per species, descriptor and height.

    data/input/structure_reference/
        reference_percentiles.csv   one row per species x height bin x descriptor
        coverage.csv                real trees per species x source x tier x 5 m bin
        descriptor_definitions.csv  unit, frame, scan robustness of every descriptor
        manifest.json               inputs, prune settings, tier rule, growpy commit
        README.md

Two kinds of rows in ``reference_percentiles.csv``:

* ``height_bin == "all"``: every real tree of the species pooled, height-normalised
  (lengths over tree height, densities per metre times tree height, ratios and angles
  as they are). The gate reads these first: only beech fills the 5 m bins.
* ``height_bin == "h20-25"`` etc.: raw values of the trees in that 5 m bin, only where
  the bin holds at least ``min_n`` trees.

Tiers are never pooled silently: a row uses tiers A and B when it has at least ``min_n``
of them, otherwise every tier, and says which in ``tiers``.

**Strata (social class).** A 20 m beech in a closed stand is a slender suppressed stem; a
free-crowned one is stout. Rows carry a ``stratum``: ``all``, or the slenderness tertile
(height over the reported DBH) within the species x 5 m bin, ``slender`` / ``medium`` /
``stout``, cut at the edges in ``strata_edges.csv``. A generated tree is placed by its
own height and exported DBH, so it is gated against real trees of its social class.
Slenderness is not a gated descriptor, so the stratification is not circular. The store is built from
``growpy-qsm-descriptors`` tables of real trees (``source_kind == "scan"``) with
``growpy-qsm-reference``; ``load_reference`` reads it back.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from growpy.structure.descriptors import DEFINITIONS, definitions_table

QUANTILES = {"p5": 0.05, "p25": 0.25, "p50": 0.5, "p75": 0.75, "p95": 0.95}
BIN_M = 5.0
MIN_N = 10
POOLED = "all"
# the catalog's species; the store keeps these (proxies resolve through score.REFERENCE_OF)
CATALOG_SPECIES = [
    "norway_spruce",
    "silver_fir",
    "douglas_fir",
    "scots_pine",
    "european_beech",
    "european_oak",
    "sycamore_maple",
    "common_ash",
    "silver_birch",
    "small_leaved_linden",
    "wild_cherry",
]
PERCENTILES_FILE = "reference_percentiles.csv"
STRATA_FILE = "strata_edges.csv"
ALL_STRATA = "all"
CORE_SET_FILE = "core_set.csv"


def default_reference_dir() -> Path:
    from growpy.config.paths import get_data_directory

    return get_data_directory() / "input" / "structure_reference"


def height_bin(height: float, bin_m: float = BIN_M) -> str:
    lo = np.floor(height / bin_m) * bin_m
    return f"h{lo:g}-{lo + bin_m:g}"


def normalise_by_height(table: pd.DataFrame) -> pd.DataFrame:
    """Lengths (unit m) over ``L1.height_m``, per-metre densities times it; the rest
    unchanged. ``L1.height_m`` itself is dropped (it would be 1)."""
    out = table.copy()
    h = out["L1.height_m"].astype(float).where(lambda s: s > 0)
    for key, (unit, *_rest) in DEFINITIONS.items():
        if key not in out.columns:
            continue
        if unit == "m":
            out[key] = out[key] / h
        elif unit == "1/m":
            out[key] = out[key] * h
    return out.drop(columns="L1.height_m")


def normalised_unit(unit: str) -> str:
    return {"m": "m/m height", "1/m": "per tree height"}.get(unit, unit)


def _tier_subset(trees: pd.DataFrame, min_n: int) -> tuple[pd.DataFrame, str]:
    good = trees[trees["tier"].isin(["A", "B"])]
    return (good, "A/B") if len(good) >= min_n else (trees, "A/B/C")


def _percentile_rows(
    trees: pd.DataFrame,
    species: str,
    hbin: str,
    tiers: str,
    units: dict,
    min_n: int,
    stratum: str = ALL_STRATA,
) -> list[dict]:
    rows = []
    for key in DEFINITIONS:
        if key not in trees.columns:
            continue
        values = trees[key].dropna().to_numpy(dtype=float)
        values = values[np.isfinite(values)]
        if len(values) < min_n:
            continue
        q = np.quantile(values, list(QUANTILES.values()))
        rows.append(
            {
                "species_key": species,
                "height_bin": hbin,
                "stratum": stratum,
                "tiers": tiers,
                "sources": ",".join(sorted(trees["source"].dropna().unique())),
                "descriptor": key,
                "unit": units[key],
                "n": len(values),
                **dict(zip(QUANTILES, q, strict=True)),
            }
        )
    return rows


def _real(table: pd.DataFrame, species: list[str] | None) -> pd.DataFrame:
    real = table[(table["source_kind"] == "scan") & table["species_key"].notna()]
    real = real[real["L1.height_m"] > 0]
    return real if species is None else real[real["species_key"].isin(species)]


def reported_dbh(table: pd.DataFrame) -> pd.Series:
    """DBH for the slenderness class: the reported one (field or point-cloud DBH of a real
    tree, the exported yield-table DBH of a Grove tree, also in its name as ``_d29cm``),
    else the QSM's own."""
    dbh = (
        table["dbh_m_reported"].astype(float)
        if "dbh_m_reported" in table
        else pd.Series(np.nan, index=table.index)
    )
    if "source_tree_id" in table:
        cm = table["source_tree_id"].astype(str).str.extract(r"_d(\d+)cm")[0]
        dbh = dbh.fillna(cm.astype(float) / 100)
    return dbh.fillna(table["dbh_m"].astype(float)) if "dbh_m" in table else dbh


def slenderness(table: pd.DataFrame) -> pd.Series:
    """Height over DBH (both in metres)."""
    return table["L1.height_m"] / reported_dbh(table).where(lambda d: d > 0)


def strata_edges(
    table: pd.DataFrame,
    species: list[str] | None = None,
    bin_m: float = BIN_M,
    min_n: int = MIN_N,
) -> pd.DataFrame:
    """Slenderness tertiles per species x height bin of the real trees (tier rule as for
    the percentile rows); bins with fewer than ``3 * min_n`` trees get none."""
    real = _real(table, species)
    bins = real["L1.height_m"].map(lambda h: height_bin(h, bin_m))
    rows = []
    for (sp, hbin), trees in real.groupby(["species_key", bins]):
        used, tiers = _tier_subset(trees, min_n)
        hd = slenderness(used).dropna()
        if len(hd) < 3 * min_n:
            continue
        p33, p67 = np.quantile(hd, [1 / 3, 2 / 3])
        rows.append(
            {
                "species_key": sp,
                "height_bin": hbin,
                "tiers": tiers,
                "n": len(hd),
                "hd_p33": p33,
                "hd_p67": p67,
            }
        )
    return pd.DataFrame(rows)


def assign_strata(
    table: pd.DataFrame,
    edges: pd.DataFrame,
    species_of: pd.Series | None = None,
    bin_m: float = BIN_M,
) -> pd.Series:
    """``slender`` / ``medium`` / ``stout`` per row (NaN where its species x bin has no
    edges). ``species_of`` maps rows to the reference species (default: their own)."""
    sp = species_of if species_of is not None else table["species_key"]
    bins = table["L1.height_m"].map(lambda h: height_bin(h, bin_m))
    idx = edges.set_index(["species_key", "height_bin"])
    hd = slenderness(table)
    out = pd.Series(np.nan, index=table.index, dtype=object)
    for i in table.index:
        key = (sp.loc[i], bins.loc[i])
        if key not in idx.index or not np.isfinite(hd.loc[i]):
            continue
        p33, p67 = idx.loc[key, ["hd_p33", "hd_p67"]]
        out.loc[i] = (
            "stout" if hd.loc[i] <= p33 else "slender" if hd.loc[i] > p67 else "medium"
        )
    return out


def build_reference(
    table: pd.DataFrame,
    species: list[str] | None = None,
    bin_m: float = BIN_M,
    min_n: int = MIN_N,
    edges: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Percentile rows from a descriptor table (real trees only are used); with
    ``edges`` also one set of rows per slenderness stratum."""
    real = _real(table, species)
    raw_units = {k: v[0] for k, v in DEFINITIONS.items()}
    norm_units = {k: normalised_unit(u) for k, u in raw_units.items()}
    bins = real["L1.height_m"].map(lambda h: height_bin(h, bin_m))
    groups = [(ALL_STRATA, real)]
    if edges is not None and len(edges):
        strata = assign_strata(real, edges, bin_m=bin_m)
        groups += [(st, real[strata == st]) for st in ("slender", "medium", "stout")]
    rows: list[dict] = []
    for stratum, subset in groups:
        for sp, trees in subset.groupby("species_key"):
            used, tiers = _tier_subset(trees, min_n)
            if len(used) >= min_n:
                rows += _percentile_rows(
                    normalise_by_height(used),
                    sp,
                    POOLED,
                    tiers,
                    norm_units,
                    min_n,
                    stratum,
                )
            for hbin, in_bin in trees.groupby(bins.loc[trees.index]):
                used, tiers = _tier_subset(in_bin, min_n)
                if len(used) >= min_n:
                    rows += _percentile_rows(
                        used, sp, hbin, tiers, raw_units, min_n, stratum
                    )
    return pd.DataFrame(rows)


def coverage(table: pd.DataFrame, bin_m: float = BIN_M) -> pd.DataFrame:
    """Real trees per species x source x tier x height bin (long form)."""
    real = table[(table["source_kind"] == "scan") & table["species_key"].notna()]
    bins = real["L1.height_m"].map(lambda h: height_bin(h, bin_m)).rename("height_bin")
    return (
        real.groupby(["species_key", "source", "tier", bins], dropna=False)
        .size()
        .rename("trees")
        .reset_index()
    )


def write_reference(
    reference: pd.DataFrame,
    cover: pd.DataFrame,
    out_dir: Path,
    manifest: dict,
    edges: pd.DataFrame | None = None,
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    reference.to_csv(out_dir / PERCENTILES_FILE, index=False, float_format="%.5g")
    if edges is not None:
        edges.to_csv(out_dir / STRATA_FILE, index=False, float_format="%.4g")
    cover.to_csv(out_dir / "coverage.csv", index=False)
    definitions_table().to_csv(out_dir / "descriptor_definitions.csv", index=False)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, default=str), encoding="utf-8"
    )


def load_reference(ref_dir: Path | None = None) -> pd.DataFrame:
    """The percentile table; raises if the store is missing or malformed."""
    ref_dir = ref_dir or default_reference_dir()
    ref = pd.read_csv(ref_dir / PERCENTILES_FILE)
    missing = {"species_key", "height_bin", "descriptor", "n", *QUANTILES} - set(
        ref.columns
    )
    if missing:
        raise ValueError(f"{ref_dir / PERCENTILES_FILE}: missing columns {missing}")
    if "stratum" not in ref.columns:
        ref["stratum"] = ALL_STRATA
    return ref


def load_strata_edges(ref_dir: Path | None = None) -> pd.DataFrame | None:
    """``strata_edges.csv`` (slenderness tertiles per species x bin) or None."""
    path = (ref_dir or default_reference_dir()) / STRATA_FILE
    return pd.read_csv(path) if path.exists() else None


def load_core_set(ref_dir: Path | None = None) -> dict[str, set[str]] | None:
    """``core_set.csv`` (``species_key``, ``descriptor``; written once XRFF-576 fixes the
    core set) as species -> descriptors; None while the store has none."""
    path = (ref_dir or default_reference_dir()) / CORE_SET_FILE
    if not path.exists():
        return None
    core = pd.read_csv(path)
    return {sp: set(g["descriptor"]) for sp, g in core.groupby("species_key")}


def load_manifest(ref_dir: Path | None = None) -> dict:
    ref_dir = ref_dir or default_reference_dir()
    return json.loads((ref_dir / "manifest.json").read_text(encoding="utf-8"))
