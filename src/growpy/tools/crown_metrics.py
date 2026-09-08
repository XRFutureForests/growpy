#!/usr/bin/env python3
"""Measure real crown geometry from exported Nanite assemblies.

Reads the ``TwigInstances`` PointInstancer out of an ``*_assembly.usd*`` and
derives the dimensions foresters actually publish, in metres, so a generated
tree can be checked against literature instead of against an impression:

    crown_diameter    2 x the 95th-percentile horizontal radius of the foliage
    crown_base        lowest height carrying a non-trivial share of the foliage
    crown_ratio       (height - crown_base) / height
    crown_projection  convex-hull area of the foliage seen from above (m^2)
    lai_proxy         total prototype leaf area / crown projection area

Why the twig instances and not the branch mesh: the CROWN is the foliage
envelope. Branch tips extend past the leafy volume and a wandering stem drags
any stem-based estimate downwards -- an earlier bole metric read 1.4 m on an
oak whose live crown visibly started near 17 m, because the stem itself
deviated laterally more than the threshold.

Percentiles, not extremes: one long limb otherwise sets the diameter, which
made crown width read non-monotonically across a parameter sweep.

Reference values for forest-grown European stands (Norway spruce, European
beech) put crown ratio near 0.57-0.60 with height to crown base of 7-10 m on
20-25 m trees (Sharma et al. 2017, PLOS One 12(10): e0186394,
doi:10.1371/journal.pone.0186394). Open-grown trees carry markedly wider
crowns and a much lower crown base than stand-grown ones (Peper, McPherson &
Mori 2001, J. Arboriculture 27(6): 306-317), so r00 is expected to sit well
above those numbers and the shaded radii near or below them.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path

import numpy as np

_NAME = re.compile(r"^(.+?)_r(\d+)_h(\d+)m_d(\d+)cm_", re.IGNORECASE)


def _hull_area(pts: np.ndarray) -> float:
    """Convex-hull area of 2-D points; 0.0 when degenerate."""
    if len(pts) < 3:
        return 0.0
    try:
        from scipy.spatial import ConvexHull

        return float(ConvexHull(pts).volume)  # 'volume' is area in 2-D
    except Exception:
        # Fall back to a bounding ellipse, which is close enough for a QA number
        # and keeps this usable without scipy.
        rx = (pts[:, 0].max() - pts[:, 0].min()) / 2.0
        ry = (pts[:, 1].max() - pts[:, 1].min()) / 2.0
        return math.pi * rx * ry


def _proto_key(name: str) -> str:
    """Match a sidecar name to a USD prototype name.

    USD prim names have to be valid identifiers, so the exporter strips the
    underscores: ``european_beech_foliage_a`` becomes ``europeanbeechfoliagea``.
    Comparing on a normalised key keeps the two sides in step without either
    having to know how the other spells it.
    """
    return "".join(c for c in name.lower() if c.isalnum())


def load_leaf_areas(twig_dir: Path) -> dict[str, float]:
    """Prototype name -> leaf-only surface area in m2, from the twig sidecars.

    Prefers ``*_leaf_area_geom.json`` over ``*_leaf_area.json``: the plain
    sidecar reports whole-mesh area with the woody shoot included (XRFF-274),
    which inflates a conifer spray most, since its needles and twig share one
    material and the material-name exclusion cannot fire at all.
    """
    areas: dict[str, float] = {}
    if not twig_dir.is_dir():
        return areas
    for suffix in ("_leaf_area.json", "_leaf_area_geom.json"):
        for f in sorted(twig_dir.glob(f"*/*{suffix}")):
            try:
                data = json.loads(f.read_text())
            except (OSError, ValueError):
                continue
            area = data.get("leaf_area_m2")
            if area:
                areas[_proto_key(f.name[: -len(suffix)])] = float(area)
    return areas


def measure_assembly(
    path: Path, leaf_areas: dict[str, float] | None = None
) -> dict | None:
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.Open(str(path))
    if stage is None:
        return None

    pts = None
    proto_idx = None
    proto_names: list[str] = []
    scales = None
    for prim in stage.Traverse():
        if prim.GetTypeName() == "PointInstancer":
            inst = UsdGeom.PointInstancer(prim)
            arr = inst.GetPositionsAttr().Get()
            if arr:
                pts = np.asarray([(p[0], p[1], p[2]) for p in arr], dtype=float)
            idx = inst.GetProtoIndicesAttr().Get()
            if idx:
                proto_idx = np.asarray(list(idx), dtype=int)
            proto_names = [t.name for t in inst.GetPrototypesRel().GetTargets()]
            sc = inst.GetScalesAttr().Get()
            if sc:
                scales = np.asarray([(v[0], v[1], v[2]) for v in sc], dtype=float)
            break
    if pts is None or len(pts) < 8:
        return None

    # Grove/USD export is Z-up in metres; the stem axis is (x, y) ~ 0.
    z = pts[:, 2]
    height = float(z.max())
    if height <= 0:
        return None

    radial = np.hypot(pts[:, 0], pts[:, 1])
    crown_d = 2.0 * float(np.percentile(radial, 95))

    # Crown base: lowest height band that still holds >=2% of the foliage. A
    # share-based rule ignores the handful of stray low twigs that would drag a
    # simple minimum to the ground.
    order = np.argsort(z)
    zs = z[order]
    idx = int(0.02 * len(zs))
    crown_base = float(zs[idx])

    proj = _hull_area(pts[:, :2])
    # Leaf area is summed per instance from its own prototype rather than from a
    # mean: the prototypes of one species differ by well over an order of
    # magnitude (beech foliage_a is 0.0101 m2, its smallest component 5e-9), so
    # an average would track which prototypes happen to be listed rather than
    # which ones the tree actually placed. Instance scale enters as its square,
    # since leaf area is an area.
    leaf_total = None
    if leaf_areas and proto_idx is not None and proto_names:
        per_proto = np.array(
            [leaf_areas.get(_proto_key(n), 0.0) for n in proto_names],
            dtype=float,
        )
        if per_proto.any():
            n = min(len(proto_idx), len(pts))
            areas = per_proto[np.clip(proto_idx[:n], 0, len(per_proto) - 1)]
            if scales is not None and len(scales) >= n:
                # Uniform-ish scale: use the geometric mean of the axes so a
                # non-uniform squash does not bias the area either way.
                factor = np.abs(scales[:n]).prod(axis=1) ** (2.0 / 3.0)
                areas = areas * factor
            leaf_total = float(areas.sum())
    lai = (leaf_total / proj) if (leaf_total and proj > 0) else None

    return {
        "n_twigs": int(len(pts)),
        "height_m": round(height, 2),
        "crown_diameter_m": round(crown_d, 2),
        "crown_base_m": round(crown_base, 2),
        "crown_ratio": round((height - crown_base) / height, 3),
        "crown_projection_m2": round(proj, 1),
        "crown_d_over_h": round(crown_d / height, 3),
        "leaf_area_m2": round(leaf_total, 2) if leaf_total else None,
        "lai": round(lai, 2) if lai else None,
    }


def render_outline(path: Path, out_png: Path, metrics: dict) -> bool:
    """Draw the measured crown envelope over the foliage points.

    Two panels: front (radius vs height, with the crown-diameter and
    crown-base lines the metrics report) and top (horizontal spread with the
    crown-diameter circle). This exists so the NUMBERS can be checked against
    the shape -- an earlier crown metric read a 1.4 m bole on a tree whose live
    crown visibly started near 17 m, and nothing caught it because nobody drew
    the measurement on the tree.
    """
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from pxr import Usd, UsdGeom

    stage = Usd.Stage.Open(str(path))
    pts = None
    for prim in stage.Traverse():
        if prim.GetTypeName() == "PointInstancer":
            arr = UsdGeom.PointInstancer(prim).GetPositionsAttr().Get()
            if arr:
                pts = np.asarray([(q[0], q[1], q[2]) for q in arr], dtype=float)
            break
    if pts is None or len(pts) < 8:
        return False

    r = np.hypot(pts[:, 0], pts[:, 1])
    cd, cb, h = (
        metrics["crown_diameter_m"],
        metrics["crown_base_m"],
        metrics["height_m"],
    )

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 5), dpi=110)
    ax1.scatter(
        np.where(pts[:, 0] >= 0, r, -r),
        pts[:, 2],
        s=1.5,
        c="#2e7d32",
        alpha=0.25,
        linewidths=0,
    )
    ax1.axhline(cb, color="#c62828", lw=1.2, ls="--", label=f"crown base {cb:.1f} m")
    ax1.axvline(-cd / 2, color="#1565c0", lw=1.0, ls=":")
    ax1.axvline(cd / 2, color="#1565c0", lw=1.0, ls=":", label=f"crown ø {cd:.1f} m")
    ax1.set_xlabel("m")
    ax1.set_ylabel("height (m)")
    ax1.set_title(f"front  |  H {h:.1f} m  ratio {metrics['crown_ratio']:.2f}")
    ax1.legend(fontsize=7, loc="upper right")
    ax1.set_aspect("equal")

    ax2.scatter(pts[:, 0], pts[:, 1], s=1.5, c="#2e7d32", alpha=0.25, linewidths=0)
    ax2.add_patch(
        plt.Circle((0, 0), cd / 2, fill=False, color="#1565c0", ls=":", lw=1.2)
    )
    ax2.set_title(f"top  |  projection {metrics['crown_projection_m2']:.0f} m²")
    ax2.set_xlabel("m")
    ax2.set_aspect("equal")

    fig.tight_layout()
    out_png.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_png, facecolor="white")
    plt.close(fig)
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("forest_dir", nargs="?", default="data/output/forest")
    ap.add_argument("--stage", default="h25m", help="height stage to measure")
    ap.add_argument("--json", type=Path, help="also write raw metrics here")
    ap.add_argument(
        "--twig-dir",
        type=Path,
        default=Path("data/assets/twigs"),
        help="twig asset root holding the *_leaf_area_geom.json sidecars",
    )
    ap.add_argument(
        "--outlines",
        action="store_true",
        help="also render a crown-outline plot beside each assembly",
    )
    args = ap.parse_args()

    root = Path(args.forest_dir)
    leaf_areas = load_leaf_areas(args.twig_dir)
    if not leaf_areas:
        print(f"note: no leaf-area sidecars under {args.twig_dir}; LAI omitted")
    rows: dict[str, dict[int, dict]] = {}
    for f in sorted(root.glob(f"*/r*/*_{args.stage}_*_full_assembly.usd*")):
        m = _NAME.match(f.name)
        if not m:
            continue
        v = measure_assembly(f, leaf_areas)
        if v:
            rows.setdefault(f.parts[-3], {})[int(m.group(2))] = v
            if args.outlines:
                render_outline(
                    f, f.with_name(f.name.split("_full_")[0] + "_crown_outline.png"), v
                )

    radii = sorted({r for d in rows.values() for r in d})
    print(
        f"stage {args.stage}   crown diameter (m) / crown base (m) / "
        "crown ratio / LAI"
    )
    print(f"{'species':<21}" + "".join(f"{f'r{r:02d}':>34}" for r in radii))
    for sp in sorted(rows):
        cells = ""
        for r in radii:
            v = rows[sp].get(r)
            cells += (
                (
                    f"{v['crown_diameter_m']:>10.1f}{v['crown_base_m']:>8.1f}"
                    f"{v['crown_ratio']:>8.2f}"
                    + (f"{v['lai']:>8.2f}" if v.get("lai") else f"{'--':>8}")
                )
                if v
                else f"{'--':>34}"
            )
        print(f"{sp:<21}{cells}")

    if args.json:
        args.json.write_text(json.dumps(rows, indent=2))
        print(f"\nraw metrics -> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
