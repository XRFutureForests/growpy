"""Forest simulation functions with Grove API integration."""

import logging
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

import pandas as pd
import the_grove_23_core as gc
from tqdm import tqdm

from ..config.preset_overrides import PresetOverrides, get_species_overrides
from .grove import add_tree_to_grove, create_grove
from .tree import extract_tree_measurements

# Type alias for snapshot data
# Dict[cycle, Dict[species, List[(model, skeleton, bones_info, height, dbh)]]]
SnapshotData = Dict[int, Dict[str, List[Tuple[Any, Any, Any, float, float]]]]


def create_forest(
    forest_data: pd.DataFrame,
) -> List[Tuple[gc.Grove, str, int, List[int]]]:
    """Create groves for each species in forest data.

    Args:
        forest_data: DataFrame with columns: x, y, species, z (optional), delay (optional), fid (optional)

    Returns:
        List of tuples: (grove_instance, species_name, tree_count, fid_list)
        fid_list contains the original CSV fids for each tree in the grove (in order)
    """
    if "z" not in forest_data.columns:
        forest_data["z"] = 0.0

    forest = []
    for species_name, species_data in forest_data.groupby("species"):
        grove = create_grove(str(species_name))

        # Collect fids for this species (use row index if fid column not present)
        fids = []
        for idx, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = int(row.get("delay", 0))
            add_tree_to_grove(grove, position, delay)
            # Use fid column if available, otherwise use DataFrame index
            fid = int(row["fid"]) if "fid" in row else int(idx)
            fids.append(fid)

        forest.append((grove, str(species_name), len(species_data), fids))

    return forest


def _run_single_growth_cycle(
    forest: List[Tuple[gc.Grove, str, int, List[int]]],
    groves: List[gc.Grove],
    cycle: int,
    total_cycles: int,
    species_overrides: Dict[str, PresetOverrides],
    preset_overrides: Optional[PresetOverrides],
) -> None:
    """Run one growth cycle: apply overrides, shade competition, simulate."""
    for grove, species_name, _, _ in forest:
        if species_name in species_overrides:
            species_overrides[species_name].apply_to_grove(grove, cycle, total_cycles)
        if preset_overrides and not preset_overrides.is_empty():
            preset_overrides.apply_to_grove(grove, cycle, total_cycles)

    if len(groves) > 1:
        all_coords = []
        for grove in groves:
            all_coords.extend(grove.build_shade_geometry_flat())
        for grove in groves:
            grove.calculate_shade_together(all_coords)

    for grove, _, _, _ in forest:
        grove.weigh_and_bend()
        grove.simulate(1)


def _apply_smoothing(
    forest: List[Tuple[gc.Grove, str, int, List[int]]],
    smooth_iterations: int,
) -> None:
    """Apply branch smoothing to all groves after simulation."""
    if smooth_iterations <= 0:
        return

    logger.info("PHASE 2: BRANCH SMOOTHING (%d iterations)", smooth_iterations)

    smooth_start = time.time()
    for grove, species_name, _, _ in forest:
        for _ in tqdm(
            range(smooth_iterations), desc=f"Smoothing {species_name}", unit="iter"
        ):
            grove.smooth()
        grove.weigh_and_bend()
        logger.info("[Smoothing] Completed for %s", species_name)

    logger.info("Branch smoothing complete (%.1fs)", time.time() - smooth_start)


def simulate_forest_growth(
    forest: List[Tuple[gc.Grove, str, int, List[int]]],
    cycles: int,
    smooth_iterations: int = 10,
    preset_overrides: Optional[PresetOverrides] = None,
    use_species_curves: bool = True,
) -> None:
    """Simulate forest growth with inter-species light competition and optional smoothing.

    The smoothing workflow (applied if smooth_iterations > 0):
    1. grove.smooth() - Reduces sharp corner angles (called smooth_iterations times)
    2. grove.weigh_and_bend() - Re-calculates branch positions based on smoothed angles

    Without step 2 (weigh_and_bend), smoothing has no effect on the final geometry!

    Preset Overrides (applied in order of priority):
        1. Species curves from seed.json files (if use_species_curves=True)
        2. CLI preset_overrides (if provided, overrides species curves)

    Args:
        forest: List of (grove, species_name, tree_count, fid_list) tuples from create_forest()
        cycles: Number of growth cycles to simulate
        smooth_iterations: Number of smoothing iterations (default: 10, recommended: 10-20)
                          Set to 0 to disable smoothing entirely
        preset_overrides: Optional PresetOverrides for dynamic parameter adjustment (overrides species curves)
        use_species_curves: Load curves from species seed.json files (default: True)
    """
    groves = [grove for grove, _, _, _ in forest]

    # Load per-species overrides from their seed.json files
    species_overrides: Dict[str, PresetOverrides] = {}
    if use_species_curves:
        for grove, species_name, _, _ in forest:
            species_ov = get_species_overrides(species_name)
            if not species_ov.is_empty():
                species_overrides[species_name] = species_ov

    logger.info("PHASE 1: GROWTH SIMULATION (%d cycles)", cycles)
    if preset_overrides and not preset_overrides.is_empty():
        logger.info(
            "  CLI overrides: %d static, %d interpolated",
            len(preset_overrides.static_overrides),
            len(preset_overrides.interpolated_overrides),
        )
    for sp, ov in species_overrides.items():
        logger.info(
            "  %s curves: %d from seed.json", sp, len(ov.interpolated_overrides)
        )
        if ov.cycle_array_overrides:
            logger.info(
                "  %s cycle arrays: %d from seed.json (calibration)",
                sp,
                len(ov.cycle_array_overrides),
            )

    growth_start = time.time()
    for cycle in tqdm(range(cycles), desc="Simulating growth cycles", unit="cycle"):
        _run_single_growth_cycle(
            forest, groves, cycle, cycles, species_overrides, preset_overrides
        )

    logger.info("Growth simulation complete (%.1fs)", time.time() - growth_start)

    _apply_smoothing(forest, smooth_iterations)


def simulate_forest_growth_with_snapshots(
    forest: List[Tuple[gc.Grove, str, int, List[int]]],
    max_cycles: int,
    snapshot_cycles: List[int],
    smooth_iterations: int = 10,
    preset_overrides: Optional[PresetOverrides] = None,
    use_species_curves: bool = True,
    quality_params: Optional[Dict] = None,
    species_snapshot_cycles: Optional[Dict[str, Dict[int, float]]] = None,
) -> SnapshotData:
    """Simulate forest growth and capture snapshots at specified cycles.

    This function runs the growth simulation and builds models at each snapshot
    cycle, capturing geometry and measurements (height, DBH) for later export.

    Args:
        forest: List of (grove, species_name, tree_count, fid_list) tuples from create_forest()
        max_cycles: Maximum number of growth cycles to simulate
        snapshot_cycles: List of cycle numbers at which to capture snapshots (e.g., [10, 20, 30])
        smooth_iterations: Number of smoothing iterations (default: 10)
        preset_overrides: Optional PresetOverrides for dynamic parameter adjustment
        use_species_curves: Load curves from species seed.json files (default: True)
        quality_params: Quality parameters for model building (vertices, etc.)
        species_snapshot_cycles: Optional per-species cycle filter.
            Dict of {species_name: {cycle: target_height}}. When provided, only
            builds models for species that have a milestone at the current cycle.
            Avoids unnecessary model builds when species have different milestone cycles.

    Returns:
        SnapshotData: Dict[cycle, Dict[species, List[(model, skeleton, bones_info, height, dbh)]]]
        Each snapshot contains built models with measurements for all trees in each species grove.
    """
    groves = [grove for grove, _, _, _ in forest]
    snapshots: SnapshotData = {}

    # Validate and sort snapshot cycles
    snapshot_cycles = sorted([c for c in snapshot_cycles if 0 < c <= max_cycles])
    if not snapshot_cycles:
        logger.warning("No valid snapshot cycles provided")
        return snapshots

    if quality_params is None:
        quality_params = {"vertices": 16}

    # Load per-species overrides from their seed.json files
    species_overrides: Dict[str, PresetOverrides] = {}
    if use_species_curves:
        for grove, species_name, _, _ in forest:
            species_ov = get_species_overrides(species_name)
            if not species_ov.is_empty():
                species_overrides[species_name] = species_ov

    logger.info("PHASE 1: GROWTH SIMULATION WITH SNAPSHOTS (%d cycles)", max_cycles)
    logger.info("  Snapshots at cycles: %s", snapshot_cycles)
    if preset_overrides and not preset_overrides.is_empty():
        logger.info(
            "  CLI overrides: %d static, %d interpolated",
            len(preset_overrides.static_overrides),
            len(preset_overrides.interpolated_overrides),
        )
    for sp, ov in species_overrides.items():
        logger.info(
            "  %s curves: %d from seed.json", sp, len(ov.interpolated_overrides)
        )
        if ov.cycle_array_overrides:
            logger.info(
                "  %s cycle arrays: %d from seed.json (calibration)",
                sp,
                len(ov.cycle_array_overrides),
            )

    growth_start = time.time()
    next_snapshot_idx = 0

    for cycle in tqdm(
        range(1, max_cycles + 1), desc="Simulating growth cycles", unit="cycle"
    ):
        # cycle - 1 maps 1-based loop counter to 0-based override index
        _run_single_growth_cycle(
            forest, groves, cycle - 1, max_cycles, species_overrides, preset_overrides
        )

        # Capture snapshot if this is a snapshot cycle
        if (
            next_snapshot_idx < len(snapshot_cycles)
            and cycle == snapshot_cycles[next_snapshot_idx]
        ):
            logger.info("[Snapshot] Capturing cycle %d", cycle)
            snapshots[cycle] = {}

            for grove, species_name, tree_count, fids in forest:
                # Skip species that don't have a milestone at this cycle
                if species_snapshot_cycles and species_name in species_snapshot_cycles:
                    if cycle not in species_snapshot_cycles[species_name]:
                        continue

                # CRITICAL BUILD ORDER: skeleton -> bones -> models
                skeleton_connected = quality_params.get("skeleton_connected", True)
                skeletons = grove.build_skeletons(skeleton_connected)

                skeleton_length = quality_params.get("skeleton_length", 2.0)
                skeleton_reduce = quality_params.get("skeleton_reduce", 0.4)
                skeleton_bias = quality_params.get("skeleton_bias", 0.5)

                all_bones = grove.tag_bone_id(
                    skeleton_length,
                    skeleton_reduce**2,
                    skeleton_bias,
                    skeleton_connected,
                )
                tree_bones = _split_bones_by_tree(all_bones, len(grove.trees))

                build_options = {
                    "resolution": quality_params.get("resolution", 24),
                    "resolution_reduce": quality_params.get("resolution_reduce", 0.8),
                    "build_cutoff_age": quality_params.get("build_cutoff_age", 0),
                    "build_cutoff_thickness": quality_params.get(
                        "build_cutoff_thickness", 0.01
                    ),
                    "build_blend": quality_params.get("build_blend", True),
                    "build_end_cap": quality_params.get("build_end_cap", True),
                }
                models = grove.build_models(build_options)
                measurements = extract_tree_measurements(grove)

                if len(models) < len(grove.trees):
                    logger.warning(
                        "  %s: build_models returned %d models for %d trees at cycle %d",
                        species_name,
                        len(models),
                        len(grove.trees),
                        cycle,
                    )

                tree_snapshots = []
                for tree_idx in range(len(grove.trees)):
                    model = models[tree_idx] if tree_idx < len(models) else None
                    skeleton = (
                        skeletons[tree_idx] if tree_idx < len(skeletons) else None
                    )
                    bones = tree_bones[tree_idx] if tree_idx < len(tree_bones) else []
                    height, dbh = (
                        measurements[tree_idx]
                        if tree_idx < len(measurements)
                        else (0.0, 0.0)
                    )
                    if model is None:
                        logger.warning(
                            "  %s tree %d: model is None at cycle %d",
                            species_name,
                            tree_idx,
                            cycle,
                        )
                    tree_snapshots.append((model, skeleton, bones, height, dbh))

                snapshots[cycle][species_name] = tree_snapshots
                logger.info(
                    "  %s: %d trees (h=%.1fm, d=%.1fcm)",
                    species_name,
                    len(tree_snapshots),
                    measurements[0][0] if measurements else 0.0,
                    measurements[0][1] * 100 if measurements else 0.0,
                )

            next_snapshot_idx += 1

    logger.info(
        "Growth simulation complete (%.1fs) - %d snapshots captured",
        time.time() - growth_start,
        len(snapshots),
    )

    # Smoothing must run AFTER the snapshot loop - it permanently modifies grove state
    _apply_smoothing(forest, smooth_iterations)

    return snapshots


def _split_bones_by_tree(all_bones: List, num_trees: int) -> List[List]:
    """Split combined bone list into per-tree bone lists.

    Grove's tag_bone_id() returns bones for all trees combined, ordered by
    tree. Each tree's first bone has is_tree_root=True (bone[0]), which is
    used to detect tree boundaries. Trees with different ages or species can
    have very different bone counts, so even-division is not reliable.

    Args:
        all_bones: Combined list of bone tuples from grove.tag_bone_id()
                   Format: (is_tree_root, parent_bone_id, start, end, radius,
                            mass, is_branch_root, branch_id)
        num_trees: Expected number of trees (used only for padding)

    Returns:
        List of bone lists, one per tree
    """
    if not all_bones or num_trees == 0:
        return [[] for _ in range(num_trees)]

    # Split on is_tree_root flag (bone[0] == True marks first bone of each tree)
    tree_bones: List[List] = []
    current: List = []
    for bone in all_bones:
        if bone[0] and current:  # is_tree_root and already have bones
            tree_bones.append(current)
            current = []
        current.append(bone)
    if current:
        tree_bones.append(current)

    # Pad with empty lists if Grove returned fewer trees than expected
    while len(tree_bones) < num_trees:
        tree_bones.append([])

    return tree_bones
