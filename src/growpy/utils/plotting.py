"""Growth curve plotting utilities for species analysis and calibration."""

from pathlib import Path
from typing import Dict, Any, List, Optional

import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
import numpy as np


def plot_growth_curves(
    species: str,
    height_curve: List[float],
    dbh_curve: List[float],
    metadata: Dict[str, Any],
    output_dir: Path,
) -> None:
    """Create and save plots of height and DBH growth curves.

    Args:
        species: Species name
        height_curve: List of heights per cycle
        dbh_curve: List of DBH values per cycle
        metadata: Analysis metadata dictionary
        output_dir: Directory to save plots
    """
    # Set up matplotlib style
    mplstyle.use("default")
    plt.style.use(
        "seaborn-v0_8" if "seaborn-v0_8" in plt.style.available else "default"
    )

    # Create figure with subplots
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    fig.suptitle(f"Growth Curves for {species}", fontsize=16, fontweight="bold")

    cycles = list(range(len(height_curve)))

    # Get individual seed curves if available
    individual_height_curves = metadata.get("individual_height_curves", [])
    individual_dbh_curves = metadata.get("individual_dbh_curves", [])
    seeds_tested = metadata.get("seeds_tested", [])

    # Plot individual seed curves (lighter colors, thinner lines)
    colors = [
        "lightblue",
        "lightgreen",
        "lightcoral",
        "lightyellow",
        "lightpink",
        "lightgray",
        "lightsteelblue",
        "lightsalmon",
        "lightseagreen",
    ]

    for i, (height_curve_seed, seed) in enumerate(
        zip(individual_height_curves, seeds_tested)
    ):
        color = colors[i % len(colors)]
        cycles_seed = list(range(len(height_curve_seed)))
        ax1.plot(
            cycles_seed,
            height_curve_seed,
            color=color,
            linewidth=1.0,
            alpha=0.6,
            linestyle="--",
            label=f"Seed {seed}",
        )

    # Plot aggregated height curve (bold line on top)
    ax1.plot(
        cycles,
        height_curve,
        "b-",
        linewidth=3.0,
        marker="o",
        markersize=4,
        alpha=0.9,
        label="Maximum (aggregated)",
        zorder=10,
    )

    ax1.set_xlabel("Growth Cycles", fontsize=12)
    ax1.set_ylabel("Height (units)", fontsize=12)
    ax1.set_title("Height Growth Over Time", fontsize=14, fontweight="bold")
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, len(cycles) - 1)
    ax1.legend(loc="lower right", fontsize=9)

    # Add height statistics as text
    height_text = f"Max Height: {metadata['max_height']:.2f}\nFinal Height: {metadata['final_height']:.2f}\nGrowth Rate: {metadata['growth_rate']:.3f} units/cycle"
    ax1.text(
        0.02,
        0.98,
        height_text,
        transform=ax1.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
    )

    # Plot individual DBH seed curves (lighter colors, thinner lines)
    for i, (dbh_curve_seed, seed) in enumerate(
        zip(individual_dbh_curves, seeds_tested)
    ):
        color = colors[i % len(colors)]
        cycles_seed = list(range(len(dbh_curve_seed)))
        ax2.plot(
            cycles_seed,
            dbh_curve_seed,
            color=color,
            linewidth=1.0,
            alpha=0.6,
            linestyle="--",
            label=f"Seed {seed}",
        )

    # Plot aggregated DBH curve (bold line on top)
    ax2.plot(
        cycles,
        dbh_curve,
        "g-",
        linewidth=3.0,
        marker="s",
        markersize=4,
        alpha=0.9,
        label="Maximum (aggregated)",
        zorder=10,
    )

    ax2.set_xlabel("Growth Cycles", fontsize=12)
    ax2.set_ylabel("DBH - Diameter at Breast Height (units)", fontsize=12)
    ax2.set_title("DBH Growth Over Time", fontsize=14, fontweight="bold")
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, len(cycles) - 1)
    ax2.legend(loc="lower right", fontsize=9)

    # Add DBH statistics as text
    dbh_text = f"Max DBH: {metadata['max_dbh']:.3f}\nFinal DBH: {metadata['final_dbh']:.3f}\nDBH Growth Rate: {metadata['dbh_growth_rate']:.4f} units/cycle"
    ax2.text(
        0.02,
        0.98,
        dbh_text,
        transform=ax2.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.8),
    )

    # Add analysis metadata as footer
    footer_text = f"Analysis: {metadata['num_seeds']} seeds, {metadata['actual_max_cycles']} max cycles (avg: {metadata['avg_actual_cycles']:.1f}) | Avg time: {metadata['avg_simulation_time']:.1f}s | Seeds tested: {', '.join([str(s) for s in metadata['seeds_tested']])}"
    if metadata["early_terminations"] > 0:
        footer_text += f" | Early terminations: {metadata['early_terminations']}/{metadata['num_seeds']}"
    if metadata["timeouts"] > 0:
        footer_text += f" | Timeouts: {metadata['timeouts']}/{metadata['num_seeds']}"
    fig.text(0.5, 0.02, footer_text, ha="center", fontsize=9, style="italic")

    plt.tight_layout()
    plt.subplots_adjust(top=0.93, bottom=0.08)

    # Save plot
    plot_path = output_dir / "growth_curves.png"
    plt.savefig(plot_path, dpi=300, bbox_inches="tight", facecolor="white")
    plt.close()

    # Also create a combined plot showing height vs DBH correlation
    _plot_height_dbh_correlation(
        species, height_curve, dbh_curve, metadata, output_dir, colors
    )


def _plot_height_dbh_correlation(
    species: str,
    height_curve: List[float],
    dbh_curve: List[float],
    metadata: Dict[str, Any],
    output_dir: Path,
    colors: List[str],
) -> None:
    """Create height vs DBH correlation plot.

    Args:
        species: Species name
        height_curve: List of heights per cycle
        dbh_curve: List of DBH values per cycle
        metadata: Analysis metadata dictionary
        output_dir: Directory to save plots
        colors: List of colors for individual seeds
    """
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))

    individual_height_curves = metadata.get("individual_height_curves", [])
    individual_dbh_curves = metadata.get("individual_dbh_curves", [])
    seeds_tested = metadata.get("seeds_tested", [])
    cycles = list(range(len(height_curve)))

    # Plot individual seed data points with different colors/markers
    for i, (height_curve_seed, dbh_curve_seed, seed) in enumerate(
        zip(individual_height_curves, individual_dbh_curves, seeds_tested)
    ):
        if len(height_curve_seed) > 0 and len(dbh_curve_seed) > 0:
            cycles_seed = list(range(len(height_curve_seed)))
            ax.scatter(
                height_curve_seed,
                dbh_curve_seed,
                c=cycles_seed,
                cmap="plasma",
                s=30,
                alpha=0.5,
                marker="o",
                label=f"Seed {seed}",
                edgecolors="none",
            )

    # Plot aggregated data points (larger, more prominent)
    scatter = ax.scatter(
        height_curve,
        dbh_curve,
        c=cycles,
        cmap="viridis",
        s=80,
        alpha=0.9,
        marker="s",
        label="Maximum (aggregated)",
        edgecolors="black",
        linewidth=0.5,
    )

    ax.set_xlabel("Height (units)", fontsize=12)
    ax.set_ylabel("DBH - Diameter at Breast Height (units)", fontsize=12)
    ax.set_title(
        f"Height vs DBH Relationship for {species}", fontsize=14, fontweight="bold"
    )
    ax.grid(True, alpha=0.3)
    ax.legend(loc="lower right", fontsize=9)

    # Add colorbar for the main aggregated data
    cbar = plt.colorbar(scatter)
    cbar.set_label("Growth Cycle (Aggregated)", fontsize=12)

    # Add trend line for aggregated data
    if len(height_curve) > 1:
        z = np.polyfit(height_curve, dbh_curve, 1)
        p = np.poly1d(z)
        ax.plot(
            height_curve,
            p(height_curve),
            "r--",
            alpha=0.8,
            linewidth=2,
            label="Trend line",
        )

        # Calculate R-squared for aggregated data
        correlation = np.corrcoef(height_curve, dbh_curve)[0, 1]
        r_squared = correlation**2
        ax.text(
            0.02,
            0.98,
            f"R² = {r_squared:.3f} (aggregated)",
            transform=ax.transAxes,
            fontsize=12,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

    plt.tight_layout()

    # Save correlation plot
    correlation_plot_path = output_dir / "height_dbh_correlation.png"
    plt.savefig(
        correlation_plot_path, dpi=300, bbox_inches="tight", facecolor="white"
    )
    plt.close()


def _init_plot_style():
    """Initialize matplotlib style for calibration plots."""
    mplstyle.use("default")
    style = "seaborn-v0_8" if "seaborn-v0_8" in plt.style.available else "default"
    plt.style.use(style)


def plot_calibration_comparison(
    species_name: str,
    grove_heights: List[float],
    grove_dbhs: List[float],
    yield_ages: List[float],
    yield_heights: List[float],
    yield_dbhs: List[float],
    table_title: str,
    output_path: Optional[Path] = None,
    calibrated_heights: Optional[np.ndarray] = None,
) -> None:
    """Plot Grove curves vs yield table curves side by side."""
    _init_plot_style()

    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    fig.suptitle(
        f"{species_name}: Grove vs Yield Table ({table_title})",
        fontsize=14,
        fontweight="bold",
    )

    # Height comparison
    ax1 = axes[0]
    grove_cycles = list(range(1, len(grove_heights) + 1))
    ax1.plot(grove_cycles, grove_heights, "b-", linewidth=2.5, label="Grove (cycles)")

    if calibrated_heights is not None:
        cal_cycles = list(range(1, len(calibrated_heights) + 1))
        ax1.plot(
            cal_cycles, calibrated_heights, "g--", linewidth=2, label="Calibrated target"
        )

    ax1.plot(
        yield_ages, yield_heights,
        "r-", alpha=1.0, linewidth=2.0, label="Yield table",
    )
    ax1.set_xlabel("Age (years) / Grove cycles")
    ax1.set_ylabel("Height (m)")
    ax1.set_title("Height over Age")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # DBH comparison
    ax2 = axes[1]
    if grove_dbhs:
        dbh_cycles = list(range(1, len(grove_dbhs) + 1))
        ax2.plot(
            dbh_cycles,
            [d * 100 for d in grove_dbhs],
            "b-", linewidth=2.5, label="Grove (cycles)",
        )

    ax2.plot(
        yield_ages, [d * 100 for d in yield_dbhs],
        "r-", alpha=1.0, linewidth=2.0, label="Yield table",
    )
    ax2.set_xlabel("Age (years) / Grove cycles")
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
    _init_plot_style()

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
        assert thicken_tips_values is not None
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
    else:
        plt.show()
    plt.close()
