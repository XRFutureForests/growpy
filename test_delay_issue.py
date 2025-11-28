#!/usr/bin/env python3
"""Test if delay values cause trees to not grow."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
from growpy.core.tree import calculate_growth_cycles_from_height

# Load test CSV
csv_path = Path("data/input/test.csv")
forest_data = pd.read_csv(csv_path)

print("=" * 70)
print("DELAY CALCULATION DEBUG")
print("=" * 70)

print("\nStep 1: Calculate cycles from height")
calculate_growth_cycles_from_height(forest_data)
print(forest_data[["fid", "species", "height", "growth_cycles", "delay"]])

print("\nStep 2: Simulate scaling down to limit=10")
growth_cycle_limit = 10
max_growth_cycles = forest_data["growth_cycles"].max()
print(f"Max growth cycles: {max_growth_cycles}")
print(f"Limit: {growth_cycle_limit}")

if max_growth_cycles > growth_cycle_limit:
    scale_factor = growth_cycle_limit / max_growth_cycles
    print(f"Scale factor: {scale_factor:.4f}")

    forest_data["growth_cycles"] = (
        forest_data["growth_cycles"] * scale_factor
    ).astype(int)
    forest_data["growth_cycles"] = forest_data["growth_cycles"].clip(lower=1)

    print("\nAfter scaling:")
    print(forest_data[["fid", "species", "growth_cycles", "delay"]])

    print("\nPROBLEM ANALYSIS:")
    print("-" * 70)
    max_cycles_after = forest_data["growth_cycles"].max()
    print(f"Max cycles after scaling: {max_cycles_after}")

    for i, row in forest_data.iterrows():
        delay = row["delay"]
        cycles = row["growth_cycles"]
        print(f"\nTree {row['fid']} ({row['species']}):")
        print(f"  Delay: {delay} cycles")
        print(f"  Growth cycles: {cycles} cycles")
        print(f"  Simulation will run for: {max_cycles_after} cycles")

        if delay > 0:
            print(f"  Tree will START growing at cycle {delay}")
            remaining = max_cycles_after - delay
            print(f"  Remaining cycles for growth: {remaining}")

            if remaining <= 0:
                print(f"  *** CRITICAL: Tree doesn't grow at all! ***")
            elif remaining < cycles:
                print(f"  *** WARNING: Tree only gets {remaining}/{cycles} growth cycles ***")
else:
    print("\nNo scaling needed - cycles are within limit")

print("\n" + "=" * 70)
