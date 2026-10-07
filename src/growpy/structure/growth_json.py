"""Exchange table -> growth JSON, the layout growpy writes for every Grove tree.

The growth JSON is what ``growpy-structure-descriptors`` and the PVE exporter read: points
with a radius (``budLateralMeristem``), and one polyline per branch with the branch it
grows from and its hierarchy. Writing a standardised QSM in that layout lets a real tree go
through exactly the code a generated one does (``readers.read_growth_json`` is the inverse).

One polyline per axis: the start of the axis' base cylinder, then the end of each of its
cylinders in order. A lateral axis keeps its own first point (where the QSM put the base of
the branch) instead of snapping to a vertex of its parent; the descriptor code finds the
nearest parent vertex itself. Numbering follows the Grove files: ``branchNumber`` from 1,
``branchParentNumber`` 0 for the trunk, ``branchHierarchyNumber`` = axis order + 1.

The file is y-up: exchange (x, y, z) is written as (x, z, y), the inverse of the reader.
What does not survive: one radius per point instead of per cylinder, ``is_virtual``, and
the source's own branch ids.
"""

from __future__ import annotations

import pandas as pd

from growpy.structure.exchange import from_exchange


def to_growth_json(cyl: pd.DataFrame) -> dict:
    """Growth-JSON dict for one standardised tree (``CYL_COLUMNS`` exchange table)."""
    work = from_exchange(cyl).sort_values(["axis_id", "axis_pos"])
    positions: list[list[float]] = []
    radii: list[list[float]] = []
    lines: list[list[int]] = []
    numbers: list[int] = []
    parents: list[int] = []
    hierarchy: list[int] = []
    axis_of_row = work.set_index("cyl_id")["axis_id"]
    for axis_id, axis in work.groupby("axis_id", sort=True):
        base = axis.iloc[0]
        line = [len(positions)]
        positions.append([base["start_x"], base["start_z"], base["start_y"]])
        radii.append([float(base["radius"]), 0.0])
        for row in axis.itertuples(index=False):
            line.append(len(positions))
            positions.append([row.end_x, row.end_z, row.end_y])
            radii.append([float(row.radius), 0.0])
        lines.append(line)
        numbers.append(int(axis_id) + 1)
        parent_axis = (
            int(axis_of_row[int(base["parent"])]) + 1 if base["parent"] >= 0 else 0
        )
        parents.append(parent_axis)
        hierarchy.append(int(base["axis_order"]) + 1)
    return {
        "points": {
            "positions": positions,
            "attributes": {"budLateralMeristem": {"values": radii}},
        },
        "primitives": {
            "points": lines,
            "attributes": {
                "branchNumber": {"values": numbers},
                "branchParentNumber": {"values": parents},
                "branchHierarchyNumber": {"values": hierarchy},
            },
        },
    }
