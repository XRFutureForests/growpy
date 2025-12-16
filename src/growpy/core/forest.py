"""Forest simulation functions with Grove API integration."""

from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import the_grove_22_core as gc
from tqdm import tqdm

from ..config.preset_overrides import PresetOverrides, get_species_overrides
from .grove import add_tree_to_grove, create_grove


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
