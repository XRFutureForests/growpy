"""Unified yield table loading and calibration math.

Supports two yield table sources:
1. Local CSV files in the configured yield_tables_dir (checked first)
2. openyieldtables.org API (fallback, requires Yield Search term in lookup CSV)

Local CSV format (age in years, height in meters, dbh in centimeters):
    age,height,dbh
    0,0.5,0.0
    10,5.2,4.5
    20,12.3,10.2
    30,18.7,16.8

File naming: <standardized_species_name>.csv (e.g., norway_spruce.csv)
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class YieldTableData:
    """Resolved yield table data for a single species and yield class."""

    ages: List[float]
    heights: List[float]
    dbhs: List[float]
    title: str
    source: str
    yield_class: Optional[float] = None
    table_id: Optional[int] = None


def load_local_yield_table(
    species_std: str, yield_tables_dir: Path
) -> Optional[YieldTableData]:
    """Load a yield table from a local CSV file.

    Args:
        species_std: Standardized species name (e.g., "norway_spruce").
        yield_tables_dir: Directory containing yield table CSVs.

    Returns:
        YieldTableData if found, None otherwise.
    """
    csv_path = yield_tables_dir / f"{species_std}.csv"
    if not csv_path.exists():
        return None

    import pandas as pd

    df = pd.read_csv(csv_path)
    required = {"age", "height", "dbh"}
    if not required.issubset(df.columns):
        logger.error(
            "Local yield table %s missing columns: %s (has: %s)",
            csv_path, required - set(df.columns), list(df.columns),
        )
        return None

    df = df.sort_values("age").reset_index(drop=True)

    return YieldTableData(
        ages=df["age"].tolist(),
        heights=df["height"].tolist(),
        dbhs=[d / 100.0 for d in df["dbh"].tolist()],
        title=f"Local: {csv_path.name}",
        source="local",
    )


def load_openyieldtables(
    table_id: int, yield_class: float
) -> Optional[YieldTableData]:
    """Load a yield table from the openyieldtables.org API.

    Args:
        table_id: Yield table ID from openyieldtables.org.
        yield_class: Yield class to select.

    Returns:
        YieldTableData if found, None otherwise.
    """
    from openyieldtables.yieldtables import get_yield_table

    table = get_yield_table(table_id)

    for yc in table.data.yield_classes:
        if float(yc.yield_class) != float(yield_class):
            continue
        ages, heights, dbhs = [], [], []
        for row in yc.rows:
            if row.dominant_height is not None:
                ages.append(row.age)
                heights.append(row.dominant_height)
                dbhs.append(row.dbh / 100.0 if row.dbh else 0.0)

        return YieldTableData(
            ages=ages,
            heights=heights,
            dbhs=dbhs,
            title=table.title,
            source="openyieldtables",
            yield_class=yield_class,
            table_id=table_id,
        )

    logger.error(
        "Yield class %s not found in table %d (%s)",
        yield_class, table_id, table.title,
    )
    return None


def auto_discover_yield_table(
    species_name: str, search_term: str
) -> Optional[Dict[str, Any]]:
    """Auto-discover the best yield table from openyieldtables.org.

    Returns:
        {"table_id": int, "yield_class": float} or None.
    """
    from openyieldtables.yieldtables import get_yield_table, get_yield_tables_meta

    meta = get_yield_tables_meta()
    term = search_term.lower()
    matches = [t for t in meta if term in t.title.lower()]
    if not matches:
        return None

    table_meta = matches[0]
    table = get_yield_table(table_meta.id)

    yc_values = []
    for yc in table.data.yield_classes:
        has_data = any(row.dominant_height is not None for row in yc.rows)
        if has_data:
            yc_values.append(float(yc.yield_class))

    if not yc_values:
        return None

    yc_values.sort()
    middle_yc = yc_values[len(yc_values) // 2]

    return {"table_id": table_meta.id, "yield_class": middle_yc}


def load_lookup_table(project_root: Path) -> Dict[str, Dict[str, str]]:
    """Load tree_asset_lookup.csv keyed by Common Name.

    Returns:
        {common_name: {"standardized": ..., "yield_search": ..., ...}}
    """
    import pandas as pd

    lookup_path = project_root / "src" / "growpy" / "config" / "tree_asset_lookup.csv"
    if not lookup_path.exists():
        logger.error("Asset lookup table not found: %s", lookup_path)
        return {}

    df = pd.read_csv(lookup_path)
    result = {}
    for _, row in df.iterrows():
        name = row["Common Name"]
        result[name] = {
            "standardized": row.get("Standardized Name", ""),
            "yield_search": str(row.get("Yield Search", "")).strip(),
        }
    return result


def resolve_yield_table(
    species_common: str,
    species_std: str,
    yield_tables_dir: Optional[Path],
    calibration_species: Dict[str, Dict[str, Any]],
    yield_search: str = "",
) -> Optional[YieldTableData]:
    """Resolve the best yield table for a species.

    Priority:
        1. Local CSV in yield_tables_dir (by standardized name)
        2. TOML override (explicit table_id + yield_class)
        3. openyieldtables auto-discovery (via Yield Search term)

    Args:
        species_common: Common name (e.g., "Norway spruce").
        species_std: Standardized name (e.g., "norway_spruce").
        yield_tables_dir: Path to local yield table CSVs.
        calibration_species: TOML [calibration.species] config.
        yield_search: Search term for openyieldtables auto-discovery.

    Returns:
        YieldTableData or None.
    """
    # 1. Try local CSV
    if yield_tables_dir and yield_tables_dir.exists():
        local = load_local_yield_table(species_std, yield_tables_dir)
        if local:
            logger.info("  Using local yield table: %s", local.title)
            return local

    # 2. Try TOML override
    toml_cfg = calibration_species.get(species_common, {})
    tid = toml_cfg.get("table_id")
    yc = toml_cfg.get("yield_class")
    if tid and yc:
        result = load_openyieldtables(tid, yc)
        if result:
            logger.info("  Using TOML override: table %d, YC %s", tid, yc)
            return result

    # 3. Auto-discover from openyieldtables
    if yield_search:
        discovered = auto_discover_yield_table(species_common, yield_search)
        if discovered:
            result = load_openyieldtables(
                discovered["table_id"], discovered["yield_class"]
            )
            if result:
                logger.info(
                    "  Auto-discovered: %s (table %d, YC %s)",
                    result.title, discovered["table_id"], discovered["yield_class"],
                )
                return result

    return None


# --- Calibration math (moved from calibrate_growth.py) ---


def estimate_flushes_per_year(
    grove_heights: List[float],
    yield_ages: List[float],
    yield_heights: List[float],
) -> float:
    """Estimate how many Grove growth cycles correspond to 1 calendar year.

    Compares the uncalibrated Grove height trajectory against the yield table
    to find the time-scaling factor. If Grove grows faster per cycle than real
    trees grow per year, fpy > 1 (multiple cycles per year). If slower, fpy < 1.

    Method:
        1. Find the Grove height at ~80% of its max (avoids noisy early/late growth).
        2. Find the age in the yield table where trees reach that same height.
        3. fpy = grove_cycle_at_reference / yield_age_at_reference.

    Returns:
        Estimated flushes_per_year, clamped to [0.3, 3.0].
    """
    from scipy.interpolate import PchipInterpolator

    if len(grove_heights) < 5 or len(yield_ages) < 2 or len(yield_heights) < 2:
        return 1.0

    grove_max = max(grove_heights)
    if grove_max < 1.0:
        return 1.0

    # Reference height: 60% of Grove max (avoids plateau and seedling phases)
    ref_height = grove_max * 0.6

    # Find Grove cycle where it reaches ref_height
    grove_cycle = None
    for i, h in enumerate(grove_heights):
        if h >= ref_height:
            grove_cycle = i + 1  # 1-based
            break
    if grove_cycle is None:
        return 1.0

    # Find yield table age where trees reach ref_height
    extended_ages = [0.0] + list(yield_ages)
    extended_heights = [0.5] + list(yield_heights)

    yield_max = max(yield_heights)
    if ref_height > yield_max:
        # Grove grows taller than yield table — use yield table max instead
        ref_height = yield_max * 0.6
        for i, h in enumerate(grove_heights):
            if h >= ref_height:
                grove_cycle = i + 1
                break

    interp = PchipInterpolator(extended_heights, extended_ages)
    try:
        yield_age = float(interp(ref_height))
    except Exception:
        return 1.0

    if yield_age <= 0.5:
        return 1.0

    fpy = grove_cycle / yield_age
    fpy = max(0.3, min(3.0, fpy))

    logger.info(
        "  flushes_per_year: %.2f (Grove cycle %d = yield age %.1f yr at h=%.1fm)",
        fpy, grove_cycle, yield_age, ref_height,
    )

    return fpy


def interpolate_yield_table(
    ages: List[float],
    values: List[float],
    max_cycles: int,
    flushes_per_year: float = 1.0,
    initial_value: float = 0.5,
) -> tuple:
    """Interpolate yield table to per-cycle resolution using PCHIP.

    Args:
        initial_value: Value at age 0. Use 0.5 for heights (sapling),
            0.0 for DBH (no trunk diameter at birth).
    """
    from scipy.interpolate import PchipInterpolator

    extended_ages = [0] + list(ages)
    extended_values = [initial_value] + list(values)

    interp = PchipInterpolator(extended_ages, extended_values)
    cycle_indices = np.arange(1, max_cycles + 1)
    calendar_ages = cycle_indices / flushes_per_year
    interpolated = np.maximum(interp(calendar_ages), 0.0)
    return cycle_indices, interpolated


def compute_grow_length_curve(
    grove_heights: List[float],
    target_heights: np.ndarray,
    base_grow_length: float,
) -> List[float]:
    """Compute per-cycle grow_length values to match target height trajectory."""
    from scipy.ndimage import uniform_filter1d

    n_cycles = min(len(grove_heights), len(target_heights))

    grove_increments = np.diff(grove_heights[:n_cycles])
    target_increments = np.diff(target_heights[:n_cycles])
    grove_increments = np.where(grove_increments < 0.001, 0.001, grove_increments)

    scale_factors = np.clip(target_increments / grove_increments, 0.5, 1.8)

    if len(scale_factors) > 5:
        scale_factors = uniform_filter1d(scale_factors, size=3)

    grow_lengths = base_grow_length * scale_factors
    max_gl = min(base_grow_length * 2.0, 0.65)
    # Floor at base_grow_length: never reduce below the seed's own value,
    # which was designed to sustain growth with its original drop values.
    grow_lengths = np.clip(grow_lengths, base_grow_length, max_gl)
    grow_lengths = np.insert(grow_lengths, 0, grow_lengths[0])

    return grow_lengths.tolist()


def compute_thicken_tips_curve(
    grove_dbhs: List[float],
    target_dbhs: np.ndarray,
    base_thicken_tips: float,
) -> List[float]:
    """Compute per-cycle thicken_tips values to match target DBH trajectory."""
    from scipy.ndimage import uniform_filter1d

    n_cycles = min(len(grove_dbhs), len(target_dbhs))

    grove_increments = np.diff(grove_dbhs[:n_cycles])
    target_increments = np.diff(target_dbhs[:n_cycles])
    grove_increments = np.where(
        np.abs(grove_increments) < 0.0001, 0.0001, grove_increments
    )

    scale_factors = np.clip(target_increments / grove_increments, 0.3, 3.0)

    if len(scale_factors) > 5:
        scale_factors = uniform_filter1d(scale_factors, size=5)

    thicken_tips_values = base_thicken_tips * scale_factors
    # Keep thicken_tips within a conservative range around the base value.
    # Large deviations disrupt tree growth balance (especially without longevity).
    # Remaining DBH correction is handled by radial scaling at export.
    ceiling = min(base_thicken_tips * 3.0, 0.03)
    thicken_tips_values = np.clip(thicken_tips_values, base_thicken_tips * 0.3, ceiling)
    thicken_tips_values = np.insert(thicken_tips_values, 0, thicken_tips_values[0])

    return thicken_tips_values.tolist()


def compute_dbh_static_overrides(
    grove_dbhs: List[float],
    target_dbhs: np.ndarray,
    base_grow_nodes: int = 3,
    base_thicken_deadwood: float = 0.0,
) -> Dict[str, float]:
    """Compute static overrides to reduce DBH toward yield table targets.

    Note: grow_nodes is NOT modified here. Reducing grow_nodes weakens the
    tree and can cause death when longevity mode is off. DBH is better
    controlled via thicken_tips_per_cycle and radial scaling at export.
    """
    n = min(len(grove_dbhs), len(target_dbhs))
    if n < 2:
        return {}

    overrides = {}

    if base_thicken_deadwood > 0:
        overrides["thicken_deadwood"] = 0.0

    return overrides


def write_calibration_to_seed_json(
    species_name: str,
    grow_lengths: List[float],
    table_title: str,
    presets_dir: Path,
    yield_class: Optional[float] = None,
    table_id: Optional[int] = None,
    thicken_tips_per_cycle: Optional[List[float]] = None,
    static_overrides: Optional[Dict[str, float]] = None,
    target_dbh_per_cycle: Optional[List[float]] = None,
    flushes_per_year: float = 1.0,
) -> Optional[Path]:
    """Write calibration data to the species seed.json."""
    species_dir = species_name.lower().replace(" ", "_")
    preset_path = presets_dir / f"{species_dir}.seed.json"

    if not preset_path.exists():
        logger.error("Preset not found: %s", preset_path)
        return None

    with open(preset_path) as f:
        preset = json.load(f)

    calibration: Dict[str, Any] = {
        "table_title": table_title,
        "grow_length_per_cycle": [round(v, 4) for v in grow_lengths],
        "description": (
            "Per-cycle values calibrated against yield table. "
            "Applied by PresetOverrides during simulation."
        ),
    }
    if table_id is not None:
        calibration["table_id"] = table_id
    if yield_class is not None:
        calibration["yield_class"] = yield_class
    if thicken_tips_per_cycle:
        calibration["thicken_tips_per_cycle"] = [
            round(v, 6) for v in thicken_tips_per_cycle
        ]
    if static_overrides:
        calibration["static_overrides"] = static_overrides
    if target_dbh_per_cycle:
        calibration["target_dbh_per_cycle"] = [
            round(v, 6) for v in target_dbh_per_cycle
        ]
    calibration["flushes_per_year"] = flushes_per_year
    preset["_yield_table_calibration"] = calibration

    with open(preset_path, "w") as f:
        json.dump(preset, f, indent=4)

    logger.info("Calibration written to %s", preset_path)
    return preset_path


def calibrate_species(
    species_name: str,
    grove_heights: List[float],
    grove_dbhs: List[float],
    yield_data: YieldTableData,
    presets_dir: Path,
    flushes_per_year: Optional[float] = None,
) -> bool:
    """Run full calibration for a single species and write results to seed.json.

    Args:
        species_name: Common name (e.g., "Norway spruce").
        grove_heights: Uncalibrated height curve from growth model.
        grove_dbhs: Uncalibrated DBH curve from growth model.
        yield_data: Resolved yield table data.
        presets_dir: Path to presets directory.
        flushes_per_year: Growth flushes per calendar year.
            None = auto-estimate from height curves (recommended).

    Returns:
        True if calibration was written successfully.
    """
    species_clean = species_name.lower().replace(" ", "_")
    max_cycles = len(grove_heights)

    # Load base preset values
    preset_path = presets_dir / f"{species_clean}.seed.json"
    if not preset_path.exists():
        logger.error("Preset not found: %s", preset_path)
        return False

    with open(preset_path) as f:
        preset = json.load(f)

    base_grow_length = preset.get("grow_length", 0.3)

    # Auto-estimate flushes_per_year from height curves if not specified
    if flushes_per_year is None:
        flushes_per_year = estimate_flushes_per_year(
            grove_heights, yield_data.ages, yield_data.heights,
        )

    # Height calibration
    _, yearly_heights = interpolate_yield_table(
        yield_data.ages, yield_data.heights, max_cycles, flushes_per_year
    )

    grow_lengths = compute_grow_length_curve(
        grove_heights, yearly_heights, base_grow_length
    )

    logger.info(
        "  grow_length: base=%.3f, range=%.4f-%.4f, avg=%.4f",
        base_grow_length, min(grow_lengths), max(grow_lengths), np.mean(grow_lengths),
    )

    # DBH calibration
    thicken_tips_values = None
    target_dbhs_interp = None

    if grove_dbhs and yield_data.dbhs:
        _, target_dbhs_interp = interpolate_yield_table(
            yield_data.ages, yield_data.dbhs, max_cycles, flushes_per_year,
            initial_value=0.0,
        )

        base_thicken_tips = preset.get("thicken_tips", 0.007)
        thicken_tips_values = compute_thicken_tips_curve(
            grove_dbhs, target_dbhs_interp, base_thicken_tips
        )

        logger.info(
            "  thicken_tips: base=%.4f, range=%.6f-%.6f",
            base_thicken_tips, min(thicken_tips_values), max(thicken_tips_values),
        )

    # Static DBH overrides
    dbh_static_overrides: Dict[str, float] = {}
    if grove_dbhs and target_dbhs_interp is not None:
        base_nodes = preset.get("grow_nodes", 3)
        base_deadwood = preset.get("thicken_deadwood", 0.0)
        dbh_static_overrides = compute_dbh_static_overrides(
            grove_dbhs, target_dbhs_interp,
            base_grow_nodes=base_nodes,
            base_thicken_deadwood=base_deadwood,
        )

        if "grow_nodes" in dbh_static_overrides:
            logger.info(
                "  grow_nodes: %d -> %d",
                base_nodes, dbh_static_overrides["grow_nodes"],
            )

    # Cap thicken_tips_reduce
    base_reduce = preset.get("thicken_tips_reduce", 0.0)
    if base_reduce > 0.5:
        dbh_static_overrides["thicken_tips_reduce"] = 0.5

    if dbh_static_overrides:
        for k, v in dbh_static_overrides.items():
            if k != "grow_nodes":
                logger.info("  %s: %s -> %s", k, preset.get(k, "?"), v)

    # Structural safety check
    actual_max_gl = min(base_grow_length * 2.0, 0.65)
    n_at_cap = sum(1 for gl in grow_lengths if gl >= actual_max_gl * 0.98)
    gl_capped = n_at_cap > len(grow_lengths) * 0.3

    write_grow_lengths = None if gl_capped else grow_lengths
    write_static = None if gl_capped else (
        dbh_static_overrides if dbh_static_overrides else None
    )

    if gl_capped:
        logger.warning(
            "  grow_length at cap for %d/%d cycles — "
            "skipping GL + static overrides (structural safety)",
            n_at_cap, len(grow_lengths),
        )

    # Target DBH for radial scaling at export
    write_target_dbh = None
    if target_dbhs_interp is not None and len(target_dbhs_interp) > 0:
        write_target_dbh = list(target_dbhs_interp[:len(grove_heights)])

    result = write_calibration_to_seed_json(
        species_name,
        write_grow_lengths or [base_grow_length] * len(grove_heights),
        yield_data.title,
        presets_dir,
        yield_class=yield_data.yield_class,
        table_id=yield_data.table_id,
        thicken_tips_per_cycle=thicken_tips_values,
        static_overrides=write_static,
        target_dbh_per_cycle=write_target_dbh,
        flushes_per_year=flushes_per_year,
    )

    return result is not None
