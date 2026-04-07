"""Pipeline B: standard forest generation by growth cycles.

Extracted from `cli/generate_forest.py`. Simulates forest growth to a
fixed cycle target and exports all trees via `export_individual_trees`.
The CLI front-end (`growpy.cli.generate_forest`) parses arguments and calls
`generate_forest_exports()`.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict, Optional

import bpy  # noqa: F401  (required; generate_forest_exports runs Grove via bpy)
import pandas as pd

from growpy import GrowPyConfig, calculate_growth_cycles_from_height, create_forest, simulate_forest_growth
from growpy.config.preset_overrides import PresetOverrides
from growpy.config.quality import get_quality_preset
from growpy.io.forest_export import export_individual_trees
from growpy.io.usd.tree_export import (
    handle_bone_limit_error as _handle_bone_limit_error,
)
from growpy.io.usd.tree_export import (
    is_bone_limit_error as _is_bone_limit_error,
)
from growpy.utils.profiling import ProfileTimer

GROWTH_CYCLE_LIMIT = 10
SMOOTH_ITERATIONS = 10

logger = logging.getLogger(__name__)


def generate_forest_exports(
    csv_path: Path,
    output_dir: Path,
    config: GrowPyConfig,
    quality: str = "high",
    growth_cycle_limit: Optional[int] = None,
    smooth_iterations: Optional[int] = None,
    include_grove_attributes: bool = False,
    verbose: bool = False,
    preset_overrides: Optional[PresetOverrides] = None,
    timer: Optional["ProfileTimer"] = None,
    skip_pve_json: bool = False,
    skip_validation: bool = False,
    skeleton_overrides: Optional[Dict[str, Any]] = None,
    export_tree_ids: Optional[set] = None,
) -> None:
    """Generate forest from CSV data and export as Nanite Assembly USD files.

    Export types are controlled by config flags (export_skeletal, export_static).

    DynamicWind attributes are now embedded directly in the USD skeleton prim
    (unreal:dynamicWind:jointNames, unreal:dynamicWind:jointSimulationGroups).

    Args:
        csv_path: Path to CSV file with forest data
        output_dir: Directory to save export files
        config: GrowPy configuration
        quality: Quality preset name ('ultra', 'high', 'medium', 'low', 'performance')
        growth_cycle_limit: Maximum growth cycles per tree (default: GROWTH_CYCLE_LIMIT)
        smooth_iterations: Number of smoothing iterations for branches (default: SMOOTH_ITERATIONS)
                          Higher values (10-20) produce smoother branches, 0 disables smoothing
        include_grove_attributes: If True, include Grove metadata in USD files (increases size ~70%)
        verbose: Print detailed progress information
        preset_overrides: Optional PresetOverrides for dynamic parameter adjustment during simulation
        timer: Optional ProfileTimer for tracking execution times
        skip_pve_json: If True, skip PVE preset JSON generation (saves ~3% export time)
        skip_validation: If True, skip assembly validation (saves ~5-10% export time)
    """
    from growpy.utils.profiling import ProfileTimer

    if timer is None:
        timer = ProfileTimer(enabled=False)

    # Clear twig file copy cache at start of export session
    from growpy.io.usd.assembly_export import clear_twig_copy_cache

    clear_twig_copy_cache()

    # Use defaults if not specified
    if growth_cycle_limit is None:
        growth_cycle_limit = GROWTH_CYCLE_LIMIT
    if smooth_iterations is None:
        smooth_iterations = SMOOTH_ITERATIONS

    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        return

    # Load forest data
    try:
        with timer.track("load_csv"):
            forest_data = pd.read_csv(csv_path)
            required_columns = ["x", "y", "species", "height"]

            # Check required columns
            missing_cols = [
                col for col in required_columns if col not in forest_data.columns
            ]
            if missing_cols:
                logger.error("Missing required columns: %s", missing_cols)
                return

            # Z column will be added by create_forest if missing

    except Exception as e:
        logger.error("Error loading CSV: %s", e)
        return

    # Cap tree heights if max_height is configured
    if config.forest_max_height > 0:
        original_max = forest_data["height"].max()
        forest_data["height"] = forest_data["height"].clip(
            upper=config.forest_max_height
        )
        logger.info(
            "Max height cap: %.1fm (original max: %.1fm)",
            config.forest_max_height,
            original_max,
        )

    with timer.track("calculate_growth_cycles"):
        try:
            calculate_growth_cycles_from_height(forest_data)
        except Exception as e:
            logger.warning("Could not calculate growth cycles from height: %s", e)
            logger.warning("  Using default: growth_cycles=10, delay=0")
            forest_data["growth_cycles"] = 10
            forest_data["delay"] = 0

        # Cap each tree's cycles individually at the limit
        forest_data["growth_cycles"] = forest_data["growth_cycles"].clip(
            upper=growth_cycle_limit, lower=1
        )

        # Recalculate delays after clipping
        max_cycles_after_clip = forest_data["growth_cycles"].max()
        forest_data["delay"] = max_cycles_after_clip - forest_data["growth_cycles"]

    try:
        with timer.track("create_forest"):
            forest = create_forest(forest_data)
        max_cycles = forest_data["growth_cycles"].max()
        # Smoothing is applied automatically during simulation:
        # 1. smooth_minimal() - Fixes ugly kinks on thick branches
        # 2. smooth() - Reduces sharp corner angles (smooth_iterations times)
        # 3. weigh_and_bend() - Re-calculates branch positions with smoothed angles
        with timer.track("simulate_forest_growth"):
            simulate_forest_growth(
                forest,
                max_cycles,
                smooth_iterations=smooth_iterations,
                preset_overrides=preset_overrides,
                use_species_curves=config.calibration_align_height,
            )
    except Exception as e:
        logger.error("Error creating/simulating forest: %s", e)
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    # Get quality settings
    quality_params = get_quality_preset(quality)

    # Hardcode skeleton parameters
    quality_params["skeleton_bias"] = 0.5
    quality_params["skeleton_connected"] = True

    # Apply skeleton overrides (allows simplified skeleton with ultra mesh)
    if skeleton_overrides:
        for key, value in skeleton_overrides.items():
            quality_params[key] = value
        logger.info("[Skeleton Overrides] Applied: %s", skeleton_overrides)

    # CRITICAL: Force minimal export for Nanite compatibility
    # Skeletal meshes: geometry + skeleton only (no materials/textures/attributes)
    # Grove attributes can be optionally added via include_grove_attributes flag
    quality_params["minimal_export"] = True

    # Include Grove attributes if requested (adds ~70% file size to skeletal meshes)
    quality_params["include_grove_attributes"] = include_grove_attributes

    # Skip optional JSON generation (passed via quality_params for simplicity)
    # Note: DynamicWind JSON is always generated for skeletal meshes
    quality_params["skip_pve_json"] = skip_pve_json
    quality_params["skip_validation"] = skip_validation
    quality_params["profile_pve"] = (
        timer.enabled
    )  # Enable PVE profiling when --profile is set
    quality_params["export_tree_ids"] = export_tree_ids

    try:
        # Twigs/foliage are copied to shared Instances/ directory by assembly_export
        # Ensure shared instances directory exists (don't wipe -- other species may share it)
        instances_dir = output_dir / "Instances"
        instances_dir.mkdir(parents=True, exist_ok=True)

        # Export types controlled by config.export_skeletal / config.export_static
        with timer.track("export_trees"):
            export_individual_trees(
                forest,
                forest_data,
                output_dir,
                config,
                quality_params,
                verbose=verbose,
                timer=timer,
            )

    except ValueError as e:
        if _is_bone_limit_error(e):
            _handle_bone_limit_error(e)
        raise

    except Exception as e:
        logger.warning("Export failed: %s", e)
