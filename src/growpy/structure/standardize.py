"""Raw cylinders from any reader -> a standardised ``QsmTree``.

A reader (``readers.py``) only parses a file into a ``RawQsm``. Everything that must be
identical across sources happens here, once: the frame (metres, z up, base at the origin),
the axis rule, the height / DBH / volume measured on the cylinders, and the quality
numbers. DBH and height are therefore comparable between datasets even when one source
reports DBH from the point cloud and another from the QSM.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
import pandas as pd

from growpy.structure.axes import assign_axes, attached_to_main_base, axis_table
from growpy.structure.exchange import to_exchange
from growpy.structure.schema import TREE_COLUMNS, QsmTree

BREAST_HEIGHT_M = 1.3
DBH_WINDOW_M = 0.2  # DBH = mean trunk diameter within 1.3 m +- this
MIN_LATERAL_AXIS_M = 0.5  # shorter first-order axes do not count as the crown base
GAP_TOLERANCE_M = 0.05  # on top of twice the parent radius


@dataclass
class RawQsm:
    """What a reader returns. ``cyl`` columns: ``parent`` (row index, -1 for a base),
    ``start_x/y/z``, ``length``, ``radius`` and either ``end_x/y/z`` or ``axis_x/y/z``
    (unit vector); optional ``radius_raw``, ``is_virtual``, ``src_branch``,
    ``src_order``, ``src_pos``, ``src_extension``. ``info`` holds what the file itself
    says (tool, format, radius correction, location)."""

    cyl: pd.DataFrame
    info: dict = field(default_factory=dict)


def _vec(df: pd.DataFrame, prefix: str) -> np.ndarray:
    return df[[f"{prefix}_x", f"{prefix}_y", f"{prefix}_z"]].to_numpy(dtype=float)


def _complete(df: pd.DataFrame) -> pd.DataFrame:
    df = df.reset_index(drop=True).copy()
    start = _vec(df, "start")
    if "end_x" not in df:
        end = start + _vec(df, "axis") * df["length"].to_numpy(dtype=float)[:, None]
        for i, c in enumerate("xyz"):
            df[f"end_{c}"] = end[:, i]
    if "length" not in df:
        df["length"] = np.linalg.norm(_vec(df, "end") - start, axis=1)
    if "axis_x" not in df:
        # a zero-length cylinder has no direction; (0, 0, 1) keeps the vector a unit one
        vec = _vec(df, "end") - start
        length = df["length"].to_numpy(dtype=float)
        unit = np.where(
            length[:, None] > 0,
            vec / np.maximum(length, 1e-12)[:, None],
            [0.0, 0.0, 1.0],
        )
        for i, c in enumerate("xyz"):
            df[f"axis_{c}"] = unit[:, i]
    df["radius_raw"] = df["radius_raw"] if "radius_raw" in df else np.nan
    df["is_virtual"] = df["is_virtual"].astype(bool) if "is_virtual" in df else False
    for col in ("src_branch", "src_order", "src_pos", "src_extension"):
        df[col] = df[col].astype(int) if col in df else -1
    df["parent"] = df["parent"].astype(int)
    return df


def measure(cyl: pd.DataFrame, continues: np.ndarray) -> dict:
    """Tree-level numbers measured on standardised cylinders (z up, base at z = 0)."""
    radius = cyl["radius"].to_numpy(dtype=float)
    length = cyl["length"].to_numpy(dtype=float)
    trunk = cyl[cyl["axis_order"] == 0]
    z0 = np.minimum(trunk["start_z"], trunk["end_z"])
    z1 = np.maximum(trunk["start_z"], trunk["end_z"])
    lo, hi = BREAST_HEIGHT_M - DBH_WINDOW_M, BREAST_HEIGHT_M + DBH_WINDOW_M
    overlap = (np.minimum(z1, hi) - np.maximum(z0, lo)).clip(lower=0)
    dbh = (
        2 * float(np.average(trunk["radius"], weights=overlap))
        if overlap.sum() > 0
        else np.nan
    )
    axes = axis_table(cyl)
    lateral = axes[(axes["axis_order"] == 1) & (axes["length"] >= MIN_LATERAL_AXIS_M)]
    crown_base = (
        float(cyl.loc[lateral["base_cyl"], "start_z"].min()) if len(lateral) else np.nan
    )

    child = cyl[cyl["parent"] >= 0]
    p = cyl.loc[child["parent"]]
    a = p[["start_x", "start_y", "start_z"]].to_numpy()
    ab = p[["end_x", "end_y", "end_z"]].to_numpy() - a
    pt = child[["start_x", "start_y", "start_z"]].to_numpy() - a
    denom = np.maximum((ab**2).sum(axis=1), 1e-12)
    t = np.clip((pt * ab).sum(axis=1) / denom, 0.0, 1.0)
    gap = np.linalg.norm(pt - ab * t[:, None], axis=1)
    gap_bad = gap > 2 * p["radius"].to_numpy() + GAP_TOLERANCE_M
    bases = child[child["axis_pos"] == 0]
    thick = (
        bases["radius"].to_numpy() > 1.1 * cyl.loc[bases["parent"], "radius"].to_numpy()
    )

    known = (cyl["src_extension"].to_numpy() >= 0) & (continues >= 0)
    agreement = (
        float((continues[known] == cyl["src_extension"].to_numpy()[known]).mean())
        if known.any()
        else np.nan
    )
    return {
        "n_cyl": len(cyl),
        "n_axes": len(axes),
        "max_axis_order": int(cyl["axis_order"].max()),
        "height_m": float(cyl["end_z"].max()),
        "dbh_m": dbh,
        "volume_m3": float((np.pi * radius**2 * length).sum()),
        "trunk_length_m": float(trunk["length"].sum()),
        "branch_length_m": float(length.sum() - trunk["length"].sum()),
        "crown_base_m": crown_base,
        "radius_min_m": float(radius.min()),
        "length_median_m": float(np.median(length)),
        "virtual_frac": float(cyl["is_virtual"].mean()),
        "gap_frac": float(gap_bad.mean()) if len(gap_bad) else 0.0,
        "thick_branch_frac": float(thick.mean()) if len(thick) else 0.0,
        "axis_agreement": agreement,
    }


def standardize(raw: RawQsm, meta: dict) -> QsmTree:
    """Frame, axes and measurements for one tree. ``meta`` carries identity, species and
    reported values (keys of ``TREE_COLUMNS``); reader ``info`` fills the QSM provenance."""
    df = _complete(raw.cyl)
    n_roots = int((df["parent"] < 0).sum())
    keep = attached_to_main_base(df["parent"].to_numpy(), df["length"].to_numpy())
    detached = df[~keep]
    if len(detached):
        new_row = np.cumsum(keep) - 1  # old row -> row after the fragments are dropped
        df = df[keep].copy()
        df["parent"] = np.where(
            df["parent"] < 0, -1, new_row[df["parent"].clip(lower=0)]
        )
        df["src_extension"] = np.where(
            df["src_extension"] < 0, -1, new_row[df["src_extension"].clip(lower=0)]
        )
        df = df.reset_index(drop=True)
    if not 0.0005 < float(df["radius"].median()) < 5.0:
        raise ValueError(
            f"median radius {df['radius'].median():.4g} is not metres (cm or mm input?)"
        )
    axes, continues = assign_axes(
        df["parent"].to_numpy(), df["length"].to_numpy(), df["radius"].to_numpy()
    )
    df = pd.concat([df, axes[["axis_id", "axis_order", "axis_pos"]]], axis=1)
    base = df.loc[
        (df["axis_id"] == 0) & (df["axis_pos"] == 0), ["start_x", "start_y", "start_z"]
    ]
    origin = base.iloc[0].to_numpy(dtype=float)
    for i, c in enumerate("xyz"):
        df[f"start_{c}"] -= origin[i]
        df[f"end_{c}"] -= origin[i]
    df.insert(0, "cyl_id", np.arange(len(df)))
    tree_meta = dict.fromkeys(TREE_COLUMNS)
    tree_meta.update({k: v for k, v in raw.info.items() if k in tree_meta})
    tree_meta.update({k: v for k, v in meta.items() if k in tree_meta})
    tree_meta.update(measure(df, continues))
    tree_meta.update(
        n_roots=n_roots,
        detached_cyl=len(detached),
        detached_length_m=float(detached["length"].sum()),
    )
    tree_meta.update(base_x_src=origin[0], base_y_src=origin[1], base_z_src=origin[2])
    return QsmTree(meta=tree_meta, cyl=to_exchange(df))
