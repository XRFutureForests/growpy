"""
Create a minimal PVE JSON test file from scratch.

This creates the absolute minimum viable PVE JSON that should import into
Unreal without crashing, based on analysis of PVE source code requirements.
"""

import json
from pathlib import Path


def create_minimal_pve_json() -> dict:
    """
    Create a minimal viable PVE JSON with a simple 3-point tree.

    Based on critical requirements from PVE source code analysis:
    - pscale must have non-zero values (prevents division by zero)
    - budDirection must have 18 floats (6 vectors) per point
    - All required JSON paths must exist

    This creates a simple Y-shaped tree with 7 points and 2 branches.
    """

    # Tree structure: Y-shape with UNIQUE points per branch (no sharing!)
    # CRITICAL: PVE branches must NOT share points - each branch needs unique indices
    # Y-SHAPED TREE STRUCTURE:
    # Branch 0 (trunk): Points 0-5 (base to fork point)
    # Branch 1 (left arm): Points 6-10 (own copy of fork + going up-left)
    # Branch 2 (right arm): Points 11-15 (own copy of fork + going up-right)
    # NOTE: Coordinates are in METERS (PVE loader multiplies by 100 to convert to Unreal cm)

    positions = [
        # Trunk - 6 points from base to fork (1.0m tall)
        [0.0, 0.0, 0.0],  # Point 0: Base
        [0.0, 0.2, 0.0],  # Point 1
        [0.0, 0.4, 0.0],  # Point 2
        [0.0, 0.6, 0.0],  # Point 3
        [0.0, 0.8, 0.0],  # Point 4
        [0.0, 1.0, 0.0],  # Point 5: Fork point (end of trunk)
        # Left arm - 5 points (own fork copy + going up-left)
        [0.0, 1.0, 0.0],  # Point 6: Left arm's copy of fork
        [-0.15, 1.25, 0.0],  # Point 7
        [-0.30, 1.50, 0.0],  # Point 8
        [-0.45, 1.75, 0.0],  # Point 9
        [-0.60, 2.00, 0.0],  # Point 10: Left tip
        # Right arm - 5 points (own fork copy + going up-right)
        [0.0, 1.0, 0.0],  # Point 11: Right arm's copy of fork
        [0.15, 1.25, 0.0],  # Point 12
        [0.30, 1.50, 0.0],  # Point 13
        [0.45, 1.75, 0.0],  # Point 14
        [0.60, 2.00, 0.0],  # Point 15: Right tip
    ]

    num_points = len(positions)  # 16 points

    # CRITICAL: pscale must be non-zero to prevent division by zero crash
    # pscale is in METERS (PVE loader multiplies by 100)
    pscales = [
        # Trunk (6 points)
        0.05,  # Point 0: 5cm radius (base)
        0.045,  # Point 1
        0.040,  # Point 2
        0.035,  # Point 3
        0.030,  # Point 4
        0.025,  # Point 5: fork end of trunk
        # Left arm (5 points)
        0.025,  # Point 6: fork copy
        0.020,  # Point 7
        0.016,  # Point 8
        0.012,  # Point 9
        0.008,  # Point 10: left tip
        # Right arm (5 points)
        0.025,  # Point 11: fork copy
        0.020,  # Point 12
        0.016,  # Point 13
        0.012,  # Point 14
        0.008,  # Point 15: right tip
    ]

    # CRITICAL: budDirection must have 18 floats (6 vectors × 3 components) per point
    # (PVMeshBuilderElement.cpp line 782, 806)
    # Indices [0] and [5] are specifically accessed
    # Default bud direction for upward growth (trunk)
    up_bud_dir = [
        0.0,
        1.0,
        0.0,  # [0] Apical direction (up)
        1.0,
        0.0,
        0.0,  # [1] Axillary direction (right)
        0.0,
        0.0,
        1.0,  # [2] Additional vector
        0.0,
        1.0,
        0.0,  # [3] Additional vector
        0.0,
        1.0,
        0.0,  # [4] Additional vector
        0.0,
        1.0,
        0.0,  # [5] Up vector (REQUIRED)
    ]
    # Left branch direction (diagonal up-left)
    left_bud_dir = [
        -0.6,
        0.8,
        0.0,  # [0] Apical direction (up-left)
        0.0,
        1.0,
        0.0,  # [1] Axillary direction (up)
        0.0,
        0.0,
        1.0,  # [2] Additional vector
        -0.6,
        0.8,
        0.0,  # [3] Additional vector
        -0.6,
        0.8,
        0.0,  # [4] Additional vector
        0.0,
        1.0,
        0.0,  # [5] Up vector (REQUIRED)
    ]
    # Right branch direction (diagonal up-right)
    right_bud_dir = [
        0.6,
        0.8,
        0.0,  # [0] Apical direction (up-right)
        0.0,
        1.0,
        0.0,  # [1] Axillary direction (up)
        0.0,
        0.0,
        1.0,  # [2] Additional vector
        0.6,
        0.8,
        0.0,  # [3] Additional vector
        0.6,
        0.8,
        0.0,  # [4] Additional vector
        0.0,
        1.0,
        0.0,  # [5] Up vector (REQUIRED)
    ]
    # 14 points: 6 trunk + 4 left + 4 right
    bud_directions = [
        up_bud_dir,  # Point 0: trunk base
        up_bud_dir,  # Point 1
        up_bud_dir,  # Point 2
        up_bud_dir,  # Point 3
        up_bud_dir,  # Point 4
        up_bud_dir,  # Point 5: fork end of trunk
        # Left arm (5 points)
        left_bud_dir,  # Point 6: left arm fork copy
        left_bud_dir,  # Point 7
        left_bud_dir,  # Point 8
        left_bud_dir,  # Point 9
        left_bud_dir,  # Point 10: left tip
        # Right arm (5 points)
        right_bud_dir,  # Point 11: right arm fork copy
        right_bud_dir,  # Point 12
        right_bud_dir,  # Point 13
        right_bud_dir,  # Point 14
        right_bud_dir,  # Point 15: right tip
    ]

    # Other required point attributes (distances in meters like positions)
    # 16 points: Trunk (6) + Left arm (5) + Right arm (5)
    # Trunk: 0 -> 0.2 -> 0.4 -> 0.6 -> 0.8 -> 1.0m
    # Left arm: starts at fork (1.0m), adds ~0.32m per segment
    # Right arm: starts at fork (1.0m), adds ~0.32m per segment
    length_from_root = [
        # Trunk (6 pts)
        0.0,
        0.2,
        0.4,
        0.6,
        0.8,
        1.0,
        # Left arm (5 pts) - starts at fork
        1.0,
        1.32,
        1.64,
        1.96,
        2.28,
        # Right arm (5 pts) - starts at fork
        1.0,
        1.32,
        1.64,
        1.96,
        2.28,
    ]
    length_from_seed = [
        # Trunk (6 pts)
        0.0,
        0.2,
        0.4,
        0.6,
        0.8,
        1.0,
        # Left arm (5 pts)
        1.0,
        1.32,
        1.64,
        1.96,
        2.28,
        # Right arm (5 pts)
        1.0,
        1.32,
        1.64,
        1.96,
        2.28,
    ]
    # Gradient from 1.0 (base/thick) to small (tip/thin) - 16 points
    lod_total_pscale_gradient = [
        # Trunk (6 pts)
        1.0,
        0.9,
        0.8,
        0.7,
        0.6,
        0.5,
        # Left arm (5 pts)
        0.5,
        0.4,
        0.32,
        0.24,
        0.16,
        # Right arm (5 pts)
        0.5,
        0.4,
        0.32,
        0.24,
        0.16,
    ]
    # generation: 0=trunk, 1=branches - 16 points
    generation = [
        # Trunk (gen 0)
        0,
        0,
        0,
        0,
        0,
        0,
        # Left arm (gen 1)
        1,
        1,
        1,
        1,
        1,
        # Right arm (gen 1)
        1,
        1,
        1,
        1,
        1,
    ]

    # LOD gradient attributes required by FPointFacade::IsValid() - 16 points
    lod_hull_gradient = [i / 15.0 for i in range(16)]  # 0.0 to 1.0
    lod_main_trunk_gradient = [1.0 - i / 15.0 for i in range(16)]  # 1.0 to 0.0
    lod_ground_gradient = [i / 15.0 for i in range(16)]  # 0.0 to 1.0

    # Bud-related attributes required by FPointFacade::IsValid()
    # budHormoneLevels - array of 6 floats per point (16 points)
    bud_hormone_levels = [
        [1.0 - i * 0.06, i * 0.06, 0.0, 0.0, 0.0, 0.0] for i in range(16)
    ]

    # njord_pixelIdx - float index per point (16 points)
    njord_pixel_idx = [1.0] * 16

    # budLightDetected - array of 4 floats per point (16 points)
    bud_light_detected = [[0.5, 0.0, 0.5, 0.0] for _ in range(16)]

    # Additional point attributes with simple defaults (16 points)
    bud_development = [[1, 0, i, 0, 0, 0] for i in range(16)]

    # branch_gradient: normalized position along current branch (0 to 1)
    # Trunk (6 pts): 0.0 to 1.0, Left arm (5 pts): 0.0 to 1.0, Right arm (5 pts): 0.0 to 1.0
    branch_gradient = (
        [i / 5.0 for i in range(6)]  # Trunk
        + [i / 4.0 for i in range(5)]  # Left arm
        + [i / 4.0 for i in range(5)]  # Right arm
    )
    # plant_gradient: overall position in tree (0 at base, 1 at tips)
    plant_gradient = [i / 15.0 for i in range(16)]

    # Primitives (branches): 3 branches for Y-shape
    # CRITICAL: Each branch has UNIQUE point indices - no sharing!
    # Branch 0 (trunk): Points [0-5] (6 points, base to fork)
    # Branch 1 (left arm): Points [6-10] (5 points, unique)
    # Branch 2 (right arm): Points [11-15] (5 points, unique)
    primitive_points = [
        [0, 1, 2, 3, 4, 5],  # Branch 0: Trunk (6 points)
        [6, 7, 8, 9, 10],  # Branch 1: Left arm (5 points, unique)
        [11, 12, 13, 14, 15],  # Branch 2: Right arm (5 points, unique)
    ]

    num_branches = len(primitive_points)  # 3 branches

    # Branch hierarchy - parents is an array showing the full parent chain (branchNumbers)
    # 3 branches: trunk, left arm, right arm
    # CRITICAL: parents array shows hierarchy path [0, parent1, parent2, ...]
    # where 0 means root and subsequent values are branchNumbers
    parents = [
        [0],  # Branch 0 (trunk): root only
        [0, 1],  # Branch 1 (left): root -> branchNumber 1 (trunk)
        [0, 1],  # Branch 2 (right): root -> branchNumber 1 (trunk)
    ]
    # CRITICAL: children contains branchNumbers (not indices!)
    # Branch 0 (branchNumber=1) has children with branchNumbers 2 and 3
    children = [
        [2, 3],  # Branch 0: children are branches with branchNumbers 2 and 3
        [],  # Branch 1 (left) has no children
        [],  # Branch 2 (right) has no children
    ]
    branch_numbers = [1, 2, 3]  # Sequential branch IDs (1-based)

    # Additional branch attributes required by FBranchFacade::IsValid()
    # Points (capital P) - point indices per branch (same as primitive_points)
    branch_points_attr = primitive_points  # Will reference the same data

    # branchSourceBudNumber - which bud this branch grew from
    # For child branches, this should be the bud number on the PARENT where they attach
    branch_source_bud_number = [
        0,  # Trunk from bud 0
        5,  # Left arm grows from trunk's bud 5 (trunk's last point)
        5,  # Right arm grows from trunk's bud 5 (trunk's last point)
    ]

    # branchHierarchyNumber - hierarchy level (0=trunk, 1=first order, etc.)
    branch_hierarchy_number = [0, 1, 1]  # Trunk=0, both arms=1

    # branchParentNumber - parent branch number (1-based, 0 for root)
    branch_parent_number = [
        0,
        1,
        1,
    ]  # Trunk has no parent, both arms' parent is branch 1

    # plantNumber - which plant this branch belongs to (1-based)
    plant_number = [1, 1, 1]  # All branches belong to plant 1

    # Foliage instancer data - use FLAT arrays for vector data (not nested)
    # Each branch has N instancers; vector data is flattened (3 floats per vector)
    # Using 3 instancers per branch like Hazel - now 3 branches
    # NOTE: All values in METERS like positions
    instancer_names = [
        ["Leaf_001", "Leaf_002", "Leaf_003"],  # Trunk
        ["Leaf_001", "Leaf_002", "Leaf_003"],  # Left arm
        ["Leaf_001", "Leaf_002", "Leaf_003"],  # Right arm
    ]
    # Flat arrays: 3 pivots × 3 floats = 9 floats per branch (meters)
    instancer_pivots = [
        [0.0, 0.4, 0.0, 0.0, 0.7, 0.0, 0.0, 1.0, 0.0],  # Along trunk
        [-0.15, 1.25, 0.0, -0.30, 1.50, 0.0, -0.45, 1.75, 0.0],  # Left arm
        [0.15, 1.25, 0.0, 0.30, 1.50, 0.0, 0.45, 1.75, 0.0],  # Right arm
    ]
    # Flat arrays: 3 up vectors × 3 floats = 9 floats per branch (unit vectors)
    instancer_ups = [
        [0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
        [0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
        [0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0],
    ]
    # Flat arrays: 3 normal vectors × 3 floats = 9 floats per branch (unit vectors)
    instancer_normals = [
        [0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
        [0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
        [0.0, 0.0, 1.0, 0.0, 0.0, 1.0, 0.0, 0.0, 1.0],
    ]
    instancer_scales = [
        [1.0, 1.0, 1.0],
        [1.0, 1.0, 1.0],
        [1.0, 1.0, 1.0],
    ]
    # instancer_LFR: length from root at each instancer position (meters)
    instancer_lfr = [
        [0.0, 0.4, 1.0],  # Trunk
        [1.25, 1.50, 1.75],  # Left arm
        [1.25, 1.50, 1.75],  # Right arm
    ]

    # Build the complete JSON structure
    pve_json = {
        "globalAttributes": {
            # Growth parameters (simplified)
            "cycle": {"isArray": False, "size": 1, "type": "int", "value": 10},
            "cycleTime": {"isArray": False, "size": 1, "type": "float", "value": 1.0},
            "gravitationalForce": {
                "isArray": False,
                "size": 1,
                "type": "float",
                "value": 1.0,
            },
            "maxBranchNumber": {"isArray": False, "size": 1, "type": "int", "value": 3},
            "maxBudNumber": {"isArray": False, "size": 1, "type": "int", "value": 16},
            "maxPscale": {"isArray": False, "size": 1, "type": "float", "value": 0.05},
            "minPscale": {"isArray": False, "size": 1, "type": "float", "value": 0.008},
            "max_curve_length": {
                "isArray": False,
                "size": 1,
                "type": "float",
                "value": 2.0,
            },
            "max_pscale": {"isArray": False, "size": 1, "type": "float", "value": 0.05},
            "randomSeed": {"isArray": False, "size": 1, "type": "int", "value": 42},
            # Growth curves (simplified arrays)
            "axialElongation": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [[0.0, 1.0], [1.0, 1.0]],
            },
            "lateralElongation": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [[0.0, 0.5], [1.0, 0.5]],
            },
            "branchingCondition": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [[0.0, 1.0], [1.0, 0.5]],
            },
            "phototropism": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [[0.0, 0.5]],
            },
            "phyllotaxy": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [[0.0, 137.5]],
            },
            # Required by PVJSONHelper required paths
            "phyllotaxyLeaf": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [[0.0, 137.5]],
            },
        },
        "points": {
            "attributes": {
                "P": {
                    "isArray": False,
                    "size": 3,
                    "type": "float",
                    "values": positions,
                },
                "pscale": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                    "values": pscales,
                },
                "budDirection": {
                    "isArray": True,
                    "size": 3,
                    "type": "float",
                    "values": bud_directions,
                },
                "lengthFromRoot": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                    "values": length_from_root,
                },
                "LOD_totalPscaleGradient": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                    "values": lod_total_pscale_gradient,
                },
                "generation": {
                    "isArray": False,
                    "size": 1,
                    "type": "int",
                    "values": generation,
                },
                "budDevelopment": {
                    "isArray": True,
                    "size": 1,
                    "type": "int",
                    "values": bud_development,
                },
                "branchGradient": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                    "values": branch_gradient,
                },
                "plantGradient": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                    "values": plant_gradient,
                },
                "budNumber": {
                    "isArray": False,
                    "size": 1,
                    "type": "int",
                    "values": list(range(16)),  # 0 to 15 for 16 points
                },
                # Required by FPointFacade::IsValid()
                "lengthFromSeed": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                    "values": length_from_seed,
                },
                "LOD_hullGradient": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                    "values": lod_hull_gradient,
                },
                "LOD_mainTrunkGradient": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                    "values": lod_main_trunk_gradient,
                },
                "LOD_groundGradient": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                    "values": lod_ground_gradient,
                },
                "budHormoneLevels": {
                    "isArray": True,
                    "size": 1,
                    "type": "float",
                    "values": bud_hormone_levels,
                },
                "njord_pixelIdx": {
                    "isArray": False,
                    "size": 1,
                    "type": "float",
                    "values": njord_pixel_idx,
                },
                "budLightDetected": {
                    "isArray": True,
                    "size": 1,
                    "type": "float",
                    "values": bud_light_detected,
                },
            },
            "positions": positions,
        },
        "primitives": {
            "attributes": {
                "parents": {
                    "isArray": True,
                    "size": 1,
                    "type": "int",
                    "values": parents,
                },
                "children": {
                    "isArray": True,
                    "size": 1,
                    "type": "int",
                    "values": children,
                },
                "branchNumber": {
                    "isArray": False,
                    "size": 1,
                    "type": "int",
                    "values": branch_numbers,
                },
                # Note: "Points" attribute is populated by PVE loader from primitives.points
                "branchSourceBudNumber": {
                    "isArray": False,
                    "size": 1,
                    "type": "int",
                    "values": branch_source_bud_number,
                },
                "branchHierarchyNumber": {
                    "isArray": False,
                    "size": 1,
                    "type": "int",
                    "values": branch_hierarchy_number,
                },
                "branchParentNumber": {
                    "isArray": False,
                    "size": 1,
                    "type": "int",
                    "values": branch_parent_number,
                },
                "plantNumber": {
                    "isArray": False,
                    "size": 1,
                    "type": "int",
                    "values": plant_number,
                },
                "instancer_name": {
                    "isArray": True,
                    "size": 1,
                    "type": "string",
                    "values": instancer_names,
                },
                "instancer_pivot": {
                    "isArray": True,
                    "size": 3,
                    "type": "float",
                    "values": instancer_pivots,
                },
                "instancer_UP": {
                    "isArray": True,
                    "size": 3,
                    "type": "float",
                    "values": instancer_ups,
                },
                "instancer_N": {
                    "isArray": True,
                    "size": 3,
                    "type": "float",
                    "values": instancer_normals,
                },
                "instancer_scale": {
                    "isArray": True,
                    "size": 1,
                    "type": "float",
                    "values": instancer_scales,
                },
                "instancer_LFR": {
                    "isArray": True,
                    "size": 1,
                    "type": "float",
                    "values": instancer_lfr,
                },
            },
            "points": primitive_points,
        },
    }

    return pve_json


def main():
    """Create and save minimal test JSON."""
    output_dir = Path("data/output/pve_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / "minimal_test_tree.json"

    print("Creating minimal PVE JSON test file...")
    pve_json = create_minimal_pve_json()

    with open(output_path, "w") as f:
        json.dump(pve_json, f, indent=2)

    num_points = len(pve_json["points"]["attributes"]["pscale"]["values"])
    num_branches = len(pve_json["primitives"]["points"])

    print(f"Created: {output_path}")
    print(f"  - {num_points} points (Y-shaped tree)")
    print(f"  - {num_branches} branches (trunk + side branch)")
    print(f"  - All critical attributes present")
    print(f"  - pscale values: {pve_json['points']['attributes']['pscale']['values']}")
    print(f"  - budDirection: 18 floats per point")


if __name__ == "__main__":
    main()
