"""Forest simulation functions with Grove API integration."""

import logging
import math
import time
from typing import Any

logger = logging.getLogger(__name__)

import pandas as pd
import the_grove_23_core as gc
from tqdm import tqdm

from ..config import get_config
from ..config.preset_overrides import PresetOverrides, get_species_overrides
from ..utils.log import is_verbose
from .grove import add_tree_to_grove, create_grove, enable_surround
from .tree import extract_tree_measurements

# Type alias for snapshot data
# Dict[cycle, Dict[species, List[(model, skeleton, bones_info, height, dbh)]]]
SnapshotData = dict[int, dict[str, list[tuple[Any, Any, Any, float, float]]]]


def create_forest(
    forest_data: pd.DataFrame,
) -> list[tuple[gc.Grove, str, int, list[int]]]:
    """Create groves for each species in forest data.

    When *individual_type* is present in the DataFrame, trees are split into
    separate groves per (species, individual_type).  This prevents the Grove
    engine's intra-grove shade from interfering between independent growth
    contexts (e.g. an open-grown tree at x=100 sharing a grove with a
    competition cluster at origin).

    Args:
        forest_data: DataFrame with columns: x, y, species, z (optional),
            delay (optional), fid (optional), individual_type (optional)

    Returns:
        List of tuples: (grove_instance, species_name, tree_count, fid_list)
        fid_list contains the original CSV fids for each tree in the grove (in order).
        When individual_type splitting is active, multiple entries may share the
        same species_name (one per context).
    """
    if "z" not in forest_data.columns:
        forest_data["z"] = 0.0

    # Split by individual_type when available to prevent intra-grove shade
    # killing isolated open-grown trees in the same grove as competition clusters
    has_individual_type = (
        "individual_type" in forest_data.columns
        and forest_data["individual_type"].notna().any()
    )
    groupby_key = ["species", "individual_type"] if has_individual_type else "species"

    forest = []
    for group_key, species_data in forest_data.groupby(groupby_key, sort=False):
        species_name = str(group_key[0]) if has_individual_type else str(group_key)
        grove = create_grove(species_name)

        # Collect fids for this grove (use row index if fid column not present)
        fids = []
        for idx, row in species_data.iterrows():
            position = (row["x"], row["y"], row["z"])
            delay = int(row.get("delay", 0))
            add_tree_to_grove(grove, position, delay)
            fid = int(row["fid"]) if "fid" in row else int(idx)
            fids.append(fid)

        # Grove's Surround shell replaces multi-tree competition clusters for
        # single-tree contexts: enable it when the tree opts in via
        # individual_type == "surround", or when surround is globally enabled.
        cfg = get_config()
        itype = str(group_key[1]).strip() if has_individual_type else ""
        if len(species_data) == 1 and (itype == "surround" or cfg.surround_enabled):
            applied = enable_surround(
                grove,
                density=cfg.surround_density,
                distance=cfg.surround_distance,
                height=cfg.surround_height,
                grow=cfg.surround_grow,
            )
            if applied:
                logger.info(
                    "Surround enabled for %s (density=%.2f distance=%.1f height=%.1f)",
                    species_name,
                    cfg.surround_density,
                    cfg.surround_distance,
                    cfg.surround_height,
                )
            else:
                logger.warning(
                    "Surround requested for %s but this Grove build does not "
                    "expose surround properties",
                    species_name,
                )

        forest.append((grove, species_name, len(species_data), fids))

    return forest


def _compute_grove_offsets(
    forest: list[tuple[gc.Grove, str, int, list[int]]],
) -> list[int]:
    """Compute the species-global tree index offset for each grove.

    When multiple groves share a species name (context splitting), each grove's
    trees need a unique global index within that species to match the original
    CSV row ordering.  Returns a list parallel to *forest* with the offset for
    each grove.
    """
    offsets = []
    species_count: dict[str, int] = {}
    for _grove, species_name, tree_count, _fids in forest:
        offsets.append(species_count.get(species_name, 0))
        species_count[species_name] = species_count.get(species_name, 0) + tree_count
    return offsets


def _run_single_growth_cycle(
    forest: list[tuple[gc.Grove, str, int, list[int]]],
    groves: list[gc.Grove],
    cycle: int,
    total_cycles: int,
    species_overrides: dict[str, PresetOverrides],
    preset_overrides: PresetOverrides | None,
    frozen_grove_indices: set | None = None,
) -> None:
    """Run one growth cycle: apply overrides, shade competition, simulate.

    Args:
        frozen_grove_indices: Set of grove indices to skip simulation for.
            Frozen groves still contribute shade geometry but do not grow.
    """
    frozen = frozen_grove_indices or set()

    for grove_idx, (grove, species_name, _, _) in enumerate(forest):
        if grove_idx in frozen:
            continue
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

    for grove_idx, (grove, _, _, _) in enumerate(forest):
        if grove_idx in frozen:
            continue
        grove.weigh_and_bend()
        grove.simulate(1)


def _apply_smoothing(
    forest: list[tuple[gc.Grove, str, int, list[int]]],
    smooth_iterations: int,
) -> None:
    """Apply branch smoothing to all groves after simulation."""
    if smooth_iterations <= 0:
        return

    logger.info("PHASE 2: BRANCH SMOOTHING (%d iterations)", smooth_iterations)

    smooth_start = time.time()
    for grove, species_name, _, _ in forest:
        for _ in tqdm(
            range(smooth_iterations), desc=f"Smoothing {species_name}", unit="iter",
            disable=not is_verbose(),
        ):
            grove.smooth()
        grove.weigh_and_bend()
        logger.info("[Smoothing] Completed for %s", species_name)

    logger.info("Branch smoothing complete (%.1fs)", time.time() - smooth_start)


def simulate_forest_growth(
    forest: list[tuple[gc.Grove, str, int, list[int]]],
    cycles: int,
    smooth_iterations: int = 10,
    preset_overrides: PresetOverrides | None = None,
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
    species_overrides: dict[str, PresetOverrides] = {}
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
    for cycle in tqdm(range(cycles), desc="Simulating growth cycles", unit="cycle", disable=not is_verbose()):
        _run_single_growth_cycle(
            forest, groves, cycle, cycles, species_overrides, preset_overrides
        )

    logger.info("Growth simulation complete (%.1fs)", time.time() - growth_start)

    _apply_smoothing(forest, smooth_iterations)


def simulate_forest_growth_with_snapshots(
    forest: list[tuple[gc.Grove, str, int, list[int]]],
    max_cycles: int,
    snapshot_cycles: list[int],
    smooth_iterations: int = 10,
    preset_overrides: PresetOverrides | None = None,
    use_species_curves: bool = True,
    quality_params: dict | None = None,
    species_snapshot_cycles: dict[str, dict[int, float]] | None = None,
    height_interval: float = 0.0,
    max_height: float = 0.0,
    species_max_height: dict[str, float] | None = None,
    competition_distance_increase: float = 0.0,
    forest_data: pd.DataFrame | None = None,
) -> tuple[SnapshotData, dict[int, dict[str, dict[int, float]]]]:
    """Simulate forest growth and capture snapshots at height milestones.

    When height_interval > 0, uses height-threshold-based snapshots: measures
    tree heights at every cycle (cheap) and builds models only when any tree
    crosses a new height milestone (e.g. 5m, 10m, 15m). No growth model
    prediction is needed -- the simulation runs until all milestones up to
    max_height are captured, growth plateaus, or the cycle limit is reached.

    When height_interval == 0, falls back to cycle-based snapshots (legacy).

    Args:
        forest: List of (grove, species_name, tree_count, fid_list) tuples from create_forest()
        max_cycles: Maximum number of growth cycles (hard safety cap)
        snapshot_cycles: List of cycle numbers for cycle-based mode (used when height_interval==0)
        smooth_iterations: Number of smoothing iterations (default: 10)
        preset_overrides: Optional PresetOverrides for dynamic parameter adjustment
        use_species_curves: Load curves from species seed.json files (default: True)
        quality_params: Quality parameters for model building (vertices, etc.)
        species_snapshot_cycles: Optional per-species cycle filter (legacy, ignored in height mode)
        height_interval: Height interval in meters for threshold-based snapshots (0 = legacy mode)
        max_height: Global height ceiling in meters for early stopping (0 = no global cap).
            Acts as an upper bound across all species (e.g. the --max-height test flag).
        species_max_height: Optional per-species height ceiling in meters (from each
            species' calibrated growth model). When set, each species stops capturing
            milestones above its own max and is considered complete at that height.
            Combined with max_height by taking the lower of the two when both apply.

    Returns:
        Tuple of:
        - SnapshotData: Dict[cycle, Dict[species, List[(model, skeleton, bones_info, height, dbh)]]]
        - milestone_map: Dict[cycle, Dict[species, Dict[tree_idx, milestone_height]]]
          Maps each snapshot to the milestone height each tree was captured at.
          Empty dict in legacy mode.
    """
    groves = [grove for grove, _, _, _ in forest]
    snapshots: SnapshotData = {}
    milestone_map: dict[int, dict[str, dict[int, float]]] = {}

    if quality_params is None:
        quality_params = {"vertices": 16}

    # Load per-species overrides from their seed.json files
    species_overrides: dict[str, PresetOverrides] = {}
    if use_species_curves:
        for grove, species_name, _, _ in forest:
            species_ov = get_species_overrides(species_name)
            if not species_ov.is_empty():
                species_overrides[species_name] = species_ov

    use_height_mode = height_interval > 0

    if use_height_mode:
        logger.info(
            "PHASE 1: GROWTH SIMULATION WITH HEIGHT MILESTONES "
            "(up to %d cycles, %.0fm interval, %.0fm target)",
            max_cycles,
            height_interval,
            max_height,
        )
    else:
        # Legacy: validate and sort snapshot cycles
        snapshot_cycles = sorted([c for c in snapshot_cycles if 0 < c <= max_cycles])
        if not snapshot_cycles:
            logger.warning("No valid snapshot cycles provided")
            return snapshots, milestone_map
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

    if use_height_mode:
        snapshots, milestone_map = _simulate_height_threshold_mode(
            forest, groves, max_cycles, height_interval,
            species_overrides, preset_overrides, quality_params,
            max_height=max_height,
            species_max_height=species_max_height,
            competition_distance_increase=competition_distance_increase,
            forest_data=forest_data,
        )
    else:
        snapshots = _simulate_cycle_based_mode(
            forest, groves, max_cycles, snapshot_cycles,
            species_overrides, preset_overrides, quality_params,
            species_snapshot_cycles,
        )

    logger.info(
        "Growth simulation complete (%.1fs) - %d snapshots captured",
        time.time() - growth_start,
        len(snapshots),
    )

    # Smoothing must run AFTER the snapshot loop - it permanently modifies grove state
    _apply_smoothing(forest, smooth_iterations)

    return snapshots, milestone_map


def _apply_competition_thinning(
    forest: list[tuple[gc.Grove, str, int, list[int]]],
    forest_data: pd.DataFrame,
    distance_increase: float,
    thinning_count: int,
    target_distances: dict[str, float] | None = None,
    current_distances: dict[int, float] | None = None,
) -> None:
    """Move competition neighbor trees outward from center to simulate thinning.

    Supports two modes:
    1. **Group-based** (preferred): When ``target_distances`` and
       ``current_distances`` are provided, repositions each neighbor to the
       species-specific target distance from center.
    2. **Legacy fixed-increment**: When ``target_distances`` is None, moves
       all neighbors outward by ``distance_increase`` meters (old behavior).

    Args:
        forest: List of (grove, species_name, tree_count, fid_list) tuples.
        forest_data: DataFrame with columns x, y, fid, individual_type.
        distance_increase: Legacy meters to move outward per thinning event.
        thinning_count: How many thinning events have been applied so far.
        target_distances: Per-species absolute target distance from center.
            When provided, overrides distance_increase.
        current_distances: Mutable dict of fid -> current distance from center.
            Updated in place after repositioning.
    """
    if not target_distances and distance_increase <= 0:
        return

    has_itype = "individual_type" in forest_data.columns
    if not has_itype:
        return

    total_moved = 0

    for grove, species_name, tree_count, fids in forest:
        for tree_idx, fid in enumerate(fids):
            if fid < 100:
                continue

            row = forest_data[forest_data["fid"] == fid]
            if row.empty:
                continue

            itype = str(row.iloc[0].get("individual_type", "")).strip()
            if itype != "competition":
                continue

            init_x = float(row.iloc[0]["x"])
            init_y = float(row.iloc[0]["y"])
            init_dist = math.sqrt(init_x * init_x + init_y * init_y)
            if init_dist < 0.001:
                continue

            # Compute the radial displacement needed
            if target_distances and current_distances is not None:
                target = target_distances.get(species_name)
                if target is None:
                    continue
                cur_dist = current_distances.get(fid, init_dist)
                delta = target - cur_dist
                if delta <= 0.01:
                    continue
                # Update tracking
                current_distances[fid] = target
            else:
                delta = distance_increase

            # Direction: along the initial position vector (radial from origin)
            dx = (init_x / init_dist) * delta
            dy = (init_y / init_dist) * delta

            grove.replant_tree(tree_idx, gc.Vector(dx, dy, 0.0), gc.Rotation(gc.Vector(0, 0, 1), 0.0))
            total_moved += 1

    if total_moved > 0:
        if target_distances:
            targets_str = ", ".join(
                f"{sp}: {d:.1f}m" for sp, d in target_distances.items()
            )
            logger.info(
                "[Thinning] Moved %d neighbor tree(s) to target distances (%s)",
                total_moved, targets_str,
            )
        else:
            cumulative = distance_increase * (thinning_count + 1)
            logger.info(
                "[Thinning] Moved %d neighbor tree(s) outward by %.1fm "
                "(cumulative: %.1fm from initial positions)",
                total_moved, distance_increase, cumulative,
            )


def _simulate_height_threshold_mode(
    forest: list[tuple[gc.Grove, str, int, list[int]]],
    groves: list[gc.Grove],
    max_cycles: int,
    height_interval: float,
    species_overrides: dict[str, PresetOverrides],
    preset_overrides: PresetOverrides | None,
    quality_params: dict,
    max_height: float = 0.0,
    species_max_height: dict[str, float] | None = None,
    plateau_cycles: int = 10,
    competition_distance_increase: float = 0.0,
    forest_data: pd.DataFrame | None = None,
) -> tuple[SnapshotData, dict[int, dict[str, dict[int, float]]]]:
    """Run simulation with height-threshold-based snapshots.

    Grows trees cycle by cycle, capturing snapshots whenever any tree crosses
    a height milestone (e.g. 5m, 10m, 15m). No growth model prediction is
    used -- the simulation simply runs until all reachable milestones up to
    max_height have been captured, growth has plateaued, or the cycle limit
    (max_cycles) is reached.

    Stop conditions (whichever comes first):
        1. All trees have captured all milestones up to max_height
        2. No tree gained height for ``plateau_cycles`` consecutive cycles
        3. Hard cycle cap (max_cycles) is reached

    Args:
        max_height: Target height ceiling in meters.  When > 0, the
            simulation can stop early once every tree has captured all
            milestones up to this height.  0 = run until max_cycles.
        plateau_cycles: Stop after this many consecutive cycles with no
            height increase across any tree (default: 10).
        competition_distance_increase: Meters to move competition neighbor
            trees outward at each height milestone (0 = disabled).
        forest_data: DataFrame with tree positions and individual_type
            (required when competition_distance_increase > 0).
    """

    snapshots: SnapshotData = {}
    milestone_map: dict[int, dict[str, dict[int, float]]] = {}

    # Compute species-global tree index offsets for split groves
    grove_offsets = _compute_grove_offsets(forest)

    # Track captured milestones per tree
    # Key: (species_name, global_tree_idx)
    captured: dict[tuple[str, int], set] = {}

    # Per-species height ceiling: the species' own calibrated max, bounded by the
    # global max_height cap (--max-height) when one is set.  0 = no ceiling.
    def _ceiling_for(species_name: str) -> float:
        sc = 0.0
        if species_max_height:
            sc = float(species_max_height.get(species_name, 0.0) or 0.0)
        if max_height > 0:
            return min(sc, max_height) if sc > 0 else max_height
        return sc

    species_ceiling: dict[str, float] = {}
    for _g, species_name, _tc, _f in forest:
        if species_name not in species_ceiling:
            species_ceiling[species_name] = _ceiling_for(species_name)

    # Build set of target milestones per tree (for early-stop check), bounded by
    # each species' own ceiling.  Species without a ceiling run to plateau/cap.
    target_milestones: dict[tuple[str, int], set] = {}
    for grove_idx, (_grove, species_name, tree_count, _fids) in enumerate(forest):
        ceiling = species_ceiling.get(species_name, 0.0)
        if ceiling <= 0:
            continue
        offset = grove_offsets[grove_idx]
        milestones = set()
        m = height_interval
        while m <= ceiling:
            milestones.add(m)
            m += height_interval
        for tree_idx in range(tree_count):
            target_milestones[(species_name, offset + tree_idx)] = milestones

    # Count total milestone captures for progress reporting
    total_captures = 0

    # Plateau detection: track max height per tree across cycles
    prev_max_heights: dict[tuple[str, int], float] = {}
    cycles_without_growth = 0

    # Competition thinning state
    thinning_count = 0
    use_legacy_thinning = (
        competition_distance_increase > 0 and forest_data is not None
    )

    # Group-based thinning: look up config for per-species scheduling
    from ..config.core import get_global_config
    config = get_global_config()
    use_group_thinning = (
        config is not None
        and bool(config.competition_groups)
        and forest_data is not None
    )

    # Track current distance from center per neighbor fid (for group-based thinning)
    neighbor_current_distances: dict[int, float] = {}
    if use_group_thinning and forest_data is not None:
        for _, row in forest_data.iterrows():
            fid = int(row["fid"]) if "fid" in row.index else 0
            if fid >= 100:
                x, y = float(row["x"]), float(row["y"])
                neighbor_current_distances[fid] = math.sqrt(x * x + y * y)

    use_thinning = use_legacy_thinning or use_group_thinning

    # Thinning triggers: only thin when a center competition tree (fid < 100,
    # individual_type == "competition") crosses a milestone.  Neighbor trees
    # (fid >= 100) and open-grown trees do not trigger thinning events.
    thinning_trigger_fids: set = set()
    if use_thinning and forest_data is not None:
        has_itype = "individual_type" in forest_data.columns
        for _, row in forest_data.iterrows():
            fid = int(row["fid"]) if "fid" in row.index else 0
            itype = str(row.get("individual_type", "")).strip() if has_itype else ""
            if fid < 100 and itype == "competition":
                thinning_trigger_fids.add(fid)

    cycle = 0
    pbar = tqdm(total=max_cycles, desc="Simulating growth cycles", unit="cycle", disable=not is_verbose())

    # Track frozen grove indices to save memory. Once a grove's own trees
    # have captured all their target milestones, that grove stops simulating
    # (no more branch data accumulation), independent of any other grove of
    # the same species (e.g. a fast open-grown tree no longer waits on its
    # slower, shaded competition siblings before it stops growing).
    frozen_grove_indices: set = set()

    # Build species -> grove index mapping for freezing
    species_grove_indices: dict[str, list[int]] = {}
    for grove_idx, (_grove, species_name, _tc, _fids) in enumerate(forest):
        species_grove_indices.setdefault(species_name, []).append(grove_idx)

    # Build target_milestones lookup keys per grove for completion checks
    grove_target_keys: dict[int, list[tuple[str, int]]] = {}
    for grove_idx, (_grove, species_name, tree_count, _fids) in enumerate(forest):
        offset = grove_offsets[grove_idx]
        keys = [
            (species_name, offset + tree_idx) for tree_idx in range(tree_count)
        ]
        grove_target_keys[grove_idx] = [k for k in keys if k in target_milestones]

    while cycle < max_cycles:
        cycle += 1
        pbar.update(1)

        _run_single_growth_cycle(
            forest, groves, cycle - 1, max_cycles, species_overrides, preset_overrides,
            frozen_grove_indices=frozen_grove_indices,
        )

        # Cheaply measure heights at every cycle (skip frozen groves)
        # Maps species -> tree_idx -> milestone height (lowest new crossing)
        new_crossings: dict[str, dict[int, float]] = {}
        any_growth = False

        for grove_idx, (grove, species_name, tree_count, fids) in enumerate(forest):
            if grove_idx in frozen_grove_indices:
                continue
            offset = grove_offsets[grove_idx]
            measurements = extract_tree_measurements(grove)
            for tree_idx, (height, _dbh) in enumerate(measurements):
                global_idx = offset + tree_idx
                key = (species_name, global_idx)

                # Plateau detection
                prev_h = prev_max_heights.get(key, 0.0)
                if height > prev_h + 0.01:
                    any_growth = True
                    prev_max_heights[key] = height

                # Find the lowest uncaptured milestone up to current height
                curr_milestone = math.floor(height / height_interval) * height_interval

                if curr_milestone >= height_interval:
                    ceiling = species_ceiling.get(species_name, 0.0)
                    m = height_interval
                    while m <= curr_milestone:
                        # Never capture milestones above the species ceiling
                        if ceiling > 0 and m > ceiling:
                            break
                        if m not in captured.get(key, set()):
                            new_crossings.setdefault(species_name, {})[global_idx] = m
                            break  # One milestone per tree per cycle
                        m += height_interval

        # Plateau detection
        if any_growth:
            cycles_without_growth = 0
        else:
            cycles_without_growth += 1
            if cycles_without_growth >= plateau_cycles:
                logger.info(
                    "Growth plateau detected: no height increase for %d "
                    "consecutive cycles. Stopping at cycle %d.",
                    plateau_cycles, cycle,
                )
                break

        if not new_crossings:
            continue

        # Build models for species that have new milestone crossings
        logger.info(
            "[Height Milestone] Cycle %d: %s",
            cycle,
            ", ".join(
                f"{sp} tree(s) {list(trees.keys())} -> {sorted(set(trees.values()))}m"
                for sp, trees in new_crossings.items()
            ),
        )

        snapshots[cycle] = {}
        milestone_map[cycle] = {}

        # Determine which species need model building
        species_with_crossings = set(new_crossings.keys())

        # Build models from groves and merge per species (supports split groves)
        merged_data: dict[str, list] = {}
        for grove_idx, (grove, species_name, tree_count, fids) in enumerate(forest):
            if species_name not in species_with_crossings:
                continue
            offset = grove_offsets[grove_idx]

            # Only build models for groves that contain a tree with a crossing
            grove_has_crossing = any(
                offset <= gidx < offset + tree_count
                for gidx in new_crossings.get(species_name, {})
            )
            if grove_has_crossing:
                tree_data = _build_models_for_grove(grove, species_name, cycle, quality_params)
                if tree_data:
                    merged_data.setdefault(species_name, []).extend(tree_data)
                else:
                    merged_data.setdefault(species_name, []).extend(
                        [(None, None, [], 0.0, 0.0)] * tree_count
                    )
            else:
                # Placeholder for grove without crossings at this cycle
                merged_data.setdefault(species_name, []).extend(
                    [(None, None, [], 0.0, 0.0)] * tree_count
                )

        for species_name in species_with_crossings:
            tree_data = merged_data.get(species_name, [])
            if not tree_data:
                continue
            snapshots[cycle][species_name] = tree_data
            milestone_map[cycle][species_name] = new_crossings[species_name]
            # Only commit milestones to captured for trees with valid models
            for global_idx, milestone_h in new_crossings[species_name].items():
                key = (species_name, global_idx)
                if global_idx < len(tree_data) and tree_data[global_idx][0] is not None:
                    captured.setdefault(key, set()).add(milestone_h)
                    total_captures += 1
                else:
                    logger.warning(
                        "  %s tree %d: model None at milestone %.0fm, "
                        "will retry next cycle",
                        species_name, global_idx,
                        milestone_h,
                    )

        # Freeze each grove individually once its own trees have captured
        # all their milestones (see frozen_grove_indices comment above).
        if target_milestones:
            for species_name in species_with_crossings:
                for grove_idx in species_grove_indices.get(species_name, []):
                    if grove_idx in frozen_grove_indices:
                        continue
                    keys = grove_target_keys.get(grove_idx, [])
                    if keys and all(
                        target_milestones[k] <= captured.get(k, set()) for k in keys
                    ):
                        frozen_grove_indices.add(grove_idx)
                        logger.info(
                            "[Grove Complete] %s (grove %d): all milestones "
                            "captured, freezing to save memory",
                            species_name,
                            grove_idx,
                        )

        # Apply competition thinning only when a center competition tree
        # (fid < 100, individual_type=competition) crossed a milestone.
        if use_thinning and thinning_trigger_fids:
            # Collect species that triggered thinning and their milestone heights
            triggered_species: dict[str, float] = {}
            should_thin = False
            for grove_idx, (_grove, species_name, _tc, fids) in enumerate(forest):
                offset = grove_offsets[grove_idx]
                for local_idx, fid in enumerate(fids):
                    if fid in thinning_trigger_fids:
                        global_idx = offset + local_idx
                        if (
                            species_name in new_crossings
                            and global_idx in new_crossings[species_name]
                        ):
                            milestone_h = new_crossings[species_name][global_idx]
                            triggered_species[species_name] = milestone_h
                            should_thin = True
            if should_thin:
                if use_group_thinning and config is not None:
                    # Group-based: compute per-species target distances
                    target_dists: dict[str, float] = {}
                    for sp, mh in triggered_species.items():
                        target = config.get_thinning_target(sp, mh)
                        if target is not None:
                            target_dists[sp] = target
                    if target_dists:
                        _apply_competition_thinning(
                            forest, forest_data,
                            0.0, thinning_count,
                            target_distances=target_dists,
                            current_distances=neighbor_current_distances,
                        )
                else:
                    # Legacy fixed-increment
                    _apply_competition_thinning(
                        forest, forest_data,
                        competition_distance_increase, thinning_count,
                    )
                thinning_count += 1

        # Early stop: all target milestones captured
        if target_milestones and all(
            target_milestones[key] <= captured.get(key, set())
            for key in target_milestones
        ):
            logger.info(
                "All per-species target milestones captured at cycle %d.",
                cycle,
            )
            break

    pbar.close()
    logger.info("  Height milestones captured: %d (in %d cycles)", total_captures, cycle)
    return snapshots, milestone_map


def _simulate_cycle_based_mode(
    forest: list[tuple[gc.Grove, str, int, list[int]]],
    groves: list[gc.Grove],
    max_cycles: int,
    snapshot_cycles: list[int],
    species_overrides: dict[str, PresetOverrides],
    preset_overrides: PresetOverrides | None,
    quality_params: dict,
    species_snapshot_cycles: dict[str, dict[int, float]] | None,
) -> SnapshotData:
    """Run simulation with cycle-based snapshots (legacy mode)."""
    snapshots: SnapshotData = {}
    next_snapshot_idx = 0

    for cycle in tqdm(
        range(1, max_cycles + 1), desc="Simulating growth cycles", unit="cycle",
        disable=not is_verbose(),
    ):
        _run_single_growth_cycle(
            forest, groves, cycle - 1, max_cycles, species_overrides, preset_overrides
        )

        if (
            next_snapshot_idx < len(snapshot_cycles)
            and cycle == snapshot_cycles[next_snapshot_idx]
        ):
            logger.info("[Snapshot] Capturing cycle %d", cycle)
            snapshots[cycle] = {}

            # Build models per grove and merge by species (supports split groves)
            merged_data: dict[str, list] = {}
            for grove, species_name, tree_count, fids in forest:
                if species_snapshot_cycles and species_name in species_snapshot_cycles:
                    if cycle not in species_snapshot_cycles[species_name]:
                        continue

                tree_data = _build_models_for_grove(
                    grove, species_name, cycle, quality_params
                )
                if tree_data:
                    merged_data.setdefault(species_name, []).extend(tree_data)

            for species_name, tree_data in merged_data.items():
                snapshots[cycle][species_name] = tree_data

            next_snapshot_idx += 1

    return snapshots


def _build_models_for_grove(
    grove: gc.Grove,
    species_name: str,
    cycle: int,
    quality_params: dict,
) -> list[tuple[Any, Any, Any, float, float]]:
    """Build skeleton, bones, and models for all trees in a grove.

    Returns list of (model, skeleton, bones_info, height, dbh) per tree.
    """
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
        skeleton = skeletons[tree_idx] if tree_idx < len(skeletons) else None
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

    if tree_snapshots:
        logger.info(
            "  %s: %d trees (h=%.1fm, d=%.1fcm)",
            species_name,
            len(tree_snapshots),
            measurements[0][0] if measurements else 0.0,
            measurements[0][1] * 100 if measurements else 0.0,
        )

    return tree_snapshots


def _split_bones_by_tree(all_bones: list, num_trees: int) -> list[list]:
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
    tree_bones: list[list] = []
    current: list = []
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
