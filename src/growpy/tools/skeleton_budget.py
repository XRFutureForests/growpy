"""Skeleton (bone) budget of catalog growth JSONs, read-only.

    growpy-skeleton-budget --out-dir <dir>
    growpy-skeleton-budget --forest-dir data/output/forest --radii 07,10 --spacing --out-dir <dir>

``skeleton_budget.csv``, per growth JSON: points (= PVE bones before the 1.02-1.61x
export factor), polylines, segment lengths, points per metre of tree height, the share
of points on branches shorter than 0.3 m, and what share of points a Douglas-Peucker
simplification at 1 / 2 / 5 cm keeps.

``spacing_budget.csv`` (``--spacing``): what ``min_point_spacing`` would save without a
regrow. It mimics the export's resampling rule (keep root, tip and every point a child
attaches to; thin the rest along each branch to at least ``s`` metres of path) and
reports kept points with the p95 and largest deviation of a dropped point from the chord
between kept neighbours; ``dp1cm`` keeps the mandatory points plus Douglas-Peucker at
1 cm. Hub: ``04-LOGIC-TIER/tree-skeleton-budget-2026-10``.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd

CELL = re.compile(r"_r(?P<r>\d+)_h(?P<h>\d+)m_d(?P<d>\d+)cm")
SPACINGS = [0.0, 0.1, 0.15, 0.2, 0.3]


def _chord_dist(p: np.ndarray, a: int, b: int) -> np.ndarray:
    """Distance of the points strictly between a and b from the chord a-b."""
    ab = p[b] - p[a]
    L2 = float(ab @ ab)
    seg = p[a + 1 : b] - p[a]
    t = np.clip(seg @ ab / L2, 0, 1) if L2 > 1e-12 else np.zeros(len(seg))
    return np.linalg.norm(seg - np.outer(t, ab), axis=1)


def douglas_peucker(p: np.ndarray, keep: np.ndarray, tol: float) -> np.ndarray:
    """Add points to ``keep`` until no dropped point is more than ``tol`` off its chord."""
    keep = keep.copy()
    ks = list(np.flatnonzero(keep))
    stack = list(zip(ks[:-1], ks[1:], strict=False))
    while stack:
        a, b = stack.pop()
        if b - a < 2:
            continue
        d = _chord_dist(p, a, b)
        i = int(np.argmax(d))
        if d[i] > tol:
            k = a + 1 + i
            keep[k] = True
            stack += [(a, k), (k, b)]
    return keep


def _ends(n: int) -> np.ndarray:
    keep = np.zeros(n, bool)
    keep[0] = keep[-1] = True
    return keep


def deviations(p: np.ndarray, keep: np.ndarray) -> np.ndarray:
    ks = np.flatnonzero(keep)
    out = [
        _chord_dist(p, a, b)
        for a, b in zip(ks[:-1], ks[1:], strict=False)
        if b - a >= 2
    ]
    return np.concatenate(out) if out else np.zeros(0)


def _growth_jsons(forest_dir: Path, radii: set[str]):
    for path in sorted(forest_dir.glob("*/r*/*_growth_data.json")):
        m = CELL.search(path.name)
        if m and m["r"] in radii:
            data = json.loads(path.read_text(encoding="utf-8"))
            pos = np.asarray(data["points"]["positions"], float)
            lines = [np.asarray(ln, int) for ln in data["primitives"]["points"]]
            yield path, m, pos, lines


def skeleton_row(path: Path, m: re.Match, pos: np.ndarray, lines: list) -> dict:
    height = float(pos[:, 1].max() - pos[:, 1].min())  # growth JSON is y up
    seglens, branch_len = [], []
    kept = {0.01: 0, 0.02: 0, 0.05: 0}
    short_pts = 0
    for idx in lines:
        p = pos[idx]
        d = np.linalg.norm(np.diff(p, axis=0), axis=1)
        seglens.extend(d.tolist())
        length = float(d.sum())
        branch_len.append(length)
        if length < 0.3:
            short_pts += len(idx) - 1
        for tol in kept:
            n = len(p)
            kept[tol] += (
                int(douglas_peucker(p, _ends(n), tol).sum()) if n > 2 else n
            ) - 1
    seglens, branch_len = np.asarray(seglens), np.asarray(branch_len)
    own_pts = sum(len(ln) - 1 for ln in lines) + 1  # first point of a line is shared
    return {
        "species": path.parts[-3],
        "radius": f"r{m['r']}",
        "height_stage": int(m["h"]),
        "height_m": round(height, 2),
        "points": len(pos),
        "polylines": len(lines),
        "points_per_m": round(len(pos) / max(height, 0.1), 1),
        "pts_per_branch": round(own_pts / max(len(lines), 1), 2),
        "seg_p50_m": round(float(np.median(seglens)), 3),
        "seg_p10_m": round(float(np.percentile(seglens, 10)), 3),
        "branches_lt_0p3m": int((branch_len < 0.3).sum()),
        "pts_on_branches_lt_0p3m_share": round(short_pts / max(own_pts, 1), 3),
        "dp_keep_1cm": round(kept[0.01] / max(own_pts - 1, 1), 3),
        "dp_keep_2cm": round(kept[0.02] / max(own_pts - 1, 1), 3),
        "dp_keep_5cm": round(kept[0.05] / max(own_pts - 1, 1), 3),
        "file_mtime": int(path.stat().st_mtime),
    }


def spacing_row(path: Path, m: re.Match, pos: np.ndarray, lines: list) -> dict:
    attach = {int(ln[0]) for ln in lines}
    row = {"species": path.parts[-3], "radius": f"r{m['r']}", "h": int(m["h"]),
           "points": len(pos)}  # fmt: skip
    for s in [*SPACINGS, "dp1cm"]:
        kept_pts: set[int] = set()
        devs = []
        for ln in lines:
            p = pos[ln]
            mand = np.array(
                [
                    i == 0 or i == len(ln) - 1 or int(ln[i]) in attach
                    for i in range(len(ln))
                ]
            )
            if s == "dp1cm":
                keep = douglas_peucker(p, mand, 0.01)
            elif s > 0:
                keep = mand.copy()
                d = np.r_[0, np.cumsum(np.linalg.norm(np.diff(p, axis=0), axis=1))]
                last = 0.0
                for i in range(len(ln)):
                    if keep[i]:
                        last = d[i]
                    elif d[i] - last >= s:
                        keep[i] = True
                        last = d[i]
            else:
                keep = np.ones(len(ln), bool)
            kept_pts.update(int(x) for x in ln[keep])
            if s != 0.0:
                devs.append(deviations(p, keep))
        dv = np.concatenate(devs) if devs else np.zeros(0)
        dv = dv if len(dv) else np.zeros(1)
        row[f"kept_{s}"] = len(kept_pts)
        row[f"dev95_cm_{s}"] = round(float(np.percentile(dv, 95)) * 100, 2) if s else 0
        row[f"devmax_cm_{s}"] = round(float(dv.max()) * 100, 1) if s else 0
    return row


def main(argv: list[str] | None = None) -> int:
    from growpy.config.paths import get_data_directory

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--forest-dir", type=Path, default=get_data_directory() / "output" / "forest"
    )
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument(
        "--radii", default="07,10", help="radius labels (default 07,10)"
    )
    parser.add_argument(
        "--spacing", action="store_true", help="also the spacing budget"
    )
    args = parser.parse_args(argv)
    radii = set(args.radii.split(","))
    skeleton, spacing = [], []
    for path, m, pos, lines in _growth_jsons(args.forest_dir, radii):
        skeleton.append(skeleton_row(path, m, pos, lines))
        if args.spacing:
            spacing.append(spacing_row(path, m, pos, lines))
    if not skeleton:
        print(f"no growth JSONs for radii {sorted(radii)} under {args.forest_dir}")
        return 1
    args.out_dir.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(skeleton)
    df.to_csv(args.out_dir / "skeleton_budget.csv", index=False)
    pd.set_option("display.width", 250)
    pd.set_option("display.max_columns", 40)
    print(
        df.groupby("species")
        .agg(
            cells=("points", "size"),
            pts_p50=("points", "median"),
            pts_max=("points", "max"),
            pts_per_m_p50=("points_per_m", "median"),
            pts_per_branch=("pts_per_branch", "median"),
            seg_p50=("seg_p50_m", "median"),
            short_share=("pts_on_branches_lt_0p3m_share", "median"),
            keep1=("dp_keep_1cm", "median"),
            keep2=("dp_keep_2cm", "median"),
            keep5=("dp_keep_5cm", "median"),
        )
        .round(3)
        .to_string()
    )
    if spacing:
        sp = pd.DataFrame(spacing)
        sp.to_csv(args.out_dir / "spacing_budget.csv", index=False)
        agg = {"points": "median"}
        for s in [*SPACINGS[1:], "dp1cm"]:
            sp[f"frac_{s}"] = sp[f"kept_{s}"] / sp["points"]
            agg[f"frac_{s}"] = "median"
            agg[f"dev95_cm_{s}"] = "median"
        print("\n" + sp.groupby("species").agg(agg).round(3).to_string())
    print(f"-> {args.out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
