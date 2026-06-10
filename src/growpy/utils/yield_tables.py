"""Yield table calibration math for growpy.

Loading, store management, and provider functionality live in pylometree.
This module re-exports the key data types and loaders and adds
growpy-specific calibration functions on top.

Yield tables are resolved from pre-ingested local data only (no runtime API
calls).  Use ``pylometree-ingest`` to populate the store beforehand.
"""

import json
import logging
from pathlib import Path
from typing import Any

import numpy as np
from pylometree.yield_tables import (  # noqa: F401
    YieldTableData,
    load_local_yield_table,
    load_store_yield_table,
    resolve_yield_table,
)

logger = logging.getLogger(__name__)


def load_lookup_table() -> dict[str, dict[str, str]]:
    """Load tree_asset_lookup.csv keyed by Common Name.

    Returns:
        {common_name: {"standardized": ..., "yield_search": ..., ...}}
    """
    from growpy.config.paths import _get_lookup_table

    df = _get_lookup_table()
    result = {}
    for _, row in df.iterrows():
        name = row["Common Name"]
        result[name] = {
            "standardized": row.get("Standardized Name", ""),
            "yield_search": str(row.get("Yield Search", "")).strip(),
        }
    return result


# --- Calibration math ---


FPY_MIN = 0.5
FPY_MAX = 2.0
FPY_RMSE_THRESHOLD = 0.25  # relative RMSE above which fpy is untrusted


def _build_yield_height_interpolator(
    yield_ages: list[float],
    yield_heights: list[float],
):
    """Build a height-from-age interpolator for the yield table.

    Returns a callable age -> height using Chapman-Richards parametric fit,
    falling back to PCHIP spline.
    """
    from scipy.interpolate import PchipInterpolator

    from growpy.utils.analysis import (
        _chapman_richards_with_baseline,
        fit_chapman_richards,
    )

    extended_ages = np.array([0.0] + list(yield_ages))
    extended_heights = np.array([0.5] + list(yield_heights))

    try:
        A, k, p, _ = fit_chapman_richards(extended_ages, extended_heights, y0=0.5)

        def cr_interp(ages):
            return _chapman_richards_with_baseline(
                np.asarray(ages, dtype=float), A, k, p, 0.5
            )

        return cr_interp
    except Exception:
        interp = PchipInterpolator(extended_ages, extended_heights)
        return interp


def _fpy_rmse(
    fpy: float,
    grove_heights: np.ndarray,
    yield_interp,
) -> float:
    """Compute RMSE between Grove heights and yield table at a given fpy."""
    cycles = np.arange(len(grove_heights))
    calendar_ages = cycles / fpy
    yield_at_cycles = np.asarray(yield_interp(calendar_ages), dtype=float)

    # Only compare the active growth region (skip first few seedling cycles
    # and stop where Grove has data)
    start = min(5, len(grove_heights) // 5)
    g = grove_heights[start:]
    y = yield_at_cycles[start:]

    return float(np.sqrt(np.mean((g - y) ** 2)))


def estimate_flushes_per_year(
    grove_heights: list[float],
    yield_ages: list[float],
    yield_heights: list[float],
) -> float:
    """Estimate how many Grove growth cycles correspond to 1 calendar year.

    Finds the fpy that minimizes RMSE between the full Grove height trajectory
    and the yield table (interpolated via Chapman-Richards or PCHIP). Uses
    bounded scalar optimization over [FPY_MIN, FPY_MAX].

    If the best-fit RMSE is too high relative to the height range (above
    FPY_RMSE_THRESHOLD), the estimate is considered unreliable and fpy falls
    back to 1.0.

    Returns:
        Estimated flushes_per_year, clamped to [FPY_MIN, FPY_MAX].
    """
    from scipy.optimize import minimize_scalar

    if len(grove_heights) < 5 or len(yield_ages) < 2 or len(yield_heights) < 2:
        return 1.0

    grove_arr = np.array(grove_heights, dtype=float)
    grove_max = grove_arr.max()
    if grove_max < 1.0:
        return 1.0

    try:
        yield_interp = _build_yield_height_interpolator(yield_ages, yield_heights)
    except Exception:
        logger.warning("  Interpolation failed — falling back to fpy=1.0")
        return 1.0

    result = minimize_scalar(
        _fpy_rmse,
        bounds=(FPY_MIN, FPY_MAX),
        method="bounded",
        args=(grove_arr, yield_interp),
    )

    fpy = float(np.clip(result.x, FPY_MIN, FPY_MAX))
    best_rmse = _fpy_rmse(fpy, grove_arr, yield_interp)

    # Relative RMSE: normalize by height range to make threshold scale-free
    height_range = grove_max - grove_arr[0]
    rel_rmse = best_rmse / height_range if height_range > 0.5 else 1.0

    if rel_rmse > FPY_RMSE_THRESHOLD:
        logger.warning(
            "  fpy=%.2f has poor fit (relRMSE=%.3f > %.3f) — falling back to 1.0",
            fpy,
            rel_rmse,
            FPY_RMSE_THRESHOLD,
        )
        return 1.0

    logger.info(
        "  flushes_per_year: %.2f (RMSE=%.2fm, relRMSE=%.3f)",
        fpy,
        best_rmse,
        rel_rmse,
    )

    return fpy


def fit_height_dbh_model(
    yield_heights: list[float],
    yield_dbhs: list[float],
) -> dict[str, float] | None:
    """Fit a power model DBH = a * H^b from yield table height/DBH pairs.

    Uses the allometric relationship between tree height and stem diameter
    to predict DBH from height, independent of age alignment.

    Returns:
        Dict with keys 'a', 'b', 'r_squared', or None if fit fails.
    """
    from scipy.optimize import least_squares

    h = np.array(yield_heights, dtype=float)
    d = np.array(yield_dbhs, dtype=float)

    # Filter to valid positive pairs
    mask = (h > 0) & (d > 0)
    h, d = h[mask], d[mask]

    if len(h) < 3:
        logger.warning("  Too few h/d pairs (%d) for height-DBH model", len(h))
        return None

    def power_func(x, a, b):
        return a * np.power(x, b)

    try:
        # Initial guess from log-log linear regression
        log_h, log_d = np.log(h), np.log(d)
        b0 = np.polyfit(log_h, log_d, 1)
        p0 = [np.exp(b0[1]), b0[0]]

        def _residuals(params):
            return power_func(h, *params) - d

        result = least_squares(_residuals, x0=p0, method="lm", max_nfev=5000)
        a, b = float(result.x[0]), float(result.x[1])

        pred = power_func(h, a, b)
        ss_res = np.sum((d - pred) ** 2)
        ss_tot = np.sum((d - np.mean(d)) ** 2)
        r_sq = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

        logger.info(
            "  height-DBH model: DBH = %.4f * H^%.4f, R²=%.4f",
            a,
            b,
            r_sq,
        )
        return {"a": round(a, 6), "b": round(b, 6), "r_squared": round(r_sq, 6)}

    except (RuntimeError, ValueError) as e:
        logger.warning("  height-DBH model fit failed: %s", e)
        return None


def predict_dbh_from_height(
    heights: list[float],
    model: dict[str, float],
) -> list[float]:
    """Predict DBH (m) from heights (m) using a fitted power model."""
    a, b = model["a"], model["b"]
    return [max(0.0, a * (h**b)) if h > 0 else 0.0 for h in heights]


def interpolate_yield_table(
    ages: list[float],
    values: list[float],
    max_cycles: int,
    flushes_per_year: float = 1.0,
    initial_value: float = 0.5,
) -> tuple:
    """Interpolate yield table to per-cycle resolution.

    Uses Chapman-Richards parametric fit for smooth interpolation with natural
    extrapolation beyond the yield table age range. Falls back to PCHIP
    spline if the parametric fit fails.

    Args:
        initial_value: Value at age 0. Use 0.5 for heights (sapling),
            0.0 for DBH (no trunk diameter at birth).
    """
    from growpy.utils.analysis import (
        _chapman_richards,
        _chapman_richards_with_baseline,
        fit_chapman_richards,
    )

    extended_ages = np.array([0.0] + list(ages))
    extended_values = np.array([initial_value] + list(values))

    cycle_indices = np.arange(1, max_cycles + 1)
    calendar_ages = cycle_indices / flushes_per_year

    try:
        A, k, p, r_sq = fit_chapman_richards(
            extended_ages, extended_values, y0=initial_value
        )
        if initial_value > 0:
            interpolated = _chapman_richards_with_baseline(
                calendar_ages, A, k, p, initial_value
            )
        else:
            interpolated = _chapman_richards(calendar_ages, A, k, p)
        interpolated = np.maximum(interpolated, 0.0)
        logger.debug(
            "  Yield table CR fit: A=%.2f, k=%.4f, p=%.2f, R²=%.4f",
            A,
            k,
            p,
            r_sq,
        )
    except (RuntimeError, ValueError) as e:
        logger.debug("  Yield table CR fit failed (%s), using PCHIP fallback", e)
        from scipy.interpolate import PchipInterpolator

        interp = PchipInterpolator(extended_ages, extended_values)
        interpolated = np.maximum(interp(calendar_ages), 0.0)

    return cycle_indices, interpolated


def compute_grow_length_curve(
    grove_heights: list[float],
    target_heights: np.ndarray,
    base_grow_length: float,
    sigma_k: float = 2.0,
) -> list[float]:
    """Compute per-cycle grow_length values to match target height trajectory.

    Outlier scale factors are clipped at k standard deviations from the mean,
    producing species-adaptive bounds instead of fixed arbitrary limits.
    """
    from scipy.ndimage import uniform_filter1d

    n_cycles = min(len(grove_heights), len(target_heights))

    grove_increments = np.diff(grove_heights[:n_cycles])
    target_increments = np.diff(target_heights[:n_cycles])
    grove_increments = np.where(grove_increments < 0.001, 0.001, grove_increments)

    raw_scale_factors = target_increments / grove_increments

    mu = np.mean(raw_scale_factors)
    sigma = np.std(raw_scale_factors)
    lower = max(mu - sigma_k * sigma, 0.1)
    upper = mu + sigma_k * sigma

    scale_factors = np.clip(raw_scale_factors, lower, upper)

    if len(scale_factors) > 5:
        scale_factors = uniform_filter1d(scale_factors, size=3)

    # Hard ceiling: prevent extreme scale factors that crash the Grove engine.
    # Empirically, all well-behaved species stay below 3x; values above that
    # cause destructive growth (e.g. Oak at 10x plateaus after 3 cycles).
    MAX_SCALE_FACTOR = 3.0
    n_capped = int(np.sum(scale_factors > MAX_SCALE_FACTOR))
    scale_factors = np.minimum(scale_factors, MAX_SCALE_FACTOR)
    if n_capped > 0:
        logger.warning(
            "  %d/%d scale factors capped at %.1fx (max grow_length=%.3f)",
            n_capped,
            len(scale_factors),
            MAX_SCALE_FACTOR,
            base_grow_length * MAX_SCALE_FACTOR,
        )

    grow_lengths = base_grow_length * scale_factors
    # Physical floor: grow_length must stay above 50% of base value.
    # Below this threshold, some trees die depending on random seed,
    # because Grove cannot sustain growth with extremely low grow_length.
    grow_lengths = np.maximum(grow_lengths, base_grow_length * 0.5)
    grow_lengths = np.insert(grow_lengths, 0, grow_lengths[0])

    return grow_lengths.tolist()


def write_calibration_to_seed_json(
    species_name: str,
    grow_lengths: list[float],
    table_title: str,
    presets_dir: Path,
    yield_class: float | None = None,
    table_id: int | None = None,
    target_dbh_per_cycle: list[float] | None = None,
    height_dbh_model: dict[str, float] | None = None,
    flushes_per_year: float = 1.0,
) -> Path | None:
    """Write calibration data to the species seed.json."""
    from growpy.utils.naming import standardize_species_name

    species_dir = standardize_species_name(species_name)
    preset_path = presets_dir / f"{species_dir}.seed.json"

    if not preset_path.exists():
        logger.error("Preset not found: %s", preset_path)
        return None

    with open(preset_path) as f:
        preset = json.load(f)

    calibration: dict[str, Any] = {
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
    if target_dbh_per_cycle:
        calibration["target_dbh_per_cycle"] = [
            round(v, 6) for v in target_dbh_per_cycle
        ]
    if height_dbh_model:
        calibration["height_dbh_model"] = height_dbh_model
    calibration["flushes_per_year"] = flushes_per_year
    preset["_yield_table_calibration"] = calibration

    with open(preset_path, "w") as f:
        json.dump(preset, f, indent=4)

    logger.info("Calibration written to %s", preset_path)
    return preset_path


def calibrate_species(
    species_name: str,
    grove_heights: list[float],
    grove_dbhs: list[float],
    yield_data: YieldTableData,
    presets_dir: Path,
    flushes_per_year: float | None = None,
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
    from growpy.utils.naming import standardize_species_name

    species_clean = standardize_species_name(species_name)
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
            grove_heights,
            yield_data.ages,
            yield_data.heights,
        )

    # Height calibration
    _, yearly_heights = interpolate_yield_table(
        yield_data.ages, yield_data.heights, max_cycles, flushes_per_year
    )

    grow_lengths = compute_grow_length_curve(
        grove_heights, yearly_heights, base_grow_length
    )

    gl_arr = np.array(grow_lengths)
    gl_cv = np.std(gl_arr) / np.mean(gl_arr) if np.mean(gl_arr) > 0 else 0.0
    logger.info(
        "  grow_length: base=%.3f, range=%.4f-%.4f, avg=%.4f, cv=%.3f",
        base_grow_length,
        min(grow_lengths),
        max(grow_lengths),
        np.mean(grow_lengths),
        gl_cv,
    )

    # Target DBH via height-DBH allometric model (applied at export via radial scaling)
    # Fit a power model DBH = a*H^b from the yield table and apply it to the
    # interpolated yield table heights for each cycle. This gives the expected
    # DBH at the target height the calibrated tree should reach.
    h_dbh_model = None
    write_target_dbh = None

    if grove_dbhs and yield_data.dbhs and yield_data.heights:
        h_dbh_model = fit_height_dbh_model(yield_data.heights, yield_data.dbhs)
        if h_dbh_model:
            # Predict target DBH from interpolated yield table heights (meters)
            write_target_dbh = predict_dbh_from_height(
                list(yearly_heights), h_dbh_model
            )

    result = write_calibration_to_seed_json(
        species_name,
        grow_lengths,
        yield_data.title,
        presets_dir,
        yield_class=yield_data.yield_class,
        table_id=yield_data.table_id,
        target_dbh_per_cycle=write_target_dbh,
        height_dbh_model=h_dbh_model,
        flushes_per_year=flushes_per_year,
    )

    return result is not None
