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
of them, otherwise every tier, and says which in ``tiers``. The store is built from
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
    trees: pd.DataFrame, species: str, hbin: str, tiers: str, units: dict, min_n: int
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
                "tiers": tiers,
                "sources": ",".join(sorted(trees["source"].dropna().unique())),
                "descriptor": key,
                "unit": units[key],
                "n": len(values),
                **dict(zip(QUANTILES, q, strict=True)),
            }
        )
    return rows


def build_reference(
    table: pd.DataFrame,
    species: list[str] | None = None,
    bin_m: float = BIN_M,
    min_n: int = MIN_N,
) -> pd.DataFrame:
    """Percentile rows from a descriptor table (real trees only are used)."""
    real = table[(table["source_kind"] == "scan") & table["species_key"].notna()]
    real = real[real["L1.height_m"] > 0]
    if species is not None:
        real = real[real["species_key"].isin(species)]
    raw_units = {k: v[0] for k, v in DEFINITIONS.items()}
    norm_units = {k: normalised_unit(u) for k, u in raw_units.items()}
    bins = real["L1.height_m"].map(lambda h: height_bin(h, bin_m))
    rows: list[dict] = []
    for sp, trees in real.groupby("species_key"):
        used, tiers = _tier_subset(trees, min_n)
        if len(used) >= min_n:
            rows += _percentile_rows(
                normalise_by_height(used), sp, POOLED, tiers, norm_units, min_n
            )
        for hbin, in_bin in trees.groupby(bins.loc[trees.index]):
            used, tiers = _tier_subset(in_bin, min_n)
            if len(used) >= min_n:
                rows += _percentile_rows(used, sp, hbin, tiers, raw_units, min_n)
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
) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    reference.to_csv(out_dir / PERCENTILES_FILE, index=False, float_format="%.5g")
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
    return ref


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
