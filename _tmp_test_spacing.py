"""Test that the spacing update produces correct initial distances and thinning fires."""

import math
import pandas as pd
from growpy.config import get_config
from growpy.pipelines.dataset_csv_planner import generate_merged_csv, _polygon_neighbors

config = get_config()

print("=" * 60)
print("1. Verify planting distances from competition groups")
print("=" * 60)

for species in ["Norway spruce", "European beech"]:
    group = config.get_competition_group(species)
    pd_val = group["planting_distance"]
    thinning = group.get("thinning", [])
    print(f"\n{species} ({group.get('__name__', '?')}):")
    print(f"  planting_distance: {pd_val}m")
    print(f"  thinning: {thinning}")

print("\n" + "=" * 60)
print("2. Verify generated merged CSV neighbor distances")
print("=" * 60)

for species in ["Norway spruce", "European beech"]:
    group = config.get_competition_group(species)
    spacing = group["planting_distance"]
    max_h = 35 if "spruce" in species.lower() else 30

    df = generate_merged_csv(species, max_h, spacing, competition_neighbors=3)

    # Check neighbor distances from center (origin)
    neighbors = df[df["fid"] >= 100]
    center = df[df["fid"] == 2].iloc[0]

    print(f"\n{species} (spacing={spacing}m):")
    print(f"  Center tree: ({center['x']}, {center['y']})")
    for _, row in neighbors.iterrows():
        dist = math.sqrt(row["x"] ** 2 + row["y"] ** 2)
        print(f"  Neighbor fid={int(row['fid'])}: ({row['x']:.3f}, {row['y']:.3f}) -> dist={dist:.3f}m")

    # Verify all neighbors are at planting_distance
    for _, row in neighbors.iterrows():
        dist = math.sqrt(row["x"] ** 2 + row["y"] ** 2)
        assert abs(dist - spacing) < 0.01, f"Expected {spacing}m, got {dist:.3f}m"
    print(f"  OK: all 3 neighbors at {spacing}m from center")

    # Verify inter-neighbor distance (equilateral triangle)
    coords = [(row["x"], row["y"]) for _, row in neighbors.iterrows()]
    for i in range(len(coords)):
        for j in range(i + 1, len(coords)):
            inter_dist = math.sqrt(
                (coords[i][0] - coords[j][0]) ** 2
                + (coords[i][1] - coords[j][1]) ** 2
            )
            print(f"  Inter-neighbor ({i+1}-{j+1}): {inter_dist:.3f}m")

print("\n" + "=" * 60)
print("3. Verify thinning deltas are positive (will fire)")
print("=" * 60)

for species in ["Norway spruce", "European beech"]:
    group = config.get_competition_group(species)
    init_dist = group["planting_distance"]
    thinning = group.get("thinning", [])

    print(f"\n{species} (init_dist={init_dist}m):")
    cur_dist = init_dist
    all_positive = True
    for h, target in thinning:
        delta = target - cur_dist
        status = "FIRE" if delta > 0.01 else "SKIP"
        if delta <= 0.01:
            all_positive = False
        print(f"  h={h}m: target={target}m, cur={cur_dist}m, delta={delta:+.2f}m -> {status}")
        if delta > 0.01:
            cur_dist = target
    assert all_positive, f"Thinning would not fire for {species}!"
    print(f"  OK: all thinning steps will fire")

print("\n" + "=" * 60)
print("ALL CHECKS PASSED")
print("=" * 60)
