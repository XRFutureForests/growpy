"""Branching-structure descriptors of a growth JSON, in the hub's schema frames (XRFF-535).

Whether a generated tree *looks* like its species used to be judged by eye after the
fact (the arm-C conifers were 0 % upturned and still looked like combs). This measures
the skeleton in the vocabulary of the knowledge hub's branching descriptor schema
(``04-LOGIC-TIER/branching-architecture/descriptor-schema``), every angle with its frame
declared, so a generated tree and a scanned/QSM tree can be compared with the SAME code:

    L1  tree and crown   crown base, crown ratio, crown width per DBH, width by depth
    L3  node and whorl   branches per node, node spacing, divergence, regularity (T1)
    L4  branch profiles  angle (chord to half length, first 0.3 m, tip), length,
                         diameter ratio, order counts and bifurcation ratio (T2)
    --  shape            straightness, bend, droop, regularity indices

Input is a growth JSON (y-up, metres): the first primitive is the trunk, a first-order
branch is a branch whose parent is the trunk, positions are polylines. A QSM converted to
that layout (cylinder chain per branch, parent id) goes through the same code.

    growpy-structure-descriptors data/output/forest/douglas_fir/r07/*h25m*_growth_data.json
    growpy-structure-descriptors <dir> --out descriptors.json
    growpy-structure-descriptors --compare OLD_DIR NEW_DIR      # side by side medians

Regularity indices are 0 for a perfectly mechanical tree (equal spacing, equal angles,
equal lengths); a real stand tree is not zero. They are not thresholds yet: there is no
reference corpus to set them from (that is what the QSM comparison is for).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics as st
import sys
from dataclasses import dataclass, field
from pathlib import Path

HEAD_M = 0.3  # a branch's initial and tip directions are read over 30 cm
MIN_BRANCH_M = 0.5  # shorter first-order branches are twigs, not branches
THIRDS = ("top", "middle", "bottom")


def _sub(a, b):
    return [a[i] - b[i] for i in range(3)]


def _len(v) -> float:
    return math.sqrt(sum(c * c for c in v))


def _from_up(v) -> float:
    """Degrees between a direction and +Y (the growth JSON is y-up)."""
    n = _len(v) or 1.0
    return math.degrees(math.acos(max(-1.0, min(1.0, v[1] / n))))


def _head(pts, m=HEAD_M):
    for p in pts[1:]:
        if _len(_sub(p, pts[0])) >= m:
            return _sub(p, pts[0])
    return _sub(pts[-1], pts[0])


def _tail(pts, m=HEAD_M):
    for p in reversed(pts[:-1]):
        if _len(_sub(pts[-1], p)) >= m:
            return _sub(pts[-1], p)
    return _sub(pts[-1], pts[0])


def _point_at_arc(pts, target: float):
    """The point at ``target`` metres along a polyline."""
    walked = 0.0
    for a, b in zip(pts, pts[1:], strict=False):
        seg = _len(_sub(b, a))
        if walked + seg >= target and seg > 0:
            t = (target - walked) / seg
            return [a[i] + (b[i] - a[i]) * t for i in range(3)]
        walked += seg
    return pts[-1]


def _quantiles(values, qs=(0.1, 0.5, 0.9)):
    if not values:
        return None
    ordered = sorted(values)
    return [round(ordered[int(q * (len(ordered) - 1))], 3) for q in qs]


def _cv(values) -> float | None:
    values = [v for v in values if v is not None]
    if len(values) < 2 or st.mean(values) == 0:
        return None
    return round(st.pstdev(values) / abs(st.mean(values)), 3)


@dataclass
class Branch:
    node: int  # trunk vertex the branch attaches to
    attach_y: float
    attach_arc: float  # metres along the trunk
    arc_m: float
    chord_angle: float  # from vertical, base to the point at half length
    head_angle: float  # from vertical, first 0.3 m
    tip_angle: float  # from vertical, last 0.3 m
    straightness: float  # chord / arc
    bend: float  # |tip - head|, degrees
    azimuth: float  # degrees about the trunk axis, of the chord to half length
    radius_ratio: float | None  # branch base radius / trunk radius at the attachment


@dataclass
class Descriptors:
    height_m: float
    n_first_order: int
    crown: dict = field(default_factory=dict)
    whorl: dict = field(default_factory=dict)
    angles: dict = field(default_factory=dict)
    lengths: dict = field(default_factory=dict)
    diameters: dict = field(default_factory=dict)
    orders: dict = field(default_factory=dict)
    shape: dict = field(default_factory=dict)


def first_order_branches(data: dict) -> tuple[list[Branch], list, list, list]:
    pos = data["points"]["positions"]
    prims = data["primitives"]["points"]
    attrs = data["primitives"]["attributes"]
    numbers = attrs["branchNumber"]["values"]
    parents = attrs["branchParentNumber"]["values"]
    radii = data["points"].get("attributes", {}).get("budLateralMeristem", {}).get("values")
    trunk_idx = prims[0]
    trunk = [pos[i] for i in trunk_idx]
    arc = [0.0]
    for a, b in zip(trunk, trunk[1:], strict=False):
        arc.append(arc[-1] + _len(_sub(b, a)))
    branches: list[Branch] = []
    for i, idx in enumerate(prims):
        if i == 0 or len(idx) < 2 or parents[i] != numbers[0]:
            continue
        pts = [pos[k] for k in idx]
        length = sum(_len(_sub(b, a)) for a, b in zip(pts, pts[1:], strict=False))
        if length < MIN_BRANCH_M:
            continue
        node = min(range(len(trunk)), key=lambda k: _len(_sub(trunk[k], pts[0])))
        half = _point_at_arc(pts, length / 2.0)
        chord = _sub(half, pts[0])
        chord_h = math.hypot(chord[0], chord[2])
        ratio = None
        if radii is not None:
            rb, rt = radii[idx[0]][0], radii[trunk_idx[node]][0]
            ratio = rb / rt if rt > 0 else None
        branches.append(Branch(
            node=node, attach_y=trunk[node][1], attach_arc=arc[node], arc_m=length,
            chord_angle=_from_up(chord), head_angle=_from_up(_head(pts)),
            tip_angle=_from_up(_tail(pts)),
            straightness=_len(_sub(pts[-1], pts[0])) / length,
            bend=abs(_from_up(_tail(pts)) - _from_up(_head(pts))),
            azimuth=math.degrees(math.atan2(chord[2], chord[0])) if chord_h > 1e-9 else 0.0,
            radius_ratio=ratio,
        ))
    return branches, pos, prims, trunk


def describe(growth_json: Path | str) -> Descriptors | None:
    data = json.loads(Path(growth_json).read_text(encoding="utf-8"))
    branches, pos, prims, trunk = first_order_branches(data)
    if not branches:
        return None
    ys = [p[1] for p in pos]
    height = max(ys) - min(ys)
    base_y = min(ys)
    out = Descriptors(height_m=round(height, 2), n_first_order=len(branches))

    # --- nodes and whorls (T1) ---------------------------------------------------
    nodes: dict[int, list[Branch]] = {}
    for b in branches:
        nodes.setdefault(b.node, []).append(b)
    ordered = sorted(nodes)
    per_node = [len(nodes[n]) for n in ordered]
    arcs = [nodes[n][0].attach_arc for n in ordered]
    spacing = [b - a for a, b in zip(arcs, arcs[1:], strict=False) if b - a > 1e-6]
    gaps_cv, len_cv, phase = [], [], []
    prev = None  # (pattern offset, period) of the previous whorl
    for n in ordered:
        group = nodes[n]
        if len(group) >= 3:
            az = sorted(b.azimuth % 360.0 for b in group)
            gaps = [(y - x) for x, y in zip(az, az[1:], strict=False)] + [az[0] + 360.0 - az[-1]]
            gaps_cv.append(_cv(gaps))
        if len(group) >= 2:
            len_cv.append(_cv([b.arc_m for b in group]))
        # how far each whorl is turned from the one below, modulo its own symmetry: a
        # regular whorl repeats every 360/n degrees, so only the offset inside that
        # period means anything (a circular mean of a symmetric whorl is undefined)
        period = 360.0 / len(group)
        offset = min(b.azimuth % 360.0 for b in group) % period
        if prev is not None and abs(prev[1] - period) < 1e-6:
            phase.append((offset - prev[0]) % period)
        prev = (offset, period)
    span = (len(trunk) - 1) if len(trunk) > 1 else 1
    out.whorl = {
        "nodes_with_branches": len(ordered),
        "branches_per_node_p10_p50_p90": _quantiles(per_node),
        "tier_spacing_m_p10_p50_p90": _quantiles(spacing),
        "tier_spacing_cv": _cv(spacing),  # 0 = every tier the same distance apart
        "divergence_gap_cv": round(st.mean([g for g in gaps_cv if g is not None]), 3) if any(g is not None for g in gaps_cv) else None,
        "length_cv_within_node": round(st.mean([g for g in len_cv if g is not None]), 3) if any(g is not None for g in len_cv) else None,
        "phase_step_cv": _cv(phase),  # 0 = every whorl turned the same angle from the last
    }

    # --- crown (L1) -----------------------------------------------------------------
    low = next((n for n in ordered if len(nodes[n]) >= 2), ordered[0])
    crown_base_y = nodes[low][0].attach_y
    crown_len = max(height - (crown_base_y - base_y), 1e-6)
    # horizontal reach of every branch point, by depth below the tip
    axis = {round(t[1], 3): (t[0], t[2]) for t in trunk}
    trunk_ys = sorted(axis)

    def axis_at(y):
        k = min(trunk_ys, key=lambda v: abs(v - y))
        return axis[k]

    bins = [0.0] * 10
    for idx in prims[1:]:
        for i in idx:
            y = pos[i][1]
            if y < crown_base_y:
                continue
            depth = (base_y + height - y) / crown_len
            if depth <= 1.0:
                ax, az = axis_at(y)
                r = math.hypot(pos[i][0] - ax, pos[i][2] - az)
                b = min(int(depth * 10), 9)
                bins[b] = max(bins[b], r)
    widths = [round(2 * r, 2) for r in bins]
    widest = max(range(10), key=lambda i: widths[i])
    out.crown = {
        "crown_base_m": round(crown_base_y - base_y, 2),
        "crown_ratio": round(crown_len / height, 3),
        "crown_width_by_depth_m": widths,  # 10 tenths of the crown, top to bottom
        "widest_at_depth_fraction": round((widest + 0.5) / 10, 2),
        "max_crown_width_m": max(widths),
        "crown_width_over_height": round(max(widths) / height, 3),
    }

    # --- angles, lengths, diameters (L4 / T2) -------------------------------------------
    def thirds(values_by_branch):
        res = {}
        order = sorted(branches, key=lambda b: -b.attach_y)  # top first
        n = len(order)
        for t, name in enumerate(THIRDS):
            part = order[t * n // 3:(t + 1) * n // 3]
            vals = [values_by_branch(b) for b in part if values_by_branch(b) is not None]
            res[name] = round(st.median(vals), 2) if vals else None
        return res

    out.angles = {
        "chord_to_half_length_deg_by_third": thirds(lambda b: b.chord_angle),  # frame: from vertical
        "initial_30cm_deg_by_third": thirds(lambda b: b.head_angle),
        "tip_30cm_deg_by_third": thirds(lambda b: b.tip_angle),
        "tip_deg_p10_p50_p90": _quantiles([b.tip_angle for b in branches]),
    }
    out.lengths = {
        "branch_length_m_by_third": thirds(lambda b: b.arc_m),
        "longest_over_crown_width": round(max(b.arc_m for b in branches) / max(max(widths), 1e-6), 2),
    }
    out.diameters = {"branch_to_stem_radius_by_third": thirds(lambda b: b.radius_ratio)}

    # --- order counts (L4.4; branch order depends on the algorithm) ---------------------------
    hier = data["primitives"]["attributes"].get("branchHierarchyNumber", {}).get("values")
    if hier:
        counts: dict[int, int] = {}
        for h in hier[1:]:
            counts[h] = counts.get(h, 0) + 1
        keys = sorted(counts)
        out.orders = {
            "branches_by_order": {str(k): counts[k] for k in keys},
            "bifurcation_ratio": {f"{a}/{b}": round(counts[a] / counts[b], 2)
                                  for a, b in zip(keys, keys[1:], strict=False) if counts[b]},
        }

    # --- shape ----------------------------------------------------------------------------
    out.shape = {
        "straightness_median": round(st.median(b.straightness for b in branches), 3),
        "straightness_p10": _quantiles([b.straightness for b in branches])[0],
        "bend_deg_median": round(st.median(b.bend for b in branches), 1),
        "upturned_tips_share": round(sum(b.tip_angle < 30 for b in branches) / len(branches), 3),
        "branch_length_cv": _cv([b.arc_m for b in branches]),
        "chord_angle_cv": _cv([b.chord_angle for b in branches]),
    }
    return out


def flatten(d: Descriptors) -> dict:
    """One flat row of the headline numbers, for tables and comparisons."""
    third = lambda blob, name: (blob or {}).get(name)  # noqa: E731
    return {
        "height_m": d.height_m,
        "crown_ratio": d.crown.get("crown_ratio"),
        "crown_w/h": d.crown.get("crown_width_over_height"),
        "widest_at": d.crown.get("widest_at_depth_fraction"),
        "br/node_p50": (d.whorl.get("branches_per_node_p10_p50_p90") or [None] * 3)[1],
        "tier_gap_m": (d.whorl.get("tier_spacing_m_p10_p50_p90") or [None] * 3)[1],
        "tier_cv": d.whorl.get("tier_spacing_cv"),
        "div_gap_cv": d.whorl.get("divergence_gap_cv"),
        "chord_top": third(d.angles["chord_to_half_length_deg_by_third"], "top"),
        "chord_mid": third(d.angles["chord_to_half_length_deg_by_third"], "middle"),
        "chord_bot": third(d.angles["chord_to_half_length_deg_by_third"], "bottom"),
        "tip_p50": (d.angles.get("tip_deg_p10_p50_p90") or [None] * 3)[1],
        "straight": d.shape.get("straightness_median"),
        "bend": d.shape.get("bend_deg_median"),
        "len_cv": d.shape.get("branch_length_cv"),
    }


def _files(target: Path) -> list[Path]:
    if target.is_file():
        return [target]
    return sorted(target.rglob("*_growth_data.json"))


def _print_table(rows: list[tuple[str, dict]]) -> None:
    if not rows:
        return
    keys = list(rows[0][1])
    print(f"{'cell':<34}" + "".join(f"{k:>12}" for k in keys))
    for name, row in rows:
        print(f"{name:<34}" + "".join(f"{('-' if row[k] is None else row[k]):>12}" for k in keys))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("targets", nargs="*", type=Path, help="growth JSON files or directories")
    parser.add_argument("--compare", nargs=2, type=Path, metavar=("A", "B"),
                        help="two directories; prints the headline numbers of matching cells side by side")
    parser.add_argument("--out", type=Path, default=None, help="full descriptors as JSON")
    args = parser.parse_args(argv)

    if args.compare:
        a_files, b_files = ({_cell(p): p for p in _files(d)} for d in args.compare)
        rows = []
        for key in sorted(set(a_files) & set(b_files)):
            da, db = describe(a_files[key]), describe(b_files[key])
            if da and db:
                fa, fb = flatten(da), flatten(db)
                rows.append((f"{key} A", fa))
                rows.append((f"{key} B", fb))
        _print_table(rows)
        return 0 if rows else 1

    results, rows = {}, []
    for target in args.targets:
        for path in _files(target):
            d = describe(path)
            if d is None:
                continue
            results[str(path)] = d.__dict__
            rows.append((_cell(path), flatten(d)))
    _print_table(rows)
    if args.out:
        args.out.write_text(json.dumps(results, indent=1), encoding="utf-8")
    return 0 if rows else 1


def _cell(path: Path) -> str:
    import re

    m = re.search(r"([A-Za-z_]+)_r(\d+)_h(\d+)m", path.name)
    return f"{m[1]} r{int(m[2]):02d} h{int(m[3]):02d}" if m else path.name


if __name__ == "__main__":
    sys.exit(main())
