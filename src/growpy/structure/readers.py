"""File parsers: one function per on-disk QSM format, each returning a ``RawQsm``.

Parsers do not interpret, correct or rename beyond the format itself; ``standardize``
does that for every format alike.

Formats verified against real files (2026-10-06):

``treeqsm_mat``   TreeQSM ``.mat``, both layouts: the 2.4 ``qsm.cylinder`` struct (Kew,
                  Belgium) and the older flat arrays ``Sta Axe Rad Len CPar CExt`` with
                  branches listed per branch in ``CiB`` (Ghent). MATLAB v7.3 (HDF5)
                  files would need h5py, which the growpy environment does not have.
``treeml_csv``    TreeML-Data ``optcsv``: TreeQSM cylinders as a csv.
``rtwig_csv``     rTwig standardised CSV (BioDiv-3DTrees corrected QSMs).
``graphml``       BioDiv-3DTrees point graph: nodes with position and radius.
``growth_json``   growpy / Grove skeleton: polylines, parent branch, radius per point
                  (the generated side of every comparison).
"""

from __future__ import annotations

import io
import json
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io as sio

from growpy.structure.standardize import RawQsm


def _xyz(frame: dict, prefix: str, array: np.ndarray) -> None:
    array = np.asarray(array, dtype=float).reshape(-1, 3)
    for i, c in enumerate("xyz"):
        frame[f"{prefix}_{c}"] = array[:, i]


def _one_based(array) -> np.ndarray:
    """MATLAB indices (1-based, 0 = none) -> row indices (0-based, -1 = none). Cast to a
    signed type first: the files store them as uint8 / uint16."""
    return np.atleast_1d(np.asarray(array)).astype(np.int64) - 1


def read_treeqsm_mat(source: str | Path | bytes) -> RawQsm:
    """A TreeQSM ``.mat`` file (path or its bytes) in either layout."""
    if isinstance(source, bytes):
        data, name = source, None
    else:
        data, name = Path(source).read_bytes(), Path(source).name
    if data[:4] == b"\x89HDF":
        raise ValueError(
            f"{name or 'input'} is a MATLAB v7.3 (HDF5) file; h5py is needed"
        )
    mat = sio.loadmat(io.BytesIO(data), squeeze_me=True, struct_as_record=False)
    qsm = mat.get("qsm")
    if qsm is not None and hasattr(qsm, "cylinder"):
        return _read_struct(qsm)
    if "Sta" in mat and "CPar" in mat:
        return _read_flat(mat)
    keys = [k for k in mat if not k.startswith("__")]
    raise ValueError(f"not a TreeQSM file (keys: {keys[:8]})")


def _read_struct(qsm) -> RawQsm:
    cyl = qsm.cylinder
    frame: dict = {}
    _xyz(frame, "start", cyl.start)
    _xyz(frame, "axis", cyl.axis)
    frame["length"] = np.atleast_1d(cyl.length).astype(float)
    frame["radius"] = np.atleast_1d(cyl.radius).astype(float)
    frame["radius_raw"] = np.atleast_1d(cyl.UnmodRadius).astype(float)
    frame["parent"] = _one_based(cyl.parent)
    frame["src_extension"] = _one_based(cyl.extension)
    frame["is_virtual"] = np.atleast_1d(cyl.added).astype(bool)
    frame["src_branch"] = np.atleast_1d(cyl.branch).astype(np.int64)
    frame["src_order"] = np.atleast_1d(cyl.BranchOrder).astype(np.int64)
    frame["src_pos"] = np.atleast_1d(cyl.PositionInBranch).astype(np.int64)
    return RawQsm(
        pd.DataFrame(frame),
        {
            "qsm_tool": "TreeQSM",
            "qsm_format": "treeqsm_mat_struct",
            # TreeQSM's TaperCor changes `radius`; UnmodRadius is the fitted value
            "radius_correction": "treeqsm_taper" if _flag(qsm, "TaperCor") else "none",
        },
    )


def _flag(qsm, name: str) -> bool:
    inputs = getattr(getattr(qsm, "rundata", None), "inputs", None)
    value = getattr(inputs, name, None)
    return bool(value) if value is not None else False


def _read_flat(mat: dict) -> RawQsm:
    n = len(np.atleast_1d(mat["Rad"]))
    frame: dict = {}
    _xyz(frame, "start", mat["Sta"])
    _xyz(frame, "axis", mat["Axe"])
    frame["length"] = np.atleast_1d(mat["Len"]).astype(float)
    frame["radius"] = np.atleast_1d(mat["Rad"]).astype(float)
    frame["parent"] = _one_based(mat["CPar"])
    frame["src_extension"] = _one_based(mat["CExt"])
    frame["is_virtual"] = np.atleast_1d(mat["Added"]).astype(bool)
    branch = np.full(n, -1, dtype=np.int64)
    pos = np.full(n, -1, dtype=np.int64)
    order = np.full(n, -1, dtype=np.int64)
    bord = np.atleast_1d(mat["BOrd"]).astype(np.int64)
    in_branch = mat["CiB"]
    if not (isinstance(in_branch, np.ndarray) and in_branch.dtype.kind == "O"):
        in_branch = [in_branch]  # squeeze_me flattens a one-branch tree
    for b, cyls in enumerate(in_branch):
        idx = _one_based(cyls)
        branch[idx] = b + 1
        pos[idx] = np.arange(1, len(idx) + 1)
        order[idx] = bord[b]
    frame.update(src_branch=branch, src_pos=pos, src_order=order)
    return RawQsm(
        pd.DataFrame(frame),
        {
            "qsm_tool": "TreeQSM",
            "qsm_format": "treeqsm_mat_flat",
            # these files keep no unmodified radius and do not say whether taper was applied
            "radius_correction": "unknown",
        },
    )


def read_treeml_csv(source: str | Path | bytes) -> RawQsm:
    """TreeML-Data ``optcsv`` file: one row per cylinder with 1-based ``cylinderID`` and
    ``parentCylID`` (0 = base), ``childCyID`` (the next cylinder in the same branch),
    ``branchID``, ``branchOrder``, ``posInBranch``, ``start_*``, unit ``axis_*``,
    ``length``, ``radius`` and ``addedVirtual``."""
    df = pd.read_csv(io.BytesIO(source) if isinstance(source, bytes) else source)
    row_of = pd.Series(np.arange(len(df)), index=df["cylinderID"].to_numpy())

    def as_row(ids: pd.Series) -> np.ndarray:  # 0 = none -> -1
        return row_of.reindex(ids.to_numpy()).fillna(-1).to_numpy(dtype=np.int64)

    frame = {
        "parent": as_row(df["parentCylID"]),
        "src_extension": as_row(df["childCyID"]),
        "src_branch": df["branchID"].to_numpy(),
        "src_order": df["branchOrder"].to_numpy(),
        "src_pos": df["posInBranch"].to_numpy(),
        "length": df["length"].to_numpy(dtype=float),
        "radius": df["radius"].to_numpy(dtype=float),
        "is_virtual": df["addedVirtual"].astype(str).str.lower().eq("true").to_numpy(),
    }
    _xyz(frame, "start", df[["start_x", "start_y", "start_z"]].to_numpy())
    _xyz(frame, "axis", df[["axis_x", "axis_y", "axis_z"]].to_numpy())
    return RawQsm(
        pd.DataFrame(frame),
        {
            "qsm_tool": "TreeQSM",
            "qsm_format": "treeml_csv",
            "radius_correction": "unknown",  # not documented with the files
        },
    )


def read_rtwig_csv(source: str | Path | bytes) -> RawQsm:
    """rTwig standardised cylinder CSV (BioDiv-3DTrees ``QSM/corrected/*_cor.csv``):
    1-based ``id`` with ``parent`` 0 for the base, ``start_*``, unit ``axis_*``, ``end_*``,
    ``radius`` (rTwig-corrected) and ``raw_radius`` (the TreeQSM fit), ``branch``,
    ``branch_order``, ``branch_position``. rTwig's derived columns (segments, growth
    length, pipe model) are not read: they are recomputable from the geometry."""
    df = pd.read_csv(io.BytesIO(source) if isinstance(source, bytes) else source)
    row_of = pd.Series(np.arange(len(df)), index=df["id"].to_numpy())
    frame = {
        "parent": row_of.reindex(df["parent"].to_numpy())
        .fillna(-1)
        .to_numpy(dtype=np.int64),
        "src_branch": df["branch"].to_numpy(),
        "src_order": df["branch_order"].to_numpy(),
        "src_pos": df["branch_position"].to_numpy(),
        "length": df["length"].to_numpy(dtype=float),
        "radius": df["radius"].to_numpy(dtype=float),
        "radius_raw": df["raw_radius"].to_numpy(dtype=float),
    }
    for prefix in ("start", "axis", "end"):
        _xyz(
            frame, prefix, df[[f"{prefix}_x", f"{prefix}_y", f"{prefix}_z"]].to_numpy()
        )
    return RawQsm(
        pd.DataFrame(frame),
        {
            "qsm_tool": "TreeQSM + rTwig",
            "qsm_version": "TreeQSM 2.4.1, rTwig 1.4.0",
            "qsm_format": "rtwig_csv",
            "radius_correction": "rtwig",
        },
    )


def read_growth_json(path: str | Path) -> RawQsm:
    """A growpy growth JSON (a Grove skeleton): polylines of shared points with a parent
    branch, one radius per point in ``budLateralMeristem``. Each polyline segment becomes a
    cylinder whose radius is the mean of its two end points. The file is y-up; the exchange
    table is z up, mapped like ``qsm_graph_to_growth`` (y -> z, z -> y), which mirrors the
    tree and is harmless for every descriptor. The radius is Grove's raw one, not the
    yield-table calibrated one realised at export (``radius_correction`` is ``none``).

    In a Grove file a branch's first point is a vertex of its parent polyline: the first
    cylinder grows from the parent cylinder that ends at that vertex, or from the parent's
    first cylinder when the branch starts at the parent's base. A file written from a QSM
    (``growth_json.to_growth_json``) gives a branch its own first point; it then grows from
    the nearest cylinder of the polyline ``branchParentNumber`` names."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    pos = np.asarray(data["points"]["positions"], dtype=float)
    radii = np.asarray(
        [r[0] for r in data["points"]["attributes"]["budLateralMeristem"]["values"]],
        dtype=float,
    )
    lines = data["primitives"]["points"]
    attrs = data["primitives"].get("attributes", {})
    numbers = attrs.get("branchNumber", {}).get("values")
    parent_numbers = attrs.get("branchParentNumber", {}).get("values")
    line_of_number = {n: i for i, n in enumerate(numbers)} if numbers else {}
    rows: list[dict] = []
    ending: dict[int, int] = {}  # point index -> row of the cylinder that ends there
    first_of: dict[int, int] = {}  # polyline number -> row of its first cylinder
    rows_of: dict[int, list[int]] = {}  # polyline number -> its cylinder rows

    def nearest(point: np.ndarray, candidates: list[int]) -> int:
        """Row of the candidate cylinder whose segment passes closest to ``point``."""
        best, best_d = -1, np.inf
        for r in candidates:
            a = np.array([rows[r]["start_x"], rows[r]["start_z"], rows[r]["start_y"]])
            b = np.array([rows[r]["end_x"], rows[r]["end_z"], rows[r]["end_y"]])
            ab = b - a
            t = np.clip(np.dot(point - a, ab) / max(np.dot(ab, ab), 1e-12), 0.0, 1.0)
            d = float(np.linalg.norm(point - (a + t * ab)))
            if d < best_d:
                best, best_d = r, d
        return best

    for number, line in enumerate(lines):
        previous = -1
        rows_of[number] = []
        for a, b in zip(line, line[1:], strict=False):
            if previous < 0:
                first_of[number] = len(rows)
                parent = ending.get(a, -1)
                if parent < 0:  # the branch starts at its parent's own base point
                    parent = next(
                        (first_of[q] for q in range(number) if lines[q][0] == a), -1
                    )
                if (
                    parent < 0 and number > 0
                ):  # its own first point: nearest parent cylinder
                    owner = (
                        line_of_number.get(parent_numbers[number])
                        if parent_numbers is not None
                        else None
                    )
                    candidates = (
                        rows_of.get(owner, [])
                        if owner is not None
                        else [r for q in range(number) for r in rows_of[q]]
                    )
                    parent = nearest(pos[a], candidates)
            else:
                parent = previous
            start, end = pos[a], pos[b]
            rows.append(
                {
                    "parent": parent,
                    "start_x": start[0],
                    "start_y": start[2],
                    "start_z": start[1],
                    "end_x": end[0],
                    "end_y": end[2],
                    "end_z": end[1],
                    "length": float(np.linalg.norm(end - start)),
                    "radius": 0.5 * (radii[a] + radii[b]),
                }
            )
            ending[b] = previous = len(rows) - 1
            rows_of[number].append(previous)
    return RawQsm(
        pd.DataFrame(rows),
        {
            "qsm_tool": "The Grove",
            "qsm_format": "growpy_growth_json",
            "radius_correction": "none",
        },
    )


def read_graphml(path: str | Path) -> RawQsm:
    """BioDiv-3DTrees point graph: one cylinder per edge, from the node nearer the lowest
    point to the other, radius the mean of its two end nodes. The graph is undirected,
    so it is rooted at its lowest node (the tree base)."""
    from growpy.tools.qsm_graph_to_growth import read_graphml as read_nodes

    nodes, edges = read_nodes(Path(path))
    adjacency: dict[str, list[str]] = {n: [] for n in nodes}
    for a, b in edges:
        adjacency[a].append(b)
        adjacency[b].append(a)
    root = min(nodes, key=lambda n: nodes[n][2])
    parent_node = {root: None}
    order = [root]
    for node in order:
        for nxt in adjacency[node]:
            if nxt not in parent_node:
                parent_node[nxt] = node
                order.append(nxt)
    cyl_of = {n: i for i, n in enumerate(order[1:])}  # cylinder ending at node n
    rows = []
    for n in order[1:]:
        p = parent_node[n]
        a, b = nodes[p], nodes[n]
        rows.append(
            {
                "parent": cyl_of.get(p, -1),
                "start_x": a[0],
                "start_y": a[1],
                "start_z": a[2],
                "end_x": b[0],
                "end_y": b[1],
                "end_z": b[2],
                "length": float(np.linalg.norm(np.subtract(b[:3], a[:3]))),
                "radius": 0.5 * (a[3] + b[3]),
            }
        )
    return RawQsm(
        pd.DataFrame(rows),
        {
            "qsm_tool": "TreeQSM",
            "qsm_version": "2.4.1",
            "qsm_format": "biodiv_graphml",
            # the files are named *_cor_graph; the BioDiv paper's correction is rTwig, but
            # the graph's own radius provenance is not documented
            "radius_correction": "unknown",
        },
    )
