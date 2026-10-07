"""The exchange table: the TreeQSM / rTwig cylinder conventions, which every other part of
the lab already speaks.

Inside ``growpy.structure`` cylinders are addressed by row (0-based, -1 for no parent),
which is what numpy wants. Everything that is stored or handed to another tool uses the
convention the published datasets, rTwig and ``digital-twin-db`` share:

* ``id`` counts from 1 and ``parent`` is 0 for the base (TreeQSM ``.mat`` and rTwig CSV
  say the same, so does ``trees.qsm_cylinders.cylinder_index``);
* ``start_*`` is the cylinder base, ``axis_*`` the unit vector to its top, ``end_*`` the top;
* ``radius`` is what the source delivered, ``raw_radius`` the unmodified fit when known;
* ``branch`` (from 1), ``branch_order`` (0 = trunk) and ``branch_position`` (from 1) are
  the rTwig names, filled here with the lab's single axis rule, not the source's own ids
  (those are kept as ``src_*``).

``to_exchange`` / ``from_exchange`` convert between the two so a stored dataset can be read
back into the row-based form without loss.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from growpy.structure.schema import CYL_COLUMNS

_INT_SRC = ("src_branch", "src_order", "src_position")


def to_exchange(work: pd.DataFrame) -> pd.DataFrame:
    """Row-based working frame -> exchange table (``CYL_COLUMNS``)."""
    out = pd.DataFrame(index=range(len(work)))
    out["id"] = work["cyl_id"].to_numpy() + 1
    out["parent"] = work["parent"].to_numpy() + 1
    for prefix in ("start", "axis", "end"):
        for c in "xyz":
            out[f"{prefix}_{c}"] = work[f"{prefix}_{c}"].to_numpy()
    out["length"] = work["length"].to_numpy()
    out["radius"] = work["radius"].to_numpy()
    out["raw_radius"] = work["radius_raw"].to_numpy()
    out["is_virtual"] = work["is_virtual"].to_numpy()
    out["branch"] = work["axis_id"].to_numpy() + 1
    out["branch_order"] = work["axis_order"].to_numpy()
    out["branch_position"] = work["axis_pos"].to_numpy() + 1
    for dst, src in zip(_INT_SRC, ("src_branch", "src_order", "src_pos"), strict=True):
        known = work[src].to_numpy() >= 0
        out[dst] = pd.array(np.where(known, work[src].to_numpy(), 0), dtype="Int64")
        out.loc[~known, dst] = pd.NA
    out["src_extension"] = work["src_extension"].to_numpy() + 1  # 0 = none
    return out[CYL_COLUMNS]


def from_exchange(cyl: pd.DataFrame) -> pd.DataFrame:
    """Exchange table -> row-based working frame (the inverse of ``to_exchange``)."""
    work = pd.DataFrame(index=range(len(cyl)))
    work["cyl_id"] = cyl["id"].to_numpy() - 1
    work["parent"] = cyl["parent"].to_numpy() - 1
    for prefix in ("start", "axis", "end"):
        for c in "xyz":
            work[f"{prefix}_{c}"] = cyl[f"{prefix}_{c}"].to_numpy()
    work["length"] = cyl["length"].to_numpy()
    work["radius"] = cyl["radius"].to_numpy()
    work["radius_raw"] = cyl["raw_radius"].to_numpy()
    work["is_virtual"] = cyl["is_virtual"].to_numpy().astype(bool)
    work["axis_id"] = cyl["branch"].to_numpy() - 1
    work["axis_order"] = cyl["branch_order"].to_numpy()
    work["axis_pos"] = cyl["branch_position"].to_numpy() - 1
    for dst, src in zip(("src_branch", "src_order", "src_pos"), _INT_SRC, strict=True):
        work[dst] = cyl[src].fillna(-1).to_numpy().astype(np.int64)
    work["src_extension"] = cyl["src_extension"].to_numpy() - 1
    return work
