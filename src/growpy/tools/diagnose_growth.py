#!/usr/bin/env python3
"""Diagnose growth simulation issues by printing per-cycle measurements.

Runs a single-species grove for N cycles and prints height, DBH,
vertex count, and bounding box at each cycle to identify where
growth stalls or geometry gets mangled.

Usage:
    conda run -n growpy python src/growpy/tools/diagnose_growth.py [species] [cycles] [--raw]

    --raw    Use raw preset without calibration overrides
"""

import bpy

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

import sys
from pathlib import Path

import the_grove_23_core as gc

from growpy import get_config
from growpy.config.preset_overrides import get_species_overrides, PresetOverrides
from growpy.core.grove import add_tree_to_grove, create_grove
from growpy.core.tree import extract_tree_measurements


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Diagnose growth per cycle for a species.")
    parser.add_argument("species", nargs="?", default="Norway spruce", help="Species name")
    parser.add_argument("max_cycles", nargs="?", type=int, default=15, help="Max growth cycles")
    parser.add_argument("--raw", action="store_true", help="Use raw preset without calibration")
    parsed = parser.parse_args()

    raw_mode = parsed.raw
    species = parsed.species
    max_cycles = parsed.max_cycles
    config = get_config()

    grove = create_grove(species)
    add_tree_to_grove(grove, (0.0, 0.0, 0.0))

    if raw_mode:
        species_overrides = PresetOverrides()
        print(f"Species: {species} [RAW PRESET - no calibration]")
    else:
        species_overrides = get_species_overrides(species)
        print(f"Species: {species}")

    print(f"Cycles: {max_cycles}")
    print(f"Overrides empty: {species_overrides.is_empty()}")
    if species_overrides.cycle_array_overrides:
        for arr in species_overrides.cycle_array_overrides:
            print(f"  cycle_array: {arr.param} ({len(arr.values)} values)")
    if species_overrides.static_overrides:
        print(f"  static: {species_overrides.static_overrides}")

    # Show key preset values
    props = grove.get_properties()
    print(f"  drop_decay={props.drop_decay}, drop_weak={props.drop_weak}, "
          f"grow_length={props.grow_length}")
    print()

    print(f"{'Cycle':>5} | {'Height':>8} | {'DBH(cm)':>8} | {'Verts':>7} | "
          f"{'BBox Y':>8} | {'BBox X':>8} | {'BBox Z':>8} | {'Faces':>7}")
    print("-" * 85)

    for cycle in range(1, max_cycles + 1):
        if not species_overrides.is_empty():
            species_overrides.apply_to_grove(grove, cycle - 1, max_cycles)

        grove.weigh_and_bend()
        grove.simulate(1)

        models = grove.build_models({
            "resolution": 8,
            "resolution_reduce": 0.5,
            "build_cutoff_age": 0,
            "build_cutoff_thickness": 0.0,
            "build_blend": False,
            "build_end_cap": False,
        })

        measurements = extract_tree_measurements(grove)
        height, dbh = measurements[0] if measurements else (0.0, 0.0)

        if models and models[0]:
            model = models[0]
            points = model.points
            n_verts = len(points)
            n_faces = len(model.faces) if hasattr(model, 'faces') else 0

            if points:
                xs = [p.x for p in points]
                ys = [p.y for p in points]
                zs = [p.z for p in points]
                bbox_y = max(ys) - min(ys)
                bbox_x = max(xs) - min(xs)
                bbox_z = max(zs) - min(zs)
            else:
                bbox_y = bbox_x = bbox_z = 0.0
        else:
            n_verts = 0
            n_faces = 0
            bbox_y = bbox_x = bbox_z = 0.0

        print(f"{cycle:5d} | {height:8.3f} | {dbh * 100:8.2f} | {n_verts:7d} | "
              f"{bbox_y:8.3f} | {bbox_x:8.3f} | {bbox_z:8.3f} | {n_faces:7d}")

    print()
    print("Note: Height/DBH are from Grove's internal measurement.")
    print("      BBox Y/X/Z are from actual model vertex positions.")
    print("      If BBox Y << Height, the mesh is being squashed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
