#!/usr/bin/env python3
"""Parameter sweep to explore DBH calibration levers in Grove.

Runs 25-cycle growth simulations with systematic parameter variations to
measure their effect on DBH. Tests untried parameters (thicken_join,
thicken_deadwood, thicken_base_shape) alongside known levers.

Usage:
    python src/growpy/cli/sweep_dbh_params.py
    python src/growpy/cli/sweep_dbh_params.py --cycles 15
    python src/growpy/cli/sweep_dbh_params.py --species "European beech"
"""

import argparse
import json
import logging
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add src to path for Grove imports
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "the_grove_23" / "modules"))

logger = logging.getLogger(__name__)

SCRIPT_DIR = Path(__file__).parent.parent.parent.parent
PRESETS_DIR = SCRIPT_DIR / "data" / "assets" / "presets"

# Species to test (common name -> preset filename stem)
SPECIES_MAP = {
    "Norway spruce": "norway_spruce",
    "European beech": "european_beech",
    "European oak": "european_oak",
}

# Parameters to sweep and their test values
# Format: param_name -> list of values to test
PARAM_SWEEPS = {
    "thicken_join": [0.0, 0.2, 0.4, 0.6, 0.8, 1.0],
    "thicken_deadwood": [0.0, 0.1, 0.2, 0.3],
    "thicken_base_shape": [0.0, 0.05, 0.1, 0.2, 0.4],
    "thicken_base_scale": [1.0, 1.1, 1.2, 1.5],
    "thicken_base_buttress": [0.0, 0.5, 1.0, 2.0],
    "thicken_tips": [0.001, 0.003, 0.005, 0.007, 0.01],
    "grow_nodes": [2, 3, 4, 6],
}


def run_single_simulation(
    species_key: str,
    param_overrides: Dict[str, float],
    cycles: int = 25,
    seed: int = 42,
) -> Tuple[float, float, List[float], List[float]]:
    """Run a single growth simulation and return final height + DBH.

    Returns:
        (final_height, final_dbh, height_curve, dbh_curve)
    """
    import the_grove_23_core as gc

    preset_path = PRESETS_DIR / f"{species_key}.seed.json"
    with open(preset_path) as f:
        preset_data = json.load(f)

    # Remove calibration data so we measure raw parameter effects
    preset_data.pop("_yield_table_calibration", None)
    # Remove curve overrides
    keys_to_remove = [k for k in preset_data if k.endswith("_curve")]
    for k in keys_to_remove:
        del preset_data[k]

    # Apply longevity overrides (prevent tree death)
    preset_data["drop_decay"] = 0.1
    preset_data["drop_weak"] = 0.1
    preset_data["drop_shaded"] = 0.0
    preset_data["drop_obsolete"] = 0.0

    # Apply test parameter overrides
    for param, value in param_overrides.items():
        preset_data[param] = value

    grove = gc.Grove()
    grove.clear_trees()
    grove.set_random_seed(seed)

    preset_json = json.dumps(preset_data)
    properties = gc.io.properties_from_json_string(preset_json)
    grove.set_properties(properties)

    grove.clear_trees()
    grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

    heights = []
    dbhs = []
    max_h = 0.0
    max_d = 0.0

    for cycle in range(cycles):
        grove.simulate(1)

        if grove.trees and len(grove.trees) > 0:
            tree = grove.trees[0]

            # Height: max z across all nodes
            def find_max_z(branch):
                local_max = 0.0
                if hasattr(branch, "nodes") and branch.nodes:
                    for node in branch.nodes:
                        if hasattr(node, "pos") and node.pos.z > local_max:
                            local_max = node.pos.z
                        if hasattr(node, "side_branches") and node.side_branches:
                            for sb in node.side_branches:
                                side_max = find_max_z(sb)
                                if side_max > local_max:
                                    local_max = side_max
                return local_max

            h = find_max_z(tree)
            if h > max_h:
                max_h = h

            # DBH at 1.3m
            d = _measure_dbh(tree, 1.3)
            if d > max_d:
                max_d = d

        heights.append(max_h)
        dbhs.append(max_d)

    return max_h, max_d, heights, dbhs


def _measure_dbh(tree, target_height: float = 1.3) -> float:
    """Measure diameter at breast height via trunk node interpolation."""
    if not hasattr(tree, "nodes") or not tree.nodes:
        return 0.0

    trunk_nodes = []
    for node in tree.nodes:
        if hasattr(node, "pos") and hasattr(node, "radius"):
            trunk_nodes.append({"height": node.pos.z, "radius": node.radius})

    if not trunk_nodes:
        return 0.0

    trunk_nodes.sort(key=lambda x: x["height"])

    if trunk_nodes[-1]["height"] < target_height:
        return 0.0

    node_below = None
    node_above = None
    for tn in trunk_nodes:
        if tn["height"] <= target_height:
            node_below = tn
        elif node_above is None:
            node_above = tn
            break

    if node_below and node_below["height"] == target_height:
        return node_below["radius"] * 2.0
    if node_below is None:
        return 0.0
    if node_above is None:
        return node_below["radius"] * 2.0

    ratio = (target_height - node_below["height"]) / (
        node_above["height"] - node_below["height"]
    )
    r = node_below["radius"] + ratio * (node_above["radius"] - node_below["radius"])
    return r * 2.0


def run_sweep(
    species_filter: Optional[str] = None,
    cycles: int = 25,
) -> Dict:
    """Run parameter sweep across species and parameters."""
    results = {}

    species_to_test = SPECIES_MAP
    if species_filter:
        species_to_test = {
            k: v for k, v in SPECIES_MAP.items() if k == species_filter
        }

    for species_name, species_key in species_to_test.items():
        print(f"\n{'='*70}")
        print(f"  {species_name} ({cycles} cycles)")
        print(f"{'='*70}")

        # Baseline: no overrides (raw preset with longevity protection)
        t0 = time.time()
        base_h, base_d, base_hc, base_dc = run_single_simulation(
            species_key, {}, cycles
        )
        dt = time.time() - t0
        print(f"\n  BASELINE: height={base_h:.2f}m, DBH={base_d*100:.1f}cm ({dt:.1f}s)")

        results[species_name] = {
            "baseline": {
                "height": base_h,
                "dbh": base_d,
                "height_curve": base_hc,
                "dbh_curve": base_dc,
            },
            "sweeps": {},
        }

        # Load preset defaults for reference
        preset_path = PRESETS_DIR / f"{species_key}.seed.json"
        with open(preset_path) as f:
            preset = json.load(f)

        for param, values in PARAM_SWEEPS.items():
            default_val = preset.get(param, "N/A")
            print(f"\n  {param} (default={default_val}):")

            param_results = []
            for val in values:
                is_default = (val == default_val)
                t0 = time.time()
                h, d, hc, dc = run_single_simulation(
                    species_key, {param: val}, cycles
                )
                dt = time.time() - t0

                delta_h = h - base_h
                delta_d = (d - base_d) * 100  # cm

                marker = " *" if is_default else ""
                print(
                    f"    {param}={val:<6} -> "
                    f"H={h:.2f}m ({delta_h:+.2f}), "
                    f"DBH={d*100:.1f}cm ({delta_d:+.1f}cm) "
                    f"[{dt:.1f}s]{marker}"
                )

                param_results.append({
                    "value": val,
                    "height": h,
                    "dbh": d,
                    "delta_height": delta_h,
                    "delta_dbh": delta_d,
                    "is_default": is_default,
                })

            results[species_name]["sweeps"][param] = param_results

    return results


def print_summary(results: Dict) -> None:
    """Print a summary of which parameters have the most DBH impact."""
    print(f"\n\n{'='*70}")
    print("  SUMMARY: Parameters ranked by DBH reduction potential")
    print(f"{'='*70}")

    for species_name, data in results.items():
        base_dbh = data["baseline"]["dbh"] * 100  # cm
        print(f"\n  {species_name} (baseline DBH: {base_dbh:.1f}cm)")
        print(f"  {'-'*60}")

        param_impacts = []
        for param, sweep in data["sweeps"].items():
            # Find the value that gives minimum DBH
            min_entry = min(sweep, key=lambda x: x["dbh"])
            max_entry = max(sweep, key=lambda x: x["dbh"])
            dbh_range = (max_entry["dbh"] - min_entry["dbh"]) * 100

            param_impacts.append({
                "param": param,
                "min_dbh": min_entry["dbh"] * 100,
                "min_val": min_entry["value"],
                "max_dbh": max_entry["dbh"] * 100,
                "max_val": max_entry["value"],
                "range": dbh_range,
                "min_height": min_entry["height"],
                "height_cost": min_entry["delta_height"],
            })

        # Sort by DBH range (biggest lever first)
        param_impacts.sort(key=lambda x: x["range"], reverse=True)

        for pi in param_impacts:
            print(
                f"    {pi['param']:<25} "
                f"DBH range: {pi['range']:5.1f}cm "
                f"(min={pi['min_dbh']:.1f}cm @{pi['min_val']}, "
                f"max={pi['max_dbh']:.1f}cm @{pi['max_val']}) "
                f"H cost: {pi['height_cost']:+.2f}m"
            )


def main():
    parser = argparse.ArgumentParser(
        description="Sweep Grove parameters to find DBH calibration levers",
    )
    parser.add_argument(
        "--cycles", type=int, default=25,
        help="Growth cycles per simulation (default: 25)",
    )
    parser.add_argument(
        "--species", type=str, default=None,
        help="Single species to test (default: all 3)",
    )
    parser.add_argument(
        "--output", type=Path, default=None,
        help="Save results JSON to file",
    )

    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING)

    print(f"Parameter sweep: {args.cycles} cycles, "
          f"{'all species' if not args.species else args.species}")
    print(f"Testing {len(PARAM_SWEEPS)} parameters x "
          f"{sum(len(v) for v in PARAM_SWEEPS.values())} values each")

    results = run_sweep(args.species, args.cycles)
    print_summary(results)

    if args.output:
        # Strip curves for compact JSON
        compact = {}
        for sp, data in results.items():
            compact[sp] = {
                "baseline": {
                    "height": data["baseline"]["height"],
                    "dbh": data["baseline"]["dbh"],
                },
                "sweeps": data["sweeps"],
            }
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(compact, f, indent=2)
        print(f"\nResults saved to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
