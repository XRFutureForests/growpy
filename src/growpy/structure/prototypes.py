"""Prototype ("average") branching structure of real trees per species x height x crown width.

Trees cannot be averaged cylinder by cylinder (there is no correspondence), so a group of
real trees is summarised three ways:

``occupancy``  every cylinder projected onto the side plane as (horizontal distance from the
               trunk, height), both over tree height, length-weighted; one map per tree,
               each summing to 1, averaged over the group (rotation-free, no matching)
``curves``     every first-order branch on the trunk unrolled into its own vertical plane:
               horizontal and vertical offset from its attachment, both over its own length,
               resampled to ``N_POINTS`` along its arc. Median and p25/p75 per crown decile
               (decile 1 = crown base, 10 = top), plus median length / height and branches
               per metre of crown
``medoid``     the real tree nearest the group median in a small descriptor vector

``template_tree`` builds a synthetic tree from the curves (straight trunk, median curve at
median length and count per decile), and ``score_curves`` measures a generated tree's
branches against them.

Radii for drawing are synthetic (``pipe_radii``): QSM branch radii are inflated by a
different amount per source, while the stem DBH is measured well. Everything is computed
after the same common-resolution prune as the descriptors (``PRUNE``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np
import pandas as pd

from growpy.io.usd.overview import _snap_to_interval
from growpy.structure.descriptors import (
    FORK_SHARE,
    MIN_BRANCH_M,
    _arc,
    _at,
    _laterals,
    _model,
    _polyline,
    _topological,
    prune,
)

PRUNE = {"max_order": 2, "min_length_m": 0.3}  # same as the descriptor run
N_POINTS = 21  # samples along each unrolled branch
THIRDS = 3  # second-order branches are summarised per third of their parent limb
DECILES = 10
LEADING_PER_DECILE = (
    1  # curves from each tree's farthest-reaching branch per decile (``leading``)
)
TRUNK_TOP_MIN = 0.9  # medoid: the trunk axis must reach 90 % of the height
OCC_X = 0.8  # occupancy map: horizontal distance from the trunk up to 0.8 x height
OCC_NX, OCC_NZ = 64, 100
HEIGHT_STEP_M = 5  # columns snap like dataset_overview.md: round(h / 5) * 5
MIN_GROUP = 5
MIN_HEIGHT_M = 2.5  # below this a tree snaps to h00
MAX_HEIGHT_M = 55.0  # QC: BioDiv beech has heights up to 127.5 m
MAX_CROWN_WIDTH_REL = 1.5  # QC: Kew spruce has crown width / height up to 6.3
BREAST_M = 1.3
MEDOID_KEYS = [
    "L1.crown_width_over_height",
    "L1.crown_ratio",
    *[f"L4.top5_length_rel_{t}" for t in ("bottom", "middle", "top")],
    *[f"L4.top5_chord_angle_deg_{t}" for t in ("bottom", "middle", "top")],
    "G.k0.lateral_density_per_m",
]
WIDTH_LABELS = {"w0": "all widths", "w1": "narrow", "w2": "middle", "w3": "wide"}


def height_label(height_m: float) -> str:
    """Catalog column of a height: ``h20m`` covers 17.5-22.5 m, as in dataset_overview.md."""
    return f"h{int(_snap_to_interval(height_m, HEIGHT_STEP_M)):02d}m"


def species_title(species_key: str) -> str:
    """``norway_spruce`` -> ``Norway_Spruce``, the catalog's file-name spelling."""
    return "_".join(w.capitalize() for w in species_key.split("_"))


# --- grouping ---------------------------------------------------------------------------


def _is_false(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["false", "0", "0.0"])


def select_groups(table: pd.DataFrame, min_n: int = MIN_GROUP) -> pd.DataFrame:
    """Group membership of the real trees of a descriptor table.

    One row per (tree, group). Groups are species x height class (``w0``, all widths) and,
    where the cell holds at least ``3 * min_n`` trees, also its crown-width tertiles
    ``w1``..``w3`` (``L1.crown_width_over_height`` cut WITHIN the cell). Tiers A/B are used
    when a cell has at least ``min_n`` of them, otherwise tier C is admitted (as in
    ``compare.py``). Cells with fewer than ``min_n`` trees are left out.
    """
    real = table[(table["source_kind"] == "scan") & table["species_key"].notna()].copy()
    cwh = real["L1.crown_width_over_height"]
    qc = (
        real["height_m"].between(MIN_HEIGHT_M, MAX_HEIGHT_M)
        & np.isfinite(cwh)
        & (cwh > 0)
        & (cwh <= MAX_CROWN_WIDTH_REL)
    )
    if "valid_qsm" in real:
        qc &= ~_is_false(real["valid_qsm"])
    real = real[qc]
    real["height_class"] = real["height_m"].map(height_label)
    rows = []
    for (species, hclass), cell in real.groupby(["species_key", "height_class"]):
        good = cell[cell["tier"].isin(["A", "B"])]
        used, tiers = (good, "A/B") if len(good) >= min_n else (cell, "A/B/C")
        if len(used) < min_n:
            continue
        base = {"species_key": species, "height_class": hclass, "tiers": tiers}
        rows += [{**base, "tree_uid": u, "width_class": "w0"} for u in used["tree_uid"]]
        if len(used) >= 3 * min_n:
            ranks = used["L1.crown_width_over_height"].rank(method="first")
            third = pd.qcut(ranks, 3, labels=["w1", "w2", "w3"])
            rows += [
                {**base, "tree_uid": u, "width_class": str(w)}
                for u, w in zip(used["tree_uid"], third, strict=True)
            ]
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out["n"] = out.groupby(["species_key", "height_class", "width_class"])[
        "tree_uid"
    ].transform("size")
    return out


def rank_medoids(members: pd.DataFrame, keys: list[str] = MEDOID_KEYS) -> pd.Series:
    """Distance of each tree to its group median: robust z per key (median / IQR within
    the group), root mean square over the keys a tree has. Index = ``members.index``."""
    x = members[[k for k in keys if k in members]].astype(float)
    med = x.median()
    iqr = x.quantile(0.75) - x.quantile(0.25)
    iqr = iqr.where(iqr > 1e-9, x.std()).replace(0, np.nan).fillna(1.0)
    z = (x - med) / iqr
    return np.sqrt((z**2).mean(axis=1, skipna=True))


def clean_stems(profiles: dict[str, dict]) -> set[str]:
    """Trees whose stem is reconstructed in one piece, for choosing a medoid: the trunk
    axis reaches ``TRUNK_TOP_MIN`` of the height, and its gaps and sinuosity are no worse
    than the median of ``profiles``. Conifer crowns hide the upper stem, and TreeQSM
    then fits it as offset pieces: a broken stem is an artefact, not a typical tree."""
    if not profiles:
        return set()
    gap = np.median([p["trunk_gap_rel"] for p in profiles.values()])
    sinuosity = np.median([p["trunk_sinuosity"] for p in profiles.values()])
    return {
        u
        for u, p in profiles.items()
        if p["trunk_top_rel"] >= TRUNK_TOP_MIN
        and p["trunk_gap_rel"] <= gap
        and p["trunk_sinuosity"] <= sinuosity
    }


# --- radii ------------------------------------------------------------------------------


def pipe_radii(
    start: np.ndarray,
    end: np.ndarray,
    parent: np.ndarray,
    trunk_rows: list[int],
    dbh_m: float,
    breast_m: float = BREAST_M,
) -> np.ndarray:
    """Pipe-model radii (cross-section area preserved at every fork), anchored at DBH.

    A cylinder's area is proportional to the branch length distal to its midpoint, scaled
    so the stem at ``breast_m`` carries the DBH area. At a fork the parent's area is split
    among the children in proportion to the length they carry, and every axis tapers
    smoothly between forks.
    """
    length = np.linalg.norm(end - start, axis=1)
    distal = length.copy()
    for i in reversed(_topological(parent)):
        if parent[i] >= 0:
            distal[parent[i]] += distal[i]
    ref = next((r for r in trunk_rows if end[r, 2] >= breast_m), trunk_rows[-1])
    dz = end[ref, 2] - start[ref, 2]
    below = float(np.clip((breast_m - start[ref, 2]) / dz, 0, 1)) if dz > 1e-9 else 0.0
    at_breast = distal[ref] - below * length[ref]
    mid = np.clip(distal - 0.5 * length, 0, None)
    return 0.5 * dbh_m * np.sqrt(mid / max(at_breast, 1e-9))


# --- one tree ---------------------------------------------------------------------------


@dataclass
class Geometry:
    """A drawable tree: row-based cylinders after a prune, trunk rows base to top."""

    start: np.ndarray
    end: np.ndarray
    parent: np.ndarray
    radius: np.ndarray  # as delivered by the source
    trunk_rows: list[int]

    @property
    def height(self) -> float:
        return float(self.end[:, 2].max())


def geometry(cyl: pd.DataFrame, **prune_kw) -> Geometry:
    """Prune an exchange table (``PRUNE`` by default) and keep what drawing needs."""
    work = prune(cyl, **(PRUNE if not prune_kw else prune_kw))
    tree = _model(work)
    return Geometry(tree.start, tree.end, tree.parent, tree.radius, tree.axes[0])


def _trunk_xy(trunk: np.ndarray, z: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    up = trunk[np.argsort(trunk[:, 2], kind="stable")]
    return np.interp(z, up[:, 2], up[:, 0]), np.interp(z, up[:, 2], up[:, 1])


def _occupancy(start, end, trunk, height) -> np.ndarray:
    seg = end - start
    length = np.linalg.norm(seg, axis=1)
    n = np.maximum(1, np.ceil(length / (height / 200)).astype(int))
    idx = np.repeat(np.arange(len(length)), n)
    frac = (np.concatenate([np.arange(k) for k in n]) + 0.5) / n[idx]
    pts = start[idx] + seg[idx] * frac[:, None]
    tx, ty = _trunk_xy(trunk, pts[:, 2])
    dist = np.hypot(pts[:, 0] - tx, pts[:, 1] - ty) / height
    occ, _, _ = np.histogram2d(
        dist,
        pts[:, 2] / height,
        bins=[OCC_NX, OCC_NZ],
        range=[[0, OCC_X], [0, 1]],
        weights=(length / n)[idx],
    )
    total = occ.sum()
    return (occ / total if total > 0 else occ).astype(np.float32)


def _unroll(points: np.ndarray) -> np.ndarray:
    """(N_POINTS, 2): horizontal and vertical offset from the attachment over arc length."""
    arc = _arc(points)
    total = arc[-1]
    s = np.linspace(0, total, N_POINTS)
    p = np.column_stack([np.interp(s, arc, points[:, i]) for i in range(3)])
    h = np.hypot(p[:, 0] - p[0, 0], p[:, 1] - p[0, 1])
    v = p[:, 2] - p[0, 2]
    return np.column_stack([h, v]) / max(total, 1e-9)


def _trunk_gaps(tree) -> float:
    rows = tree.axes[0]
    return float(
        np.linalg.norm(tree.start[rows[1:]] - tree.end[rows[:-1]], axis=1).sum()
    )


def _trunk_sinuosity(tree) -> float:
    rows = tree.axes[0]
    chord = float(np.linalg.norm(tree.end[rows[-1]] - tree.start[rows[0]]))
    arc = float(tree.length[rows].sum()) + _trunk_gaps(tree)
    return arc / chord if chord > 1e-9 else float("nan")


def _divergence_deg(parent: np.ndarray, attach_arc: float, child: np.ndarray) -> float:
    """Horizontal angle between the parent limb's direction at the attachment and the
    child's initial direction (its first 30 %), in degrees (0 = along the parent)."""
    arc = _arc(parent)
    ahead = _at(parent, arc, min(arc[-1], attach_arc + 0.15))
    behind = _at(parent, arc, max(0.0, attach_arc - 0.15))
    t = (ahead - behind)[:2]
    carc = _arc(child)
    c = (_at(child, carc, 0.3 * carc[-1]) - child[0])[:2]
    nt, nc = float(np.linalg.norm(t)), float(np.linalg.norm(c))
    if nt < 1e-9 or nc < 1e-9:
        return float("nan")
    return math.degrees(math.acos(max(-1.0, min(1.0, float(t @ c) / (nt * nc)))))


def _second_order(laterals: list, firsts: list) -> dict:
    """Second-order branches on the first-order limbs (``firsts``): unrolled curve, third
    of the parent they leave from (0 base .. 2 tip), length over the parent's, horizontal
    divergence from the parent, and branches per metre of first-order length per third."""
    by_axis = {b.axis: b for b in firsts}
    curves, third, ratio, div = [], [], [], []
    for b in laterals:
        parent = by_axis.get(b.parent_axis)
        if b.order != 2 or parent is None or parent.length <= 0:
            continue
        curves.append(_unroll(b.points))
        third.append(min(THIRDS - 1, int(b.attach_arc / parent.length * THIRDS)))
        ratio.append(b.length / parent.length)
        div.append(_divergence_deg(parent.points, b.attach_arc, b.points))
    total = sum(b.length for b in firsts)
    third_a = np.array(third, dtype=int)
    per_m = (
        np.bincount(third_a, minlength=THIRDS) / (total / THIRDS)
        if total > 0
        else np.full(THIRDS, np.nan)
    )
    o2 = np.stack(curves) if curves else np.zeros((0, N_POINTS, 2))
    return {
        "o2_curves": o2.astype(np.float32),
        "o2_third": third_a,
        "o2_len_ratio": np.array(ratio),
        "o2_div_deg": np.array(div),
        "o2_per_m": per_m,
    }


def _forks(tree, firsts: list, height: float, crown_base: float) -> dict:
    """Crown forks on the trunk: first-order limbs above the crown base carrying at least
    ``FORK_SHARE`` of the branch length the leader carries above the same point (the
    descriptors' fork rule). Height over tree height, that share, the limb's unrolled
    curve and length over height; plus the stem's wander, its horizontal offset from the
    vertical through its base at tenths of the height (0.1 .. 1.0), over height."""
    trunk = tree.axes[0]
    after = {r: trunk[k + 1] for k, r in enumerate(trunk[:-1])}
    z, share, curves, lengths = [], [], [], []
    for b in firsts:
        cont = after.get(b.attach_row)
        if cont is None or not b.points[0, 2] >= crown_base:
            continue
        carried = tree.subtree[tree.axes[b.axis][0]] / max(tree.subtree[cont], 1e-9)
        if carried >= FORK_SHARE:
            z.append(b.points[0, 2] / height)
            share.append(carried)
            curves.append(_unroll(b.points))
            lengths.append(b.length / height)
    stem = _polyline(tree, trunk)
    up = stem[np.argsort(stem[:, 2], kind="stable")]
    wander = np.hypot(up[:, 0] - stem[0, 0], up[:, 1] - stem[0, 1]) / height
    knots = np.linspace(0.1, 1.0, 10)
    return {
        "fork_z": np.array(z),
        "fork_share": np.array(share),
        "fork_curves": (
            np.stack(curves) if curves else np.zeros((0, N_POINTS, 2))
        ).astype(np.float32),
        "fork_len_rel": np.array(lengths),
        "stem_offset": np.interp(knots, up[:, 2] / height, wander),
    }


def tree_profile(cyl: pd.DataFrame, keep_geometry: bool = False) -> dict | None:
    """Occupancy map, unrolled first-order branches and their crown deciles for one tree."""
    work = prune(cyl, **PRUNE)
    if work.empty:
        return None
    tree = _model(work)
    height = float(tree.end[:, 2].max())
    if height <= 0:
        return None
    trunk = _polyline(tree, tree.axes[0])
    laterals = _laterals(tree)
    firsts = [
        b
        for b in laterals
        if b.order == 1 and b.parent_axis == 0 and b.length >= MIN_BRANCH_M
    ]
    attach = np.array([b.points[0, 2] for b in firsts])
    crown_base = float(np.quantile(attach, 0.1)) if len(attach) else float("nan")
    crown_len = height - crown_base
    if firsts and crown_len > 0:
        rel = np.clip((attach - crown_base) / crown_len, 0, 0.9999)
        decile = (rel * DECILES).astype(int)
        curves = np.stack([_unroll(b.points) for b in firsts])
        count = np.bincount(decile, minlength=DECILES) / (crown_len / DECILES)
    else:
        decile = np.zeros(0, int)
        curves = np.zeros((0, N_POINTS, 2))
        count = np.full(DECILES, np.nan)
    out = {
        "height_m": height,
        "crown_base_m": crown_base,
        "occupancy": _occupancy(tree.start, tree.end, trunk, height),
        "curves": curves.astype(np.float32),
        "decile": decile,
        "length_rel": np.array([b.length for b in firsts]) / height,
        "count_per_m": count,
        # stem quality, for choosing a medoid (``clean_stems``): where the trunk axis
        # ends, how much of it is gaps between its cylinders, how far it wanders
        "trunk_top_rel": float(trunk[:, 2].max()) / height,
        "trunk_gap_rel": _trunk_gaps(tree) / height,
        "trunk_sinuosity": _trunk_sinuosity(tree),
        **_second_order(laterals, firsts),
        **_forks(tree, firsts, height, crown_base),
    }
    if keep_geometry:
        out["geometry"] = Geometry(
            tree.start, tree.end, tree.parent, tree.radius, tree.axes[0]
        )
    return out


# --- a group ----------------------------------------------------------------------------


def leading(profile: dict, decile: int, k: int = LEADING_PER_DECILE) -> np.ndarray:
    """Indices of a tree's ``k`` first-order branches whose tip ends farthest from their
    attachment (straight line) in crown decile ``decile`` (0-based).

    Not arc length: a QSM's longest "branches" are often zigzag fragments whose tip ends
    near where they start. Not horizontal reach either: that prefers flat branches and
    made beech limbs 10-15 degrees flatter than the descriptors' five longest branches
    (straight-line reach matches them within ~5-9 degrees, and on Kew spruce at 20 m it
    reaches as far as the crown outline)."""
    sel = np.flatnonzero(profile["decile"] == decile)
    tip = profile["curves"][sel][:, -1, :]
    reach = np.hypot(tip[:, 0], tip[:, 1]) * profile["length_rel"][sel]
    return sel[np.argsort(-reach, kind="stable")[:k]]


def _wquantile(values: np.ndarray, weights: np.ndarray, qs) -> np.ndarray:
    order = np.argsort(values)
    v, w = values[order], weights[order]
    cum = (np.cumsum(w) - 0.5 * w) / w.sum()
    return np.interp(qs, cum, v)


def group_curves(profiles: list[dict]) -> pd.DataFrame:
    """Median curve and p25/p75 band per crown decile, one row per (decile, point).

    Only each tree's leading branch per decile (``leading``) enters the curves and
    lengths: conifer QSMs break long branches into fragments and label stem pieces as
    branches, which would otherwise set the median. Branches are pooled, each tree weighing 1 per decile, so a
    densely resolved tree does not outvote the others. ``count_per_m_p50`` counts all
    branches of at least ``MIN_BRANCH_M``.
    """
    rows = []
    for d in range(DECILES):
        curves, weights, lengths, counts = [], [], [], []
        for p in profiles:
            sel = leading(p, d)
            k = len(sel)
            counts.append(p["count_per_m"][d])
            if k:
                curves.append(p["curves"][sel])
                weights.append(np.full(k, 1.0 / k))
                lengths.append(p["length_rel"][sel])
        if not curves:
            continue
        c = np.concatenate(curves).astype(float)
        w = np.concatenate(weights)
        length = _wquantile(np.concatenate(lengths), w, [0.25, 0.5, 0.75])
        base = {
            "decile": d + 1,
            "n_trees": len(curves),
            "n_branches": len(c),
            "length_rel_p25": length[0],
            "length_rel_p50": length[1],
            "length_rel_p75": length[2],
            "count_per_m_p50": float(np.nanmedian(counts)),
        }
        for i in range(N_POINTS):
            h = _wquantile(c[:, i, 0], w, [0.25, 0.5, 0.75])
            v = _wquantile(c[:, i, 1], w, [0.25, 0.5, 0.75])
            rows.append(
                {
                    **base,
                    "point": i,
                    "s_rel": i / (N_POINTS - 1),
                    "h_p25": h[0],
                    "h_p50": h[1],
                    "h_p75": h[2],
                    "v_p25": v[0],
                    "v_p50": v[1],
                    "v_p75": v[2],
                }
            )
    return pd.DataFrame(rows)


def group_occupancy(profiles: list[dict]) -> np.ndarray:
    """Share of the group's trees with branch length in each side-plane cell (0..1): a
    consensus silhouette in which one tree's stray cylinders count for 1 / n."""
    return np.mean([p["occupancy"] > 0 for p in profiles], axis=0)


def group_second_order(profiles: list[dict]) -> pd.DataFrame:
    """Median second-order branch per third of the parent limb (1 base .. 3 tip), one row
    per (third, point): unrolled curve, length over the parent's, horizontal divergence
    from the parent, branches per metre of parent. Each tree weighs 1 per third."""
    rows = []
    for t in range(THIRDS):
        curves, weights, ratios, divs, per_m = [], [], [], [], []
        for p in profiles:
            if "o2_third" not in p:
                continue
            per_m.append(p["o2_per_m"][t])
            sel = p["o2_third"] == t
            k = int(sel.sum())
            if k:
                curves.append(p["o2_curves"][sel])
                weights.append(np.full(k, 1.0 / k))
                ratios.append(p["o2_len_ratio"][sel])
                divs.append(p["o2_div_deg"][sel])
        if not curves:
            continue
        c = np.concatenate(curves).astype(float)
        w = np.concatenate(weights)
        div = np.concatenate(divs)
        ok = np.isfinite(div)
        base = {
            "third": t + 1,
            "n_trees": len(curves),
            "n_branches": len(c),
            "len_ratio_p50": float(_wquantile(np.concatenate(ratios), w, [0.5])[0]),
            "div_deg_p50": (
                float(_wquantile(div[ok], w[ok], [0.5])[0])
                if ok.any()
                else float("nan")
            ),
            "per_m_p50": float(np.nanmedian(per_m)),
        }
        for i in range(N_POINTS):
            h = _wquantile(c[:, i, 0], w, [0.5])[0]
            v = _wquantile(c[:, i, 1], w, [0.5])[0]
            rows.append({**base, "point": i, "h_p50": h, "v_p50": v})
    return pd.DataFrame(rows)


def group_forks(profiles: list[dict], min_rate: float = 0.5) -> dict | None:
    """How a group's trees split: share of trees with a crown fork (``rate``), forks per
    tree (median, ``n``), their heights (``z_rel``: ``n`` quantiles of all fork heights),
    the median fork-limb curve and length over height, the median share it carries, and
    the median stem wander (``stem_offset``). None when fewer than ``min_rate`` of the
    trees fork: the group keeps a single leader."""
    profs = [p for p in profiles if "fork_z" in p]
    if not profs:
        return None
    counts = np.array([len(p["fork_z"]) for p in profs])
    rate = float(np.mean(counts > 0))
    if rate < min_rate:
        return None
    n = max(1, round(float(np.median(counts))))
    forking = [p for p in profs if len(p["fork_z"])]
    heights = np.concatenate([p["fork_z"] for p in forking])
    w = np.concatenate(
        [np.full(len(p["fork_z"]), 1.0 / len(p["fork_z"])) for p in forking]
    )
    c = np.concatenate([p["fork_curves"] for p in forking]).astype(float)
    curve = np.array(
        [
            [_wquantile(c[:, i, k], w, [0.5])[0] for k in range(2)]
            for i in range(N_POINTS)
        ]
    )
    return {
        "rate": rate,
        "n": n,
        "z_rel": _wquantile(heights, w, (np.arange(n) + 0.5) / n),
        "curve": curve,
        "len_rel": float(
            _wquantile(np.concatenate([p["fork_len_rel"] for p in forking]), w, [0.5])[
                0
            ]
        ),
        "share": float(
            _wquantile(np.concatenate([p["fork_share"] for p in forking]), w, [0.5])[0]
        ),
        "stem_offset": np.median([p["stem_offset"] for p in profs], axis=0),
        "n_trees": len(profs),
    }


GOLDEN_ANGLE = math.pi * (3 - math.sqrt(5))


def template_tree(
    curves: pd.DataFrame,
    height_m: float,
    crown_base_rel: float,
    second: pd.DataFrame | None = None,
    forks: dict | None = None,
    envelope: tuple[np.ndarray, np.ndarray] | None = None,
    trunk_segments: int = 50,
) -> Geometry:
    """A synthetic tree: a vertical trunk carrying, in every crown decile, the median
    number of branches per metre, each the decile's median curve at its median length,
    placed evenly and turned by the golden angle. Radius column left at zero (see
    ``pipe_radii``).

    ``second`` (``group_second_order``): every limb carries the median second-order
    branches of each of its thirds, alternating left and right at the median divergence.

    ``forks`` (``group_forks``, broadleaves): the stem wanders by the group's median
    horizontal offset profile, and at the median fork heights the leader splits into
    co-dominant limbs (median fork-limb curve and length, spread evenly around the stem,
    the first opposite the wander). Branches above a fork are shared out in turn among
    the leader and the limbs that reach their height, so the limbs grow crowns of their
    own and the pipe radii thicken them like real co-leaders.

    ``envelope`` (median crown outline: z and half width, both over height): each
    decile's branch keeps its median shape but is lengthened or shortened (0.5-3 x)
    until its tip reaches the outline at the tip's height. The median branch is a
    typical branch, so without this a decurrent crown comes out as a narrow cone
    inside the rounded envelope that its many branches of varied length fill.
    """
    zs = np.linspace(0, height_m, trunk_segments + 1)
    offset = np.zeros_like(zs)
    if forks is not None:
        knots = np.linspace(0, 1, len(forks["stem_offset"]) + 1)
        values = np.concatenate([[0.0], forks["stem_offset"]])
        offset = np.interp(zs / height_m, knots, values) * height_m
    leader = np.column_stack([offset, np.zeros_like(zs), zs])  # wanders towards +x
    start = [leader[i] for i in range(trunk_segments)]
    end = [leader[i + 1] for i in range(trunk_segments)]
    parent = [i - 1 for i in range(trunk_segments)]
    trunk_rows = list(range(trunk_segments))
    stems = [(leader, trunk_rows)]
    if forks is not None:
        heights = forks["z_rel"]
        length = forks["len_rel"] * height_m
        h = forks["curve"][:, 0] * length
        v = forks["curve"][:, 1] * length
        for k, zf in enumerate(heights):
            p0, row = _attach(leader, trunk_rows, zf * height_m)
            az = math.pi + 2 * math.pi * k / len(heights)
            pts = np.column_stack(
                [p0[0] + h * math.cos(az), p0[1] + h * math.sin(az), p0[2] + v]
            )
            rows = []
            for j in range(len(pts) - 1):
                start.append(pts[j])
                end.append(pts[j + 1])
                parent.append(row)
                row = len(start) - 1
                rows.append(row)
            stems.append((pts, rows))
    base = crown_base_rel * height_m
    span = (height_m - base) / DECILES
    turn = 0
    for d, dec in curves.groupby("decile"):
        dec = dec.sort_values("point")
        n = max(1, round(float(dec["count_per_m_p50"].iloc[0]) * span))
        median_length = float(dec["length_rel_p50"].iloc[0]) * height_m
        h_rel = dec["h_p50"].to_numpy()
        v_rel = dec["v_p50"].to_numpy()
        lo = base + (int(d) - 1) * span
        for k in range(n):
            z = lo + (k + 0.5) * span / n
            length = median_length
            if envelope is not None:
                length = _to_envelope(
                    h_rel, v_rel, z, median_length, height_m, envelope
                )
            h, v = h_rel * length, v_rel * length
            az = turn * GOLDEN_ANGLE
            reach = [st for st in stems if st[0][:, 2].min() <= z <= st[0][:, 2].max()]
            stem_pts, stem_rows = (reach or stems[:1])[turn % max(1, len(reach))]
            turn += 1
            p0, row = _attach(stem_pts, stem_rows, z)
            pts = np.column_stack(
                [p0[0] + h * math.cos(az), p0[1] + h * math.sin(az), p0[2] + v]
            )
            limb = []
            for j in range(len(pts) - 1):
                start.append(pts[j])
                end.append(pts[j + 1])
                parent.append(row)
                row = len(start) - 1
                limb.append(row)
            if second is not None and len(second):
                _add_second_order(pts, limb, az, second, start, end, parent)
    start_a, end_a = np.array(start), np.array(end)
    return Geometry(
        start_a, end_a, np.array(parent), np.zeros(len(start_a)), trunk_rows
    )


def _to_envelope(h_rel, v_rel, z, length, height_m, envelope) -> float:
    """Length at which a branch of shape (``h_rel``, ``v_rel``) attached at ``z`` reaches
    the crown outline at its tip's height (fixed point, clipped to 0.5-3 x ``length``);
    ``length`` unchanged where the tip lies outside the outline's height range."""
    z_env, half_env = (np.asarray(a, dtype=float) for a in envelope)
    order = np.argsort(z_env)
    z_env, half_env = z_env[order] * height_m, half_env[order] * height_m
    reach = float(np.max(h_rel))
    if reach <= 1e-6:
        return length
    out = length
    for _ in range(8):
        tip = z + float(v_rel[-1]) * out
        if not z_env[0] <= tip <= z_env[-1]:
            return length if out == length else out
        out = float(
            np.clip(np.interp(tip, z_env, half_env) / reach, 0.5 * length, 3 * length)
        )
    return out


def _attach(pts: np.ndarray, rows: list[int], z: float) -> tuple[np.ndarray, int]:
    """The point of a polyline (``pts``, cylinder ``rows`` between its points) at height
    ``z``, and the row it lies on; the nearest point when the polyline never crosses z."""
    for j in range(len(rows)):
        z0, z1 = pts[j, 2], pts[j + 1, 2]
        if min(z0, z1) <= z <= max(z0, z1):
            t = (z - z0) / (z1 - z0) if abs(z1 - z0) > 1e-12 else 0.0
            return pts[j] + t * (pts[j + 1] - pts[j]), rows[j]
    j = int(np.argmin(np.abs(pts[:-1, 2] - z)))
    return pts[j].copy(), rows[j]


def _add_second_order(pts, limb, az, second, start, end, parent) -> None:
    arc = _arc(pts)
    total = arc[-1]
    if total <= 0:
        return
    side = 1
    for t, sec in second.groupby("third"):
        sec = sec.sort_values("point")
        n = round(float(sec["per_m_p50"].iloc[0]) * total / THIRDS)
        div = float(sec["div_deg_p50"].iloc[0])
        div = math.radians(div if np.isfinite(div) else 60.0)
        length = float(sec["len_ratio_p50"].iloc[0]) * total
        h = sec["h_p50"].to_numpy() * length
        v = sec["v_p50"].to_numpy() * length
        for k in range(n):
            s = (int(t) - 1 + (k + 0.5) / n) * total / THIRDS
            j = int(np.clip(np.searchsorted(arc, s) - 1, 0, len(limb) - 1))
            p0 = _at(pts, arc, s)
            tangent = pts[j + 1, :2] - pts[j, :2]
            heading = (
                math.atan2(tangent[1], tangent[0])
                if np.linalg.norm(tangent) > 1e-9
                else az
            )
            ang = heading + side * div
            side = -side
            sub = np.column_stack(
                [p0[0] + h * math.cos(ang), p0[1] + h * math.sin(ang), p0[2] + v]
            )
            row = limb[j]
            for i in range(len(sub) - 1):
                start.append(sub[i])
                end.append(sub[i + 1])
                parent.append(row)
                row = len(start) - 1


def score_curves(profile: dict, curves: pd.DataFrame) -> pd.DataFrame:
    """A tree's leading first-order branches (``leading``, as in ``group_curves``)
    against a group's median curves, per crown decile.

    ``dv_signed``  mean (tree - real median) vertical offset over branch length; negative
                   means the branches hang lower than the real median
    ``dv_abs``     the same, absolute
    ``in_band``    share of curve points whose vertical offset lies inside the real p25-p75
    """
    rows = []
    for d, dec in curves.groupby("decile"):
        sel = leading(profile, int(d) - 1)
        if not len(sel):
            continue
        dec = dec.sort_values("point")
        v = profile["curves"][sel][:, :, 1].astype(float)
        diff = v - dec["v_p50"].to_numpy()
        inside = (v >= dec["v_p25"].to_numpy()) & (v <= dec["v_p75"].to_numpy())
        rows.append(
            {
                "decile": int(d),
                "n_branches": len(sel),
                "dv_signed": float(diff[:, 1:].mean()),
                "dv_abs": float(np.abs(diff[:, 1:]).mean()),
                "in_band": float(inside[:, 1:].mean()),
            }
        )
    return pd.DataFrame(rows)
