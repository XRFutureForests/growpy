"""Structure descriptors on the cylinder table, one code path for scanned and generated trees.

Three groups, each value declared in ``DEFINITIONS`` with level, unit, frame and how well it
survives a TLS/QSM scan (the hub's descriptor schema, ``branching-architecture/
descriptor-schema``):

``L*``  tree, crown, node and branch geometry (the ports of ``growpy-structure-descriptors``),
        measured on each branch from its OWN first cylinder (a Grove growth JSON gives a
        branch its parent's vertex as first point, which made branch:stem radius read 1.0)
``G*``  growth-rule fingerprint, size-free: what a stochastic L-system rule per axis order
        would need - lateral density, insertion angle and lateral length relative to the
        parent's remaining length by relative position on the parent, fork share, pipe
        exponent, fork asymmetry
``T*``  topology, scale-free: Strahler orders with bifurcation and length ratios, path-length
        fraction, partition asymmetry, length and radius scaling between axis orders
``S*``  branching sequence along axes: each axis cut into ten parts, each part labelled by
        its strongest lateral (none, short, long, fork); the label shares, a first-order
        Markov chain along them, and the unbranched base and tip zones
``F*``  branch and crown form, the traits the eye reads and the angle descriptors miss
        (Grove preset tuning, 2026-10-07/08): dangling lower branches, branches that sag and
        curl up ("wave"), how irregular branch lengths and whorls are (azimuth gaps, counts,
        missing branches), holes in the crown, crown asymmetry, the branch-angle gradient
        down the crown, the leader above the top whorl, crown diameter per DBH

Before anything is measured both kinds of tree are cut to a common resolution
(``prune``): a QSM loses small branches and Grove keeps every twig, so without it the
counts, ratios and Strahler orders differ by construction. Absolute sizes (heights, metres)
are only in the L group; G and T are ratios, angles and exponents.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from growpy.structure.axes import assign_axes
from growpy.structure.exchange import from_exchange

HEAD_M = 0.3  # initial and tip directions are read over 30 cm
MIN_BRANCH_M = 0.5  # shorter first-order axes do not count as branches
MIN_LATERAL_M = 0.2  # shorter laterals do not count in the growth-rule fingerprint
NODE_TOL_M = 0.1  # first-order branches attached within this arc length form one node
FORK_SHARE = (
    0.5  # a lateral is a fork when its subtree is at least half the continuation's
)

LEVELS = {
    "L": "tree, crown, node and branch geometry",
    "G": "growth-rule fingerprint",
    "T": "topology",
    "S": "branching sequence along axes",
    "F": "branch and crown form",
}
LOWER_CROWN = (
    0.4  # "lower crown" = the lowest 40 % of the span from lowest branch to top
)
HANG_DEG = 120.0  # pointing more than 30 deg below horizontal, measured from vertical
WAVE_MIN_M = 1.0  # first-order branches shorter than this get no wave measure
BREAST_HEIGHT_M = (
    1.3  # same rule as standardize.measure: mean trunk diameter at 1.3 +- 0.2 m
)
DBH_WINDOW_M = 0.2
SHORT_RATIO = (
    0.2  # a lateral shorter than this share of the parent beyond it is "short"
)
MIN_PARENT_M = 1.0  # axes shorter than this get no sequence
TOP_N = 5  # rank-matched branch descriptors use the N longest first-order branches per third
SYMBOLS = (
    "none",
    "short",
    "long",
    "fork",
)  # ranked: a decile takes its strongest event

# key -> (unit, frame, robustness to TLS/QSM, description)
DEFINITIONS: dict[str, tuple[str, str, str, str]] = {
    "L1.height_m": ("m", "base to highest cylinder end", "yes", "tree height"),
    "L1.trunk_lean_deg": (
        "deg",
        "from vertical, chord from the trunk base to its top",
        "yes",
        "trunk lean",
    ),
    "L1.trunk_sinuosity": (
        "-",
        "trunk arc length / base-to-top chord (1 = straight)",
        "yes",
        "trunk sinuosity",
    ),
    "L1.trunk_bow_rel": (
        "-",
        "largest distance of the trunk from its base-to-top chord / tree height",
        "yes",
        "trunk bow",
    ),
    "L1.crown_base_m": (
        "m",
        "lowest first-order branch >= 0.5 m",
        "weak",
        "crown base, lowest-branch rule",
    ),
    "L1.crown_base_p10_m": (
        "m",
        "10th percentile of first-order attachment heights",
        "weak",
        "crown base, percentile rule",
    ),
    "L1.crown_ratio": (
        "-",
        "(height - crown_base_p10) / height",
        "yes",
        "crown length ratio",
    ),
    "L1.crown_width_over_height": (
        "-",
        "2 x p95 horizontal distance from the trunk / height",
        "yes",
        "crown width over height",
    ),
    "L1.widest_at_depth": (
        "-",
        "relative depth below the top, 0 top .. 1 crown base",
        "yes",
        "where the crown is widest",
    ),
    **{
        f"L1.crown_width_rel_d{k:02d}": (
            "-",
            f"2 x p95 horizontal distance from the trunk / height, tenth {k} of crown depth (1 = top)",
            "yes",
            f"crown outline, depth tenth {k}",
        )
        for k in range(1, 11)
    },
    **{
        f"L4.top5_{name}_{third}": (
            unit,
            f"median over the 5 longest first-order branches of the {third} crown third; {frame}",
            "yes",
            f"{text} of the longest branches, {third} third",
        )
        for third in ("top", "middle", "bottom")
        for name, unit, frame, text in (
            ("length_rel", "-", "branch length / tree height", "relative length"),
            (
                "chord_angle_deg",
                "deg",
                "from vertical, base to the point at half length",
                "branch angle",
            ),
            ("initial_angle_deg", "deg", "from vertical, first 0.3 m", "initial angle"),
        )
    },
    "L3.nodes_per_m": (
        "1/m",
        "first-order nodes per metre of crown length, attachments within 0.1 m merged",
        "weak",
        "node frequency on the trunk",
    ),
    "L3.branches_per_node_p50": (
        "-",
        "first-order branches >= 0.5 m per node",
        "weak",
        "branches per node",
    ),
    "L3.tier_spacing_p50_m": (
        "m",
        "arc length between successive trunk nodes",
        "weak",
        "tier spacing",
    ),
    "L3.tier_spacing_cv": (
        "-",
        "coefficient of variation of tier spacing",
        "weak",
        "regularity of tier spacing",
    ),
    **{
        f"L4.{name}_{third}": (
            unit,
            frame,
            robust,
            f"{text}, {third} third of the crown",
        )
        for third in ("top", "middle", "bottom")
        for name, unit, frame, robust, text in (
            (
                "chord_angle_deg",
                "deg",
                "from vertical, base to the point at half length",
                "yes",
                "branch angle",
            ),
            (
                "initial_angle_deg",
                "deg",
                "from vertical, first 0.3 m",
                "yes",
                "initial branch angle",
            ),
            (
                "length_m",
                "m",
                "arc length of the first-order axis",
                "yes",
                "branch length",
            ),
            (
                "length_rel",
                "-",
                "branch length / tree height",
                "yes",
                "relative branch length",
            ),
            (
                "radius_ratio",
                "-",
                "branch first cylinder / trunk cylinder it grows from",
                "weak",
                "branch:stem radius",
            ),
            ("straightness", "-", "chord / arc length", "weak", "branch straightness"),
        )
    },
    "L4.tip_angle_deg_p50": (
        "deg",
        "from vertical, last 0.3 m of first-order branches",
        "no",
        "tip angle",
    ),
    "L4.upturned_share": (
        "-",
        "share of first-order tips pointing above horizontal",
        "no",
        "upturned tips",
    ),
    **{
        f"G.k{k}.{name}": (
            unit,
            frame,
            robust,
            f"{text}, laterals of order {k + 1} on order-{k} axes",
        )
        for k in (0, 1)
        for name, unit, frame, robust, text in (
            (
                "lateral_density_per_m",
                "1/m",
                "laterals >= 0.2 m per metre of parent axis",
                "weak",
                "lateral density",
            ),
            (
                "attach_relpos_p50",
                "-",
                "relative position on the parent, 0 base .. 1 tip",
                "yes",
                "median attachment position",
            ),
            (
                "insertion_deg_base",
                "deg",
                "between lateral's first 0.3 m and parent cylinder axis, parent base third",
                "yes",
                "insertion angle",
            ),
            (
                "insertion_deg_mid",
                "deg",
                "same, middle third of the parent",
                "yes",
                "insertion angle",
            ),
            (
                "insertion_deg_tip",
                "deg",
                "same, tip third of the parent",
                "yes",
                "insertion angle",
            ),
            (
                "length_ratio_base",
                "-",
                "lateral length / parent length beyond the attachment, base third",
                "yes",
                "apical control",
            ),
            ("length_ratio_mid", "-", "same, middle third", "yes", "apical control"),
            ("length_ratio_tip", "-", "same, tip third", "yes", "apical control"),
            (
                "fork_share",
                "-",
                "laterals whose subtree is >= 0.5 of the continuation's",
                "yes",
                "fork share",
            ),
        )
    },
    "G.pipe_exponent_p50": (
        "-",
        "a in r_parent^a = sum r_child^a at branching cylinders",
        "weak",
        "pipe-model exponent (2 = area preserving)",
    ),
    "G.area_ratio_p50": (
        "-",
        "sum r_child^2 / r_parent^2 at branching cylinders",
        "weak",
        "cross-section ratio at forks",
    ),
    "G.fork_asymmetry_p50": (
        "-",
        "smaller / larger subtree length of the two largest children",
        "yes",
        "fork asymmetry",
    ),
    **{
        f"S.k{k}.{name}": (unit, frame, robust, f"{text}, along order-{k} axes")
        for k in (0, 1)
        for name, unit, frame, robust, text in (
            (
                "bare_base_rel",
                "-",
                "relative position of the first lateral >= 0.2 m, 0 base .. 1 tip",
                "weak",
                "unbranched base zone",
            ),
            (
                "bare_tip_rel",
                "-",
                "1 - relative position of the last lateral",
                "weak",
                "unbranched apical zone",
            ),
            *(
                (
                    f"share_{s}",
                    "-",
                    "share of axis deciles whose strongest event is this one",
                    "weak",
                    f"{s} deciles",
                )
                for s in SYMBOLS
            ),
            *(
                (
                    f"persist_{s}",
                    "-",
                    "P(next decile has the same event | this one), first-order Markov",
                    "weak",
                    f"{s} persistence",
                )
                for s in SYMBOLS
            ),
        )
    },
    "T.strahler_max": (
        "-",
        "Horton-Strahler order of the base, counted from the tips",
        "no",
        "maximum Strahler order",
    ),
    "T.bifurcation_ratio": (
        "-",
        "geometric mean of N(k) / N(k+1) over Strahler streams",
        "no",
        "bifurcation ratio",
    ),
    "T.length_ratio": (
        "-",
        "geometric mean of mean stream length L(k+1) / L(k)",
        "weak",
        "Strahler length ratio",
    ),
    "T.path_fraction": (
        "-",
        "mean base-to-tip path length / longest path",
        "weak",
        "path-length fraction",
    ),
    "T.partition_asymmetry": (
        "-",
        "Van Pelt |r - s| / (r + s - 2) over forks, tip counts",
        "weak",
        "topological asymmetry",
    ),
    "T.axis_length_ratio_1_0": (
        "-",
        "median order-1 axis length / trunk length",
        "yes",
        "length scaling order 1 to 0",
    ),
    "T.axis_length_ratio_2_1": (
        "-",
        "median order-2 / median order-1 axis length",
        "weak",
        "length scaling order 2 to 1",
    ),
    "T.axis_radius_ratio_2_1": (
        "-",
        "median base radius order 2 / order 1",
        "weak",
        "radius scaling order 2 to 1",
    ),
    "T.n_axes_order_1": (
        "-",
        "axes of order 1 after pruning",
        "weak",
        "first-order axis count",
    ),
    "T.n_axes_order_2": (
        "-",
        "axes of order 2 after pruning",
        "no",
        "second-order axis count",
    ),
    "F.crown_m_per_dbh_cm": (
        "m/cm",
        "crown diameter (L1 crown width) / DBH in cm; DBH as passed to describe(), else the "
        "trunk at 1.3 +- 0.2 m (a Grove skeleton's raw radius runs ~1.2x the exported DBH: "
        "pass dbh_m_reported for generated trees)",
        "yes",
        "crown diameter per DBH",
    ),
    "F.lower_hang_len_frac": (
        "-",
        "first-order branches >= 0.5 m attached in the lowest 40 % of the crown span: share "
        "of their length pointing more than 30 deg below horizontal",
        "weak",
        "dangling lower branches",
    ),
    "F.lower_tips_hanging": (
        "-",
        "same branches: share whose last 0.3 m points more than 30 deg below horizontal",
        "no",
        "hanging lower tips",
    ),
    "F.wave_sag_rel_p50": (
        "-",
        "first-order branches >= 1 m: deepest point below the base-to-tip chord / branch "
        "length (0 = no belly)",
        "weak",
        "branch belly, the sag of a branch that curls up again",
    ),
    "F.wave_rise_rel_p50": (
        "-",
        "same branches: highest point above the base-to-tip chord / branch length",
        "weak",
        "branch arching",
    ),
    "F.wave_tip_turn_deg_p50": (
        "deg",
        "same branches: angle between the first and the last 0.3 m",
        "no",
        "tip curl",
    ),
    "F.length_cv_p50": (
        "-",
        "coefficient of variation of first-order branch length within each tenth of the "
        "crown height that holds >= 3 branches, median over tenths",
        "weak",
        "irregularity of branch lengths",
    ),
    "F.whorl_gap_cv_p50": (
        "-",
        "trunk nodes with >= 3 first-order branches: coefficient of variation of the azimuth "
        "gaps between neighbouring branches, median over nodes (0 = evenly spaced)",
        "weak",
        "irregularity of branch azimuths in a whorl",
    ),
    "F.crown_offset_rel": (
        "-",
        "horizontal distance of the mean first-order tip position from the trunk / mean "
        "tip distance from the trunk (0 = symmetric crown)",
        "yes",
        "crown asymmetry",
    ),
    "F.angle_gradient_deg": (
        "deg",
        "chord angle from vertical of the 5 longest first-order branches, bottom third "
        "minus top third (> 0: steeper at the top, flatter below)",
        "yes",
        "branch angle gradient down the crown",
    ),
    "F.branches_per_node_cv": (
        "-",
        "coefficient of variation of the first-order branch count per trunk node "
        "(0 = every whorl the same)",
        "weak",
        "irregularity of whorl counts",
    ),
    "F.whorl_gap_max_deg_p50": (
        "deg",
        "trunk nodes with >= 2 first-order branches: largest azimuth gap between "
        "neighbouring branches, median over nodes (an even whorl of n: 360 / n)",
        "weak",
        "missing branches in a whorl",
    ),
    "F.crown_holes_share": (
        "-",
        "the crown span (lowest first-order branch to top) cut into 10 heights x 8 "
        "azimuth sectors around the trunk: share of cells no first-order branch reaches",
        "weak",
        "holes in the crown",
    ),
    "F.leader_m": (
        "m",
        "trunk arc length above the topmost first-order attachment (the twig audit's "
        "leader)",
        "weak",
        "leader length",
    ),
    "F.leader_rel": ("-", "F.leader_m / tree height", "weak", "relative leader length"),
}
CROWN_BANDS, CROWN_SECTORS = 10, 8  # F.crown_holes_share grid
HOLE_STEP_M = 0.25  # branch polylines are sampled this finely for the hole grid
HOLE_MIN_REACH_M = 0.1  # samples this close to the trunk have no meaningful azimuth


def definitions_table() -> pd.DataFrame:
    rows = [
        {
            "key": k,
            "level": LEVELS[k[0]],
            "unit": u,
            "frame": f,
            "robust": r,
            "description": d,
        }
        for k, (u, f, r, d) in DEFINITIONS.items()
    ]
    return pd.DataFrame(rows)


# --- resolution ----------------------------------------------------------------------


def _keep_rows(work: pd.DataFrame, keep: np.ndarray) -> pd.DataFrame:
    """Rows where ``keep`` (closed under descendants), parents re-indexed, axes rerun."""
    new_row = np.cumsum(keep) - 1
    work = work[keep].reset_index(drop=True)
    work["parent"] = np.where(
        work["parent"] < 0, -1, new_row[work["parent"].clip(lower=0)]
    )
    axes, _ = assign_axes(
        work["parent"].to_numpy(), work["length"].to_numpy(), work["radius"].to_numpy()
    )
    work[["axis_id", "axis_order", "axis_pos"]] = axes[
        ["axis_id", "axis_order", "axis_pos"]
    ].to_numpy()
    return work


def prune(
    cyl: pd.DataFrame,
    min_radius_m: float = 0.0,
    max_order: int | None = None,
    min_length_m: float = 0.0,
) -> pd.DataFrame:
    """Cut a tree to a common resolution and recompute its axes. Returns a row-based frame.

    Three rules, each dropping whole subtrees, applied in this order:
    ``min_radius_m``  a cylinder thinner than this goes, with everything growing from it
                      (off by default: radius means different things per source, and the
                      Grove skeleton keeps a radius floor where a QSM does not)
    ``min_length_m``  a lateral axis shorter than this goes, with its descendants: the
                      length below which a scan stops resolving branches
    ``max_order``     axes above this order go
    """
    work = from_exchange(cyl)
    parent = work["parent"].to_numpy()
    radius = work["radius"].to_numpy()
    keep = np.zeros(len(work), dtype=bool)
    for i in _topological(parent):
        keep[i] = parent[i] < 0 or (keep[parent[i]] and radius[i] >= min_radius_m)
    work = _keep_rows(work, keep)
    if min_length_m > 0:
        length = work.groupby("axis_id")["length"].sum()
        base = work[work["axis_pos"] == 0].set_index("axis_id")
        parent_axis = base["parent"].map(
            lambda p: int(work.at[p, "axis_id"]) if p >= 0 else -1
        )
        dropped: dict[int, bool] = {}
        for a in sorted(base.index):  # an axis is numbered after the axis it grows from
            pa = int(parent_axis[a])
            dropped[a] = pa >= 0 and (length[a] < min_length_m or dropped[pa])
        work = _keep_rows(work, ~work["axis_id"].map(dropped).to_numpy(dtype=bool))
    if max_order is not None and (work["axis_order"] > max_order).any():
        # closed under descendants: order only grows away from the trunk
        work = _keep_rows(work, (work["axis_order"] <= max_order).to_numpy())
    work["cyl_id"] = np.arange(len(work))
    return work


def _topological(parent: np.ndarray) -> list[int]:
    children: list[list[int]] = [[] for _ in range(len(parent))]
    order = []
    for i, p in enumerate(parent):
        (order if p < 0 else children[p]).append(i)
    for i in order:
        order.extend(children[i])
    return order


# --- tree model ------------------------------------------------------------------------


@dataclass
class _Tree:
    start: np.ndarray
    end: np.ndarray
    length: np.ndarray
    radius: np.ndarray
    parent: np.ndarray
    children: list[list[int]]
    order: list[int]  # topological
    axis_id: np.ndarray
    axis_order: np.ndarray
    axes: dict[int, list[int]]  # axis id -> rows from base to tip
    subtree: np.ndarray  # supported length, cylinder included
    tips: np.ndarray  # tips supported
    path: np.ndarray  # path length from the base to the cylinder's end


def _model(work: pd.DataFrame) -> _Tree:
    parent = work["parent"].to_numpy()
    n = len(parent)
    children: list[list[int]] = [[] for _ in range(n)]
    for i, p in enumerate(parent):
        if p >= 0:
            children[p].append(i)
    order = _topological(parent)
    length = work["length"].to_numpy(dtype=float)
    subtree = length.copy()
    tips = np.array([0 if c else 1 for c in children], dtype=float)
    for i in reversed(order):
        if parent[i] >= 0:
            subtree[parent[i]] += subtree[i]
            tips[parent[i]] += tips[i]
    path = length.copy()
    for i in order:
        if parent[i] >= 0:
            path[i] += path[parent[i]]
    axes: dict[int, list[int]] = {}
    for i in work.sort_values(["axis_id", "axis_pos"]).index:
        axes.setdefault(int(work.at[i, "axis_id"]), []).append(int(i))
    return _Tree(
        start=work[["start_x", "start_y", "start_z"]].to_numpy(dtype=float),
        end=work[["end_x", "end_y", "end_z"]].to_numpy(dtype=float),
        length=length,
        radius=work["radius"].to_numpy(dtype=float),
        parent=parent,
        children=children,
        order=order,
        axis_id=work["axis_id"].to_numpy(),
        axis_order=work["axis_order"].to_numpy(),
        axes=axes,
        subtree=subtree,
        tips=tips,
        path=path,
    )


def _polyline(tree: _Tree, rows: list[int]) -> np.ndarray:
    return np.vstack([tree.start[rows[0]], tree.end[rows]])


def _arc(points: np.ndarray) -> np.ndarray:
    return np.concatenate(
        [[0.0], np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
    )


def _at(points: np.ndarray, arc: np.ndarray, target: float) -> np.ndarray:
    return np.array([np.interp(target, arc, points[:, i]) for i in range(3)])


def _from_vertical(v: np.ndarray) -> float:
    n = float(np.linalg.norm(v))
    return (
        math.degrees(math.acos(max(-1.0, min(1.0, v[2] / n))))
        if n > 1e-12
        else float("nan")
    )


def _between(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na < 1e-12 or nb < 1e-12:
        return float("nan")
    return math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(a, b)) / (na * nb)))))


def _median(values) -> float:
    values = [v for v in values if v is not None and np.isfinite(v)]
    return float(np.median(values)) if values else float("nan")


def _q(values, q: float) -> float:
    values = [v for v in values if v is not None and np.isfinite(v)]
    return float(np.quantile(values, q)) if values else float("nan")


def _third(x: float, names=("base", "mid", "tip")) -> str:
    return names[min(2, max(0, int(x * 3)))]


@dataclass
class _Lateral:
    axis: int
    parent_axis: int
    order: int
    attach_row: int
    attach_arc: float  # metres along the parent axis
    parent_len: float
    length: float
    points: np.ndarray


def _laterals(tree: _Tree) -> list[_Lateral]:
    lengths = {a: float(tree.length[rows].sum()) for a, rows in tree.axes.items()}
    arc_before: dict[
        int, float
    ] = {}  # row -> arc length along its axis at the row's start
    for rows in tree.axes.values():
        acc = 0.0
        for r in rows:
            arc_before[r] = acc
            acc += tree.length[r]
    out = []
    for a, rows in tree.axes.items():
        base = rows[0]
        attach = int(tree.parent[base])
        if attach < 0:
            continue
        seg = tree.end[attach] - tree.start[attach]
        t = float(
            np.clip(
                np.dot(tree.start[base] - tree.start[attach], seg)
                / max(np.dot(seg, seg), 1e-12),
                0,
                1,
            )
        )
        parent_axis = int(tree.axis_id[attach])
        out.append(
            _Lateral(
                axis=a,
                parent_axis=parent_axis,
                order=int(tree.axis_order[base]),
                attach_row=attach,
                attach_arc=arc_before[attach] + t * tree.length[attach],
                parent_len=lengths[parent_axis],
                length=lengths[a],
                points=_polyline(tree, rows),
            )
        )
    return out


# --- the three groups ----------------------------------------------------------------------


def _geometry(tree: _Tree, laterals: list[_Lateral]) -> dict:
    out: dict = {}
    height = float(tree.end[:, 2].max())
    out["L1.height_m"] = height
    trunk = _polyline(tree, tree.axes[0])
    # trunk form: lean of the base-to-top chord, and how far the stem bows away from it
    chord = trunk[-1] - trunk[0]
    out["L1.trunk_lean_deg"] = _from_vertical(chord)
    arc = float(np.linalg.norm(np.diff(trunk, axis=0), axis=1).sum())
    out["L1.trunk_sinuosity"] = arc / max(float(np.linalg.norm(chord)), 1e-9)
    rel = trunk - trunk[0]
    unit = chord / max(float(np.linalg.norm(chord)), 1e-9)
    off = np.linalg.norm(rel - np.outer(rel @ unit, unit), axis=1)
    out["L1.trunk_bow_rel"] = float(off.max()) / height if height > 0 else float("nan")
    firsts = [b for b in laterals if b.order == 1 and b.length >= MIN_BRANCH_M]
    attach_z = [float(b.points[0, 2]) for b in firsts]
    out["L1.crown_base_m"] = min(attach_z) if attach_z else float("nan")
    base_p10 = _q(attach_z, 0.1)
    out["L1.crown_base_p10_m"] = base_p10
    crown_len = height - base_p10 if np.isfinite(base_p10) else float("nan")
    out["L1.crown_ratio"] = crown_len / height if height > 0 else float("nan")

    # crown width by depth: horizontal distance of every cylinder end from the trunk line
    up = trunk[np.argsort(trunk[:, 2], kind="stable")]  # np.interp needs increasing z
    zs = tree.end[:, 2]
    tx = np.interp(zs, up[:, 2], up[:, 0])
    ty = np.interp(zs, up[:, 2], up[:, 1])
    radial = np.hypot(tree.end[:, 0] - tx, tree.end[:, 1] - ty)
    widths = []
    if np.isfinite(crown_len) and crown_len > 0:
        for k in range(10):
            hi = height - k * crown_len / 10
            lo = height - (k + 1) * crown_len / 10
            sel = radial[(zs <= hi) & (zs > lo)]
            widths.append(2 * float(np.quantile(sel, 0.95)) if len(sel) else 0.0)
    out["L1.crown_width_over_height"] = (
        max(widths) / height if widths and height > 0 else float("nan")
    )
    out["L1.widest_at_depth"] = (
        (int(np.argmax(widths)) + 0.5) / 10
        if widths and max(widths) > 0
        else float("nan")
    )
    for k in range(10):  # the crown's outline: width / height per tenth of crown depth
        out[f"L1.crown_width_rel_d{k + 1:02d}"] = (
            widths[k] / height if widths and height > 0 else float("nan")
        )

    # nodes on the trunk
    on_trunk = sorted(b.attach_arc for b in firsts if b.parent_axis == 0)
    nodes: list[list[float]] = []
    for s in on_trunk:
        if nodes and s - nodes[-1][-1] <= NODE_TOL_M:
            nodes[-1].append(s)
        else:
            nodes.append([s])
    spacing = [b[0] - a[0] for a, b in zip(nodes, nodes[1:], strict=False)]
    out["L3.nodes_per_m"] = (
        len(nodes) / crown_len
        if np.isfinite(crown_len) and crown_len > 0
        else float("nan")
    )
    out["L3.branches_per_node_p50"] = _median([len(n) for n in nodes])
    out["L3.tier_spacing_p50_m"] = _median(spacing)
    out["L3.tier_spacing_cv"] = (
        float(np.std(spacing) / np.mean(spacing))
        if len(spacing) > 1 and np.mean(spacing) > 0
        else float("nan")
    )

    # first-order branch profiles by crown third
    per_third: dict[str, dict[str, list[float]]] = {}
    tips, upturned = [], []
    for b in firsts:
        depth = (
            (height - b.points[0, 2]) / crown_len
            if np.isfinite(crown_len) and crown_len > 0
            else 0.5
        )
        third = ("top", "middle", "bottom")[min(2, max(0, int(depth * 3)))]
        arc = _arc(b.points)
        chord = _at(b.points, arc, arc[-1] / 2) - b.points[0]
        head = _at(b.points, arc, min(HEAD_M, arc[-1])) - b.points[0]
        tail = b.points[-1] - _at(b.points, arc, max(0.0, arc[-1] - HEAD_M))
        rows = tree.axes[b.axis]
        d = per_third.setdefault(third, {})
        d.setdefault("chord_angle_deg", []).append(_from_vertical(chord))
        d.setdefault("initial_angle_deg", []).append(_from_vertical(head))
        d.setdefault("length_m", []).append(b.length)
        d.setdefault("length_rel", []).append(b.length / height)
        d.setdefault("radius_ratio", []).append(
            tree.radius[rows[0]] / tree.radius[b.attach_row]
        )
        d.setdefault("straightness", []).append(
            float(np.linalg.norm(b.points[-1] - b.points[0])) / max(arc[-1], 1e-12)
        )
        d.setdefault("ranked", []).append(
            (b.length / height, _from_vertical(chord), _from_vertical(head))
        )
        tip = _from_vertical(tail)
        tips.append(tip)
        upturned.append(1.0 if tip < 90 else 0.0)
    for third in ("top", "middle", "bottom"):
        # the TOP_N longest branches only: a scan that misses small branches still sees
        # these, so the comparison does not depend on how many branches each source finds
        top = sorted(per_third.get(third, {}).get("ranked", []), reverse=True)[:TOP_N]
        out[f"L4.top{TOP_N}_length_rel_{third}"] = _median([t[0] for t in top])
        out[f"L4.top{TOP_N}_chord_angle_deg_{third}"] = _median([t[1] for t in top])
        out[f"L4.top{TOP_N}_initial_angle_deg_{third}"] = _median([t[2] for t in top])
    for third in ("top", "middle", "bottom"):
        for name in (
            "chord_angle_deg",
            "initial_angle_deg",
            "length_m",
            "length_rel",
            "radius_ratio",
            "straightness",
        ):
            out[f"L4.{name}_{third}"] = _median(per_third.get(third, {}).get(name, []))
    out["L4.tip_angle_deg_p50"] = _median(tips)
    out["L4.upturned_share"] = float(np.mean(upturned)) if upturned else float("nan")
    return out


def _growth_rules(tree: _Tree, laterals: list[_Lateral]) -> dict:
    out: dict = {}
    for k in (0, 1):
        kids = [b for b in laterals if b.order == k + 1 and b.length >= MIN_LATERAL_M]
        parent_axes = [
            a for a, rows in tree.axes.items() if int(tree.axis_order[rows[0]]) == k
        ]
        parent_length = sum(float(tree.length[tree.axes[a]].sum()) for a in parent_axes)
        prefix = f"G.k{k}."
        out[prefix + "lateral_density_per_m"] = (
            len(kids) / parent_length if parent_length > 0 else float("nan")
        )
        rel = [b.attach_arc / b.parent_len for b in kids if b.parent_len > 0]
        out[prefix + "attach_relpos_p50"] = _median(rel)
        by: dict[str, dict[str, list[float]]] = {}
        forks = []
        for b in kids:
            third = _third(b.attach_arc / b.parent_len if b.parent_len > 0 else 0.5)
            arc = _arc(b.points)
            head = _at(b.points, arc, min(HEAD_M, arc[-1])) - b.points[0]
            axis_vec = tree.end[b.attach_row] - tree.start[b.attach_row]
            remaining = b.parent_len - b.attach_arc
            d = by.setdefault(third, {})
            d.setdefault("insertion", []).append(_between(head, axis_vec))
            if remaining > 0.05:
                d.setdefault("ratio", []).append(b.length / remaining)
            cont = [
                c
                for c in tree.children[b.attach_row]
                if tree.axis_id[c] == b.parent_axis
            ]
            base = tree.axes[b.axis][0]
            if cont:
                forks.append(
                    1.0
                    if tree.subtree[base] >= FORK_SHARE * tree.subtree[cont[0]]
                    else 0.0
                )
        for third in ("base", "mid", "tip"):
            out[f"{prefix}insertion_deg_{third}"] = _median(
                by.get(third, {}).get("insertion", [])
            )
            out[f"{prefix}length_ratio_{third}"] = _median(
                by.get(third, {}).get("ratio", [])
            )
        out[prefix + "fork_share"] = float(np.mean(forks)) if forks else float("nan")

    exponents, areas, asym = [], [], []
    for i, kids in enumerate(tree.children):
        if len(kids) < 2:
            continue
        rp = tree.radius[i]
        rc = tree.radius[kids]
        if rp > 0:
            areas.append(float((rc**2).sum() / rp**2))
            exponents.append(_pipe_exponent(rc / rp))
        sizes = sorted(tree.subtree[kids], reverse=True)[:2]
        asym.append(sizes[1] / sizes[0] if sizes[0] > 0 else float("nan"))
    out["G.pipe_exponent_p50"] = _median(exponents)
    out["G.area_ratio_p50"] = _median(areas)
    out["G.fork_asymmetry_p50"] = _median(asym)
    return out


def _pipe_exponent(ratios: np.ndarray, lo: float = 0.5, hi: float = 6.0) -> float:
    """``a`` with sum(ratios**a) == 1 by bisection; NaN when no root lies in [lo, hi]."""
    if (ratios <= 0).any() or (ratios >= 1).any():
        return float("nan")

    def f(a: float) -> float:
        return float((ratios**a).sum() - 1.0)

    if f(lo) < 0 or f(hi) > 0:
        return float("nan")
    for _ in range(60):
        mid = 0.5 * (lo + hi)
        if f(mid) > 0:
            lo = mid
        else:
            hi = mid
    return 0.5 * (lo + hi)


def _event(tree: _Tree, b: _Lateral) -> int:
    """Rank of a lateral's event: 3 fork, 2 long, 1 short (``SYMBOLS``)."""
    cont = [c for c in tree.children[b.attach_row] if tree.axis_id[c] == b.parent_axis]
    if (
        cont
        and tree.subtree[tree.axes[b.axis][0]] >= FORK_SHARE * tree.subtree[cont[0]]
    ):
        return 3
    remaining = b.parent_len - b.attach_arc
    return 2 if remaining <= 0.05 or b.length / remaining >= SHORT_RATIO else 1


def _sequences(tree: _Tree, laterals: list[_Lateral]) -> dict:
    """Each axis is cut into ten equal parts of its length; a part takes the strongest event
    among the laterals leaving it (none < short < long < fork). The deciles' shares and a
    first-order Markov chain along them describe the branching zones independent of size:
    a bare base, a zone of long laterals, a short-shoot top, forking."""
    out: dict = {}
    for k in (0, 1):
        prefix = f"S.k{k}."
        seqs, bare_base, bare_tip = [], [], []
        for a, rows in tree.axes.items():
            if (
                int(tree.axis_order[rows[0]]) != k
                or tree.length[rows].sum() < MIN_PARENT_M
            ):
                continue
            kids = [
                b for b in laterals if b.parent_axis == a and b.length >= MIN_LATERAL_M
            ]
            seq = [0] * 10
            rel = []
            for b in kids:
                r = min(max(b.attach_arc / b.parent_len, 0.0), 0.999)
                rel.append(r)
                seq[int(r * 10)] = max(seq[int(r * 10)], _event(tree, b))
            seqs.append(seq)
            if rel:
                bare_base.append(min(rel))
                bare_tip.append(1.0 - max(rel))
        out[prefix + "bare_base_rel"] = _median(bare_base)
        out[prefix + "bare_tip_rel"] = _median(bare_tip)
        counts = np.zeros(4)
        moves = np.zeros((4, 4))
        for seq in seqs:
            for s in seq:
                counts[s] += 1
            for x, y in zip(seq, seq[1:], strict=False):
                moves[x, y] += 1
        for i, name in enumerate(SYMBOLS):
            out[f"{prefix}share_{name}"] = (
                counts[i] / counts.sum() if counts.sum() else float("nan")
            )
            row = moves[i].sum()
            out[f"{prefix}persist_{name}"] = moves[i, i] / row if row else float("nan")
    return out


def _topology(tree: _Tree) -> dict:
    out: dict = {}
    n = len(tree.parent)
    strahler = np.ones(n, dtype=int)
    for i in reversed(tree.order):
        kids = tree.children[i]
        if kids:
            orders = sorted((strahler[c] for c in kids), reverse=True)
            strahler[i] = (
                orders[0] + 1
                if len(orders) > 1 and orders[1] == orders[0]
                else orders[0]
            )
    out["T.strahler_max"] = float(strahler.max())
    # a stream is a maximal chain of cylinders of one order; it starts where the parent differs
    starts = [
        i
        for i in range(n)
        if tree.parent[i] < 0 or strahler[tree.parent[i]] != strahler[i]
    ]
    stream_len: dict[int, list[float]] = {}
    for s in starts:
        total, node = 0.0, s
        while True:
            total += tree.length[node]
            same = [c for c in tree.children[node] if strahler[c] == strahler[s]]
            if not same:
                break
            node = max(same, key=lambda c: tree.subtree[c])
        stream_len.setdefault(int(strahler[s]), []).append(total)
    ks = sorted(stream_len)
    rb = [
        len(stream_len[a]) / len(stream_len[b])
        for a, b in zip(ks, ks[1:], strict=False)
    ]
    rl = [
        np.mean(stream_len[b]) / np.mean(stream_len[a])
        for a, b in zip(ks, ks[1:], strict=False)
    ]
    out["T.bifurcation_ratio"] = (
        float(np.exp(np.mean(np.log(rb)))) if rb else float("nan")
    )
    out["T.length_ratio"] = float(np.exp(np.mean(np.log(rl)))) if rl else float("nan")
    tips = [i for i in range(n) if not tree.children[i]]
    paths = tree.path[tips]
    out["T.path_fraction"] = (
        float(paths.mean() / paths.max())
        if len(paths) and paths.max() > 0
        else float("nan")
    )
    asym = []
    for kids in tree.children:
        if len(kids) >= 2:
            r, s = sorted(tree.tips[kids], reverse=True)[:2]
            asym.append(abs(r - s) / (r + s - 2) if r + s > 2 else 0.0)
    out["T.partition_asymmetry"] = float(np.mean(asym)) if asym else float("nan")
    lengths = {a: float(tree.length[rows].sum()) for a, rows in tree.axes.items()}
    base_r = {a: float(tree.radius[rows[0]]) for a, rows in tree.axes.items()}
    by_order: dict[int, list[int]] = {}
    for a, rows in tree.axes.items():
        by_order.setdefault(int(tree.axis_order[rows[0]]), []).append(a)

    def med(order: int, values: dict) -> float:
        return _median([values[a] for a in by_order.get(order, [])])

    out["T.axis_length_ratio_1_0"] = (
        med(1, lengths) / med(0, lengths) if med(0, lengths) > 0 else float("nan")
    )
    out["T.axis_length_ratio_2_1"] = (
        med(2, lengths) / med(1, lengths) if med(1, lengths) > 0 else float("nan")
    )
    out["T.axis_radius_ratio_2_1"] = (
        med(2, base_r) / med(1, base_r) if med(1, base_r) > 0 else float("nan")
    )
    out["T.n_axes_order_1"] = float(len(by_order.get(1, [])))
    out["T.n_axes_order_2"] = float(len(by_order.get(2, [])))
    return out


def _trunk_dbh(tree: _Tree) -> float:
    """Mean trunk diameter at 1.3 +- 0.2 m, length-weighted (standardize.measure)."""
    rows = tree.axes[0]
    z0 = np.minimum(tree.start[rows, 2], tree.end[rows, 2])
    z1 = np.maximum(tree.start[rows, 2], tree.end[rows, 2])
    lo, hi = BREAST_HEIGHT_M - DBH_WINDOW_M, BREAST_HEIGHT_M + DBH_WINDOW_M
    overlap = (np.minimum(z1, hi) - np.maximum(z0, lo)).clip(min=0)
    if overlap.sum() <= 0:
        return float("nan")
    return 2 * float(np.average(tree.radius[rows], weights=overlap))


def _branch_wave(points: np.ndarray, length: float) -> tuple[float, float, float]:
    """(sag, rise, tip turn) of one branch against its base-to-tip chord, own frame:
    the vertical offset of every point from the chord at the same projection onto it."""
    p = points - points[0]
    chord = p[-1]
    c2 = float(chord @ chord)
    if c2 < 1e-12 or length <= 0:
        return float("nan"), float("nan"), float("nan")
    t = np.clip(p @ chord / c2, 0.0, 1.0)
    dz = p[:, 2] - t * chord[2]
    arc = _arc(points)
    head = _at(points, arc, min(HEAD_M, arc[-1])) - points[0]
    tail = points[-1] - _at(points, arc, max(0.0, arc[-1] - HEAD_M))
    return (
        max(0.0, -float(dz.min())) / length,
        max(0.0, float(dz.max())) / length,
        _between(head, tail),
    )


def _form(
    tree: _Tree, laterals: list[_Lateral], geometry: dict, dbh_m: float | None
) -> dict:
    out: dict = {}
    height = geometry["L1.height_m"]
    dbh = (
        dbh_m
        if dbh_m is not None and np.isfinite(dbh_m) and dbh_m > 0
        else _trunk_dbh(tree)
    )
    width = geometry["L1.crown_width_over_height"] * height
    out["F.crown_m_per_dbh_cm"] = (
        width / (100 * dbh) if np.isfinite(dbh) and dbh > 0 else float("nan")
    )

    firsts = [b for b in laterals if b.order == 1 and b.length >= MIN_BRANCH_M]
    nan_keys = (
        "F.lower_hang_len_frac",
        "F.lower_tips_hanging",
        "F.wave_sag_rel_p50",
        "F.wave_rise_rel_p50",
        "F.wave_tip_turn_deg_p50",
        "F.length_cv_p50",
        "F.whorl_gap_cv_p50",
        "F.crown_offset_rel",
        "F.branches_per_node_cv",
        "F.whorl_gap_max_deg_p50",
        "F.crown_holes_share",
    )

    # leader: trunk arc above the topmost first-order attachment, any length after prune
    trunk_len = float(tree.length[tree.axes[0]].sum())
    on_trunk_all = [
        b.attach_arc for b in laterals if b.order == 1 and b.parent_axis == 0
    ]
    leader = trunk_len - max(on_trunk_all) if on_trunk_all else float("nan")
    out["F.leader_m"] = leader
    out["F.leader_rel"] = leader / height if height > 0 else float("nan")

    if not firsts:
        out.update(dict.fromkeys(nan_keys, float("nan")))
    else:
        # lower crown: dangling length and hanging tips
        top = max(float(b.points[:, 2].max()) for b in firsts)
        base = min(float(b.points[0, 2]) for b in firsts)
        cut = base + LOWER_CROWN * (top - base)
        hang, hanging_tips = [], []
        for b in firsts:
            if b.points[0, 2] > cut:
                continue
            seg = np.diff(b.points, axis=0)
            seg_len = np.linalg.norm(seg, axis=1)
            angle = np.degrees(
                np.arccos(np.clip(seg[:, 2] / np.maximum(seg_len, 1e-12), -1, 1))
            )
            hang.append(
                float(seg_len[angle > HANG_DEG].sum() / max(seg_len.sum(), 1e-12))
            )
            arc = _arc(b.points)
            tail = b.points[-1] - _at(b.points, arc, max(0.0, arc[-1] - HEAD_M))
            hanging_tips.append(1.0 if _from_vertical(tail) > HANG_DEG else 0.0)
        out["F.lower_hang_len_frac"] = float(np.mean(hang)) if hang else float("nan")
        out["F.lower_tips_hanging"] = (
            float(np.mean(hanging_tips)) if hanging_tips else float("nan")
        )

        # wave: belly under the chord, arching above it, tip curl
        waves = [
            _branch_wave(b.points, b.length) for b in firsts if b.length >= WAVE_MIN_M
        ]
        out["F.wave_sag_rel_p50"] = _median([w[0] for w in waves])
        out["F.wave_rise_rel_p50"] = _median([w[1] for w in waves])
        out["F.wave_tip_turn_deg_p50"] = _median([w[2] for w in waves])

        # irregularity: branch lengths within each tenth of the crown height
        span = max(top - base, 1e-9)
        tenths: dict[int, list[float]] = {}
        for b in firsts:
            k = min(9, int((b.points[0, 2] - base) / span * 10))
            tenths.setdefault(k, []).append(b.length)
        cvs = [
            float(np.std(v) / np.mean(v))
            for v in tenths.values()
            if len(v) >= 3 and np.mean(v) > 0
        ]
        out["F.length_cv_p50"] = _median(cvs)

        # irregularity: azimuth gaps inside whorls on the trunk (nodes as in L3)
        on_trunk = sorted(
            (b for b in firsts if b.parent_axis == 0), key=lambda b: b.attach_arc
        )
        nodes: list[list[_Lateral]] = []
        for b in on_trunk:
            if nodes and b.attach_arc - nodes[-1][-1].attach_arc <= NODE_TOL_M:
                nodes[-1].append(b)
            else:
                nodes.append([b])
        gap_cvs, gap_max = [], []
        for node in nodes:
            if len(node) < 2:
                continue
            az = []
            for b in node:
                arc = _arc(b.points)
                head = _at(b.points, arc, min(HEAD_M, arc[-1])) - b.points[0]
                az.append(math.atan2(head[1], head[0]))
            az = np.sort(np.mod(az, 2 * math.pi))
            gaps = np.diff(np.append(az, az[0] + 2 * math.pi))
            gap_max.append(math.degrees(float(gaps.max())))
            if len(node) >= 3:
                gap_cvs.append(float(np.std(gaps) / np.mean(gaps)))
        out["F.whorl_gap_cv_p50"] = _median(gap_cvs)
        out["F.whorl_gap_max_deg_p50"] = _median(gap_max)
        counts = [len(n) for n in nodes]
        out["F.branches_per_node_cv"] = (
            float(np.std(counts) / np.mean(counts)) if counts else float("nan")
        )

        # asymmetry: mean tip position against the trunk line at the tips' heights
        trunk = _polyline(tree, tree.axes[0])
        up = trunk[np.argsort(trunk[:, 2], kind="stable")]
        tips = np.array([b.points[-1] for b in firsts])
        rel = np.column_stack(
            [
                tips[:, 0] - np.interp(tips[:, 2], up[:, 2], up[:, 0]),
                tips[:, 1] - np.interp(tips[:, 2], up[:, 2], up[:, 1]),
            ]
        )
        reach = float(np.mean(np.hypot(rel[:, 0], rel[:, 1])))
        out["F.crown_offset_rel"] = (
            float(np.hypot(*rel.mean(axis=0))) / reach if reach > 0 else float("nan")
        )

        # holes: which (height band x azimuth sector) cells of the crown branches reach
        occupied = np.zeros((CROWN_BANDS, CROWN_SECTORS), dtype=bool)
        for b in firsts:
            arc = _arc(b.points)
            steps = np.arange(0.0, arc[-1] + 1e-9, HOLE_STEP_M)
            pts = np.array([_at(b.points, arc, s) for s in steps])
            dx = pts[:, 0] - np.interp(pts[:, 2], up[:, 2], up[:, 0])
            dy = pts[:, 1] - np.interp(pts[:, 2], up[:, 2], up[:, 1])
            far = np.hypot(dx, dy) >= HOLE_MIN_REACH_M
            band = np.clip(
                ((pts[:, 2] - base) / span * CROWN_BANDS).astype(int),
                0,
                CROWN_BANDS - 1,
            )
            sector = (
                np.mod(np.arctan2(dy, dx), 2 * math.pi) / (2 * math.pi) * CROWN_SECTORS
            ).astype(int)
            occupied[band[far], np.clip(sector[far], 0, CROWN_SECTORS - 1)] = True
        out["F.crown_holes_share"] = 1.0 - float(occupied.mean())

    top_angle = geometry.get(f"L4.top{TOP_N}_chord_angle_deg_top", float("nan"))
    bottom_angle = geometry.get(f"L4.top{TOP_N}_chord_angle_deg_bottom", float("nan"))
    out["F.angle_gradient_deg"] = bottom_angle - top_angle
    return out


def describe(
    cyl: pd.DataFrame,
    min_radius_m: float = 0.0,
    max_order: int | None = None,
    min_length_m: float = 0.0,
    dbh_m: float | None = None,
) -> dict:
    """All descriptors of one tree (exchange table in, ``DEFINITIONS`` keys out), after
    ``prune`` cut it to the common resolution.

    ``dbh_m`` is the DBH the crown is set against (``F.crown_m_per_dbh_cm``);
    without it the trunk is measured at 1.3 m. Pass the exported (yield-table) DBH
    for Grove trees: their raw skeleton radius runs about 1.2x it, which reads the
    crown about 1.2x too narrow."""
    work = prune(cyl, min_radius_m, max_order, min_length_m)
    tree = _model(work)
    laterals = _laterals(tree)
    geometry = _geometry(tree, laterals)
    out = {
        **geometry,
        **_growth_rules(tree, laterals),
        **_topology(tree),
        **_sequences(tree, laterals),
        **_form(tree, laterals, geometry, dbh_m),
    }
    out["n_cyl_pruned"] = float(len(work))
    return out
