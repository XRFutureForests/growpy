"""Forest simulation functions with Grove API integration."""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import the_grove_22_core as gc
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


def simulate_forest_growth(
    forest: List[Tuple[gc.Grove, str, int, List[int]]],
    cycles: int,
    smooth_iterations: int = 10,
    preset_overrides: Optional[PresetOverrides] = None,
    use_species_curves: bool = True,
) -> None:
    """Simulate forest growth with inter-species light competition and optional smoothing.

    The smoothing workflow (applied if smooth_iterations > 0):
    1. grove.smooth_minimal() - Fixes ugly kinks on thick branches (one-time operation)
    2. grove.smooth() - Reduces sharp corner angles (called smooth_iterations times)
    3. grove.weigh_and_bend() - Re-calculates branch positions based on smoothed angles

    Without step 3 (weigh_and_bend), smoothing has no effect on the final geometry!

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
    import time

    groves = [grove for grove, _, _, _ in forest]

    # Load per-species overrides from their seed.json files
    species_overrides: Dict[str, PresetOverrides] = {}
    if use_species_curves:
        for grove, species_name, _, _ in forest:
            species_ov = get_species_overrides(species_name)
            if not species_ov.is_empty():
                species_overrides[species_name] = species_ov

    print(f"\n{'='*60}")
    print(f"PHASE 1: GROWTH SIMULATION ({cycles} cycles)")
    if preset_overrides and not preset_overrides.is_empty():
        print(
            f"  CLI overrides: {len(preset_overrides.static_overrides)} static, "
            f"{len(preset_overrides.interpolated_overrides)} interpolated"
        )
    if species_overrides:
        for sp, ov in species_overrides.items():
            print(f"  {sp} curves: {len(ov.interpolated_overrides)} from seed.json")
    print(f"{'='*60}")

    growth_start = time.time()
    for cycle in tqdm(range(cycles), desc="Simulating growth cycles", unit="cycle"):
        # Apply preset overrides at each cycle (for dynamic parameter adjustment)
        for grove, species_name, _, _ in forest:
            # First apply species-specific curves from seed.json
            if species_name in species_overrides:
                species_overrides[species_name].apply_to_grove(grove, cycle, cycles)

            # Then apply CLI overrides (these take priority)
            if preset_overrides and not preset_overrides.is_empty():
                preset_overrides.apply_to_grove(grove, cycle, cycles)

        if len(groves) > 1:
            all_coords = []
            for grove in groves:
                coords = grove.create_shade_geometry_coords()
                all_coords.extend(coords)

            for grove in groves:
                grove.calculate_shade_together(all_coords)

        for grove, species_name, tree_count, fids in forest:
            grove.weigh_and_bend()
            grove.simulate(1)

    growth_elapsed = time.time() - growth_start
    print(f"\nGrowth simulation complete ({growth_elapsed:.1f}s)")

    # Apply smoothing AFTER simulation but BEFORE building
    # This reduces sharp branch angles for smoother geometry
    if smooth_iterations > 0:
        print(f"\n{'='*60}")
        print(f"PHASE 2: BRANCH SMOOTHING ({smooth_iterations} iterations)")
        print(f"{'='*60}")

        smooth_start = time.time()
        for grove, species_name, _, _ in forest:
            grove.smooth_minimal()
            # Show progress for smoothing iterations
            for i in tqdm(
                range(smooth_iterations),
                desc=f"Smoothing {species_name}",
                unit="iter",
            ):
                grove.smooth()

            # CRITICAL: Re-calculate branch bending after smoothing
            # This applies the smoothed angles to actual branch positions
            grove.weigh_and_bend()
            print(f"[Smoothing] Completed for {species_name}")

        smooth_elapsed = time.time() - smooth_start
        print(f"\nBranch smoothing complete ({smooth_elapsed:.1f}s)")


def simulate_forest_growth_with_snapshots(
    forest: List[Tuple[gc.Grove, str, int, List[int]]],
    max_cycles: int,
    snapshot_cycles: List[int],
    smooth_iterations: int = 10,
    preset_overrides: Optional[PresetOverrides] = None,
    use_species_curves: bool = True,
    quality_params: Optional[Dict] = None,
) -> SnapshotData:
    """Simulate forest growth and capture snapshots at specified cycle intervals.

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

    Returns:
        SnapshotData: Dict[cycle, Dict[species, List[(model, skeleton, bones_info, height, dbh)]]]
        Each snapshot contains built models with measurements for all trees in each species grove.
    """
    import time

    groves = [grove for grove, _, _, _ in forest]
    snapshots: SnapshotData = {}

    # Validate and sort snapshot cycles
    snapshot_cycles = sorted([c for c in snapshot_cycles if 0 < c <= max_cycles])
    if not snapshot_cycles:
        print("Warning: No valid snapshot cycles provided")
        return snapshots

    # Default quality params if not provided
    if quality_params is None:
        quality_params = {"vertices": 16}

    # Load per-species overrides from their seed.json files
    species_overrides: Dict[str, PresetOverrides] = {}
    if use_species_curves:
        for grove, species_name, _, _ in forest:
            species_ov = get_species_overrides(species_name)
            if not species_ov.is_empty():
                species_overrides[species_name] = species_ov

    print(f"\n{'='*60}")
    print(f"PHASE 1: GROWTH SIMULATION WITH SNAPSHOTS ({max_cycles} cycles)")
    print(f"  Snapshots at cycles: {snapshot_cycles}")
    if preset_overrides and not preset_overrides.is_empty():
        print(
            f"  CLI overrides: {len(preset_overrides.static_overrides)} static, "
            f"{len(preset_overrides.interpolated_overrides)} interpolated"
        )
    print(f"{'='*60}")

    growth_start = time.time()
    next_snapshot_idx = 0

    for cycle in tqdm(
        range(1, max_cycles + 1), desc="Simulating growth cycles", unit="cycle"
    ):
        # Apply preset overrides at each cycle
        for grove, species_name, _, _ in forest:
            if species_name in species_overrides:
                species_overrides[species_name].apply_to_grove(
                    grove, cycle - 1, max_cycles
                )
            if preset_overrides and not preset_overrides.is_empty():
                preset_overrides.apply_to_grove(grove, cycle - 1, max_cycles)

        # Light competition for multi-species forests
        if len(groves) > 1:
            all_coords = []
            for grove in groves:
                coords = grove.create_shade_geometry_coords()
                all_coords.extend(coords)
            for grove in groves:
                grove.calculate_shade_together(all_coords)

        # Simulate one cycle
        for grove, species_name, tree_count, fids in forest:
            grove.weigh_and_bend()
            grove.simulate(1)

        # Capture snapshot if this is a snapshot cycle
        if (
            next_snapshot_idx < len(snapshot_cycles)
            and cycle == snapshot_cycles[next_snapshot_idx]
        ):
            print(f"\n  [Snapshot] Capturing cycle {cycle}...")
            snapshots[cycle] = {}

            for grove, species_name, tree_count, fids in forest:
                # Apply minimal smoothing before building snapshot
                grove.smooth_minimal()
                for _ in range(min(smooth_iterations, 5)):  # Quick smooth for snapshots
                    grove.smooth()
                grove.weigh_and_bend()

                # CRITICAL BUILD ORDER: skeleton -> bones -> models
                # 1. Build skeletons first
                skeletons = grove.build_skeletons()

                # 2. Tag bone IDs with reduction parameters
                # Note: tag_bone_id() takes positional args: (length, reduce, bias, connected)
                skeleton_length = quality_params.get("skeleton_length", 2.0)
                skeleton_reduce = quality_params.get("skeleton_reduce", 0.4)
                skeleton_bias = quality_params.get("skeleton_bias", 0.5)
                skeleton_connected = quality_params.get("skeleton_connected", True)

                all_bones = grove.tag_bone_id(
                    skeleton_length,
                    skeleton_reduce**2,  # Squared like Grove UI does
                    skeleton_bias,
                    skeleton_connected,
                )
                tree_bones = _split_bones_by_tree(all_bones, len(grove.trees))

                # 3. NOW build models (with bone_id attributes already tagged)
                build_options = {"vertices": quality_params.get("vertices", 16)}
                models = grove.build_models(build_options)

                # Extract measurements for each tree
                measurements = extract_tree_measurements(grove)

                # Store snapshot data for each tree
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
                    tree_snapshots.append((model, skeleton, bones, height, dbh))

                snapshots[cycle][species_name] = tree_snapshots
                print(
                    f"    {species_name}: {len(tree_snapshots)} trees (h={measurements[0][0]:.1f}m, d={measurements[0][1]*100:.1f}cm)"
                )

            next_snapshot_idx += 1

    growth_elapsed = time.time() - growth_start
    print(
        f"\nGrowth simulation complete ({growth_elapsed:.1f}s) - {len(snapshots)} snapshots captured"
    )

    return snapshots


def _split_bones_by_tree(all_bones: List, num_trees: int) -> List[List]:
    """Split combined bone list into per-tree bone lists.

    Grove's tag_bone_id() returns bones for all trees combined.
    This function splits them based on tree count.

    Args:
        all_bones: Combined list of bone tuples from grove.tag_bone_id()
        num_trees: Number of trees in the grove

    Returns:
        List of bone lists, one per tree
    """
    if not all_bones or num_trees == 0:
        return [[] for _ in range(num_trees)]

    # Simple split - assumes bones are ordered by tree
    bones_per_tree = len(all_bones) // num_trees if num_trees > 0 else 0

    if bones_per_tree == 0:
        return [all_bones] + [[] for _ in range(num_trees - 1)]

    tree_bones = []
    for i in range(num_trees):
        start = i * bones_per_tree
        end = start + bones_per_tree if i < num_trees - 1 else len(all_bones)
        tree_bones.append(all_bones[start:end])

    return tree_bones
