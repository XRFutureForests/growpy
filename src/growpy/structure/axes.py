"""One axis rule for every tree, real or generated.

A source's own branch ids cannot be compared across tools: TreeQSM starts a branch at a
new order, rTwig renumbers them, a point graph has none, and a Grove skeleton has its own.
The MTG vocabulary needs one answer to "which child continues the axis" (``<``) and which
children start a lateral axis (``+``). The rule is the one the BioDiv graph converter
already uses, because TreeQSM radii are too noisy to decide forks (the radius rule ended
trunks at 1-5 m): **the child with the longer supported subtree continues the parent's
axis; ties go to the larger radius.** Subtree size is summed cylinder length, so it does
not depend on how long a tool makes its cylinders.
"""

from __future__ import annotations

import numpy as np
import pandas as pd


def assign_axes(
    parent: np.ndarray, length: np.ndarray, radius: np.ndarray
) -> tuple[pd.DataFrame, np.ndarray]:
    """Axis columns for a cylinder tree.

    ``parent`` is the row index of each cylinder's parent, -1 for a base. Returns a frame
    with ``axis_id``, ``axis_order``, ``axis_pos``, ``n_children`` and ``subtree_length``
    (same row order as the input) and the continuing child of each cylinder (-1 for
    none). Axis 0 is the trunk. A second base (a tool that split the tree in two) becomes
    a first-order axis of the trunk, which ``n_roots`` in the tree table reports.
    """
    n = len(parent)
    if n == 0:
        raise ValueError("empty cylinder table")
    parent = np.asarray(parent, dtype=np.int64)
    if ((parent < -1) | (parent >= n) | (parent == np.arange(n))).any():
        raise ValueError("parent index out of range or self-referencing")
    children: list[list[int]] = [[] for _ in range(n)]
    roots: list[int] = []
    for i, p in enumerate(parent):
        (roots if p < 0 else children[p]).append(i)
    if not roots:
        raise ValueError("no base cylinder (every parent is set: a cycle)")
    order = list(roots)
    for i in order:  # breadth first from every base; list grows while we walk it
        order.extend(children[i])
    if len(order) != n:
        raise ValueError(f"{n - len(order)} cylinders unreachable from a base (cycle)")

    sub = np.asarray(length, dtype=float).copy()
    for i in reversed(order):  # leaves first
        if parent[i] >= 0:
            sub[parent[i]] += sub[i]

    def rank(i: int) -> tuple[float, float]:
        return (sub[i], float(radius[i]))

    axis_id = np.full(n, -1, dtype=np.int64)
    axis_order = np.zeros(n, dtype=np.int64)
    axis_pos = np.zeros(n, dtype=np.int64)
    continues = np.full(n, -1, dtype=np.int64)
    next_axis = 0
    main = max(roots, key=rank)
    for r in [main] + [r for r in roots if r != main]:
        axis_id[r] = next_axis
        axis_order[r] = 0 if r == main else 1
        next_axis += 1
    for i in order:
        kids = children[i]
        if not kids:
            continue
        cont = max(kids, key=rank)
        continues[i] = cont
        axis_id[cont] = axis_id[i]
        axis_order[cont] = axis_order[i]
        axis_pos[cont] = axis_pos[i] + 1
        for k in kids:
            if k != cont:
                axis_id[k] = next_axis
                axis_order[k] = axis_order[i] + 1
                next_axis += 1
    frame = pd.DataFrame(
        {
            "axis_id": axis_id,
            "axis_order": axis_order,
            "axis_pos": axis_pos,
            "n_children": [len(c) for c in children],
            "subtree_length": sub,
        }
    )
    return frame, continues


def attached_to_main_base(parent: np.ndarray, length: np.ndarray) -> np.ndarray:
    """Mask of the cylinders connected to the main base, the one whose component holds
    the most cylinder length. TreeML trees carry about 50 loose fragments each (a base
    with no parent, order 0, radius 1-3 cm: leftovers TreeQSM fitted outside the tree);
    they are not part of the structure and would otherwise count as axes."""
    n = len(parent)
    children: list[list[int]] = [[] for _ in range(n)]
    roots: list[int] = []
    for i, p in enumerate(parent):
        (roots if p < 0 else children[p]).append(i)
    base_of = np.full(n, -1, dtype=np.int64)
    order = list(roots)
    for r in roots:
        base_of[r] = r
    for i in order:
        for c in children[i]:
            base_of[c] = base_of[i]
            order.append(c)
    total = dict.fromkeys(roots, 0.0)
    for i in range(n):
        if base_of[i] >= 0:
            total[base_of[i]] += length[i]
    main = max(roots, key=total.__getitem__)
    return base_of == main


def axis_table(cyl: pd.DataFrame) -> pd.DataFrame:
    """One row per axis: its order, the axis it grows from, base and attachment cylinder,
    cylinder count and length. This is the axis level of an MTG; a lateral axis is a
    ``+`` edge from ``parent_axis`` and the cylinders inside an axis are ``<`` edges."""
    base = cyl[cyl["axis_pos"] == 0].set_index("axis_id")
    grouped = cyl.groupby("axis_id")
    parent_cyl = base["parent"]
    attach_axis = cyl["axis_id"].to_numpy()[parent_cyl.clip(lower=0).to_numpy()]
    return pd.DataFrame(
        {
            "axis_order": base["axis_order"],
            "parent_axis": np.where(parent_cyl.to_numpy() >= 0, attach_axis, -1),
            "base_cyl": base["cyl_id"],
            "attach_cyl": parent_cyl,
            "n_cyl": grouped.size(),
            "length": grouped["length"].sum(),
        }
    ).reset_index()
