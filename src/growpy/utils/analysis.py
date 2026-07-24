"""Species growth analysis for The Grove 2.3 species presets.

This module provides the SpeciesGrowthAnalyzer class for generating height curves
and growth prediction models from Grove species presets.
"""

import json
import logging
import multiprocessing as mp
import os
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import the_grove_23_core as gc
from scipy.optimize import least_squares
from tqdm import tqdm

from ..constants import BREAST_HEIGHT_METERS
from .log import is_verbose


def _chapman_richards(t, A, k, p):
    """Chapman-Richards growth function: h(t) = A * (1 - exp(-k*t))^p."""
    return A * (1.0 - np.exp(-k * t)) ** p


def _chapman_richards_with_baseline(t, A, k, p, y0):
    """Chapman-Richards with baseline: h(t) = y0 + (A - y0) * (1 - exp(-k*t))^p."""
    return y0 + (A - y0) * (1.0 - np.exp(-k * t)) ** p


def fit_chapman_richards(
    x: np.ndarray,
    y: np.ndarray,
    y0: float = 0.0,
) -> tuple[float, float, float, float]:
    """Fit Chapman-Richards growth function to (x, y) data.

    Fits h(t) = y0 + (A - y0) * (1 - exp(-k*t))^p when y0 > 0,
    or    h(t) = A * (1 - exp(-k*t))^p              when y0 == 0.

    Args:
        x: Independent variable (ages or cycles).
        y: Dependent variable (heights or DBH).
        y0: Baseline value at t=0. Use 0.0 for standard form.

    Returns:
        Tuple of (A, k, p, r_squared).

    Raises:
        RuntimeError: If fewer than 4 data points or curve_fit fails.
    """
    x = np.asarray(x, dtype=float).flatten()
    y = np.asarray(y, dtype=float).flatten()

    if len(x) < 4:
        raise RuntimeError(f"Need >= 4 data points for Chapman-Richards, got {len(x)}")

    y_max = float(np.max(y))
    if y_max <= 0:
        raise RuntimeError("All y values <= 0, cannot fit growth model")

    A_init = y_max * 1.3
    k_init = 0.03
    p_init = 1.5

    A_lo = y_max * 1.01
    A_hi = y_max * 5.0

    if y0 > 0:

        def _model(t, A, k, p):
            return _chapman_richards_with_baseline(t, A, k, p, y0)

    else:
        _model = _chapman_richards

    def _residuals(params):
        return _model(x, *params) - y

    result = least_squares(
        _residuals,
        x0=[A_init, k_init, p_init],
        bounds=([A_lo, 1e-4, 0.1], [A_hi, 1.0, 10.0]),
        method="dogbox",
        max_nfev=50000,
    )

    if not result.success:
        raise RuntimeError(f"Least squares failed: {result.message}")

    A, k, p = result.x
    y_pred = _model(x, A, k, p)
    ss_res = np.sum((y - y_pred) ** 2)
    ss_tot = np.sum((y - np.mean(y)) ** 2)
    r_squared = 1.0 - ss_res / ss_tot if ss_tot > 0 else 0.0

    return float(A), float(k), float(p), float(r_squared)


class ChapmanRichardsModel:
    """Parametric growth model using the Chapman-Richards function.

    Forward:  h(t) = A * (1 - exp(-k*t))^p
    Inverse:  t(h) = -ln(1 - (h/A)^(1/p)) / k   for 0 <= h < A

    For heights near or beyond the asymptote A, the inverse extrapolates
    linearly using the slope at h = 0.98*A.
    """

    EXTRAP_THRESHOLD = 0.98

    def __init__(self):
        self.A = None
        self.k = None
        self.p = None
        self.r_squared = None
        self.heights = None
        self.cycles = None
        self._extrap_t = None
        self._extrap_slope = None

    def fit(self, heights, cycles):
        """Fit Chapman-Richards to a height curve (cycles -> heights).

        Args:
            heights: Observed heights (y-axis).
            cycles: Corresponding cycle indices (x-axis).

        Returns:
            self
        """
        self.heights = np.asarray(heights, dtype=float).flatten()
        self.cycles = np.asarray(cycles, dtype=float).flatten()

        self.A, self.k, self.p, self.r_squared = fit_chapman_richards(
            self.cycles, self.heights
        )

        self._compute_extrapolation_constants()
        return self

    def _compute_extrapolation_constants(self):
        """Pre-compute constants for linear extrapolation beyond the asymptote."""
        h_boundary = self.A * self.EXTRAP_THRESHOLD
        self._extrap_t = self._raw_inverse(h_boundary)
        dh_dt = (
            self.A
            * self.k
            * self.p
            * np.exp(-self.k * self._extrap_t)
            * (1.0 - np.exp(-self.k * self._extrap_t)) ** (self.p - 1.0)
        )
        self._extrap_slope = 1.0 / dh_dt if dh_dt > 1e-12 else 0.0

    def _raw_inverse(self, h):
        """Analytic inverse: t = -ln(1 - (h/A)^(1/p)) / k."""
        ratio = np.clip(h / self.A, 1e-12, 1.0 - 1e-12)
        return -np.log(1.0 - ratio ** (1.0 / self.p)) / self.k

    def forward(self, t):
        """Evaluate h(t) = A * (1 - exp(-k*t))^p."""
        t = np.asarray(t, dtype=float)
        return self.A * (1.0 - np.exp(-self.k * t)) ** self.p

    def predict(self, X):
        """Predict cycles from target heights (inverse of the growth curve).

        Interface-compatible with PiecewiseLinearModel.predict().

        Args:
            X: Target heights, any shape (will be flattened).

        Returns:
            Array of predicted cycle counts.
        """
        targets = np.asarray(X, dtype=float).flatten()
        results = np.empty_like(targets, dtype=float)

        h_boundary = self.A * self.EXTRAP_THRESHOLD

        for i, h in enumerate(targets):
            if h <= 0:
                results[i] = 0.0
            elif h < h_boundary:
                results[i] = self._raw_inverse(h)
            else:
                results[i] = self._extrap_t + self._extrap_slope * (h - h_boundary)

        return results

    def to_dict(self) -> dict[str, Any]:
        """Serialize model parameters to a JSON-compatible dict."""
        return {
            "model_type": "chapman_richards",
            "A": self.A,
            "k": self.k,
            "p": self.p,
            "r_squared": self.r_squared,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "ChapmanRichardsModel":
        """Reconstruct model from a parameter dict."""
        model = cls()
        model.A = d["A"]
        model.k = d["k"]
        model.p = d["p"]
        model.r_squared = d.get("r_squared")
        model.heights = None
        model.cycles = None
        model._compute_extrapolation_constants()
        return model


class PiecewiseLinearModel:
    """Piecewise linear model on the height curve.

    Interpolates within training range, extrapolates the last segment's
    slope for heights beyond what was trained.
    """

    def __init__(self):
        self.heights = None
        self.cycles = None

    def fit(self, heights, cycles):
        self.heights = np.asarray(heights).flatten()
        self.cycles = np.asarray(cycles).flatten()
        return self

    def predict(self, X):
        targets = np.asarray(X).flatten()
        results = np.empty_like(targets, dtype=float)
        for i, t in enumerate(targets):
            if t <= self.heights[-1]:
                results[i] = np.interp(t, self.heights, self.cycles)
            else:
                # Extrapolate using slope of last two distinct points
                dh = self.heights[-1] - self.heights[-2]
                dc = self.cycles[-1] - self.cycles[-2]
                slope = dc / dh if dh > 0 else 0.0
                results[i] = self.cycles[-1] + slope * (t - self.heights[-1])
        return results

    def to_dict(self) -> dict[str, Any]:
        """Serialize model parameters to a JSON-compatible dict."""
        return {
            "model_type": "piecewise_linear",
            "heights": self.heights.tolist(),
            "cycles": self.cycles.tolist(),
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PiecewiseLinearModel":
        """Reconstruct model from a parameter dict."""
        model = cls()
        model.heights = np.array(d["heights"])
        model.cycles = np.array(d["cycles"])
        return model


# Backward-compatible alias for loading old .pkl files
SimpleLinearModel = PiecewiseLinearModel

from .plotting import plot_growth_curves

# Set up logging
logger = logging.getLogger(__name__)


def find_max_height_in_branch(branch: Any) -> float:
    """Recursively find the maximum Z height across a branch and its side branches.

    Walks ``branch.nodes`` and any ``node.side_branches`` recursively,
    returning the highest ``node.pos.z`` value found (or 0.0 when the
    branch has no nodes).
    """
    local_max = 0.0
    if hasattr(branch, "nodes") and branch.nodes:
        for node in branch.nodes:
            if hasattr(node, "pos") and node.pos.z > local_max:
                local_max = node.pos.z

            if hasattr(node, "side_branches") and node.side_branches:
                for side_branch in node.side_branches:
                    side_max = find_max_height_in_branch(side_branch)
                    if side_max > local_max:
                        local_max = side_max
    return local_max


def _process_single_species_for_parallel(args_tuple):
    """Process a single species in a parallel worker.

    This function is designed to be called by multiprocessing workers.
    It takes a tuple of arguments to work around multiprocessing limitations.

    Args:
        args_tuple: Tuple of (species, assets_dir, height_model_flushes, num_seeds,
                              height_growth_threshold, max_cycles_without_growth, timeout_seconds)

    Returns:
        Tuple of (species, success, results_dict, error_message)
    """
    (
        species,
        assets_dir,
        height_model_flushes,
        num_seeds,
        height_growth_threshold,
        max_cycles_without_growth,
        timeout_seconds,
    ) = args_tuple

    try:
        # Create a temporary analyzer instance for this species
        analyzer = SpeciesGrowthAnalyzer(
            assets_dir,
            height_model_flushes,
            num_seeds,
            height_growth_threshold,
            max_cycles_without_growth,
            timeout_seconds,
        )

        # Generate height and DBH curves
        height_curve, dbh_curve, metadata = analyzer.generate_height_curve_for_species(
            species
        )

        # Create growth model
        growth_model = analyzer.create_growth_model_for_species(species, height_curve)

        # Prepare results dictionary
        results = {
            "height_curve": height_curve,
            "dbh_curve": dbh_curve,
            "metadata": metadata,
            "growth_model": growth_model,
        }

        return (species, True, results, None)

    except Exception as e:
        error_msg = f"Failed to process {species}: {str(e)}"
        return (species, False, None, error_msg)


class SpeciesGrowthAnalyzer:
    """Analyzes growth patterns for Grove species and creates prediction models."""

    def __init__(
        self,
        assets_dir: Path,
        height_model_flushes: int = 75,
        num_seeds: int = 3,
        height_growth_threshold: float = 0.01,
        max_cycles_without_growth: int = 10,
        timeout_seconds: int = 60,
        target_height: float = 0.0,
    ):
        """Initialize the growth analyzer.

        Args:
            assets_dir: Directory containing prepared GrowPy assets
            height_model_flushes: Maximum number of growth cycles for height curve
                generation (safety cap when target_height is set)
            num_seeds: Number of different random seeds to average for robust curves
            height_growth_threshold: Minimum height increase to consider as growth
            max_cycles_without_growth: Number of cycles without growth before stopping
            timeout_seconds: Maximum time in seconds for growth simulation per seed
            target_height: If > 0, stop simulating once max_height_achieved reaches
                this value (meters), instead of always running height_model_flushes
                cycles. 0 disables early stopping (default, original behavior).
        """
        self.assets_dir = Path(assets_dir)
        self.presets_dir = self.assets_dir / "presets"
        self.output_dir = self.assets_dir / "growth_models"

        # Validate assets directory
        if not self.assets_dir.exists():
            raise FileNotFoundError(f"Assets directory not found: {self.assets_dir}")

        if not self.presets_dir.exists():
            raise FileNotFoundError(f"Presets directory not found: {self.presets_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.height_model_flushes = height_model_flushes
        self.num_seeds = num_seeds

        # Height monitoring configuration
        self.height_growth_threshold = height_growth_threshold
        self.max_cycles_without_growth = max_cycles_without_growth
        self.timeout_seconds = timeout_seconds
        self.target_height = target_height

        # Results storage
        self.height_curves = {}
        self.dbh_curves = {}
        self.growth_models = {}
        self.analysis_metadata = {}

    def apply_species_preset(self, grove, species: str, radius: float = 0.0) -> bool:
        """Apply a species preset to a grove using direct file loading.

        Uses the original drop_decay/drop_weak values from the seed.json preset
        so that calibration matches what generate_forest.py will produce.

        Args:
            grove: Grove object to apply preset to
            species: Species name (e.g., "Fagaceae - European oak")
            radius: Surround radius (meters) to load a radius-specific
                calibrated preset for, falling back to the base preset when
                no radius-specific calibration exists yet.

        Returns:
            True if successful, False otherwise
        """
        from growpy.config.paths import _radius_suffix

        try:
            preset_file = self.presets_dir / f"{species}{_radius_suffix(radius)}.seed.json"
            if radius and not preset_file.exists():
                preset_file = self.presets_dir / f"{species}.seed.json"
            if not preset_file.exists():
                logger.error(f"Preset file not found: {preset_file}")
                return False

            with open(preset_file) as f:
                preset_data = json.load(f)

            # Performance: disable twig placement (not needed for height/DBH curves)
            # In Blender, growing without twigs selected is equivalent
            preset_data["twig_density"] = 0.0

            preset_json = json.dumps(preset_data)
            properties = gc.io.properties_from_json_string(preset_json)
            grove.set_properties(properties)

            logger.debug(
                f"Applied preset for species: {species} from file: {preset_file}"
            )
            return True

        except (FileNotFoundError, json.JSONDecodeError, KeyError, RuntimeError) as e:
            logger.error(f"Failed to apply species preset {species}: {e}")
            return False

    def get_available_species(self) -> list[str]:
        """Get list of all available Grove species presets from preset files."""
        try:
            species_list = []
            preset_files = list(self.presets_dir.glob("*.json"))

            for preset_file in preset_files:
                if preset_file.name.startswith("."):
                    continue

                species_name = preset_file.stem
                if species_name.endswith(".seed"):
                    species_name = species_name[:-5]

                if species_name:
                    species_list.append(species_name)

            logger.info(
                f"Found {len(species_list)} species presets in assets directory"
            )
            return sorted(species_list)

        except OSError as e:
            logger.error(f"Failed to get available species from directory: {e}")
            return []

    def get_growth_model_name_for_species(self, species: str) -> str:
        """Generate a safe folder name from species preset name.

        Args:
            species: Species name (e.g., "Fagaceae - European oak")

        Returns:
            Growth model name (e.g., "Fagaceae_European_oak")
        """
        safe_name = (
            species.replace(" - ", "_")
            .replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")

        if safe_name.startswith("."):
            safe_name = safe_name[1:]

        logger.debug(
            f"Generated growth model name '{safe_name}' for species '{species}'"
        )
        return safe_name

    def calculate_dbh_at_height(
        self, tree, target_height: float = BREAST_HEIGHT_METERS
    ) -> float:
        """Calculate diameter at breast height using linear interpolation.

        Finds the closest nodes below and above the target height and interpolates
        between them to get the exact diameter at the specified height.

        Args:
            tree: The Grove tree object
            target_height: Height at which to measure diameter (default 1.3m for DBH)

        Returns:
            Diameter at the specified height, or 0.0 if tree doesn't reach that height
        """
        if not hasattr(tree, "nodes") or not tree.nodes:
            return 0.0

        trunk_nodes = []
        for node in tree.nodes:
            if hasattr(node, "pos") and hasattr(node, "radius"):
                trunk_nodes.append({"height": node.pos.z, "radius": node.radius})

        if not trunk_nodes:
            return 0.0

        trunk_nodes.sort(key=lambda x: x["height"])
        max_height = trunk_nodes[-1]["height"]

        if max_height < target_height:
            return 0.0

        node_below = None
        node_above = None

        for trunk_node in trunk_nodes:
            if trunk_node["height"] <= target_height:
                node_below = trunk_node
            elif trunk_node["height"] > target_height and node_above is None:
                node_above = trunk_node
                break

        if node_below and node_below["height"] == target_height:
            return node_below["radius"] * 2.0

        if node_below is None:
            if trunk_nodes[0]["height"] >= target_height * 0.95:
                return trunk_nodes[0]["radius"] * 2.0
            else:
                return 0.0

        if node_above is None:
            return node_below["radius"] * 2.0

        height_ratio = (target_height - node_below["height"]) / (
            node_above["height"] - node_below["height"]
        )
        interpolated_radius = node_below["radius"] + height_ratio * (
            node_above["radius"] - node_below["radius"]
        )

        return interpolated_radius * 2.0

    def generate_height_curve_for_species(
        self, species: str, radius: float = 0.0
    ) -> tuple[list[float], list[float], dict[str, Any]]:
        """Generate height and DBH curves for a species with multiple seeds.

        Args:
            species: Species name
            radius: Surround radius (meters) to simulate under. 0 = open-grown
                (no Grove Surround shell); >0 applies Grove's Surround shell at
                this distance and loads the matching radius-specific preset.

        Returns:
            Tuple of (averaged_height_curve, averaged_dbh_curve, metadata)
        """
        all_height_curves = []
        all_dbh_curves = []
        seed_metadata = []

        seeds_to_test = [1, 7, 13, 23, 42, 100, 111, 123, 666][: self.num_seeds]

        seed_progress = tqdm(
            seeds_to_test,
            desc=f"Testing seeds for {species[:25]}",
            leave=False,
            disable=(self.num_seeds <= 1) or not is_verbose(),
        )

        # Load species-specific overrides (includes yield table calibration)
        from growpy.config.preset_overrides import get_species_overrides

        species_overrides = get_species_overrides(species, radius)

        # Always apply longevity overrides during initial simulation (data collection).
        # The tree must survive long enough to produce usable height/DBH curves
        # for calibration, regardless of the longevity_mode setting.
        # Forest generation will respect longevity_mode independently.
        from growpy.config.preset_overrides import LONGEVITY_OVERRIDES

        for param, value in LONGEVITY_OVERRIDES.static_overrides.items():
            if param not in species_overrides.static_overrides:
                species_overrides.static_overrides[param] = value
        has_overrides = not species_overrides.is_empty()
        if has_overrides:
            logger.info(
                "  [%s] Applying %d cycle array overrides, %d interpolated overrides, "
                "%d static overrides",
                species,
                len(species_overrides.cycle_array_overrides),
                len(species_overrides.interpolated_overrides),
                len(species_overrides.static_overrides),
            )

        if radius:
            from growpy.config import get_config
            from growpy.core.grove import enable_surround

            surround_cfg = get_config()

        for seed in seed_progress:
            try:
                grove = gc.Grove()
                grove.clear_trees()
                grove.set_random_seed(seed)

                if not self.apply_species_preset(grove, species, radius):
                    logger.error(
                        f"Failed to apply species preset for {species} with seed {seed}"
                    )
                    continue

            except (RuntimeError, AttributeError, MemoryError) as e:
                logger.error(f"Failed to create grove with species {species}: {e}")
                continue

            grove.clear_trees()
            if radius:
                enable_surround(
                    grove,
                    density=surround_cfg.surround_density,
                    distance=radius,
                    height=surround_cfg.surround_height,
                    grow=surround_cfg.surround_grow,
                )
            grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

            heights_this_seed = []
            dbh_this_seed = []
            max_height_achieved = 0.0
            max_dbh_achieved = 0.0
            cycles_without_growth = 0
            simulation_start_time = time.time()

            cycle_progress = tqdm(
                range(self.height_model_flushes),
                desc=f"  {species[:20]} seed={seed}",
                leave=False,
                unit="cy",
                bar_format="{l_bar}{bar}| {n_fmt}/{total_fmt} [{elapsed}<{remaining}]",
                disable=not is_verbose(),
            )

            for cycle in cycle_progress:
                # Apply per-cycle overrides (yield table calibration, longevity curves)
                if has_overrides:
                    species_overrides.apply_to_grove(
                        grove, cycle, self.height_model_flushes
                    )
                grove.simulate(1)

                elapsed_time = time.time() - simulation_start_time
                if elapsed_time > self.timeout_seconds:
                    logger.warning(
                        f"Species {species}, seed {seed}: Simulation timeout after "
                        f"{elapsed_time:.1f} seconds at cycle {cycle + 1}."
                    )
                    break

                current_height = 0.0
                current_dbh = 0.0
                previous_max_height = max_height_achieved

                if grove.trees and len(grove.trees) > 0:
                    tree = grove.trees[0]

                    current_height = find_max_height_in_branch(tree)
                    current_dbh = self.calculate_dbh_at_height(
                        tree, target_height=BREAST_HEIGHT_METERS
                    )

                    if current_height > max_height_achieved:
                        max_height_achieved = current_height

                    if current_dbh > max_dbh_achieved:
                        max_dbh_achieved = current_dbh

                    heights_this_seed.append(max_height_achieved)
                    dbh_this_seed.append(max_dbh_achieved)
                else:
                    heights_this_seed.append(max_height_achieved)
                    dbh_this_seed.append(max_dbh_achieved)

                cycle_progress.set_postfix_str(
                    f"h={max_height_achieved:.1f}m dbh={max_dbh_achieved:.1f}cm"
                )

                height_increase = max_height_achieved - previous_max_height

                if height_increase < self.height_growth_threshold:
                    cycles_without_growth += 1
                    if cycle > 5:
                        logger.debug(
                            f"Species {species}, seed {seed}, cycle {cycle}: "
                            f"No significant growth ({height_increase:.4f})"
                        )
                else:
                    cycles_without_growth = 0

                if (
                    cycles_without_growth >= self.max_cycles_without_growth
                    and cycle > 10
                ):
                    logger.info(
                        f"Species {species}, seed {seed}: Height growth stopped after "
                        f"{cycle + 1} cycles (max height: {max_height_achieved:.3f})"
                    )
                    break

                if self.target_height > 0 and max_height_achieved >= self.target_height:
                    logger.info(
                        f"Species {species}, seed {seed}: Reached target height "
                        f"{self.target_height:.1f}m after {cycle + 1} cycles "
                        f"(max height: {max_height_achieved:.3f})"
                    )
                    break

            cycle_progress.close()
            all_height_curves.append(heights_this_seed)
            all_dbh_curves.append(dbh_this_seed)
            actual_cycles = len(heights_this_seed)
            final_elapsed_time = time.time() - simulation_start_time

            seed_metadata.append(
                {
                    "seed": seed,
                    "final_height": heights_this_seed[-1] if heights_this_seed else 0.0,
                    "max_height": max_height_achieved,
                    "final_dbh": dbh_this_seed[-1] if dbh_this_seed else 0.0,
                    "max_dbh": max_dbh_achieved,
                    "actual_cycles": actual_cycles,
                    "early_termination": actual_cycles < self.height_model_flushes,
                    "cycles_without_growth": cycles_without_growth,
                    "simulation_time": final_elapsed_time,
                    "timeout_occurred": final_elapsed_time > self.timeout_seconds,
                }
            )

            seed_progress.set_postfix(seed=seed)

        if not all_height_curves:
            raise ValueError(f"No successful growth curves generated for {species}")

        max_heights = []
        max_dbhs = []
        max_cycles_achieved = (
            max(len(curve) for curve in all_height_curves) if all_height_curves else 0
        )

        for cycle in range(max_cycles_achieved):
            cycle_heights = [
                curve[cycle] for curve in all_height_curves if cycle < len(curve)
            ]
            cycle_dbhs = [
                curve[cycle] for curve in all_dbh_curves if cycle < len(curve)
            ]

            max_heights.append(max(cycle_heights) if cycle_heights else 0.0)
            max_dbhs.append(max(cycle_dbhs) if cycle_dbhs else 0.0)

        early_terminations = sum(
            1 for meta in seed_metadata if meta.get("early_termination", False)
        )
        timeouts = sum(
            1 for meta in seed_metadata if meta.get("timeout_occurred", False)
        )
        avg_actual_cycles = (
            sum(meta.get("actual_cycles", 0) for meta in seed_metadata)
            / len(seed_metadata)
            if seed_metadata
            else 0
        )
        avg_simulation_time = (
            sum(meta.get("simulation_time", 0) for meta in seed_metadata)
            / len(seed_metadata)
            if seed_metadata
            else 0
        )

        metadata = {
            "species": species,
            "planned_cycles": self.height_model_flushes,
            "actual_max_cycles": max_cycles_achieved,
            "avg_actual_cycles": avg_actual_cycles,
            "avg_simulation_time": avg_simulation_time,
            "early_terminations": early_terminations,
            "timeouts": timeouts,
            "num_seeds": len(all_height_curves),
            "seeds_tested": [m["seed"] for m in seed_metadata],
            "final_height": max_heights[-1] if max_heights else 0.0,
            "max_height": max(max_heights) if max_heights else 0.0,
            "final_dbh": max_dbhs[-1] if max_dbhs else 0.0,
            "max_dbh": max(max_dbhs) if max_dbhs else 0.0,
            "growth_rate": (
                max(max_heights) / max_cycles_achieved
                if max_heights and max_cycles_achieved > 0
                else 0.0
            ),
            "dbh_growth_rate": (
                max(max_dbhs) / max_cycles_achieved
                if max_dbhs and max_cycles_achieved > 0
                else 0.0
            ),
            "height_curve": max_heights,
            "dbh_curve": max_dbhs,
            "individual_height_curves": all_height_curves,
            "individual_dbh_curves": all_dbh_curves,
            "seed_results": seed_metadata,
        }

        return max_heights, max_dbhs, metadata

    def create_growth_model_for_species(self, species: str, height_curve: list[float]):
        """Create a growth model to predict required cycles from target height.

        Tries Chapman-Richards parametric fit first (better extrapolation).
        Falls back to PiecewiseLinearModel if the fit fails or is poor.

        Args:
            species: Species name
            height_curve: List of heights per cycle

        Returns:
            Fitted ChapmanRichardsModel or PiecewiseLinearModel
        """
        if not height_curve:
            raise ValueError(f"Empty height curve for {species}")

        heights = np.array(height_curve)
        cycles = np.arange(len(height_curve))

        non_zero_mask = heights > 0.01
        if np.any(non_zero_mask):
            heights = heights[non_zero_mask]
            cycles = cycles[non_zero_mask]

        if len(heights) < 2:
            raise ValueError(f"Insufficient growth data for {species}")

        try:
            model = ChapmanRichardsModel()
            model.fit(heights, cycles)
            if model.r_squared < 0.9:
                logger.warning(
                    "  Chapman-Richards poor fit (R²=%.3f) for %s, using piecewise",
                    model.r_squared,
                    species,
                )
                raise RuntimeError("Poor fit")
            logger.info(
                "  Chapman-Richards fit: A=%.2f, k=%.4f, p=%.2f, R²=%.4f",
                model.A,
                model.k,
                model.p,
                model.r_squared,
            )
            return model
        except (RuntimeError, ValueError) as e:
            logger.warning(
                "  Chapman-Richards fit failed for %s (%s), falling back to piecewise",
                species,
                e,
            )
            model = PiecewiseLinearModel()
            model.fit(heights, cycles)
            return model

    def _analyze_single_species(self, species: str, radius: float = 0.0) -> bool:
        """Core analysis logic for a single species.

        Args:
            species: Species name to analyze
            radius: Surround radius (meters) to simulate under (0 = open-grown)

        Returns:
            True if successful, False otherwise
        """
        try:
            height_curve, dbh_curve, metadata = self.generate_height_curve_for_species(
                species, radius
            )
            growth_model = self.create_growth_model_for_species(species, height_curve)

            self.height_curves[species] = height_curve
            self.dbh_curves[species] = dbh_curve
            self.growth_models[species] = growth_model
            self.analysis_metadata[species] = metadata

            self.save_species_results(species, radius)
            return True

        except SystemExit as e:
            logger.critical(
                "FATAL: Grove module called sys.exit(%s) during %s", e.code, species
            )
            raise
        except Exception as e:
            logger.error("Failed to analyze species %s: %s", species, e, exc_info=True)
            return False

    def analyze_all_species(
        self,
        parallel: bool = True,
        max_workers: int | None = None,
        species_filter: list | None = None,
        radius: float = 0.0,
    ) -> dict[str, bool]:
        """Analyze all available species (sequential or parallel).

        Args:
            parallel: Whether to use parallel processing (default: True).
                Forced to False when radius > 0 -- the parallel worker path
                does not yet support simulating under Surround.
            max_workers: Maximum number of parallel workers (default: CPU count - 1)
            species_filter: Optional list of species to process (if None, processes all)
            radius: Surround radius (meters) to simulate all species under
                (0 = open-grown, the default)

        Returns:
            Dictionary mapping species to success status
        """
        species_list = self.get_available_species()

        # Filter species if requested
        if species_filter:
            species_list = [s for s in species_list if s in species_filter]

        if parallel and radius:
            logger.warning(
                "Surround radius %.1f requested; parallel worker path doesn't "
                "support it yet, falling back to sequential",
                radius,
            )
            parallel = False

        if parallel:
            return self._analyze_parallel(species_list, max_workers)
        else:
            return self._analyze_sequential(species_list, radius)

    def _analyze_sequential(
        self, species_list: list[str], radius: float = 0.0
    ) -> dict[str, bool]:
        """Analyze species sequentially.

        Args:
            species_list: List of species names to analyze
            radius: Surround radius (meters) to simulate under (0 = open-grown)

        Returns:
            Dictionary mapping species to success status
        """
        results = {}
        progress = tqdm(
            species_list,
            desc="Analyzing species (sequential)",
            disable=not is_verbose(),
        )

        for species in progress:
            progress.set_description(f"Analyzing: {species[:30]}...")
            results[species] = self._analyze_single_species(species, radius)

            if not results[species]:
                logger.warning("FAILED %s", species)

        successful = sum(1 for success in results.values() if success)
        logger.info("Analysis complete: %d/%d species", successful, len(species_list))

        return results

    def _analyze_parallel(
        self, species_list: list[str], max_workers: int | None
    ) -> dict[str, bool]:
        """Analyze species in parallel.

        Args:
            species_list: List of species names to analyze
            max_workers: Maximum number of parallel workers

        Returns:
            Dictionary mapping species to success status
        """
        results = {}

        if max_workers is None:
            max_workers = max(1, mp.cpu_count() - 1)

        logger.info(
            f"Using {max_workers} parallel workers for {len(species_list)} species"
        )

        # Avoid CPU oversubscription: each worker process runs numpy/scipy, which
        # each spawn their own BLAS thread pool. Cap inner threads (children inherit
        # these env vars on spawn) so we don't end up with max_workers x cores threads.
        for _thread_var in (
            "OMP_NUM_THREADS",
            "OPENBLAS_NUM_THREADS",
            "MKL_NUM_THREADS",
        ):
            os.environ.setdefault(_thread_var, "1")

        process_args = [
            (
                species,
                self.assets_dir,
                self.height_model_flushes,
                self.num_seeds,
                self.height_growth_threshold,
                self.max_cycles_without_growth,
                self.timeout_seconds,
            )
            for species in species_list
        ]

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_species = {
                executor.submit(_process_single_species_for_parallel, args): args[0]
                for args in process_args
            }

            progress = tqdm(
                total=len(species_list),
                desc="Analyzing species (parallel)",
                unit="species",
                disable=not is_verbose(),
            )

            for future in as_completed(future_to_species):
                species_name = future_to_species[future]

                try:
                    species, success, species_results, error_msg = future.result()

                    if success and species_results is not None:
                        self.height_curves[species] = species_results["height_curve"]
                        self.dbh_curves[species] = species_results["dbh_curve"]
                        self.growth_models[species] = species_results["growth_model"]
                        self.analysis_metadata[species] = species_results["metadata"]

                        self.save_species_results(species)
                        results[species] = True
                    else:
                        logger.warning("FAILED %s: %s", species, error_msg)
                        results[species] = False

                except Exception as e:
                    logger.error("FAILED %s: %s", species_name, e)
                    results[species_name] = False

                progress.update(1)

            progress.close()

        successful = sum(1 for success in results.values() if success)
        logger.info(
            "Parallel analysis complete: %d/%d species", successful, len(species_list)
        )

        return results

    def save_species_results(self, species: str, radius: float = 0.0):
        """Save results for a single species in its own subfolder.

        Args:
            species: Species name to save results for
            radius: Surround radius (meters) these results were simulated
                under (0 = open-grown). Written to a radius-specific
                subfolder when > 0, so different radii don't overwrite
                each other's output.

        Returns:
            Path to the species output directory
        """
        growth_model_name = self.get_growth_model_name_for_species(species)
        species_dir = self.output_dir / growth_model_name
        if radius:
            species_dir = species_dir / f"r{radius:g}"
        species_dir.mkdir(parents=True, exist_ok=True)

        if species in self.height_curves:
            curve_path = species_dir / "height_curve.json"
            with open(curve_path, "w") as f:
                json.dump(
                    {
                        "species": species,
                        "height_curve": self.height_curves[species],
                        "actual_cycles": len(self.height_curves[species]),
                        "metadata": self.analysis_metadata.get(species, {}),
                    },
                    f,
                    indent=2,
                )

        if species in self.dbh_curves:
            dbh_curve_path = species_dir / "dbh_curve.json"
            with open(dbh_curve_path, "w") as f:
                json.dump(
                    {
                        "species": species,
                        "dbh_curve": self.dbh_curves[species],
                        "actual_cycles": len(self.dbh_curves[species]),
                        "metadata": self.analysis_metadata.get(species, {}),
                    },
                    f,
                    indent=2,
                )

        if species in self.growth_models:
            model_path = species_dir / "growth_model.pkl"
            joblib.dump(self.growth_models[species], model_path)

            model = self.growth_models[species]
            if hasattr(model, "to_dict"):
                params_path = species_dir / "growth_model_params.json"
                with open(params_path, "w") as f:
                    json.dump(model.to_dict(), f, indent=2)

        if species in self.analysis_metadata:
            metadata_path = species_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(self.analysis_metadata[species], f, indent=2)

        # Inject flushes_per_year from calibration data if available
        metadata = self.analysis_metadata[species]
        if "flushes_per_year" not in metadata:
            from growpy.config.paths import _radius_suffix

            preset_path = (
                self.presets_dir / f"{species}{_radius_suffix(radius)}.seed.json"
            )
            if radius and not preset_path.exists():
                preset_path = self.presets_dir / f"{species}.seed.json"
            if preset_path.exists():
                with open(preset_path) as f:
                    cal = json.load(f).get("_yield_table_calibration", {})
                fpy = cal.get("flushes_per_year")
                if fpy:
                    metadata["flushes_per_year"] = fpy

        try:
            plot_growth_curves(
                species,
                self.height_curves[species],
                self.dbh_curves[species],
                metadata,
                species_dir,
            )
        except (ImportError, ValueError, OSError, TypeError) as e:
            logger.warning("Failed to generate plots for %s: %s", species, e)

        return species_dir

    def save_growth_models(self, radius: float = 0.0):
        """Save growth models in species-specific subfolders."""
        logger.info("Saving individual species results...")
        saved_count = 0

        for species in tqdm(
            self.analysis_metadata.keys(),
            desc="Saving species",
            leave=False,
            disable=not is_verbose(),
        ):
            self.save_species_results(species, radius)
            saved_count += 1

        logger.info("Saved %d species models to: %s", saved_count, self.output_dir)

    def update_lookup_table_with_new_models(self):
        """Update tree asset lookup table with new growth model names."""
        try:
            from growpy.config.paths import _get_lookup_table_path

            lookup_table_path = _get_lookup_table_path()

            df = pd.read_csv(lookup_table_path)
            updated_count = 0

            for species in self.analysis_metadata.keys():
                preset_name = f"{species}.seed.json"
                new_growth_model_name = self.get_growth_model_name_for_species(species)

                mask = df["Preset"] == preset_name
                if mask.any():
                    df.loc[mask, "Growth Model"] = new_growth_model_name
                    updated_count += 1

            if updated_count > 0:
                backup_path = lookup_table_path.with_suffix(".csv.backup")
                if not backup_path.exists():
                    df_original = pd.read_csv(lookup_table_path)
                    df_original.to_csv(backup_path, index=False)
                    logger.info(f"Created backup: {backup_path}")

                df.to_csv(lookup_table_path, index=False)
                logger.info(
                    f"Updated lookup table with {updated_count} new growth model names"
                )
            else:
                logger.warning("No updates were made to the lookup table")

        except (
            FileNotFoundError,
            PermissionError,
            pd.errors.ParserError,
            KeyError,
            OSError,
        ) as e:
            logger.error(f"Failed to update lookup table: {e}")

    def generate_lookup_table_summary(self):
        """Generate a summary CSV of species analyzed and their growth models."""
        try:
            summary_path = self.output_dir / "species_analysis_summary.csv"
            summary_data = []

            for species in self.analysis_metadata.keys():
                metadata = self.analysis_metadata[species]
                growth_model_name = self.get_growth_model_name_for_species(species)

                summary_data.append(
                    {
                        "Species": species,
                        "Preset_File": f"{species}.seed.json",
                        "Growth_Model_Name": growth_model_name,
                        "Final_Height": metadata.get("final_height", 0.0),
                        "Max_Height": metadata.get("max_height", 0.0),
                        "Final_DBH": metadata.get("final_dbh", 0.0),
                        "Max_DBH": metadata.get("max_dbh", 0.0),
                        "Growth_Rate": metadata.get("growth_rate", 0.0),
                        "Planned_Cycles": metadata.get("planned_cycles", 0),
                        "Actual_Max_Cycles": metadata.get("actual_max_cycles", 0),
                        "Avg_Actual_Cycles": metadata.get("avg_actual_cycles", 0.0),
                        "Avg_Simulation_Time": metadata.get("avg_simulation_time", 0.0),
                        "Early_Terminations": metadata.get("early_terminations", 0),
                        "Timeouts": metadata.get("timeouts", 0),
                        "Seeds_Tested": len(metadata.get("seeds_tested", [])),
                    }
                )

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_csv(summary_path, index=False)

            logger.info(f"Generated species analysis summary: {summary_path}")
            logger.info(f"Summary contains {len(summary_data)} analyzed species")

        except (KeyError, OSError) as e:
            logger.error(f"Failed to generate lookup table summary: {e}")
