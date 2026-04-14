"""Generate growth model report across all processed species.

Produces growth_model_report.md in the growth_models directory, wrapping
existing per-species plots with explanatory text and a cross-species
comparison summary.
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

logger = logging.getLogger(__name__)


def _read_species_data(species_dir: Path) -> Optional[Dict[str, Any]]:
    """Read metadata and growth model params for one species."""
    meta_path = species_dir / "metadata.json"
    params_path = species_dir / "growth_model_params.json"
    if not meta_path.exists():
        return None

    with open(meta_path, encoding="utf-8") as f:
        meta = json.load(f)

    params = {}
    if params_path.exists():
        with open(params_path, encoding="utf-8") as f:
            params = json.load(f)

    return {"metadata": meta, "params": params, "dir": species_dir}


def _read_calibration_info(presets_dir: Path, species: str) -> Optional[Dict[str, Any]]:
    """Read calibration info from seed.json preset if present."""
    preset_path = presets_dir / f"{species}.seed.json"
    if not preset_path.exists():
        return None

    with open(preset_path, encoding="utf-8") as f:
        preset = json.load(f)

    return preset.get("_yield_table_calibration")


def _display_name(species_std: str) -> str:
    return species_std.replace("_", " ").title()


def _fmt(value, decimals=2) -> str:
    if value is None:
        return "-"
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def _plot_cross_species_height(
    all_data: Dict[str, Dict[str, Any]], output_path: Path
) -> None:
    """Plot all species height curves on a single figure for comparison."""
    fig, ax = plt.subplots(figsize=(10, 6))

    for species, data in sorted(all_data.items()):
        meta = data["metadata"]
        heights = meta.get("height_curve", [])
        fpy = meta.get("flushes_per_year", 1.0)
        ages = [i / fpy for i in range(len(heights))]
        label = _display_name(species)
        ax.plot(ages, heights, linewidth=2, label=label)

    ax.set_xlabel("Age (years)", fontsize=11)
    ax.set_ylabel("Height (m)", fontsize=11)
    ax.set_title("Height Growth Comparison Across Species", fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _plot_cross_species_dbh(
    all_data: Dict[str, Dict[str, Any]], output_path: Path
) -> None:
    """Plot all species DBH curves on a single figure for comparison."""
    fig, ax = plt.subplots(figsize=(10, 6))

    for species, data in sorted(all_data.items()):
        meta = data["metadata"]
        dbh_curve = meta.get("dbh_curve", [])
        dbh_cm = [d * 100 for d in dbh_curve]
        fpy = meta.get("flushes_per_year", 1.0)
        ages = [i / fpy for i in range(len(dbh_cm))]
        label = _display_name(species)
        ax.plot(ages, dbh_cm, linewidth=2, label=label)

    ax.set_xlabel("Age (years)", fontsize=11)
    ax.set_ylabel("DBH (cm)", fontsize=11)
    ax.set_title("DBH Growth Comparison Across Species", fontsize=13)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def _plot_simulation_performance(
    all_data: Dict[str, Dict[str, Any]], output_path: Path
) -> None:
    """Bar chart of simulation time and cycle count per species."""
    species_names = sorted(all_data.keys())
    display_names = [_display_name(s) for s in species_names]
    sim_times = [
        all_data[s]["metadata"].get("avg_simulation_time", 0) for s in species_names
    ]
    cycles = [
        all_data[s]["metadata"].get("actual_max_cycles", 0) for s in species_names
    ]

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))

    colors = plt.cm.Set2(np.linspace(0, 1, len(species_names)))

    bars1 = ax1.barh(display_names, sim_times, color=colors)
    ax1.set_xlabel("Avg Simulation Time (s)", fontsize=11)
    ax1.set_title("Simulation Time per Species", fontsize=13)
    for bar, val in zip(bars1, sim_times):
        ax1.text(
            bar.get_width() + 5,
            bar.get_y() + bar.get_height() / 2,
            f"{val:.0f}s",
            va="center",
            fontsize=9,
        )

    bars2 = ax2.barh(display_names, cycles, color=colors)
    ax2.set_xlabel("Completed Cycles", fontsize=11)
    ax2.set_title("Simulation Cycles per Species", fontsize=13)
    for bar, val in zip(bars2, cycles):
        ax2.text(
            bar.get_width() + 0.5,
            bar.get_y() + bar.get_height() / 2,
            str(val),
            va="center",
            fontsize=9,
        )

    plt.tight_layout()
    fig.savefig(output_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)


def generate_growth_model_report(
    models_dir: Path,
    presets_dir: Optional[Path] = None,
) -> Path:
    """Generate a comprehensive growth model report as Markdown.

    Scans all species in models_dir, reads metadata and growth model params,
    generates cross-species comparison plots, and writes a Markdown report
    that wraps existing per-species plots with explanatory text.

    Args:
        models_dir: Path to data/assets/growth_models/.
        presets_dir: Path to data/assets/presets/ (for calibration info).

    Returns:
        Path to the generated growth_model_report.md file.
    """
    if presets_dir is None:
        presets_dir = models_dir.parent / "presets"

    all_data: Dict[str, Dict[str, Any]] = {}
    for species_dir in sorted(models_dir.iterdir()):
        if not species_dir.is_dir():
            continue
        data = _read_species_data(species_dir)
        if data:
            all_data[species_dir.name] = data

    if not all_data:
        logger.warning("No growth model data found in %s", models_dir)
        output = models_dir / "growth_model_report.md"
        output.write_text("# Growth Model Report\n\nNo species data found.\n")
        return output

    # Generate cross-species comparison plots
    logger.info("Generating cross-species comparison plots...")
    _plot_cross_species_height(all_data, models_dir / "cross_species_height.png")
    _plot_cross_species_dbh(all_data, models_dir / "cross_species_dbh.png")
    _plot_simulation_performance(all_data, models_dir / "simulation_performance.png")

    # Collect calibration info per species
    calibration: Dict[str, Optional[Dict]] = {}
    for species in all_data:
        calibration[species] = _read_calibration_info(presets_dir, species)

    n_species = len(all_data)
    n_calibrated = sum(1 for v in calibration.values() if v is not None)

    lines: List[str] = []

    # --- Header ---
    lines.append("# Growth Model Report")
    lines.append("")
    lines.append(
        f"Growth model analysis for **{n_species} species** generated by "
        f"the GrowPy pipeline. "
    )
    if n_calibrated > 0:
        lines.append(
            f"Of these, **{n_calibrated}** were calibrated against forestry yield tables."
        )
    else:
        lines.append("No species were calibrated against yield tables in this run.")
    lines.append("")

    # --- Summary Table ---
    lines.append("## Summary")
    lines.append("")
    lines.append(
        "| Species | Max Height (m) | Final DBH (cm) | Height Rate (m/yr) "
        "| DBH Rate (cm/yr) | Cycles | Sim Time (s) | CR R^2 | Calibrated |"
    )
    lines.append("| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | :---: |")

    for species in sorted(all_data.keys()):
        data = all_data[species]
        meta = data["metadata"]
        params = data["params"]
        fpy = meta.get("flushes_per_year", 1.0)

        max_h = meta.get("max_height")
        final_dbh_cm = meta.get("final_dbh", 0) * 100
        h_rate = meta.get("growth_rate", 0) * fpy
        d_rate = meta.get("dbh_growth_rate", 0) * fpy * 100
        cycles = meta.get("actual_max_cycles", 0)
        sim_time = meta.get("avg_simulation_time", 0)
        r2 = params.get("r_squared")
        cal = "Yes" if calibration.get(species) else "No"

        lines.append(
            f"| {_display_name(species)} "
            f"| {_fmt(max_h)} | {_fmt(final_dbh_cm, 1)} "
            f"| {_fmt(h_rate)} | {_fmt(d_rate, 1)} "
            f"| {cycles} | {_fmt(sim_time, 0)} "
            f"| {_fmt(r2, 3)} | {cal} |"
        )

    lines.append("")

    # --- Cross-Species Comparison ---
    lines.append("## Cross-Species Comparison")
    lines.append("")
    lines.append(
        "The following plots compare height and diameter growth trajectories "
        "across all species on a common age axis. Ages are derived from "
        "simulation cycles divided by the species-specific flushes-per-year "
        "ratio (fpy) determined during calibration."
    )
    lines.append("")
    lines.append("### Height Growth")
    lines.append("")
    lines.append("![Height comparison](cross_species_height.png)")
    lines.append("")
    lines.append("### Diameter Growth")
    lines.append("")
    lines.append("![DBH comparison](cross_species_dbh.png)")
    lines.append("")

    # --- Simulation Performance ---
    lines.append("## Simulation Performance")
    lines.append("")
    lines.append(
        "Simulation time varies significantly between species due to "
        "differences in branching complexity and crown architecture. "
        "Species with denser crowns (e.g. broadleaves) typically require "
        "more computation per cycle."
    )
    lines.append("")
    lines.append("![Simulation performance](simulation_performance.png)")
    lines.append("")

    # --- Per-Species Detail Sections ---
    lines.append("## Species Details")
    lines.append("")

    for species in sorted(all_data.keys()):
        data = all_data[species]
        meta = data["metadata"]
        params = data["params"]
        cal_info = calibration.get(species)
        species_dir_name = species
        fpy = meta.get("flushes_per_year", 1.0)

        display = _display_name(species)
        lines.append(f"### {display}")
        lines.append("")

        # Key metrics
        max_h = meta.get("max_height", 0)
        final_dbh_m = meta.get("final_dbh", 0)
        final_dbh_cm = final_dbh_m * 100
        h_rate_yr = meta.get("growth_rate", 0) * fpy
        d_rate_yr = meta.get("dbh_growth_rate", 0) * fpy * 100
        planned = meta.get("planned_cycles", 0)
        actual = meta.get("actual_max_cycles", 0)
        sim_time = meta.get("avg_simulation_time", 0)
        n_seeds = meta.get("num_seeds", 0)
        early = meta.get("early_terminations", 0)
        timeouts = meta.get("timeouts", 0)

        lines.append(
            f"Simulated for **{actual} cycles** "
            f"(planned: {planned}) with **{n_seeds} seed(s)**, "
            f"averaging **{sim_time:.0f}s** per seed."
        )
        if early > 0 or timeouts > 0:
            lines.append(f" Early terminations: {early}. Timeouts: {timeouts}.")
        lines.append("")

        lines.append(f"- **Maximum height**: {max_h:.2f} m")
        lines.append(f"- **Final DBH**: {final_dbh_cm:.1f} cm")
        lines.append(f"- **Height growth rate**: {h_rate_yr:.2f} m/year")
        lines.append(f"- **DBH growth rate**: {d_rate_yr:.1f} cm/year")
        lines.append(f"- **Flushes per year**: {fpy:.2f}")
        lines.append("")

        # Chapman-Richards model fit
        if params:
            cr_a = params.get("A")
            cr_k = params.get("k")
            cr_p = params.get("p")
            cr_r2 = params.get("r_squared")
            lines.append(
                f"**Chapman-Richards fit**: "
                f"A={_fmt(cr_a, 2)}, k={_fmt(cr_k, 5)}, p={_fmt(cr_p, 3)}, "
                f"R^2={_fmt(cr_r2, 4)}"
            )
            lines.append("")

        # Calibration details
        if cal_info:
            table_title = cal_info.get("table_title", "unknown")
            lines.append(
                f"**Calibration**: Calibrated against yield table *{table_title}*."
            )
            lines.append("")
        else:
            lines.append("**Calibration**: Not calibrated (no matching yield table).")
            lines.append("")

        # Embed existing plots
        lines.append("#### Growth Curves")
        lines.append("")
        lines.append(
            "Height and DBH over simulation age with Chapman-Richards model fit overlay."
        )
        lines.append("")
        lines.append(f"![Growth curves]({species_dir_name}/growth_curves.png)")
        lines.append("")

        lines.append("#### Height-DBH Relationship")
        lines.append("")
        lines.append(
            "Allometric power-law relationship between height and diameter, "
            "colored by tree age. The dashed line shows the fitted model "
            "DBH = a * H^b."
        )
        lines.append("")
        lines.append(
            f"![Height-DBH correlation]({species_dir_name}/height_dbh_correlation.png)"
        )
        lines.append("")

        lines.append("#### Growth Rates and Stem Volume")
        lines.append("")
        lines.append(
            "Left: estimated stem volume accumulation over time (form factor f=0.45). "
            "Right: annual height and DBH growth increments showing the "
            "characteristic peak and gradual decline with age."
        )
        lines.append("")
        lines.append(f"![Growth increments]({species_dir_name}/growth_increments.png)")
        lines.append("")

        # Calibration comparison plot (only if calibrated)
        comparison_png = data["dir"] / "growth_comparison.png"
        if comparison_png.exists():
            if cal_info:
                lines.append("#### Yield Table Calibration")
                lines.append("")
                lines.append(
                    "Comparison of Grove simulation output against forestry yield "
                    "table reference data. The green curve (after calibration) shows "
                    "the effect of per-cycle grow_length overrides on height, and "
                    "radial scaling on DBH at export."
                )
            else:
                lines.append("#### Grove Growth Curves")
                lines.append("")
                lines.append(
                    "Grove simulation output for height and diameter over time."
                )
            lines.append("")
            lines.append(
                f"![Calibration comparison]({species_dir_name}/growth_comparison.png)"
            )
            lines.append("")

        lines.append("---")
        lines.append("")

    # --- Footer ---
    lines.append(
        "Report generated by `create_growth_models.py`. "
        "All plots are saved alongside their species data in "
        "`data/assets/growth_models/`."
    )
    lines.append("")

    output_path = models_dir / "growth_model_report.md"
    output_path.write_text("\n".join(lines), encoding="utf-8")
    logger.info("Growth model report written to %s", output_path)
    return output_path
