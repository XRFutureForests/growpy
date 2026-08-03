"""Species height-DBH allometry, fitted from yield tables alone.

The allometric power model ``DBH = a * H^b`` relates a tree's height to its
stem diameter at breast height.  Unlike yield-table *calibration* (which aligns
Grove's growth pacing to a yield table's height-at-age curve), this fit needs
nothing but the height and DBH columns of a yield table:

- no Grove simulation (this module never imports ``the_grove_23_core``),
- no cycle axis -- height indexes the model directly, so how many cycles a tree
  took to reach a height is irrelevant,
- no surround radius -- shading changes how fast a tree reaches a height, not
  the diameter it carries at that height.

That makes it cheap enough to rebuild on demand, and it is the only yield-table
product dataset production needs: trees are grown to height milestones, and
their DBH is realised at export by scaling the stem mesh toward the diameter
this model predicts for the height actually measured.

Artifacts are written to ``data/assets/allometry/<standardized_species>.json``.
They are deliberately kept out of the per-species ``seed.json`` files, whose
``_yield_table_calibration`` block is stripped between calibration runs.
"""

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

logger = logging.getLogger(__name__)

ALLOMETRY_DIRNAME = "allometry"

# Below the fitted height range the power model is extrapolating, and a power
# law extrapolated downward drifts toward implausibly slender stems.  Grove's
# own pipe model is physically derived and more trustworthy there, so the
# allometric correction is faded out: full weight at the fitted lower bound,
# zero at BLEND_FLOOR_FRAC of it.
BLEND_FLOOR_FRAC = 0.5

# load_species_allometry() is called once per tree per export stage (directly
# and via get_height_dbh_model()/correction_weight()); cache by resolved
# artifact path so a dataset run doesn't re-read the same per-species JSON
# from disk hundreds of times. write_species_allometry() keeps this in sync.
_allometry_cache: dict[str, dict | None] = {}


def get_allometry_dir() -> Path:
    """Directory holding per-species allometry artifacts."""
    from growpy.config.paths import get_assets_directory

    return get_assets_directory() / ALLOMETRY_DIRNAME


def _artifact_path(species: str) -> Path:
    from growpy.utils.naming import standardize_species_name

    return get_allometry_dir() / f"{standardize_species_name(species)}.json"


def build_species_allometry(
    species_common: str,
    config=None,
    yield_tables_dir: Path | None = None,
) -> dict | None:
    """Fit the height-DBH model for one species from its yield table.

    Table selection intentionally omits the ``preferred_h50`` hint that
    calibration uses, since that hint is derived from a Grove simulation and
    would reintroduce the dependency this module exists to avoid.  Site index
    mainly governs how fast height accrues with age; the height-DBH
    relationship is comparatively stable across site classes, so selecting by
    configured site index / region alone is sufficient here.

    Args:
        species_common: Common name as used in tree_asset_lookup.csv.
        config: Resolved GrowPyConfig (loaded via get_config() when omitted).
        yield_tables_dir: Override for the local yield table directory.

    Returns:
        Allometry record dict, or None when no yield table or fit is available.
    """
    from growpy.utils.yield_tables import (
        fit_height_dbh_model,
        load_lookup_table,
        resolve_yield_table,
    )

    if config is None:
        from growpy.config import get_config

        config = get_config()

    if yield_tables_dir is None:
        from growpy.config.paths import get_project_root

        yield_tables_dir = config.calibration_yield_tables_dir
        if not yield_tables_dir.is_absolute():
            yield_tables_dir = get_project_root() / yield_tables_dir

    lookup = load_lookup_table()
    entry = lookup.get(species_common)
    if entry is None:
        logger.warning("No lookup entry for %s -- skipping allometry", species_common)
        return None

    species_std = entry.get("standardized", "")
    yield_search = entry.get("yield_search", "")

    explicit_si = config.calibration_species.get(species_common, {}).get(
        "site_index", config.yield_sources_preferred_site_index
    )

    yield_data = resolve_yield_table(
        species_common=species_common,
        species_std=species_std,
        yield_tables_dir=yield_tables_dir,
        calibration_species=config.calibration_species,
        yield_search=yield_search,
        store_dir=config.yield_sources_store_dir,
        preferred_site_index=explicit_si,
        preferred_region=config.yield_sources_preferred_region,
        preferred_h50=None,
    )

    if yield_data is None:
        logger.warning("No yield table for %s -- skipping allometry", species_common)
        return None

    if not yield_data.heights or not yield_data.dbhs:
        logger.warning(
            "Yield table for %s has no height/DBH pairs -- skipping allometry",
            species_common,
        )
        return None

    model = fit_height_dbh_model(yield_data.heights, yield_data.dbhs)
    if model is None:
        logger.warning("Height-DBH fit failed for %s", species_common)
        return None

    # Mirror the fit's own row filter so height_range_m describes the range the
    # model was actually fitted on, not the raw table extent.
    from growpy.utils.yield_tables import MIN_FIT_DBH_M

    pairs = [
        (h, d)
        for h, d in zip(yield_data.heights, yield_data.dbhs, strict=False)
        if h > 0 and d >= MIN_FIT_DBH_M
    ]
    height_range = [min(h for h, _ in pairs), max(h for h, _ in pairs)]

    return {
        "species": species_std,
        "common_name": species_common,
        "source": {
            "table_id": yield_data.table_id,
            "title": yield_data.title,
            "yield_class": yield_data.yield_class,
            "region": yield_data.region,
            "site_index": yield_data.site_index,
        },
        "height_dbh_model": model,
        "height_range_m": height_range,
        "heights": list(yield_data.heights),
        "dbhs": list(yield_data.dbhs),
        "generated": datetime.now(UTC).isoformat(timespec="seconds"),
    }


def write_species_allometry(record: dict) -> Path:
    """Write an allometry record to its per-species artifact path."""
    out_path = _artifact_path(record["species"])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(record, f, indent=2)
    _allometry_cache[str(out_path)] = record
    return out_path


def load_species_allometry(species: str) -> dict | None:
    """Load a species' allometry artifact, or None when absent/unreadable.

    Cached by resolved artifact path (see _allometry_cache).
    """
    path = _artifact_path(species)
    key = str(path)
    if key in _allometry_cache:
        return _allometry_cache[key]
    if not path.exists():
        _allometry_cache[key] = None
        return None
    try:
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        logger.warning("Could not read allometry artifact %s: %s", path, e)
        record = None
    _allometry_cache[key] = record
    return record


def get_height_dbh_model(species: str, preset_path: Path | None = None) -> dict | None:
    """Resolve a species' height-DBH model, preferring the allometry artifact.

    Falls back to the ``_yield_table_calibration.height_dbh_model`` block in a
    seed.json so existing calibrated presets keep working until they are
    regenerated.

    Args:
        species: Species name (common or standardized).
        preset_path: Optional seed.json to fall back to.

    Returns:
        ``{"a": ..., "b": ...}`` or None when no model is available.
    """
    record = load_species_allometry(species)
    if record:
        model = record.get("height_dbh_model")
        if model and "a" in model and "b" in model:
            return model

    if preset_path is not None:
        from growpy.config.preset_overrides import load_height_dbh_model_from_preset

        return load_height_dbh_model_from_preset(preset_path)

    return None


def _smoothstep(t: float) -> float:
    """C1-continuous 0->1 ramp (3t^2 - 2t^3), clamped to [0, 1]."""
    t = max(0.0, min(1.0, t))
    return t * t * (3.0 - 2.0 * t)


def correction_weight(species: str, height_m: float) -> float:
    """Fraction of the allometric DBH correction to apply at *height_m*.

    Returns 1.0 at or above the fitted lower bound and fades to 0.0 at
    ``BLEND_FLOOR_FRAC`` of it, leaving Grove's own pipe-model diameter
    untouched for saplings the yield table never described.  Species with no
    allometry artifact get 1.0 (nothing to fade toward).
    """
    record = load_species_allometry(species)
    if not record:
        return 1.0
    rng = record.get("height_range_m")
    if not rng or len(rng) != 2 or rng[0] <= 0:
        return 1.0

    low = float(rng[0])
    if height_m >= low:
        return 1.0

    floor = low * BLEND_FLOOR_FRAC
    if height_m <= floor:
        return 0.0
    return _smoothstep((height_m - floor) / (low - floor))


def build_all_allometries(
    species_names: list[str],
    config=None,
) -> dict[str, Path]:
    """Build and write allometry artifacts for several species.

    Returns:
        {common_name: artifact_path} for species that produced a fit.
    """
    written: dict[str, Path] = {}
    for species in species_names:
        record = build_species_allometry(species, config=config)
        if record is None:
            continue
        path = write_species_allometry(record)
        model = record["height_dbh_model"]
        logger.info(
            "  %s: DBH = %.6f * H^%.4f (R2=%.4f) -> %s",
            species,
            model["a"],
            model["b"],
            model.get("r_squared", float("nan")),
            path.name,
        )
        written[species] = path
    return written
