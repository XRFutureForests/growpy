"""Growth curve plotting utilities for species analysis and calibration."""

from pathlib import Path
from typing import Dict, Any, List, Optional

import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
import numpy as np


def _init_plot_style():
    """Initialize matplotlib style for all plots."""
    mplstyle.use("default")
    style = "seaborn-v0_8" if "seaborn-v0_8" in plt.style.available else "default"
    plt.style.use(style)


def _extract_common(metadata: Dict[str, Any], height_curve, dbh_curve):
    """Extract common data used across multiple plot functions."""
    fpy = metadata.get("flushes_per_year", 1.0)
    ages = np.array([(i + 1) / fpy for i in range(len(height_curve))])
    heights = np.array(height_curve)
    dbh_cm = np.array(dbh_curve) * 100
    individual_h = metadata.get("individual_height_curves", [])
    individual_d = metadata.get("individual_dbh_curves", [])
    seeds = metadata.get("seeds_tested", [])
    return fpy, ages, heights, dbh_cm, individual_h, individual_d, seeds


def _seed_envelope(individual_curves, scale=1.0):
    """Compute min/max envelope across seed curves.

    Returns (min_arr, max_arr) of equal length, or (None, None) if < 2 seeds.
    """
    if len(individual_curves) < 2:
        return None, None
    max_len = max(len(c) for c in individual_curves)
    padded = []
    for c in individual_curves:
        arr = np.array(c) * scale
        if len(arr) < max_len:
            arr = np.pad(arr, (0, max_len - len(arr)), constant_values=np.nan)
        padded.append(arr)
    stacked = np.array(padded)
    return np.nanmin(stacked, axis=0), np.nanmax(stacked, axis=0)


# -- Seed colors used across all plots --
SEED_COLORS = [
    "lightblue", "lightgreen", "lightcoral", "lightyellow", "lightpink",
    "lightgray", "lightsteelblue", "lightsalmon", "lightseagreen",
]


def plot_growth_curves(
    species: str,
    height_curve: List[float],
    dbh_curve: List[float],
    metadata: Dict[str, Any],
    output_dir: Path,
) -> None:
    """Create and save growth curve plots plus additional diagnostic plots.

    Generates:
    - growth_curves.png: Height and DBH over age with model fit overlay
    - height_dbh_correlation.png: Allometric H-DBH relationship
    - growth_increments.png: CAI/MAI and stem volume estimates
    """
    _init_plot_style()

    fpy, ages, heights, dbh_cm, ind_h, ind_d, seeds = _extract_common(
        metadata, height_curve, dbh_curve
    )

    # Load model params if available (for Chapman-Richards overlay)
    model_params = _load_model_params(output_dir)

    _plot_growth_curves_main(
        species, ages, heights, dbh_cm, ind_h, ind_d, seeds,
        fpy, metadata, model_params, output_dir,
    )
    _plot_height_dbh_correlation(
        species, ages, heights, dbh_cm, ind_h, ind_d, seeds,
        fpy, metadata, output_dir,
    )
    _plot_growth_increments(
        species, ages, heights, dbh_cm, fpy, metadata, output_dir,
    )


def _load_model_params(output_dir: Path) -> Optional[Dict[str, float]]:
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
    species, ages, heights, dbh_cm, ind_h, ind_d, seeds,
    fpy, metadata, model_params, output_dir,
):
    """Main growth curves: height and DBH over age with model fit and bands."""
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
    fig.suptitle(f"Growth Curves for {species}", fontsize=16, fontweight="bold")

    # -- Height subplot --
    # Seed confidence band
    h_min, h_max = _seed_envelope(ind_h, scale=1.0)
    if h_min is not None:
        band_ages = np.array([(j + 1) / fpy for j in range(len(h_min))])
        ax1.fill_between(
            band_ages, h_min, h_max,
            alpha=0.15, color="blue", label="Seed range",
        )

    # Individual seed curves
    for i, (hc, seed) in enumerate(zip(ind_h, seeds)):
        color = SEED_COLORS[i % len(SEED_COLORS)]
        ages_s = [(j + 1) / fpy for j in range(len(hc))]
        ax1.plot(
            ages_s, hc, color=color, linewidth=1.0, alpha=0.6,
            linestyle="--", label=f"Seed {seed}",
        )

    # Aggregated curve
    ax1.plot(
        ages, heights, "b-", linewidth=3.0, marker="o", markersize=4,
        alpha=0.9, label="Maximum (aggregated)", zorder=10,
    )

    # Chapman-Richards model fit overlay
    if model_params:
        A, k, p = model_params["A"], model_params["k"], model_params["p"]
        r2 = model_params.get("r_squared", 0)
        t_smooth = np.linspace(0, ages[-1] * fpy, 200)
        h_fit = A * (1.0 - np.exp(-k * t_smooth)) ** p
        ages_fit = t_smooth / fpy
        ax1.plot(
            ages_fit, h_fit, "r--", linewidth=1.5, alpha=0.8,
            label=f"Chapman-Richards (R²={r2:.3f})",
        )

    ax1.set_xlabel("Age (years)", fontsize=12)
    ax1.set_ylabel("Height (m)", fontsize=12)
    ax1.set_title("Height Growth Over Time", fontsize=14, fontweight="bold")
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, ages[-1] if len(ages) else 1)
    ax1.legend(loc="lower right", fontsize=9)

    growth_rate_yr = metadata["growth_rate"] * fpy
    height_text = (
        f"Max Height: {metadata['max_height']:.2f} m\n"
        f"Final Height: {metadata['final_height']:.2f} m\n"
        f"Growth Rate: {growth_rate_yr:.3f} m/year"
    )
    ax1.text(
        0.02, 0.98, height_text, transform=ax1.transAxes, fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
    )

    # -- DBH subplot --
    d_min, d_max = _seed_envelope(ind_d, scale=100.0)
    if d_min is not None:
        band_ages = np.array([(j + 1) / fpy for j in range(len(d_min))])
        ax2.fill_between(
            band_ages, d_min, d_max,
            alpha=0.15, color="green", label="Seed range",
        )

    for i, (dc, seed) in enumerate(zip(ind_d, seeds)):
        color = SEED_COLORS[i % len(SEED_COLORS)]
        ages_s = [(j + 1) / fpy for j in range(len(dc))]
        ax2.plot(
            ages_s, [d * 100 for d in dc], color=color, linewidth=1.0,
            alpha=0.6, linestyle="--", label=f"Seed {seed}",
        )

    ax2.plot(
        ages, dbh_cm, "g-", linewidth=3.0, marker="s", markersize=4,
        alpha=0.9, label="Maximum (aggregated)", zorder=10,
    )

    ax2.set_xlabel("Age (years)", fontsize=12)
    ax2.set_ylabel("DBH (cm)", fontsize=12)
    ax2.set_title("DBH Growth Over Time", fontsize=14, fontweight="bold")
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, ages[-1] if len(ages) else 1)
    ax2.legend(loc="lower right", fontsize=9)

    dbh_rate_yr = metadata["dbh_growth_rate"] * 100 * fpy
    dbh_text = (
        f"Max DBH: {metadata['max_dbh'] * 100:.1f} cm\n"
        f"Final DBH: {metadata['final_dbh'] * 100:.1f} cm\n"
        f"DBH Growth Rate: {dbh_rate_yr:.2f} cm/year"
    )
    ax2.text(
        0.02, 0.98, dbh_text, transform=ax2.transAxes, fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.8),
    )

    # Footer
    max_age = metadata["actual_max_cycles"] / fpy
    avg_age = metadata["avg_actual_cycles"] / fpy
    footer = (
        f"Analysis: {metadata['num_seeds']} seeds, {max_age:.0f} years max "
        f"(avg: {avg_age:.0f}) | Avg time: {metadata['avg_simulation_time']:.1f}s "
        f"| Seeds tested: {', '.join(str(s) for s in metadata['seeds_tested'])}"
    )
    if fpy != 1.0:
        footer += f" | fpy: {fpy:.2f}"
    if metadata["early_terminations"] > 0:
        footer += (
            f" | Early terminations: "
            f"{metadata['early_terminations']}/{metadata['num_seeds']}"
        )
    if metadata["timeouts"] > 0:
        footer += f" | Timeouts: {metadata['timeouts']}/{metadata['num_seeds']}"
    fig.text(0.5, 0.02, footer, ha="center", fontsize=9, style="italic")

    plt.tight_layout()
    plt.subplots_adjust(top=0.93, bottom=0.08)
    plt.savefig(
        output_dir / "growth_curves.png",
        dpi=300, bbox_inches="tight", facecolor="white",
    )
    plt.close()


def _plot_height_dbh_correlation(
    species, ages, heights, dbh_cm, ind_h, ind_d, seeds,
    fpy, metadata, output_dir,
):
    """Height vs DBH with allometric power-law fit instead of linear."""
    fig, ax = plt.subplots(1, 1, figsize=(10, 8))

    # Individual seed scatter
    for i, (hc, dc, seed) in enumerate(zip(ind_h, ind_d, seeds)):
        if len(hc) > 0 and len(dc) > 0:
            ages_s = [(j + 1) / fpy for j in range(len(hc))]
            ax.scatter(
                hc, [d * 100 for d in dc], c=ages_s, cmap="plasma",
                s=30, alpha=0.5, marker="o", label=f"Seed {seed}",
                edgecolors="none",
            )

    # Aggregated scatter
    scatter = ax.scatter(
        heights, dbh_cm, c=ages, cmap="viridis", s=80, alpha=0.9,
        marker="s", label="Maximum (aggregated)",
        edgecolors="black", linewidth=0.5,
    )

    ax.set_xlabel("Height (m)", fontsize=12)
    ax.set_ylabel("DBH (cm)", fontsize=12)
    ax.set_title(
        f"Height vs DBH Relationship for {species}",
        fontsize=14, fontweight="bold",
    )
    ax.grid(True, alpha=0.3)

    cbar = plt.colorbar(scatter)
    cbar.set_label("Age (years)", fontsize=12)

    # Allometric power-law fit: DBH = a * H^b (log-linear regression)
    stats_text = ""
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
            d_fit = a * h_smooth ** b

            # R² for allometric fit
            d_pred = a * h_pos ** b
            ss_res = np.sum((d_pos - d_pred) ** 2)
            ss_tot = np.sum((d_pos - d_pos.mean()) ** 2)
            r2 = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0

            ax.plot(
                h_smooth, d_fit, "r--", alpha=0.8, linewidth=2,
                label=f"Allometric: DBH = {a:.2f} * H^{b:.2f}",
            )
            stats_text = f"DBH = {a:.2f} * H^{b:.2f}\nR² = {r2:.3f}"

    if stats_text:
        ax.text(
            0.02, 0.98, stats_text, transform=ax.transAxes, fontsize=12,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
        )

    ax.legend(loc="lower right", fontsize=9)
    plt.tight_layout()
    plt.savefig(
        output_dir / "height_dbh_correlation.png",
        dpi=300, bbox_inches="tight", facecolor="white",
    )
    plt.close()


def _plot_growth_increments(
    species, ages, heights, dbh_cm, fpy, metadata, output_dir,
):
    """CAI/MAI increment curves for height and DBH, plus stem volume estimate.

    Current Annual Increment (CAI): year-over-year change.
    Mean Annual Increment (MAI): cumulative value / age.
    Volume estimated using standard form factor: V = f * pi/4 * DBH² * H.
    """
    if len(ages) < 3:
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))
    fig.suptitle(
        f"Growth Increments and Volume for {species}",
        fontsize=16, fontweight="bold",
    )

    # Height increments
    ax_h = axes[0, 0]
    h_cai = np.diff(heights) * fpy  # m/year
    h_mai = heights[1:] / ages[1:]  # m/year
    cai_ages = ages[1:]

    ax_h.plot(cai_ages, h_cai, "b-", linewidth=2, label="CAI (height)")
    ax_h.plot(cai_ages, h_mai, "b--", linewidth=2, label="MAI (height)")

    # Mark culmination (CAI = MAI crossover)
    diff = h_cai[:len(h_mai)] - h_mai[:len(h_cai)]
    crossings = np.where(np.diff(np.sign(diff)))[0]
    if len(crossings) > 0:
        cx = crossings[0]
        ax_h.axvline(cai_ages[cx], color="gray", linestyle=":", alpha=0.7)
        ax_h.annotate(
            f"Culmination ~{cai_ages[cx]:.0f} yr",
            xy=(cai_ages[cx], h_mai[cx]), xytext=(10, 10),
            textcoords="offset points", fontsize=9,
            arrowprops=dict(arrowstyle="->", color="gray"),
        )

    ax_h.set_xlabel("Age (years)", fontsize=11)
    ax_h.set_ylabel("Height increment (m/year)", fontsize=11)
    ax_h.set_title("Height: CAI and MAI", fontsize=13, fontweight="bold")
    ax_h.legend(fontsize=9)
    ax_h.grid(True, alpha=0.3)
    ax_h.set_xlim(0, ages[-1])

    # DBH increments
    ax_d = axes[0, 1]
    d_cai = np.diff(dbh_cm) * fpy  # cm/year
    d_mai = dbh_cm[1:] / ages[1:]  # cm/year

    ax_d.plot(cai_ages, d_cai, "g-", linewidth=2, label="CAI (DBH)")
    ax_d.plot(cai_ages, d_mai, "g--", linewidth=2, label="MAI (DBH)")

    diff_d = d_cai[:len(d_mai)] - d_mai[:len(d_cai)]
    crossings_d = np.where(np.diff(np.sign(diff_d)))[0]
    if len(crossings_d) > 0:
        cx = crossings_d[0]
        ax_d.axvline(cai_ages[cx], color="gray", linestyle=":", alpha=0.7)
        ax_d.annotate(
            f"Culmination ~{cai_ages[cx]:.0f} yr",
            xy=(cai_ages[cx], d_mai[cx]), xytext=(10, 10),
            textcoords="offset points", fontsize=9,
            arrowprops=dict(arrowstyle="->", color="gray"),
        )

    ax_d.set_xlabel("Age (years)", fontsize=11)
    ax_d.set_ylabel("DBH increment (cm/year)", fontsize=11)
    ax_d.set_title("DBH: CAI and MAI", fontsize=13, fontweight="bold")
    ax_d.legend(fontsize=9)
    ax_d.grid(True, alpha=0.3)
    ax_d.set_xlim(0, ages[-1])

    # Stem volume estimate: V = f * pi/4 * (DBH_m)^2 * H
    ax_v = axes[1, 0]
    form_factor = 0.45  # typical conifer/broadleaf average
    dbh_m = dbh_cm / 100.0
    volume = form_factor * (np.pi / 4) * dbh_m ** 2 * heights  # m³

    ax_v.plot(ages, volume, "purple", linewidth=2.5)
    ax_v.fill_between(ages, 0, volume, alpha=0.1, color="purple")

    ax_v.set_xlabel("Age (years)", fontsize=11)
    ax_v.set_ylabel("Stem volume (m³)", fontsize=11)
    ax_v.set_title(
        f"Estimated Stem Volume (f={form_factor})",
        fontsize=13, fontweight="bold",
    )
    ax_v.grid(True, alpha=0.3)
    ax_v.set_xlim(0, ages[-1])

    vol_text = f"Final: {volume[-1]:.2f} m³\nMax: {volume.max():.2f} m³"
    ax_v.text(
        0.02, 0.98, vol_text, transform=ax_v.transAxes, fontsize=10,
        verticalalignment="top",
        bbox=dict(boxstyle="round", facecolor="plum", alpha=0.6),
    )

    # Volume increment (CAI/MAI for volume)
    ax_vi = axes[1, 1]
    v_cai = np.diff(volume) * fpy  # m³/year
    v_mai = volume[1:] / ages[1:]

    ax_vi.plot(cai_ages, v_cai, "purple", linewidth=2, label="CAI (volume)")
    ax_vi.plot(cai_ages, v_mai, "purple", linewidth=2, linestyle="--",
               label="MAI (volume)")

    diff_v = v_cai[:len(v_mai)] - v_mai[:len(v_cai)]
    crossings_v = np.where(np.diff(np.sign(diff_v)))[0]
    if len(crossings_v) > 0:
        cx = crossings_v[0]
        ax_vi.axvline(cai_ages[cx], color="gray", linestyle=":", alpha=0.7)
        ax_vi.annotate(
            f"Optimal rotation ~{cai_ages[cx]:.0f} yr",
            xy=(cai_ages[cx], v_mai[cx]), xytext=(10, 10),
            textcoords="offset points", fontsize=9,
            arrowprops=dict(arrowstyle="->", color="gray"),
        )

    ax_vi.set_xlabel("Age (years)", fontsize=11)
    ax_vi.set_ylabel("Volume increment (m³/year)", fontsize=11)
    ax_vi.set_title("Volume: CAI and MAI", fontsize=13, fontweight="bold")
    ax_vi.legend(fontsize=9)
    ax_vi.grid(True, alpha=0.3)
    ax_vi.set_xlim(0, ages[-1])

    plt.tight_layout()
    plt.subplots_adjust(top=0.93)
    plt.savefig(
        output_dir / "growth_increments.png",
        dpi=300, bbox_inches="tight", facecolor="white",
    )
    plt.close()


def plot_calibration_comparison(
    species_name: str,
    uncalibrated_heights: List[float],
    uncalibrated_dbhs: List[float],
    yield_ages: List[float],
    yield_heights: List[float],
    yield_dbhs: List[float],
    table_title: str,
    flushes_per_year: float = 1.0,
    calibrated_heights: Optional[List[float]] = None,
    calibrated_dbhs: Optional[List[float]] = None,
    target_dbh_per_cycle: Optional[List[float]] = None,
    output_path: Optional[Path] = None,
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
        yield_ages, yield_heights,
        "r-", linewidth=2.0, label="Yield table (reference)",
    )

    ax1.plot(
        uncal_years, uncalibrated_heights,
        "b-", linewidth=2.0, alpha=0.6, label="Grove (before calibration)",
    )

    if calibrated_heights is not None:
        cal_years = [
            (i + 1) / flushes_per_year for i in range(len(calibrated_heights))
        ]
        ax1.plot(
            cal_years, calibrated_heights,
            "g-", linewidth=2.5, label="Grove (after calibration)",
        )

    # Limit x-axis to the Grove data range so curves are clearly visible
    grove_max_year = max(uncal_years[-1] if uncal_years else 0,
                         cal_years[-1] if calibrated_heights is not None else 0)
    if grove_max_year > 0:
        ax1.set_xlim(0, grove_max_year * 1.15)

    ax1.set_xlabel("Age (years)")
    ax1.set_ylabel("Height (m)")
    ax1.set_title("Height over Age")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # DBH comparison
    ax2 = axes[1]

    ax2.plot(
        yield_ages, [d * 100 for d in yield_dbhs],
        "r-", linewidth=2.0, label="Yield table (reference)",
    )

    if uncalibrated_dbhs:
        uncal_dbh_years = uncal_years[:len(uncalibrated_dbhs)]
        ax2.plot(
            uncal_dbh_years,
            [d * 100 for d in uncalibrated_dbhs],
            "b-", linewidth=2.0, alpha=0.6, label="Grove (before calibration)",
        )

    if calibrated_dbhs is not None:
        cal_dbh_years = [
            (i + 1) / flushes_per_year for i in range(len(calibrated_dbhs))
        ]
        ax2.plot(
            cal_dbh_years,
            [d * 100 for d in calibrated_dbhs],
            "g-", linewidth=2.5, label="Grove (after calibration)",
        )

    if target_dbh_per_cycle is not None:
        target_dbh_years = [
            (i + 1) / flushes_per_year for i in range(len(target_dbh_per_cycle))
        ]
        ax2.plot(
            target_dbh_years,
            [d * 100 for d in target_dbh_per_cycle],
            "g--", linewidth=2.0, alpha=0.8, label="Export DBH (radial scaling)",
        )

    # Match x-axis range to the height plot
    grove_max_year = max(uncal_years[-1] if uncal_years else 0,
                         (len(calibrated_dbhs) / flushes_per_year
                          if calibrated_dbhs is not None else 0))
    if grove_max_year > 0:
        ax2.set_xlim(0, grove_max_year * 1.15)

    ax2.set_xlabel("Age (years)")
    ax2.set_ylabel("DBH (cm)")
    ax2.set_title("Diameter at Breast Height over Age")
    ax2.legend(loc="upper left")
    ax2.grid(True, alpha=0.3)

    # Annotate fpy so the conversion factor is visible
    fig.text(
        0.99, 0.01,
        f"flushes_per_year = {flushes_per_year:.2f}",
        ha="right", va="bottom", fontsize=9, color="gray",
    )

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
    else:
        plt.show()
    plt.close()


def plot_grove_curves_only(
    species_name: str,
    grove_heights: List[float],
    grove_dbhs: List[float],
    flushes_per_year: float = 1.0,
    output_path: Optional[Path] = None,
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
        years, grove_heights,
        "b-", linewidth=2.0, label="Grove simulation",
    )
    ax1.set_xlabel("Age (years)")
    ax1.set_ylabel("Height (m)")
    ax1.set_title("Height over Age")
    ax1.legend(loc="upper left")
    ax1.grid(True, alpha=0.3)

    # DBH
    ax2 = axes[1]
    if grove_dbhs:
        dbh_years = years[:len(grove_dbhs)]
        ax2.plot(
            dbh_years,
            [d * 100 for d in grove_dbhs],
            "b-", linewidth=2.0, label="Grove simulation",
        )
    ax2.set_xlabel("Age (years)")
    ax2.set_ylabel("DBH (cm)")
    ax2.set_title("Diameter at Breast Height over Age")
    ax2.legend(loc="upper left")
    ax2.grid(True, alpha=0.3)

    fig.text(
        0.99, 0.01,
        f"flushes_per_year = {flushes_per_year:.2f}",
        ha="right", va="bottom", fontsize=9, color="gray",
    )

    plt.tight_layout()

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        plt.savefig(output_path, dpi=150, bbox_inches="tight")
    else:
        plt.show()
    plt.close()
