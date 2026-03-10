#!/usr/bin/env python3
"""Compare Grove growth curves with real-world yield tables and generate calibration overrides.

Fetches yield table data from openyieldtables.org and compares against Grove's
simulated height/DBH curves. Optionally generates per-species grow_length curves
that adjust Grove's growth rate to match the yield table trajectory.

Usage:
    # Compare Grove vs yield table (interactive table selection)
    python src/growpy/cli/compare_growth.py --species "Norway spruce"

    # Compare with specific yield table ID and yield class
    python src/growpy/cli/compare_growth.py --species "Norway spruce" --table-id 2 --yield-class 12

    # Generate calibration overrides and write to seed.json
    python src/growpy/cli/compare_growth.py --species "Norway spruce" --table-id 2 --yield-class 12 --calibrate

    # Compare all species with growth models
    python src/growpy/cli/compare_growth.py --all
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
import numpy as np

from openyieldtables.yieldtables import get_yield_table, get_yield_tables_meta

logger = logging.getLogger(__name__)

# Species name mapping: growpy name -> yield table search terms
SPECIES_YIELD_TABLE_MAP = {
    "Norway spruce": {"search": "Fichte", "tree_type": "coniferous"},
    "European beech": {"search": "Buche", "tree_type": "deciduous"},
    "Silver fir": {"search": "Tanne", "tree_type": "coniferous"},
    "European oak": {"search": "Eiche", "tree_type": "deciduous"},
}


def find_yield_tables_for_species(species_name: str) -> list:
    """Find matching yield tables for a species from the API."""
    meta = get_yield_tables_meta()
    search_info = SPECIES_YIELD_TABLE_MAP.get(species_name, {})
    search_term = search_info.get("search", species_name.split()[-1])

    matches = []
    for table in meta:
        if search_term.lower() in table.title.lower():
            matches.append(table)
    return matches


def load_yield_table_curves(
    table_id: int,
    yield_class: Optional[float] = None,
) -> Dict[str, List[Tuple[float, float]]]:
    """Load height-over-age and DBH-over-age curves from a yield table.

    Returns dict with 'height' and 'dbh' keys, each a list of (age, value) tuples.
    If yield_class is None, returns all yield classes.
    """
    table = get_yield_table(table_id)
    result = {}

    for yc in table.data.yield_classes:
        if yield_class is not None and float(yc.yield_class) != float(yield_class):
            continue
        ages = []
        heights = []
        dbhs = []
        for row in yc.rows:
            if row.dominant_height is not None:
                ages.append(row.age)
                heights.append(row.dominant_height)
                dbhs.append(row.dbh / 100.0 if row.dbh else 0.0)  # cm -> m

        yc_key = f"YC {yc.yield_class}"
        result[yc_key] = {
            "ages": ages,
            "heights": heights,
            "dbhs": dbhs,
            "yield_class": yc.yield_class,
        }

    return result, table.title


def load_grove_curves(species_name: str) -> Optional[dict]:
    """Load Grove's simulated growth curves from growth model files."""
    species_dir = species_name.lower().replace(" ", "_")
    growth_model_dir = Path("data/assets/growth_models") / species_dir

    height_curve_path = growth_model_dir / "height_curve.json"
    if not height_curve_path.exists():
        return None

    with open(height_curve_path) as f:
        data = json.load(f)

    return {
        "height_curve": data["height_curve"],
        "dbh_curve": data.get("metadata", {}).get("dbh_curve", []),
        "species": species_name,
    }


def interpolate_yield_table(
    ages: List[float],
    heights: List[float],
    max_cycles: int,
) -> np.ndarray:
    """Interpolate yield table to per-cycle (per-year) resolution.

    Yield tables have coarse age steps (5-10 years). This interpolates
    to annual resolution using PCHIP. For years before the first yield table
    entry, linearly interpolates from height=0 at age=0 to the first entry.
    """
    from scipy.interpolate import PchipInterpolator

    # Add origin point (age 0, height ~0) for sensible early-age interpolation
    # Use a small starting height (sapling) to avoid negative values
    extended_ages = [0] + list(ages)
    extended_heights = [0.5] + list(heights)

    # PCHIP preserves monotonicity (no overshoot like cubic spline)
    interp = PchipInterpolator(extended_ages, extended_heights)
    # Generate yearly values from age 1 to max_cycles
    yearly_ages = np.arange(1, max_cycles + 1)
    yearly_heights = interp(yearly_ages)
    # Ensure no negative heights
    yearly_heights = np.maximum(yearly_heights, 0.1)
    return yearly_ages, yearly_heights


def compute_grow_length_curve(
    grove_heights: List[float],
    target_heights: np.ndarray,
    base_grow_length: float,
) -> List[float]:
    """Compute per-cycle grow_length values to match target height trajectory.

    Strategy: For each cycle, compute the ratio between the desired height
    increment (from yield table) and the Grove height increment, then scale
    grow_length proportionally.

    Args:
        grove_heights: Grove's height per cycle (from simulation)
        target_heights: Target height per cycle (from yield table, interpolated)
        base_grow_length: Original grow_length from species preset

    Returns:
        List of grow_length values, one per cycle
    """
    n_cycles = min(len(grove_heights), len(target_heights))

    # Height increments per cycle
    grove_increments = np.diff(grove_heights[:n_cycles])
    target_increments = np.diff(target_heights[:n_cycles])

    # Avoid division by zero
    grove_increments = np.where(grove_increments < 0.001, 0.001, grove_increments)

    # Scale factor per cycle
    scale_factors = target_increments / grove_increments

    # Clamp to reasonable range (0.5x to 1.8x base grow_length)
    # Higher values cause structural instability (tree dies from thin+long branches)
    scale_factors = np.clip(scale_factors, 0.5, 1.8)

    # Smooth the scale factors to avoid jitter
    from scipy.ndimage import uniform_filter1d

    if len(scale_factors) > 5:
        scale_factors = uniform_filter1d(scale_factors, size=3)

    grow_lengths = base_grow_length * scale_factors
    # Absolute cap: long segments cause structural failure in some species
    # Cap at 2x base AND absolute 0.65m (whichever is lower)
    max_gl = min(base_grow_length * 2.0, 0.65)
    grow_lengths = np.clip(grow_lengths, base_grow_length * 0.5, max_gl)
    # Prepend first value for cycle 0
    grow_lengths = np.insert(grow_lengths, 0, grow_lengths[0])

    return grow_lengths.tolist()


def compute_thicken_tips_curve(
    grove_dbhs: List[float],
    target_dbhs: np.ndarray,
    base_thicken_tips: float,
) -> List[float]:
    """Compute per-cycle thicken_tips values to match target DBH trajectory.

    Strategy: Same ratio approach as grow_length calibration. For each cycle,
    compute the ratio between desired DBH increment and Grove's DBH increment,
    then scale thicken_tips proportionally.

    thicken_tips sets the initial diameter of new growth segments. Since trunk
    diameter is cumulative (mass of all branches above), adjusting thicken_tips
    affects the rate of diameter accumulation per cycle.

    Args:
        grove_dbhs: Grove's DBH per cycle (from simulation, in meters)
        target_dbhs: Target DBH per cycle (from yield table, interpolated, in meters)
        base_thicken_tips: Original thicken_tips from species preset

    Returns:
        List of thicken_tips values, one per cycle
    """
    n_cycles = min(len(grove_dbhs), len(target_dbhs))

    # DBH increments per cycle
    grove_increments = np.diff(grove_dbhs[:n_cycles])
    target_increments = np.diff(target_dbhs[:n_cycles])

    # Avoid division by zero (DBH can be 0 for young trees below 1.3m)
    grove_increments = np.where(
        np.abs(grove_increments) < 0.0001, 0.0001, grove_increments
    )

    # Scale factor per cycle
    scale_factors = target_increments / grove_increments

    # Clamp to reasonable range (thicken_tips is very small: 0.003-0.01)
    scale_factors = np.clip(scale_factors, 0.05, 20.0)

    # Smooth to avoid jitter
    from scipy.ndimage import uniform_filter1d

    if len(scale_factors) > 5:
        scale_factors = uniform_filter1d(scale_factors, size=5)

    thicken_tips_values = base_thicken_tips * scale_factors
    # Clamp to physically reasonable range
    # Floor at 40% of base to prevent paper-thin branches (structural instability)
    floor = max(0.001, base_thicken_tips * 0.4)
    thicken_tips_values = np.clip(thicken_tips_values, floor, 0.05)
    # Prepend first value for cycle 0
    thicken_tips_values = np.insert(thicken_tips_values, 0, thicken_tips_values[0])

    return thicken_tips_values.tolist()


def plot_comparison(
    species_name: str,
    grove_data: dict,
    yield_curves: dict,
    table_title: str,
    output_path: Optional[Path] = None,
    calibrated_heights: Optional[np.ndarray] = None,
    selected_yc: Optional[str] = None,
) -> None:
    """Plot Grove curves vs yield table curves side by side."""
    mplstyle.use("default")
    style = "seaborn-v0_8" if "seaborn-v0_8" in plt.style.available else "default"
    plt.style.use(style)

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(
        f"{species_name}: Grove vs Yield Table ({table_title})",
        fontsize=14,
        fontweight="bold",
    )

    # --- Height comparison ---
    ax1 = axes[0]
    grove_heights = grove_data["height_curve"]
    grove_cycles = list(range(1, len(grove_heights) + 1))
    ax1.plot(grove_cycles, grove_heights, "b-", linewidth=2.5, label="Grove (cycles)")

    if calibrated_heights is not None:
        cal_cycles = list(range(1, len(calibrated_heights) + 1))
        ax1.plot(
            cal_cycles, calibrated_heights, "g--", linewidth=2, label="Calibrated target"
        )

    for yc_name, yc_data in yield_curves.items():
        is_selected = selected_yc and yc_name == selected_yc
        alpha = 1.0 if is_selected else 0.3
        lw = 2.0 if is_selected else 0.8
        ax1.plot(
            yc_data["ages"],
            yc_data["heights"],
            "r-" if is_selected else "r-",
            alpha=alpha,
            linewidth=lw,
            label=f"Yield {yc_name}" if is_selected else None,
        )

    # Light gray for non-selected yield classes (add single legend entry)
    non_selected = [k for k in yield_curves if k != selected_yc]
    if non_selected:
        ax1.plot([], [], "r-", alpha=0.3, linewidth=0.8, label="Other yield classes")

    ax1.set_xlabel("Age (years) / Grove cycles")
    ax1.set_ylabel("Height (m)")
    ax1.set_title("Height over Age")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # --- DBH comparison ---
    ax2 = axes[1]
    grove_dbhs = grove_data.get("dbh_curve", [])
    if grove_dbhs:
        dbh_cycles = list(range(1, len(grove_dbhs) + 1))
        ax2.plot(
            dbh_cycles,
            [d * 100 for d in grove_dbhs],  # m -> cm
            "b-",
            linewidth=2.5,
            label="Grove (cycles)",
        )

    for yc_name, yc_data in yield_curves.items():
        is_selected = selected_yc and yc_name == selected_yc
        alpha = 1.0 if is_selected else 0.3
        lw = 2.0 if is_selected else 0.8
        ax2.plot(
            yc_data["ages"],
            [d * 100 for d in yc_data["dbhs"]],  # m -> cm
            "r-" if is_selected else "r-",
            alpha=alpha,
            linewidth=lw,
            label=f"Yield {yc_name}" if is_selected else None,
        )

    if non_selected:
        ax2.plot([], [], "r-", alpha=0.3, linewidth=0.8, label="Other yield classes")

    ax2.set_xlabel("Age (years) / Grove cycles")
    ax2.set_ylabel("DBH (cm)")
    ax2.set_title("Diameter at Breast Height over Age")
    ax2.legend(loc="upper left")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info("Plot saved to %s", output_path)
    else:
        plt.show()


def plot_calibration_detail(
    species_name: str,
    grove_heights: List[float],
    target_heights: np.ndarray,
    grow_lengths: List[float],
    base_grow_length: float,
    output_path: Optional[Path] = None,
    grove_dbhs: Optional[List[float]] = None,
    target_dbhs: Optional[np.ndarray] = None,
    thicken_tips_values: Optional[List[float]] = None,
    base_thicken_tips: Optional[float] = None,
) -> None:
    """Plot calibration details: height + DBH targets and parameter curves."""
    mplstyle.use("default")
    style = "seaborn-v0_8" if "seaborn-v0_8" in plt.style.available else "default"
    plt.style.use(style)

    has_dbh = grove_dbhs and target_dbhs is not None and thicken_tips_values
    n_rows = 4 if has_dbh else 2
    fig, axes = plt.subplots(n_rows, 1, figsize=(14, 5 * n_rows))
    fig.suptitle(
        f"{species_name}: Growth Rate Calibration",
        fontsize=14,
        fontweight="bold",
    )

    n = min(len(grove_heights), len(target_heights))
    cycles = list(range(1, n + 1))

    # Row 1: Height comparison
    ax1 = axes[0]
    ax1.plot(cycles, grove_heights[:n], "b-", linewidth=2, label="Grove (uncalibrated)")
    ax1.plot(cycles, target_heights[:n], "r--", linewidth=2, label="Yield table target")
    ax1.set_xlabel("Cycle / Year")
    ax1.set_ylabel("Height (m)")
    ax1.set_title("Height Trajectory")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

    # Row 2: grow_length curve
    ax2 = axes[1]
    gl_cycles = list(range(1, len(grow_lengths) + 1))
    ax2.plot(gl_cycles, grow_lengths, "g-", linewidth=2, label="Calibrated grow_length")
    ax2.axhline(
        y=base_grow_length, color="b", linestyle=":", alpha=0.7,
        label=f"Original ({base_grow_length})",
    )
    ax2.set_xlabel("Cycle / Year")
    ax2.set_ylabel("grow_length (m)")
    ax2.set_title("grow_length per Cycle (applied via PresetOverrides)")
    ax2.legend()
    ax2.grid(True, alpha=0.3)

    if has_dbh:
        n_dbh = min(len(grove_dbhs), len(target_dbhs))
        dbh_cycles = list(range(1, n_dbh + 1))

        # Row 3: DBH comparison
        ax3 = axes[2]
        ax3.plot(
            dbh_cycles,
            [d * 100 for d in grove_dbhs[:n_dbh]],
            "b-", linewidth=2, label="Grove (uncalibrated)",
        )
        ax3.plot(
            dbh_cycles,
            [d * 100 for d in target_dbhs[:n_dbh]],
            "r--", linewidth=2, label="Yield table target",
        )
        ax3.set_xlabel("Cycle / Year")
        ax3.set_ylabel("DBH (cm)")
        ax3.set_title("DBH Trajectory")
        ax3.legend()
        ax3.grid(True, alpha=0.3)

        # Row 4: thicken_tips curve
        ax4 = axes[3]
        tt_cycles = list(range(1, len(thicken_tips_values) + 1))
        ax4.plot(
            tt_cycles, thicken_tips_values, "g-", linewidth=2,
            label="Calibrated thicken_tips",
        )
        if base_thicken_tips is not None:
            ax4.axhline(
                y=base_thicken_tips, color="b", linestyle=":", alpha=0.7,
                label=f"Original ({base_thicken_tips})",
            )
        ax4.set_xlabel("Cycle / Year")
        ax4.set_ylabel("thicken_tips (m)")
        ax4.set_title("thicken_tips per Cycle (applied via PresetOverrides)")
        ax4.legend()
        ax4.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
        logger.info("Calibration plot saved to %s", output_path)
    else:
        plt.show()


def compute_dbh_static_overrides(
    grove_dbhs: List[float],
    target_dbhs: np.ndarray,
    base_thicken_base_scale: float,
    base_thicken_base_buttress: float,
    base_grow_nodes: int = 3,
) -> Dict[str, float]:
    """Compute static overrides to reduce DBH toward yield table targets.

    Uses multiple levers:
    1. Reduce grow_nodes (fewer internodes = fewer thickening events per cycle).
       The caller must compensate grow_length per-cycle values proportionally.
    2. Reduce thicken_base_scale (trunk base multiplier, min 1.0).
    3. Reduce thicken_base_buttress (basal flare).

    The grow_nodes reduction is the primary lever since it directly reduces
    the number of radial thickening events without affecting height.
    """
    n = min(len(grove_dbhs), len(target_dbhs))
    if n < 2:
        return {}

    grove_final_dbh = grove_dbhs[n - 1]
    target_final_dbh = target_dbhs[n - 1]

    if grove_final_dbh < 0.001 or target_final_dbh < 0.001:
        return {}

    dbh_ratio = target_final_dbh / grove_final_dbh

    overrides = {}

    if dbh_ratio < 0.9:
        # Primary lever: reduce grow_nodes
        # Each node adds a thickening event, so fewer nodes = less thickening.
        # Cap reduction at 50% of original to preserve tree architecture
        # (branching density, crown shape). Use sqrt of ratio for partial correction.
        node_factor = max(0.5, dbh_ratio ** 0.5)
        new_nodes = max(2, round(base_grow_nodes * node_factor))
        if new_nodes < base_grow_nodes:
            overrides["grow_nodes"] = new_nodes

        # Secondary lever: reduce thicken_base_scale (min 1.0)
        new_base_scale = max(1.0, base_thicken_base_scale * dbh_ratio)
        overrides["thicken_base_scale"] = round(new_base_scale, 4)

        # Tertiary lever: reduce buttress
        if base_thicken_base_buttress > 0:
            new_buttress = max(0.0, base_thicken_base_buttress * dbh_ratio)
            overrides["thicken_base_buttress"] = round(new_buttress, 4)

    return overrides


def write_calibration_to_seed_json(
    species_name: str,
    grow_lengths: List[float],
    yield_table_id: int,
    yield_class: float,
    table_title: str,
    thicken_tips_per_cycle: Optional[List[float]] = None,
    static_overrides: Optional[Dict[str, float]] = None,
) -> Path:
    """Write calibration data to the species seed.json.

    Adds a `_yield_table_calibration` key with per-cycle values and optional
    static overrides that are loaded by the PresetOverrides system.
    """
    species_dir = species_name.lower().replace(" ", "_")
    preset_path = Path("data/assets/presets") / f"{species_dir}.seed.json"

    if not preset_path.exists():
        logger.error("Preset not found: %s", preset_path)
        return None

    with open(preset_path) as f:
        preset = json.load(f)

    calibration = {
        "table_id": yield_table_id,
        "yield_class": yield_class,
        "table_title": table_title,
        "grow_length_per_cycle": [round(v, 4) for v in grow_lengths],
        "description": (
            "Per-cycle values calibrated against yield table. "
            "Applied by PresetOverrides during simulation."
        ),
    }
    if thicken_tips_per_cycle:
        calibration["thicken_tips_per_cycle"] = [
            round(v, 6) for v in thicken_tips_per_cycle
        ]
    if static_overrides:
        calibration["static_overrides"] = static_overrides
    preset["_yield_table_calibration"] = calibration

    with open(preset_path, "w") as f:
        json.dump(preset, f, indent=4)

    logger.info("Calibration written to %s", preset_path)
    return preset_path


def run_comparison(
    species_name: str,
    table_id: Optional[int] = None,
    yield_class: Optional[float] = None,
    calibrate: bool = False,
    output_dir: Optional[Path] = None,
) -> Optional[List[float]]:
    """Run full comparison and optional calibration for a species.

    Returns grow_length curve if calibrate=True, else None.
    """
    # Load Grove curves
    grove_data = load_grove_curves(species_name)
    if grove_data is None:
        logger.error(
            "No growth model found for %s. Run create_growth_models.py first.",
            species_name,
        )
        return None

    # Find or use specified yield table
    if table_id is None:
        matches = find_yield_tables_for_species(species_name)
        if not matches:
            logger.error("No yield tables found for %s", species_name)
            return None
        print(f"\nAvailable yield tables for {species_name}:")
        for m in matches:
            countries = ", ".join(m.country_codes) if m.country_codes else "?"
            print(f"  ID {m.id:3d}: {m.title} ({countries})")
        print(f"\nUsing first match: ID {matches[0].id} ({matches[0].title})")
        table_id = matches[0].id

    # Load yield table data
    yield_curves, table_title = load_yield_table_curves(table_id, yield_class)
    if not yield_curves:
        logger.error("No data found for table %d, yield class %s", table_id, yield_class)
        return None

    print(f"\nYield table: {table_title} (ID {table_id})")
    print(f"Yield classes available: {list(yield_curves.keys())}")

    # Select yield class for calibration
    selected_yc = None
    if yield_class is not None:
        # Match the key format from load_yield_table_curves (uses int from API)
        selected_yc = f"YC {int(yield_class)}"
    elif len(yield_curves) == 1:
        selected_yc = list(yield_curves.keys())[0]

    # Print comparison summary
    grove_heights = grove_data["height_curve"]
    print(f"\nGrove: {len(grove_heights)} cycles, "
          f"height {grove_heights[0]:.1f}m -> {grove_heights[-1]:.1f}m")

    if selected_yc and selected_yc in yield_curves:
        yc_data = yield_curves[selected_yc]
        print(f"Yield table ({selected_yc}): ages {yc_data['ages'][0]}-{yc_data['ages'][-1]}, "
              f"height {yc_data['heights'][0]:.1f}m -> {yc_data['heights'][-1]:.1f}m")

        # Rate comparison
        grove_rate = (grove_heights[-1] - grove_heights[0]) / len(grove_heights)
        yt_rate = (yc_data["heights"][-1] - yc_data["heights"][0]) / (
            yc_data["ages"][-1] - yc_data["ages"][0]
        )
        print(f"\nGrowth rate comparison:")
        print(f"  Grove:       {grove_rate:.3f} m/cycle")
        print(f"  Yield table: {yt_rate:.3f} m/year")
        print(f"  Ratio:       {yt_rate / grove_rate:.1f}x (yield table is faster)")

    # Output directory
    if output_dir is None:
        output_dir = Path("data/output/growth_comparison")

    species_clean = species_name.lower().replace(" ", "_")

    # Calibration
    calibrated_heights = None
    grow_lengths = None
    if calibrate and selected_yc and selected_yc in yield_curves:
        yc_data = yield_curves[selected_yc]
        max_cycles = len(grove_heights)

        # Interpolate yield table to per-cycle resolution
        yearly_ages, yearly_heights = interpolate_yield_table(
            yc_data["ages"], yc_data["heights"], max_cycles
        )
        calibrated_heights = yearly_heights

        # Load base grow_length from preset
        preset_path = Path("data/assets/presets") / f"{species_clean}.seed.json"
        with open(preset_path) as f:
            preset = json.load(f)
        base_grow_length = preset.get("grow_length", 0.3)

        # Compute calibration curve
        grow_lengths = compute_grow_length_curve(
            grove_heights, yearly_heights, base_grow_length
        )

        print(f"\nCalibration (grow_length):")
        print(f"  Base:    {base_grow_length}")
        print(f"  Range:   {min(grow_lengths):.4f} - {max(grow_lengths):.4f}")
        print(f"  Average: {np.mean(grow_lengths):.4f}")

        # DBH calibration
        grove_dbhs = grove_data.get("dbh_curve", [])
        thicken_tips_values = None
        base_thicken_tips = None
        target_dbhs_interp = None

        if grove_dbhs and yc_data["dbhs"]:
            _, target_dbhs_interp = interpolate_yield_table(
                yc_data["ages"], yc_data["dbhs"], max_cycles
            )

            base_thicken_tips = preset.get("thicken_tips", 0.007)

            thicken_tips_values = compute_thicken_tips_curve(
                grove_dbhs, target_dbhs_interp, base_thicken_tips
            )

            print(f"\nCalibration (thicken_tips):")
            print(f"  Base:    {base_thicken_tips}")
            print(f"  Range:   {min(thicken_tips_values):.6f} - {max(thicken_tips_values):.6f}")
            print(f"  Average: {np.mean(thicken_tips_values):.6f}")

            # DBH rate comparison
            grove_dbh_rate = (grove_dbhs[-1] - grove_dbhs[0]) / len(grove_dbhs)
            yt_dbh_rate = (yc_data["dbhs"][-1] - yc_data["dbhs"][0]) / (
                yc_data["ages"][-1] - yc_data["ages"][0]
            )
            print(f"\nDBH rate comparison:")
            print(f"  Grove:       {grove_dbh_rate * 100:.3f} cm/cycle")
            print(f"  Yield table: {yt_dbh_rate * 100:.3f} cm/year")

        # Compute static DBH overrides (grow_nodes, thicken_base_scale, etc.)
        dbh_static_overrides = {}
        if grove_dbhs and target_dbhs_interp is not None:
            base_scale = preset.get("thicken_base_scale", 1.2)
            base_buttress = preset.get("thicken_base_buttress", 2.0)
            base_nodes = preset.get("grow_nodes", 3)
            dbh_static_overrides = compute_dbh_static_overrides(
                grove_dbhs,
                target_dbhs_interp,
                base_scale,
                base_buttress,
                base_grow_nodes=base_nodes,
            )

            # If grow_nodes was reduced, do NOT rescale grow_length here.
            # The node reduction changes the baseline growth — the per-cycle
            # grow_length values will be recalibrated after re-growing with
            # reduced nodes. The grow_length values written here are from the
            # original calibration and will be overwritten on the next iteration.
            if "grow_nodes" in dbh_static_overrides:
                new_nodes = dbh_static_overrides["grow_nodes"]
                print(f"\n  grow_nodes reduced {base_nodes} -> {new_nodes} "
                      f"(fewer thickening events per cycle)")

        # Cap thicken_tips_reduce to prevent branch thinning instability
        base_reduce = preset.get("thicken_tips_reduce", 0.0)
        if base_reduce > 0.5:
            dbh_static_overrides["thicken_tips_reduce"] = 0.5

        if dbh_static_overrides:
            print(f"\nStatic DBH overrides:")
            for k, v in dbh_static_overrides.items():
                orig = preset.get(k, "?")
                print(f"  {k}: {orig} -> {v}")

        # Plot calibration detail (height + DBH)
        plot_calibration_detail(
            species_name,
            grove_heights,
            yearly_heights,
            grow_lengths,
            base_grow_length,
            output_dir / f"{species_clean}_calibration.png",
            grove_dbhs=grove_dbhs,
            target_dbhs=target_dbhs_interp,
            thicken_tips_values=thicken_tips_values,
            base_thicken_tips=base_thicken_tips,
        )

        # Detect structurally fragile species: if grow_length was heavily capped
        # for a large fraction of cycles, skip GL and static overrides
        # to avoid structural instability (thin trunk + long segments = death)
        actual_max_gl = min(base_grow_length * 2.0, 0.65)
        n_at_cap = sum(1 for gl in grow_lengths if gl >= actual_max_gl * 0.98)
        gl_capped = n_at_cap > len(grow_lengths) * 0.3  # >30% of cycles at cap

        write_grow_lengths = None if gl_capped else grow_lengths
        write_static = None if gl_capped else (
            dbh_static_overrides if dbh_static_overrides else None
        )

        if gl_capped:
            print(f"\n  [!] grow_length at cap for {n_at_cap}/{len(grow_lengths)} "
                  f"cycles (cap={actual_max_gl:.3f}) for {species_name} — "
                  "skipping GL + static overrides (structural safety)")

        # Write to seed.json
        write_calibration_to_seed_json(
            species_name,
            write_grow_lengths or [base_grow_length] * len(grove_heights),
            table_id,
            yield_curves[selected_yc]["yield_class"],
            table_title,
            thicken_tips_per_cycle=thicken_tips_values,
            static_overrides=write_static,
        )

    # Plot comparison
    plot_comparison(
        species_name,
        grove_data,
        yield_curves,
        table_title,
        output_dir / f"{species_clean}_comparison.png",
        calibrated_heights=calibrated_heights,
        selected_yc=selected_yc,
    )

    return grow_lengths


def main():
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Compare Grove growth curves with yield tables"
    )
    parser.add_argument(
        "--species",
        type=str,
        help="Species name (e.g., 'Norway spruce')",
    )
    parser.add_argument(
        "--table-id",
        type=int,
        help="Yield table ID from openyieldtables.org",
    )
    parser.add_argument(
        "--yield-class",
        type=float,
        help="Specific yield class to compare against",
    )
    parser.add_argument(
        "--calibrate",
        action="store_true",
        help="Generate grow_length calibration curve and write to seed.json",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Compare all species that have growth models",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output/growth_comparison"),
        help="Output directory for comparison plots",
    )
    parser.add_argument(
        "--list-tables",
        action="store_true",
        help="List available yield tables for a species",
    )

    args = parser.parse_args()

    if args.list_tables:
        species = args.species or "Norway spruce"
        matches = find_yield_tables_for_species(species)
        print(f"\nYield tables matching '{species}':")
        for m in matches:
            countries = ", ".join(m.country_codes) if m.country_codes else "?"
            print(f"  ID {m.id:3d}: {m.title} ({countries}) - YC step: {m.yield_class_step}")
        return

    if args.all:
        growth_models_dir = Path("data/assets/growth_models")
        if not growth_models_dir.exists():
            logger.error("No growth models found at %s", growth_models_dir)
            return
        for species_dir in sorted(growth_models_dir.iterdir()):
            if not species_dir.is_dir():
                continue
            species_name = species_dir.name.replace("_", " ").title()
            # Normalize capitalization for known species
            name_map = {
                "Norway Spruce": "Norway spruce",
                "European Beech": "European beech",
                "European Oak": "European oak",
                "Silver Fir": "Silver fir",
            }
            species_name = name_map.get(species_name, species_name)
            print(f"\n{'=' * 60}")
            print(f"  {species_name}")
            print(f"{'=' * 60}")
            run_comparison(
                species_name,
                table_id=args.table_id,
                yield_class=args.yield_class,
                calibrate=args.calibrate,
                output_dir=args.output_dir,
            )
        return

    if not args.species:
        parser.error("--species is required (or use --all)")

    run_comparison(
        args.species,
        table_id=args.table_id,
        yield_class=args.yield_class,
        calibrate=args.calibrate,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
