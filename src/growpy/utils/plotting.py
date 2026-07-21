"""Growth curve plotting utilities for species analysis and calibration."""

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
import numpy as np


def _init_plot_style():
    """Initialize matplotlib style for all plots."""
    mplstyle.use("default")
    style = "seaborn-v0_8" if "seaborn-v0_8" in plt.style.available else "default"
    plt.style.use(style)


def _display_name(species_std: str) -> str:
    """Convert snake_case species name to Title Case display name."""
    return species_std.replace("_", " ").title()


def _add_flush_axis(ax, fpy: float) -> None:
    """Add flush labels on the same x-axis as age, showing both years and flushes."""
    # Get current tick locations
    ticks = ax.get_xticks()

    # Calculate flush values for each tick
    flushes = ticks * fpy

    # Format tick labels to show both age (years) and flushes
    tick_labels = []
    for age, flush in zip(ticks, flushes):
        # Show flush count in parentheses after age
        flush_str = f"{flush:.1f}"
        tick_labels.append(f"{age:.0f}({flush_str})")

    # Set ticks explicitly to avoid warning
    ax.set_xticks(ticks)
    ax.set_xticklabels(tick_labels)

    # Update x-axis label to indicate both metrics
    ax.set_xlabel("Age (years) [Flushes]", fontsize=12)


def _extract_common(metadata: dict[str, Any], height_curve, dbh_curve):
    """Extract common data used across multiple plot functions."""
    fpy = metadata.get("flushes_per_year", 1.0)
    ages = np.array([(i + 1) / fpy for i in range(len(height_curve))])
    heights = np.array(height_curve)
    dbh_cm = np.array(dbh_curve) * 100
    return fpy, ages, heights, dbh_cm


def plot_growth_curves(
    species: str,
    height_curve: list[float],
    dbh_curve: list[float],
    metadata: dict[str, Any],
    output_dir: Path,
) -> None:
    """Create and save growth curve plots plus additional diagnostic plots.

    Generates:
    - growth_curves.png: Height and DBH over age with model fit overlay
    - height_dbh_correlation.png: Allometric H-DBH relationship
    - growth_increments.png: CAI/MAI and stem volume estimates
    """
    _init_plot_style()

    fpy, ages, heights, dbh_cm = _extract_common(metadata, height_curve, dbh_curve)

    # Load model params if available (for Chapman-Richards overlay)
    model_params = _load_model_params(output_dir)

    _plot_growth_curves_main(
        species, ages, heights, dbh_cm, fpy, metadata, model_params, output_dir
    )
    _plot_height_dbh_correlation(
        species, ages, heights, dbh_cm, fpy, metadata, output_dir
    )
    _plot_growth_increments(species, ages, heights, dbh_cm, fpy, metadata, output_dir)


def _load_model_params(output_dir: Path) -> dict[str, float] | None:
    """Try to load Chapman-Richards model params from the species output dir."""
    import json

    params_path = output_dir / "growth_model_params.json"
    if not params_path.exists():
        return None
    with open(params_path) as f:
        params = json.load(f)
    if params.get("model_type") != "chapman_richards":
        return None
    return params


def _plot_growth_curves_main(
    species,
    ages,
    heights,
    dbh_cm,
    fpy,
    metadata,
    model_params,
    output_dir,
):
    """Main growth curves: height and DBH over age with model fit."""
    display = _display_name(species)
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    fig.suptitle(f"Growth Curves for {display}", fontsize=16, fontweight="bold")

    # -- Height subplot --
    ax1.plot(
        ages,
        heights,
        "b-",
        linewidth=2.5,
        marker="o",
        markersize=3,
        alpha=0.9,
        label="Simulation",
        zorder=10,
    )

    # Chapman-Richards model fit overlay
    if model_params:
        A, k, p = model_params["A"], model_params["k"], model_params["p"]
        r2 = model_params.get("r_squared", 0)
        t_smooth = np.linspace(0, ages[-1] * fpy, 200)
        h_fit = A * (1.0 - np.exp(-k * t_smooth)) ** p
        ages_fit = t_smooth / fpy
        ax1.plot(
            ages_fit,
            h_fit,
            "r--",
            linewidth=1.5,
            alpha=0.8,
            label=f"Chapman-Richards (R\u00b2={r2:.3f})",
        )

    ax1.set_xlabel("Age (years)", fontsize=12)
    ax1.set_ylabel("Height (m)", fontsize=12)
    ax1.set_title("Height Growth Over Time", fontsize=14, fontweight="bold")
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, ages[-1] if len(ages) else 1)
    ax1.legend(loc="lower right", fontsize=9)
    _add_flush_axis(ax1, fpy)

    growth_rate_yr = metadata["growth_rate"] * fpy
    height_text = (
        f"Max Height: {metadata['max_height']:.2f} m\n"
        f"Final Height: {metadata['final_height']:.2f} m\n"
        f"Growth Rate: {growth_rate_yr:.3f} m/year"
    )
    ax1.text(
        0.02,
        0.98,
        height_text,
        transform=ax1.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
    )

    # -- DBH subplot --
    ax2.plot(
        ages,
        dbh_cm,
        "g-",
        linewidth=2.5,
        marker="o",
        markersize=3,
        alpha=0.9,
        label="Simulation",
        zorder=10,
    )

    ax2.set_xlabel("Age (years)", fontsize=12)
    ax2.set_ylabel("DBH (cm)", fontsize=12)
    ax2.set_title("DBH Growth Over Time", fontsize=14, fontweight="bold")
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, ages[-1] if len(ages) else 1)
    ax2.legend(loc="lower right", fontsize=9)
    _add_flush_axis(ax2, fpy)

    dbh_rate_yr = metadata["dbh_growth_rate"] * 100 * fpy
    dbh_text = (
        f"Max DBH: {metadata['max_dbh'] * 100:.1f} cm\n"
        f"Final DBH: {metadata['final_dbh'] * 100:.1f} cm\n"
        f"DBH Growth Rate: {dbh_rate_yr:.2f} cm/year"
    )
    ax2.text(
        0.02,
        0.98,
        dbh_text,
        transform=ax2.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.8),
    )

    # Footer
    max_age = metadata["actual_max_cycles"] / fpy
    footer = (
        f"{metadata['actual_max_cycles']} cycles over {max_age:.0f} years "
        f"| Simulation time: {metadata['avg_simulation_time']:.1f}s "
        f"| fpy: {fpy:.2f}"
    )
    if metadata["early_terminations"] > 0:
        footer += f" | Early terminations: {metadata['early_terminations']}"
    if metadata["timeouts"] > 0:
        footer += f" | Timeouts: {metadata['timeouts']}"
    fig.text(0.5, 0.02, footer, ha="center", fontsize=9, style="italic")

    plt.tight_layout()
    plt.subplots_adjust(top=0.93, bottom=0.08)
    plt.savefig(
        output_dir / "growth_curves.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close()


def _plot_height_dbh_correlation(
    species,
    ages,
    heights,
    dbh_cm,
    fpy,
    metadata,
    output_dir,
):
    """Height vs DBH with allometric power-law fit.

    Shows GrowPy simulation scatter with a fit from simulation data.
    When yield table allometry data is available (yield_table_allometry.json),
    overlays the yield-table-derived power model and raw data points.
    """
    display = _display_name(species)
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))

    # Simulation scatter
    scatter = ax.scatter(
        heights,
        dbh_cm,
        c=ages,
        cmap="viridis",
        s=40,
        alpha=0.9,
        marker="o",
        label="Simulation",
        edgecolors="black",
        linewidth=0.3,
    )

    ax.set_xlabel("Height (m)", fontsize=12)
    ax.set_ylabel("DBH (cm)", fontsize=12)
    ax.set_title(
        f"Height vs DBH Relationship for {display}",
        fontsize=14,
        fontweight="bold",
    )
    ax.grid(True, alpha=0.3)

    cbar = plt.colorbar(scatter)
    cbar.set_label("Age (years)", fontsize=12)

    # Allometric power-law fit: DBH = a * H^b (log-linear regression)
    stats_lines = []
    if len(heights) > 3:
        mask = (heights > 0.1) & (dbh_cm > 0.1)
        h_pos = heights[mask]
        d_pos = dbh_cm[mask]

        if len(h_pos) > 3:
            log_h = np.log(h_pos)
            log_d = np.log(d_pos)
            b, log_a = np.polyfit(log_h, log_d, 1)
            a = np.exp(log_a)

            h_smooth = np.linspace(h_pos.min(), h_pos.max(), 200)
            d_fit = a * h_smooth**b

            # R² for allometric fit
            d_pred = a * h_pos**b
            ss_res = np.sum((d_pos - d_pred) ** 2)
            ss_tot = np.sum((d_pos - d_pos.mean()) ** 2)
            r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0

            ax.plot(
                h_smooth,
                d_fit,
                "r--",
                alpha=0.8,
                linewidth=2,
                label=f"GrowPy: DBH = {a:.2f} * H^{b:.2f}",
            )
            stats_lines.append(f"GrowPy: DBH = {a:.2f} * H^{b:.2f} (R²={r2:.3f})")

    # Yield table allometric overlay
    yt_allom_path = output_dir / "yield_table_allometry.json"
    if yt_allom_path.exists():
        import json as _json

        with open(yt_allom_path) as _f:
            yt_allom = _json.load(_f)

        yt_model = yt_allom.get("model")
        yt_heights_m = yt_allom.get("heights", [])
        yt_dbhs_m = yt_allom.get("dbhs", [])
        table_title = yt_allom.get("table_title", "Yield table")

        # Plot raw yield table data points (DBH in cm)
        if yt_heights_m and yt_dbhs_m:
            yt_h = np.array(yt_heights_m, dtype=float)
            yt_d = np.array(yt_dbhs_m, dtype=float) * 100  # m -> cm
            valid = (yt_h > 0) & (yt_d > 0)
            if valid.any():
                ax.scatter(
                    yt_h[valid],
                    yt_d[valid],
                    marker="D",
                    s=60,
                    facecolors="none",
                    edgecolors="green",
                    linewidth=1.5,
                    zorder=5,
                    label=f"Yield table ({table_title})",
                )

        # Overlay yield-table-derived allometric model
        if yt_model:
            yt_a = yt_model["a"]
            yt_b = yt_model["b"]
            yt_r2 = yt_model.get("r_squared", 0)

            h_range = np.linspace(
                max(0.5, min(heights.min(), min(yt_heights_m) if yt_heights_m else 1)),
                max(heights.max(), max(yt_heights_m) if yt_heights_m else 30),
                200,
            )
            yt_d_fit = yt_a * h_range**yt_b * 100  # m -> cm

            ax.plot(
                h_range,
                yt_d_fit,
                "g-",
                alpha=0.9,
                linewidth=2.5,
                label=f"Yield table: DBH = {yt_a:.4f} * H^{yt_b:.2f}",
            )
            stats_lines.append(
                f"Yield table: DBH = {yt_a:.4f} * H^{yt_b:.2f} (R²={yt_r2:.3f})"
            )

    if stats_lines:
        ax.text(
            0.02,
            0.98,
            "\n".join(stats_lines),
            transform=ax.transAxes,
            fontsize=11,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

    ax.legend(loc="lower right", fontsize=9)
    plt.tight_layout()
    plt.savefig(
        output_dir / "height_dbh_correlation.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close()


def _plot_growth_increments(
    species,
    ages,
    heights,
    dbh_cm,
    fpy,
    metadata,
    output_dir,
):
    """Stem volume and annual growth rates for height and DBH.

    Volume estimated using standard form factor: V = f * pi/4 * DBH^2 * H.
    Growth rates are simple year-over-year differences.
    """
    if len(ages) < 3:
        return

    display = _display_name(species)
    fig, (ax_v, ax_r) = plt.subplots(1, 2, figsize=(14, 6))
    fig.suptitle(
        f"Growth Summary for {display}",
        fontsize=16,
        fontweight="bold",
    )

    cai_ages = ages[1:]

    # -- Stem volume --
    form_factor = 0.45
    dbh_m = dbh_cm / 100.0
    volume = form_factor * (np.pi / 4) * dbh_m**2 * heights

    ax_v.plot(ages, volume, color="purple", linewidth=2.5)
    ax_v.fill_between(ages, 0, volume, alpha=0.1, color="purple")

    ax_v.set_xlabel("Age (years)", fontsize=11)
    ax_v.set_ylabel("Stem volume (m\u00b3)", fontsize=11)
    ax_v.set_title(
        f"Estimated Stem Volume (f={form_factor})",
        fontsize=13,
        fontweight="bold",
    )
    ax_v.grid(True, alpha=0.3)
    ax_v.set_xlim(0, ages[-1])
    _add_flush_axis(ax_v, fpy)

    vol_text = f"{volume[-1]:.2f} m\u00b3"
    ax_v.text(
        0.02,
        0.98,
        vol_text,
        transform=ax_v.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="plum", alpha=0.6),
    )

    # -- Annual growth rates --
    h_rate = np.diff(heights) * fpy  # m/year
    d_rate = np.diff(dbh_cm) * fpy  # cm/year

    ax_r.plot(cai_ages, h_rate, "b-", linewidth=2, label="Height (m/year)")
    ax_r.set_xlabel("Age (years)", fontsize=11)
    ax_r.set_ylabel("Height growth (m/year)", fontsize=11, color="blue")
    ax_r.tick_params(axis="y", labelcolor="blue")
    ax_r.grid(True, alpha=0.3)
    ax_r.set_xlim(0, ages[-1])

    ax_d = ax_r.twinx()
    ax_d.plot(cai_ages, d_rate, "g-", linewidth=2, label="DBH (cm/year)")
    ax_d.set_ylabel("DBH growth (cm/year)", fontsize=11, color="green")
    ax_d.tick_params(axis="y", labelcolor="green")

    lines_r, labels_r = ax_r.get_legend_handles_labels()
    lines_d, labels_d = ax_d.get_legend_handles_labels()
    ax_r.legend(lines_r + lines_d, labels_r + labels_d, loc="upper right", fontsize=9)

    ax_r.set_title("Annual Growth Rates", fontsize=13, fontweight="bold")
    _add_flush_axis(ax_r, fpy)

    plt.tight_layout()
    plt.subplots_adjust(top=0.90)
    plt.savefig(
        output_dir / "growth_increments.png",
        dpi=300,
        bbox_inches="tight",
        facecolor="white",
    )
    plt.close()


def plot_calibration_comparison(
    species_name: str,
    uncalibrated_heights: list[float],
    uncalibrated_dbhs: list[float],
    yield_ages: list[float],
    yield_heights: list[float],
    yield_dbhs: list[float],
    table_title: str,
    flushes_per_year: float = 1.0,
    calibrated_heights: list[float] | None = None,
    calibrated_dbhs: list[float] | None = None,
    target_dbh_per_cycle: list[float] | None = None,
    output_path: Path | None = None,
) -> None:
    """Plot Grove curves vs yield table with a consistent year-based x-axis.

    Shows up to three curves per metric:
    - Yield table (forestry reference data)
    - Grove simulation before calibration
    - Grove simulation after calibration (re-simulated with overrides)

    The DBH chart additionally shows the target DBH that will be applied
    at export time via radial mesh scaling (from yield table interpolation).

    All Grove data is converted from cycle indices to calendar years using
    flushes_per_year, so every line shares the same time axis.
    """
    _init_plot_style()

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(
        f"{species_name}: Grove vs Yield Table ({table_title})",
        fontsize=14,
        fontweight="bold",
    )

    # Convert cycle indices to calendar years
    uncal_years = [(i + 1) / flushes_per_year for i in range(len(uncalibrated_heights))]

    # Height comparison
    ax1 = axes[0]

    ax1.plot(
        yield_ages,
        yield_heights,
        "r-",
        linewidth=2.0,
        label="Yield table (reference)",
    )

    ax1.plot(
        uncal_years,
        uncalibrated_heights,
        "b-",
        linewidth=2.0,
        alpha=0.6,
        label="Grove (before calibration)",
    )

    if calibrated_heights is not None:
        cal_years = [(i + 1) / flushes_per_year for i in range(len(calibrated_heights))]
        ax1.plot(
            cal_years,
            calibrated_heights,
            "g-",
            linewidth=2.5,
            label="Grove (after calibration)",
        )

    # Show the full extent of all series. The yield table reference often
    # covers a longer age range than the current Grove simulation, and
    # keeping that visible is what makes long-term divergence between
    # calibrated/uncalibrated and the reference legible.
    max_year = max(
        yield_ages[-1] if yield_ages else 0,
        uncal_years[-1] if uncal_years else 0,
        cal_years[-1] if calibrated_heights is not None else 0,
    )
    if max_year > 0:
        ax1.set_xlim(0, max_year * 1.05)

    ax1.set_xlabel("Age (years)")
    ax1.set_ylabel("Height (m)")
    ax1.set_title("Height over Age")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # DBH comparison
    ax2 = axes[1]

    ax2.plot(
        yield_ages,
        [d * 100 for d in yield_dbhs],
        "r-",
        linewidth=2.0,
        label="Yield table (reference)",
    )

    if uncalibrated_dbhs:
        uncal_dbh_years = uncal_years[: len(uncalibrated_dbhs)]
        ax2.plot(
            uncal_dbh_years,
            [d * 100 for d in uncalibrated_dbhs],
            "b-",
            linewidth=2.0,
            alpha=0.6,
            label="Grove (before calibration)",
        )

    if calibrated_dbhs is not None:
        cal_dbh_years = [
            (i + 1) / flushes_per_year for i in range(len(calibrated_dbhs))
        ]
        ax2.plot(
            cal_dbh_years,
            [d * 100 for d in calibrated_dbhs],
            "g-",
            linewidth=2.5,
            label="Grove (after calibration)",
        )

    if target_dbh_per_cycle is not None:
        target_dbh_years = [
            (i + 1) / flushes_per_year for i in range(len(target_dbh_per_cycle))
        ]
        ax2.plot(
            target_dbh_years,
            [d * 100 for d in target_dbh_per_cycle],
            "g--",
            linewidth=2.0,
            alpha=0.8,
            label="Export DBH (radial scaling)",
        )

    # Match x-axis range to the height plot (see comment above)
    max_year = max(
        yield_ages[-1] if yield_ages else 0,
        uncal_years[-1] if uncal_years else 0,
        (len(calibrated_dbhs) / flushes_per_year if calibrated_dbhs is not None else 0),
        (
            len(target_dbh_per_cycle) / flushes_per_year
            if target_dbh_per_cycle is not None
            else 0
        ),
    )
    if max_year > 0:
        ax2.set_xlim(0, max_year * 1.05)

    ax2.set_xlabel("Age (years)")
    ax2.set_ylabel("DBH (cm)")
    ax2.set_title("Diameter at Breast Height over Age")
    ax2.legend(loc="upper left")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
    else:
        plt.show()
    plt.close()


def plot_grove_curves_only(
    species_name: str,
    grove_heights: list[float],
    grove_dbhs: list[float],
    flushes_per_year: float = 1.0,
    output_path: Path | None = None,
) -> None:
    """Plot Grove-only growth curves for species without yield table data.

    Shows height and DBH over time from the uncalibrated Grove simulation,
    without any yield table reference overlay.
    """
    _init_plot_style()

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(
        f"{species_name}: Grove Growth Curves (uncalibrated)",
        fontsize=14,
        fontweight="bold",
    )

    years = [(i + 1) / flushes_per_year for i in range(len(grove_heights))]

    # Height
    ax1 = axes[0]
    ax1.plot(
        years,
        grove_heights,
        "b-",
        linewidth=2.0,
        label="Grove simulation",
    )
    ax1.set_xlabel("Age (years)")
    ax1.set_ylabel("Height (m)")
    ax1.set_title("Height over Age")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # DBH
    ax2 = axes[1]
    if grove_dbhs:
        dbh_years = years[: len(grove_dbhs)]
        ax2.plot(
            dbh_years,
            [d * 100 for d in grove_dbhs],
            "b-",
            linewidth=2.0,
            label="Grove simulation",
        )
    ax2.set_xlabel("Age (years)")
    ax2.set_ylabel("DBH (cm)")
    ax2.set_title("Diameter at Breast Height over Age")
    ax2.legend(loc="upper left")
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
    else:
        plt.show()
    plt.close()
