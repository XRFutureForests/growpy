"""Standardised QSM trees as MTGs (multiscale tree graphs, OpenAlea's ``openalea.mtg``).

One MTG per tree, two scales: the tree (scale 1, label ``T``) and its cylinders (scale 2,
label ``C``). A cylinder follows its parent with ``<`` when both lie on the same axis and
``+`` where a new axis branches off, so axes, orders and branching events are native MTG
queries. Every cylinder carries its geometry and the single axis rule's result:

``XX YY ZZ``           start point (m, the canonical frame: z up, base at the origin)
``EndX EndY EndZ``     end point (m)
``Length Radius``      m; ``Radius`` as delivered by the source (see ``radius_correction``)
``Axis Order AxisPos`` axis id, branch order (0 = trunk), position along the axis
``Row``                the cylinder's row in the pruned table (exact round trip)

Trees are written after ``prototypes.PRUNE`` (the common resolution of the descriptors)
and ``coarsen``: consecutive cylinders of an axis are merged into segments of at least
``SEGMENT_M`` (0.25 m, about Kew's native cylinder length and below the 0.3 m lateral
threshold). BioDiv's rTwig QSMs are made of 6-10 cm cylinders, 4,000-13,000 per pruned
tree, which as MTG text came to ~23 MB per tree. Branch points survive: a lateral hangs
on the segment that contains its original parent cylinder. Needs ``openalea.mtg``, which
is not on PyPI (conda ``-c openalea3``; the ``growpy-openalea`` env), so it is imported
inside the functions.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from growpy.structure.descriptors import prune
from growpy.structure.prototypes import PRUNE

PROPERTIES = [
    ("XX", "REAL"),
    ("YY", "REAL"),
    ("ZZ", "REAL"),
    ("EndX", "REAL"),
    ("EndY", "REAL"),
    ("EndZ", "REAL"),
    ("Length", "REAL"),
    ("Radius", "REAL"),
    ("Axis", "INT"),
    ("Order", "INT"),
    ("AxisPos", "INT"),
    ("Row", "INT"),
    # tree-level, set on the T vertex only
    ("tree_uid", "ALPHA"),
    ("species_key", "ALPHA"),
    ("source", "ALPHA"),
    ("tier", "ALPHA"),
    ("height_m", "REAL"),
    ("dbh_m", "REAL"),
]
SEGMENT_M = 0.25
TREE_PROPERTIES = ["tree_uid", "species_key", "source", "tier", "height_m", "dbh_m"]


def to_mtg(cyl: pd.DataFrame, meta: dict | None = None, **prune_kw):
    """An exchange table (one tree) -> ``openalea.mtg.MTG``, after ``PRUNE`` and
    ``coarsen``."""
    import openalea.mtg as mtg

    work = coarsen(prune(cyl, **(PRUNE if not prune_kw else prune_kw)))
    g = mtg.MTG()
    tree_attrs = {k: meta[k] for k in TREE_PROPERTIES if meta and pd.notna(meta.get(k))}
    plant = g.add_component(g.root, label="T", **tree_attrs)
    parent = work["parent"].to_numpy()
    axis = work["axis_id"].to_numpy()
    vid: dict[int, int] = {}
    order = np.argsort(_depth(parent), kind="stable")
    for i in order:
        r = work.iloc[i]
        attrs = {
            "XX": float(r.start_x),
            "YY": float(r.start_y),
            "ZZ": float(r.start_z),
            "EndX": float(r.end_x),
            "EndY": float(r.end_y),
            "EndZ": float(r.end_z),
            "Length": float(r.length),
            "Radius": float(r.radius),
            "Axis": int(r.axis_id),
            "Order": int(r.axis_order),
            "AxisPos": int(r.axis_pos),
            "Row": int(i),
        }
        p = int(parent[i])
        if p < 0:
            vid[i] = g.add_component(plant, label="C", **attrs)
        else:
            edge = "<" if axis[i] == axis[p] else "+"
            vid[i] = g.add_child(vid[p], label="C", edge_type=edge, **attrs)
    return g


def coarsen(work: pd.DataFrame, segment_m: float = SEGMENT_M) -> pd.DataFrame:
    """Merge consecutive cylinders of each axis into segments of at least ``segment_m``
    (the axis's last segment may be shorter). A segment runs from its first cylinder's
    start to its last cylinder's end; its radius is the length-weighted mean; laterals
    keep their own start points and hang on the segment containing their parent."""
    work = work.sort_values(["axis_id", "axis_pos"])
    seg_of = np.empty(len(work), dtype=int)
    rows = []
    for _, axis in work.groupby("axis_id", sort=False):
        idx = axis.index.to_numpy()
        acc, first = 0.0, 0
        for k, i in enumerate(idx):
            acc += float(work.at[i, "length"])
            if acc >= segment_m or k == len(idx) - 1:
                chunk = idx[first : k + 1]
                lengths = work.loc[chunk, "length"].to_numpy()
                head, tail = work.loc[chunk[0]], work.loc[chunk[-1]]
                seg_of[chunk] = len(rows)
                rows.append(
                    {
                        "first": chunk[0],
                        "start_x": head.start_x,
                        "start_y": head.start_y,
                        "start_z": head.start_z,
                        "end_x": tail.end_x,
                        "end_y": tail.end_y,
                        "end_z": tail.end_z,
                        "radius": float(
                            np.average(
                                work.loc[chunk, "radius"],
                                weights=np.maximum(lengths, 1e-9),
                            )
                        ),
                        "axis_id": int(head.axis_id),
                        "axis_order": int(head.axis_order),
                    }
                )
                acc, first = 0.0, k + 1
    out = pd.DataFrame(rows)
    # seg_of is indexed by row label (the pruned frame's labels are its row numbers)
    first_parent = work["parent"].reindex(out["first"]).to_numpy()
    out["parent"] = [int(seg_of[p]) if p >= 0 else -1 for p in first_parent]
    out["length"] = np.linalg.norm(
        out[["end_x", "end_y", "end_z"]].to_numpy()
        - out[["start_x", "start_y", "start_z"]].to_numpy(),
        axis=1,
    )
    out["axis_pos"] = out.groupby("axis_id").cumcount()
    out["cyl_id"] = np.arange(len(out))
    return out.drop(columns="first")


def _depth(parent: np.ndarray) -> np.ndarray:
    depth = np.full(len(parent), -1)
    for i in range(len(parent)):
        chain, j = [], i
        while j >= 0 and depth[j] < 0:
            chain.append(j)
            j = parent[j]
        d = depth[j] if j >= 0 else -1
        for k in reversed(chain):
            d += 1
            depth[k] = d
    return depth


def from_mtg(g) -> pd.DataFrame:
    """The first tree of an MTG -> the row-based working frame ``descriptors._model``
    reads (parents re-indexed to rows, axes as stored)."""
    p = g.properties()
    vids = sorted(
        (v for v in g.vertices(scale=2) if g.label(v) == "C"), key=p["Row"].get
    )
    row = {v: k for k, v in enumerate(vids)}
    frame = pd.DataFrame(
        {
            "parent": [row.get(g.parent(v), -1) for v in vids],
            "start_x": [p["XX"][v] for v in vids],
            "start_y": [p["YY"][v] for v in vids],
            "start_z": [p["ZZ"][v] for v in vids],
            "end_x": [p["EndX"][v] for v in vids],
            "end_y": [p["EndY"][v] for v in vids],
            "end_z": [p["EndZ"][v] for v in vids],
            "length": [p["Length"][v] for v in vids],
            "radius": [p["Radius"][v] for v in vids],
            "axis_id": [p["Axis"][v] for v in vids],
            "axis_order": [p["Order"][v] for v in vids],
            "axis_pos": [p["AxisPos"][v] for v in vids],
        }
    )
    frame["cyl_id"] = np.arange(len(frame))
    return frame


def tree_meta(g) -> dict:
    plant = next(iter(g.vertices(scale=1)))
    return {k: g.property(k).get(plant) for k in TREE_PROPERTIES}


def write(g, path: Path) -> Path:
    from openalea.mtg.io import write_mtg

    present = g.property_names()
    text = write_mtg(g, properties=[p for p in PROPERTIES if p[0] in present])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def read(path: Path):
    from openalea.mtg.io import read_mtg

    return read_mtg(Path(path).read_text(encoding="utf-8"), verbose=False)
