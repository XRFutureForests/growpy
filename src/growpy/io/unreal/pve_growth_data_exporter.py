"""
Minimal Growth Data JSON exporter for PVE's Growth Data JSON Importer node (UE 5.8).

Bypasses the deprecated Preset Loader and the full Megaplants-style recipe
(``pve_grove_mapper.generate_pve_from_grove``) entirely. Emits only the fields
``PVJSONHelper::LoadGrowthDataJsonToCollection()`` requires:

    points.positions
    points.attributes.budDirection.values
    primitives.points
    primitives.attributes.{parents, children, branchNumber}.values

See docs/05-PRESENTATION-TIER/pve-node-reference.md, "Direct skeleton
ingestion (growth-data JSON)" for the schema reference.

NOTE on coordinates: positions are written in Grove's native (X, Y, Z) order,
local to the tree origin, in metres -- left UNCONVERTED. The importer itself
applies ``FVector3f(pos[0], pos[2], pos[1]) * 100`` (Z-up -> Y-up swap +
metres -> centimetres). Pre-swapping here (as the Megaplants mapper does for
its own ``points.positions``/``P`` attribute) would double-transform the
skeleton once loaded.

NOTE on status: the importer node is development-gated in 5.8 Preview
(``UPVGrowthDataJsonImporterSettings`` is ``DevelopmentOnly`` / not exposed to
the node library) -- treat this exporter's output as a prototype target, not
a stable contract, until XRFF-250 validates it end-to-end against a live
editor.
"""

import json
import logging
from pathlib import Path
from typing import Any

from .pve_grove_mapper import (
    _calculate_branch_parents_from_skeleton,
    _calculate_bud_directions,
)
from .pve_hierarchy_builder import build_hierarchy_arrays

logger = logging.getLogger(__name__)


def build_growth_data_json(skeleton: Any) -> dict:
    """
    Build the minimal growth-data JSON for PVE's Growth Data JSON Importer.

    Args:
        skeleton: Grove skeleton object (``points`` + ``poly_lines``),
            pre-built by the export phase -- same object passed to
            ``map_grove_to_pve()``.

    Returns:
        Dict matching the minimal schema (see module docstring).
    """
    skeleton_points = skeleton.points
    num_points = len(skeleton_points)
    poly_lines = skeleton.poly_lines
    num_branches = len(poly_lines)

    if num_points == 0 or num_branches == 0:
        return {
            "points": {
                "positions": [],
                "attributes": {
                    "budDirection": {
                        "isArray": True,
                        "size": 3,
                        "type": "float",
                        "values": [],
                    }
                },
            },
            "primitives": {
                "points": [],
                "attributes": {
                    "parents": {
                        "isArray": False,
                        "size": 1,
                        "type": "int",
                        "values": [],
                    },
                    "children": {
                        "isArray": True,
                        "size": 1,
                        "type": "int",
                        "values": [],
                    },
                    "branchNumber": {
                        "isArray": False,
                        "size": 1,
                        "type": "int",
                        "values": [],
                    },
                },
            },
        }

    # Local (origin-subtracted) positions, native Grove axis order/units --
    # the importer does the Z-up->Y-up swap and m->cm scale on load.
    origin = skeleton_points[0]
    positions = [
        [p[0] - origin[0], p[1] - origin[1], p[2] - origin[2]]
        for p in skeleton_points
    ]

    # Reuse the same per-point direction calc the Megaplants path uses --
    # already in the no-swap convention this importer expects.
    bud_directions = _calculate_bud_directions(skeleton)

    # Rebase poly_line point indices to 0 (Grove uses global indices across
    # all skeletons in a grove; this skeleton's points array is 0-indexed).
    all_indices = [idx for pl in poly_lines for idx in pl]
    index_offset = min(all_indices) if all_indices else 0
    primitive_points = [
        [idx - index_offset for idx in pl] for pl in poly_lines
    ]

    # Immediate parent per branch (self-reference for roots), not the full
    # ancestor chain the Megaplants "parents" attribute uses.
    parents = _calculate_branch_parents_from_skeleton(skeleton, num_branches)
    children = build_hierarchy_arrays(None, num_branches, skeleton)["children"][
        "values"
    ]
    branch_numbers = list(range(num_branches))

    return {
        "points": {
            "positions": positions,
            "attributes": {
                "budDirection": {
                    "isArray": True,
                    "size": 3,
                    "type": "float",
                    "values": bud_directions,
                },
            },
        },
        "primitives": {
            "points": primitive_points,
            "attributes": {
                "parents": {
                    "isArray": False,
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
            },
        },
    }


def generate_growth_data_from_grove(
    grove: Any,
    output_path: Path,
    tree_index: int = 0,
    skeleton: Any | None = None,
    verbose: bool = True,
) -> dict:
    """
    Build the growth-data JSON from a Grove simulation and write it to disk.

    Args:
        grove: Grove object after simulation.
        output_path: Path to save the generated JSON.
        tree_index: Index of tree in grove (used only if skeleton not given).
        skeleton: Pre-built skeleton from the export phase. If None, builds
            one from ``grove`` (matches ``map_grove_to_pve``'s fallback).
        verbose: Whether to log progress.

    Returns:
        The generated growth-data dictionary.
    """
    if skeleton is None:
        skeletons = grove.build_skeletons(True)
        if tree_index < len(skeletons):
            skeleton = skeletons[tree_index]

    data = build_growth_data_json(skeleton)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2)

    if verbose:
        logger.info(
            "[OK] Growth Data JSON (prototype, XRFF-250): %s", output_path.name
        )
    return data
