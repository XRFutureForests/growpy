#!/usr/bin/env python3
"""Calibrate growth models against real-world yield tables.

Step 3b of the pipeline (runs after create_growth_models.py).
Defaults from growpy.toml [calibration]. See docs/cli-reference.md.

Fetches yield table data from openyieldtables.org and compares against Grove's
simulated height/DBH curves. For species with configured yield tables, generates
per-cycle grow_length overrides that adjust Grove's growth rate to match the
yield table trajectory. Calibration data is written to the seed.json files
and automatically applied by the PresetOverrides system during forest generation.

Usage:
    # Calibrate all species configured in growpy.toml [calibration.species]
    python src/growpy/cli/calibrate_growth.py

    # Compare only (plot without writing calibration)
    python src/growpy/cli/calibrate_growth.py --compare-only

    # Calibrate a single species with explicit yield table
    python src/growpy/cli/calibrate_growth.py --species "Norway spruce" --table-id 2 --yield-class 12

    # List available yield tables for a species
    python src/growpy/cli/calibrate_growth.py --species "Norway spruce" --list-tables
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional

import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
import numpy as np

logger = logging.getLogger(__name__)


def find_yield_tables_for_species(
    species_name: str, search_term: Optional[str] = None
) -> list:
    """Find matching yield tables for a species from the API."""
    from openyieldtables.yieldtables import get_yield_tables_meta

    meta = get_yield_tables_meta()
    # Use explicit search term, or fall back to last word of species name
    term = (search_term or species_name.split()[-1]).lower()
    return [t for t in meta if term in t.title.lower()]


def load_yield_table_curves(
    table_id: int,
    yield_class: Optional[float] = None,
) -> tuple:
    """Load height-over-age and DBH-over-age curves from a yield table."""
    from openyieldtables.yieldtables import get_yield_table

    table = get_yield_table(table_id)
    result = {}

    for yc in table.data.yield_classes:
        if yield_class is not None and float(yc.yield_class) != float(yield_class):
            continue
        ages, heights, dbhs = [], [], []
        for row in yc.rows:
            if row.dominant_height is not None:
                ages.append(row.age)
                heights.append(row.dominant_height)
                dbhs.append(row.dbh / 100.0 if row.dbh else 0.0)

        result[f"YC {yc.yield_class}"] = {
            "ages": ages,
            "heights": heights,
            "dbhs": dbhs,
            "yield_class": yc.yield_class,
        }

    return result, table.title


def load_grove_curves(species_name: str, growth_models_dir: Path) -> Optional[dict]:
    """Load Grove's simulated growth curves from growth model files."""
    species_dir = species_name.lower().replace(" ", "_")
    height_curve_path = growth_models_dir / species_dir / "height_curve.json"

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
    values: List[float],
    max_cycles: int,
    flushes_per_year: float = 1.0,
    initial_value: float = 0.5,
) -> tuple:
    """Interpolate yield table to per-cycle resolution using PCHIP.

    When flushes_per_year != 1.0, cycle numbers are converted to calendar
    years before looking up the yield table. For example, with
    flushes_per_year=0.5, cycle 25 maps to age 50 in the yield table.

    Args:
        initial_value: Value at age 0. Use 0.5 for heights (sapling),
            0.0 for DBH (no trunk diameter at birth).
    """
    from scipy.interpolate import PchipInterpolator

    extended_ages = [0] + list(ages)
    extended_values = [initial_value] + list(values)

    interp = PchipInterpolator(extended_ages, extended_values)
    # Convert cycle indices to calendar years for yield table lookup
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
    grow_lengths = np.clip(grow_lengths, base_grow_length * 0.5, max_gl)
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

    scale_factors = np.clip(target_increments / grove_increments, 0.05, 20.0)

    if len(scale_factors) > 5:
        scale_factors = uniform_filter1d(scale_factors, size=5)

    thicken_tips_values = base_thicken_tips * scale_factors
    floor = 0.0005
    thicken_tips_values = np.clip(thicken_tips_values, floor, 0.05)
    thicken_tips_values = np.insert(thicken_tips_values, 0, thicken_tips_values[0])

    return thicken_tips_values.tolist()


def compute_dbh_static_overrides(
    grove_dbhs: List[float],
    target_dbhs: np.ndarray,
    base_grow_nodes: int = 3,
    base_thicken_deadwood: float = 0.0,
) -> Dict[str, float]:
    """Compute static overrides to reduce DBH toward yield table targets.

    Uses levers that affect DBH at breast height (1.3m):
    - grow_nodes: fewer nodes = less cumulative radial thickening
    - thicken_deadwood: set to 0 to eliminate dead branch thickening

    Note: thicken_base_scale, thicken_base_buttress, and thicken_base_shape
    have zero effect on DBH at 1.3m (they only affect the trunk base below
    breast height). They are intentionally excluded.
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
        node_factor = max(0.5, dbh_ratio ** 0.5)
        new_nodes = max(2, round(base_grow_nodes * node_factor))
        if new_nodes < base_grow_nodes:
            overrides["grow_nodes"] = new_nodes

    # Always disable dead branch thickening for DBH reduction
    if base_thicken_deadwood > 0:
        overrides["thicken_deadwood"] = 0.0

    return overrides


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

    # Height comparison
    ax1 = axes[0]
    grove_heights = grove_data["height_curve"]
    grove_cycles = list(range(1, len(grove_heights) + 1))
    ax1.plot(grove_cycles, grove_heights, "b-", linewidth=2.5, label="Grove (cycles)")

    if calibrated_heights is not None:
        cal_cycles = list(range(1, len(calibrated_heights) + 1))
        ax1.plot(
            cal_cycles, calibrated_heights, "g--", linewidth=2, label="Calibrated target"
        )

    non_selected = []
    for yc_name, yc_data in yield_curves.items():
        is_selected = selected_yc and yc_name == selected_yc
        if not is_selected:
            non_selected.append(yc_name)
        ax1.plot(
            yc_data["ages"],
            yc_data["heights"],
            "r-",
            alpha=1.0 if is_selected else 0.3,
            linewidth=2.0 if is_selected else 0.8,
            label=f"Yield {yc_name}" if is_selected else None,
        )

    if non_selected:
        ax1.plot([], [], "r-", alpha=0.3, linewidth=0.8, label="Other yield classes")

    ax1.set_xlabel("Age (years) / Grove cycles")
    ax1.set_ylabel("Height (m)")
    ax1.set_title("Height over Age")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # DBH comparison
    ax2 = axes[1]
    grove_dbhs = grove_data.get("dbh_curve", [])
    if grove_dbhs:
        dbh_cycles = list(range(1, len(grove_dbhs) + 1))
        ax2.plot(
            dbh_cycles,
            [d * 100 for d in grove_dbhs],
            "b-",
            linewidth=2.5,
            label="Grove (cycles)",
        )

    for yc_name, yc_data in yield_curves.items():
        is_selected = selected_yc and yc_name == selected_yc
        ax2.plot(
            yc_data["ages"],
            [d * 100 for d in yc_data["dbhs"]],
            "r-",
            alpha=1.0 if is_selected else 0.3,
            linewidth=2.0 if is_selected else 0.8,
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

    ax1 = axes[0]
    ax1.plot(cycles, grove_heights[:n], "b-", linewidth=2, label="Grove (uncalibrated)")
    ax1.plot(cycles, target_heights[:n], "r--", linewidth=2, label="Yield table target")
    ax1.set_xlabel("Cycle / Year")
    ax1.set_ylabel("Height (m)")
    ax1.set_title("Height Trajectory")
    ax1.legend()
    ax1.grid(True, alpha=0.3)

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

    if has_dbh and grove_dbhs is not None and target_dbhs is not None:
        assert thicken_tips_values is not None  # guaranteed by has_dbh
        n_dbh = min(len(grove_dbhs), len(target_dbhs))
        dbh_cycles = list(range(1, n_dbh + 1))

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


def write_calibration_to_seed_json(
    species_name: str,
    grow_lengths: List[float],
    yield_table_id: int,
    yield_class: float,
    table_title: str,
    presets_dir: Path,
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
    if target_dbh_per_cycle:
        calibration["target_dbh_per_cycle"] = [
            round(v, 6) for v in target_dbh_per_cycle
        ]
    if flushes_per_year != 1.0:
        calibration["flushes_per_year"] = flushes_per_year
    preset["_yield_table_calibration"] = calibration

    with open(preset_path, "w") as f:
        json.dump(preset, f, indent=4)

    logger.info("Calibration written to %s", preset_path)
    return preset_path


def run_calibration(
    species_name: str,
    table_id: int,
    yield_class: float,
    growth_models_dir: Path,
    presets_dir: Path,
    output_dir: Path,
    calibrate: bool = True,
    plot: bool = True,
    flushes_per_year: float = 1.0,
) -> Optional[List[float]]:
    """Run comparison and optional calibration for a single species.

    Returns grow_length curve if calibrate=True, else None.
    """
    grove_data = load_grove_curves(species_name, growth_models_dir)
    if grove_data is None:
        logger.warning(
            "No growth model for %s — skipping (run create_growth_models.py first)",
            species_name,
        )
        return None

    yield_curves, table_title = load_yield_table_curves(table_id, yield_class)
    if not yield_curves:
        logger.error("No data for table %d, yield class %s", table_id, yield_class)
        return None

    selected_yc = f"YC {int(yield_class)}"
    if selected_yc not in yield_curves:
        if len(yield_curves) == 1:
            selected_yc = list(yield_curves.keys())[0]
        else:
            logger.error(
                "Yield class %s not found in table %d. Available: %s",
                yield_class, table_id, list(yield_curves.keys()),
            )
            return None

    grove_heights = grove_data["height_curve"]
    yc_data = yield_curves[selected_yc]

    fpy_info = f", flushes/yr={flushes_per_year}" if flushes_per_year != 1.0 else ""
    logger.info(
        "%s: %d cycles, height %.1fm -> %.1fm | Yield table: %s%s",
        species_name, len(grove_heights),
        grove_heights[0], grove_heights[-1], table_title, fpy_info,
    )

    species_clean = species_name.lower().replace(" ", "_")
    calibrated_heights = None
    grow_lengths = None

    if calibrate:
        max_cycles = len(grove_heights)

        yearly_ages, yearly_heights = interpolate_yield_table(
            yc_data["ages"], yc_data["heights"], max_cycles, flushes_per_year
        )
        calibrated_heights = yearly_heights

        preset_path = presets_dir / f"{species_clean}.seed.json"
        with open(preset_path) as f:
            preset = json.load(f)
        base_grow_length = preset.get("grow_length", 0.3)

        grow_lengths = compute_grow_length_curve(
            grove_heights, yearly_heights, base_grow_length
        )

        logger.info(
            "  grow_length: base=%.3f, range=%.4f-%.4f, avg=%.4f",
            base_grow_length, min(grow_lengths), max(grow_lengths), np.mean(grow_lengths),
        )

        # DBH calibration
        grove_dbhs = grove_data.get("dbh_curve", [])
        thicken_tips_values = None
        base_thicken_tips = None
        target_dbhs_interp = None

        if grove_dbhs and yc_data["dbhs"]:
            _, target_dbhs_interp = interpolate_yield_table(
                yc_data["ages"], yc_data["dbhs"], max_cycles, flushes_per_year,
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
        dbh_static_overrides = {}
        if grove_dbhs and target_dbhs_interp is not None:
            base_nodes = preset.get("grow_nodes", 3)
            base_deadwood = preset.get("thicken_deadwood", 0.0)
            dbh_static_overrides = compute_dbh_static_overrides(
                grove_dbhs,
                target_dbhs_interp,
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

        # Plot calibration detail
        if plot:
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

        # Build target DBH per cycle for radial scaling at export time
        write_target_dbh = None
        if target_dbhs_interp is not None and len(target_dbhs_interp) > 0:
            write_target_dbh = list(target_dbhs_interp[:len(grove_heights)])

        write_calibration_to_seed_json(
            species_name,
            write_grow_lengths or [base_grow_length] * len(grove_heights),
            table_id,
            yield_curves[selected_yc]["yield_class"],
            table_title,
            presets_dir,
            thicken_tips_per_cycle=thicken_tips_values,
            static_overrides=write_static,
            target_dbh_per_cycle=write_target_dbh,
            flushes_per_year=flushes_per_year,
        )

    # Comparison plot
    if plot:
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
    """Main function for command line usage."""
    from growpy.config import get_config
    from growpy.utils.log import setup_logging

    config = get_config()
    script_dir = Path(__file__).parent.parent.parent.parent

    parser = argparse.ArgumentParser(
        description=(
            "Calibrate growth models against yield tables from openyieldtables.org. "
            "Runs after create_growth_models.py. Species yield table mappings are "
            "configured in growpy.toml [calibration.species]."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Calibrate all configured species
    python src/growpy/cli/calibrate_growth.py

    # Compare only (no calibration, just plots)
    python src/growpy/cli/calibrate_growth.py --compare-only

    # Override for a single species
    python src/growpy/cli/calibrate_growth.py --species "Norway spruce" --table-id 2 --yield-class 12

    # List available yield tables
    python src/growpy/cli/calibrate_growth.py --species "Norway spruce" --list-tables

Note: Requires growth models from create_growth_models.py.
      Yield table config is in growpy.toml [calibration.species].
        """,
    )

    parser.add_argument(
        "--species",
        type=str,
        default=None,
        help="Single species to calibrate (default: all configured in toml)",
    )
    parser.add_argument(
        "--table-id",
        type=int,
        default=None,
        help="Yield table ID (overrides toml config for --species)",
    )
    parser.add_argument(
        "--yield-class",
        type=float,
        default=None,
        help="Yield class (overrides toml config for --species)",
    )
    parser.add_argument(
        "--compare-only",
        action="store_true",
        help="Generate comparison plots without writing calibration to seed.json",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="Skip plot generation",
    )
    parser.add_argument(
        "--output-dir",
        dest="output_dir_cal",
        type=Path,
        default=None,
        help="Output directory for plots (default: from config)",
    )
    parser.add_argument(
        "--list-tables",
        action="store_true",
        help="List available yield tables for --species and exit",
    )
    parser.add_argument(
        "--flushes-per-year",
        type=float,
        default=None,
        help=(
            "Growth flushes per calendar year (default: from config, fallback 1.0). "
            "Controls cycle-to-age mapping: 0.5 means 1 cycle = 2 years."
        ),
    )

    args = parser.parse_args()
    config.resolve(args)
    setup_logging(verbose=config.verbose)

    # Resolve paths
    growth_models_dir = script_dir / "data" / "assets" / "growth_models"
    presets_dir = script_dir / "data" / "assets" / "presets"
    output_dir = config.calibration_output_dir
    if not output_dir.is_absolute():
        output_dir = script_dir / output_dir

    do_calibrate = not args.compare_only
    do_plot = config.calibration_plot and not args.no_plot

    # List tables mode
    if args.list_tables:
        species = args.species or "Norway spruce"
        # Use search term from toml config if available
        search = config.calibration_species.get(species, {}).get("search")
        matches = find_yield_tables_for_species(species, search_term=search)
        term_info = f" (search: '{search}')" if search else ""
        print(f"\nYield tables matching '{species}'{term_info}:")
        for m in matches:
            countries = ", ".join(m.country_codes) if m.country_codes else "?"
            print(
                f"  ID {m.id:3d}: {m.title} ({countries})"
                f" - YC step: {m.yield_class_step}"
            )
        return 0

    if not growth_models_dir.exists():
        logger.error("Growth models not found at %s", growth_models_dir)
        logger.error("Run create_growth_models.py first.")
        return 1

    # Build species list to process
    species_configs = {}

    if args.species:
        # Single species from CLI
        if args.table_id is None or args.yield_class is None:
            # Try to get from toml config
            toml_cfg = config.calibration_species.get(args.species, {})
            table_id = args.table_id or toml_cfg.get("table_id")
            yield_class = args.yield_class or toml_cfg.get("yield_class")
            if table_id is None or yield_class is None:
                logger.error(
                    "No yield table configured for '%s'. "
                    "Provide --table-id and --yield-class, or add to "
                    "[calibration.species] in growpy.toml.",
                    args.species,
                )
                return 1
        else:
            table_id = args.table_id
            yield_class = args.yield_class
        toml_fpy = config.calibration_species.get(args.species, {}).get(
            "flushes_per_year", 1.0
        )
        species_configs[args.species] = {
            "table_id": table_id,
            "yield_class": yield_class,
            "flushes_per_year": args.flushes_per_year or toml_fpy,
        }
    else:
        # All species from toml config
        species_configs = config.calibration_species
        if not species_configs:
            logger.error(
                "No species configured in [calibration.species]. "
                "Add entries to growpy.toml or use --species with --table-id/--yield-class."
            )
            return 1

    # Process each species
    n_ok = 0
    n_total = len(species_configs)

    for species_name, cfg in species_configs.items():
        table_id = cfg.get("table_id")
        yield_class = cfg.get("yield_class")

        if table_id is None or yield_class is None:
            logger.warning(
                "Skipping %s: missing table_id or yield_class in config",
                species_name,
            )
            continue

        logger.info("")
        logger.info("=" * 60)
        logger.info("  %s (table %d, YC %s)", species_name, table_id, yield_class)
        logger.info("=" * 60)

        fpy = float(cfg.get("flushes_per_year", 1.0))

        result = run_calibration(
            species_name=species_name,
            table_id=table_id,
            yield_class=yield_class,
            growth_models_dir=growth_models_dir,
            presets_dir=presets_dir,
            output_dir=output_dir,
            calibrate=do_calibrate,
            plot=do_plot,
            flushes_per_year=fpy,
        )

        if result is not None or not do_calibrate:
            n_ok += 1

    action = "calibrated" if do_calibrate else "compared"
    logger.info("")
    logger.info("Done: %d/%d species %s", n_ok, n_total, action)

    return 0


if __name__ == "__main__":
    sys.exit(main())
