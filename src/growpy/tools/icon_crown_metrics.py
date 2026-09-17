#!/usr/bin/env python3
"""Measure crown-fill and twig-blob metrics from icon image pairs.

``src/growpy/io/usd/preview.py::generate_icon_image`` writes two PNGs per
tree per view:

- ``{prefix}_icon_{view}.png``       -- branch skeleton only (LineCollection,
  color ``#3b2a1a``, alpha 1.0, white background).
- ``{prefix}_icon_{view}_twigs.png`` -- the SAME matplotlib figure, saved
  again after ``ax.scatter(..., s=4, c="#1f7a1f", alpha=0.5, linewidths=0,
  zorder=3)`` draws twig dots on top.

Because the twig image is a re-save of the identical figure state, the two
PNGs are pixel-identical except where green dots were composited. This
module exploits that directly: it never registers or re-projects anything,
it just diffs the pair and treats every pixel that both (a) changed and
(b) reads as green-dominant hue as twig coverage.

Three properties of the source renderer shape every metric here:

1. **The branch icon is not the full skeleton.** ``generate_icon_image``
   only draws segments whose radius is >= the 25th percentile of all
   segment radii (thin twigs/branch tips are dropped). The drawn black
   structure therefore UNDERSTATES the true crown envelope, and green
   legitimately extends past it -- a raw ``green_px / branch_px`` ratio
   can exceed 1.0 on a perfectly healthy crown. ``crown_fill`` is
   therefore defined against the convex hull of the UNION of branch and
   green pixels, not against the branch hull alone. The branch-only hull
   is still reported (``black_hull_px`` / ``crown_fill_vs_black_hull``)
   as a diagnostic so this bias is visible, not hidden.

2. **Stroke width is scale-dependent, hull area is not.** Linewidth is
   ``radius * 2 * pts_per_meter`` against a fixed 30 m reference height,
   so branch strokes on a 5 m tree are much thinner than on a 15 m tree
   even though both are autoscaled to fill the same square canvas. Any
   metric normalised by raw branch-pixel COUNT is not comparable across
   height stages. Every ratio in this module is normalised by hull AREA
   instead, which is scale-free by construction.

3. **Green is drawn at alpha=0.5, so its rendered colour depends on how
   many dots overlap at a pixel.** One isolated dot over white composites
   pale; a dozen stacked dots composite near-saturated. Two consequences:
   - Green pixels are detected by a hue/channel-relation test (G reads
     meaningfully above both R and B, AND the pixel changed from the
     base image) -- never by exact-match against ``#1f7a1f``.
   - Because the base (branch-only) image gives the exact background
     colour under every twig-covered pixel, the compositing depth k
     (how many alpha=0.5 layers stacked there) is recoverable in closed
     form: ``twig_color = green + (base_color - green) * (1-alpha)^k``.
     This is a cheaper and more informative "lumpiness" signal than
     connected-component counting alone, and is used for
     ``blob_saturation`` below.

Two independent "how lumped is the green" estimates are reported because
they are blind to different things:

- ``blob_largest_cc`` (largest connected component / total green pixels)
  captures spatial EXTENT: many small separate dots vs. one big fused
  mass. It is blind to overlap depth -- a single-pixel-wide chain of
  barely-touching dots scores identically to a densely stacked blob of
  the same footprint.
- ``blob_saturation`` (mean compositing depth, normalised so one dot
  layer maps to ~0 and heavy stacking maps to ~1) captures OVERLAP
  DEPTH at a point. It is blind to spatial arrangement -- widely
  dispersed but individually deep stacks score identically to one
  contiguous deep blob.

``dot_count`` is an area-based lower bound (component area / expected
single-dot area), not a true instance count: once dots overlap, the
image alone cannot recover how many are stacked at a pixel beyond what
the compositing-depth estimate reports, and two dots landing on exactly
the same footprint are indistinguishable from one. It is always reported
alongside ``dot_count_is_lower_bound: true``.

No pass/fail thresholds are hardcoded here (see the "uncalibrated
placeholder" constants below) -- this module reports raw measurements
for a human/lead-agent calibration pass to threshold later.

Usage:
    growpy-icon-metrics <path> [--json OUT.json] [--contact-sheet OUT.png]
                                [--views front,side,top]

``<path>`` accepts a single icon-pair prefix (with or without the
``_icon_<view>[.png]`` suffix), a single icon PNG file, or a directory to
walk recursively for all icon pairs beneath it (a tree dir, a species
dir, or all of ``data/output/forest/``).
"""

from __future__ import annotations

import json
import logging
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

logger = logging.getLogger(__name__)

# --- module constants -------------------------------------------------
# The colour/alpha constants mirror io/usd/preview.py::generate_icon_image
# exactly. The threshold constants below them are NOT calibrated against
# any human-agreed reference set -- they only gate pixel classification
# (what counts as "changed" / "green" / "branch"), not any pass/fail
# verdict. Treat them as uncalibrated placeholders.

GREEN_RGB = (0x1F, 0x7A, 0x1F)  # preview.py scatter color "#1f7a1f"
GREEN_ALPHA = 0.5  # preview.py scatter alpha
WHITE_RGB = (255, 255, 255)  # preview.py icon facecolor

# Uncalibrated placeholders -- classification thresholds only, not
# quality gates.
DIFF_NOISE_FLOOR = 10  # min per-pixel L1 diff (base vs twig) to call "changed"
GREEN_HUE_MARGIN = 6  # min (G - max(R,B)) to call a changed pixel "green"
BRANCH_WHITE_DISTANCE = 15  # min Euclidean distance from white to call "branch"
COMPOSITING_DENOM_FLOOR = 15.0  # min |base-green| per channel to trust that channel

# preview.py generate_icon_image: dpi=150, and the icon-view twig scatter
# uses s=4 (points^2). Used only to convert a connected-component's pixel
# area into an estimated dot count; if that scatter size ever changes in
# preview.py, this constant must move with it. dot_count is a lower bound
# regardless (see module docstring), so drift here degrades precision,
# not correctness of the "lower bound" framing.
ICON_DPI_FALLBACK = 150.0
ICON_TWIG_MARKER_PTS2 = 4.0

VIEWS: tuple[str, ...] = ("front", "side", "top")

_ICON_BASE_RE = re.compile(r"^(?P<prefix>.+)_icon_(?P<view>front|side|top)\.png$")
_ICON_ANY_RE = re.compile(
    r"^(?P<prefix>.+)_icon_(?P<view>front|side|top)(?:_twigs)?\.png$"
)


@dataclass
class ViewMetrics:
    """Per-view crown-fill / twig-blob metrics. See module docstring."""

    view: str
    image_path: str
    base_image_path: str
    width_px: int
    height_px: int
    green_px: int
    branch_px: int
    hull_px: int
    black_hull_px: int
    crown_fill: float
    crown_fill_vs_black_hull: float
    blob_largest_cc: float
    blob_saturation: float
    connected_components: int
    dot_count: int
    dot_count_is_lower_bound: bool = True

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class IconPairAnalysis:
    """A ``ViewMetrics`` plus the raw arrays used to compute it.

    The arrays are kept around only for contact-sheet rendering; they are
    never serialised (use ``.metrics.to_dict()`` for that).
    """

    metrics: ViewMetrics
    base_rgb: np.ndarray
    twig_rgb: np.ndarray
    green_mask: np.ndarray
    branch_mask: np.ndarray


def _load_image_rgb(path: Path) -> tuple[np.ndarray, float]:
    """Load a PNG as an (H, W, 3) uint8 array, plus its DPI (or fallback)."""
    with Image.open(path) as img:
        dpi_info = img.info.get("dpi")
        dpi = float(dpi_info[0]) if dpi_info else ICON_DPI_FALLBACK
        rgb = np.asarray(img.convert("RGB"), dtype=np.uint8)
    return rgb, dpi


def classify_masks(
    base_rgb: np.ndarray, twig_rgb: np.ndarray
) -> tuple[np.ndarray, np.ndarray]:
    """Return (green_mask, branch_mask) for an icon pair.

    ``green_mask``: pixels that changed from base->twig AND read as
    green-dominant hue in the twig image (never an exact-colour match --
    see module docstring point 3).

    ``branch_mask``: pixels in the BASE (branch-only) image that are not
    (approximately) the white background.
    """
    diff = np.abs(twig_rgb.astype(np.int16) - base_rgb.astype(np.int16))
    changed = diff.sum(axis=-1) > DIFF_NOISE_FLOOR

    r = twig_rgb[..., 0].astype(np.int16)
    g = twig_rgb[..., 1].astype(np.int16)
    b = twig_rgb[..., 2].astype(np.int16)
    green_hue = (g - np.maximum(r, b)) > GREEN_HUE_MARGIN
    green_mask = changed & green_hue

    white = np.array(WHITE_RGB, dtype=np.float64)
    dist_from_white = np.sqrt(
        np.sum((base_rgb.astype(np.float64) - white) ** 2, axis=-1)
    )
    branch_mask = dist_from_white > BRANCH_WHITE_DISTANCE

    return green_mask, branch_mask


def _convex_hull_px_count(mask: np.ndarray) -> int:
    """Pixel count inside the convex hull of the True cells of ``mask``."""
    ys, xs = np.nonzero(mask)
    n = len(xs)
    if n == 0:
        return 0
    if n <= 2:
        return n

    points = np.stack([xs, ys], axis=1)
    try:
        from scipy.spatial import ConvexHull

        hull = ConvexHull(points)
        hull_pts = [(float(points[v][0]), float(points[v][1])) for v in hull.vertices]
    except Exception:
        # Degenerate (e.g. collinear) point set -- bounding box is a
        # conservative area proxy.
        return int((xs.max() - xs.min() + 1) * (ys.max() - ys.min() + 1))

    h, w = mask.shape
    hull_img = Image.new("L", (w, h), 0)
    ImageDraw.Draw(hull_img).polygon(hull_pts, fill=255)
    return int(np.count_nonzero(np.asarray(hull_img)))


def _connected_components(
    mask: np.ndarray,
) -> tuple[np.ndarray, int, np.ndarray]:
    """8-connected component labeling. Returns (labeled, num, sizes)."""
    from scipy import ndimage

    labeled, num = ndimage.label(mask, structure=np.ones((3, 3), dtype=int))
    if num == 0:
        return labeled, 0, np.array([])
    sizes = ndimage.sum(mask, labeled, index=np.arange(1, num + 1))
    return labeled, num, sizes


def _compositing_depth(
    base_rgb: np.ndarray, twig_rgb: np.ndarray, green_mask: np.ndarray
) -> np.ndarray:
    """Per-green-pixel compositing-depth score in [0, 1].

    Solves ``twig = green + (base - green) * (1-alpha)^k`` for
    ``s = (1-alpha)^k`` per channel (using only channels where the base
    color is far enough from green to trust the ratio), takes the
    per-pixel median across valid channels, then maps s -> depth so that
    a single alpha=0.5 layer (s=0.5) reads as 0 and heavy stacking
    (s->0) reads towards 1.
    """
    if not np.any(green_mask):
        return np.array([])

    green = np.array(GREEN_RGB, dtype=np.float64)
    base = base_rgb.astype(np.float64)
    twig = twig_rgb.astype(np.float64)

    denom = base - green
    numer = twig - green
    valid = np.abs(denom) > COMPOSITING_DENOM_FLOOR

    with np.errstate(divide="ignore", invalid="ignore"):
        safe_denom = np.where(denom == 0, np.nan, denom)
        s = np.where(valid, numer / safe_denom, np.nan)

    s_median = np.nanmedian(s, axis=-1)
    no_valid_channel = ~np.any(valid, axis=-1)
    # No channel trustworthy at this pixel (base color itself too close
    # to green) -- fall back to assuming a single alpha layer.
    s_median = np.where(no_valid_channel, 1.0 - GREEN_ALPHA, s_median)
    s_median = np.nan_to_num(s_median, nan=1.0 - GREEN_ALPHA)
    s_median = np.clip(s_median, 1e-3, 1.0)

    depth = np.clip(1.0 - 2.0 * s_median, 0.0, 1.0)
    return depth[green_mask]


def _estimate_dot_count(
    component_sizes: np.ndarray, single_dot_area_px: float
) -> int:
    """Area-based lower-bound dot count. See module docstring."""
    if component_sizes.size == 0:
        return 0
    counts = np.maximum(1, np.round(component_sizes / max(single_dot_area_px, 1e-6)))
    return int(counts.sum())


def analyze_icon_pair(base_path: Path, twig_path: Path, view: str) -> IconPairAnalysis:
    """Compute crown-fill / blob metrics for one branch/twig icon pair."""
    base_rgb, _base_dpi = _load_image_rgb(base_path)
    twig_rgb, twig_dpi = _load_image_rgb(twig_path)
    if base_rgb.shape != twig_rgb.shape:
        raise ValueError(
            f"Icon pair size mismatch: {base_path} {base_rgb.shape} vs "
            f"{twig_path} {twig_rgb.shape}"
        )
    h, w = base_rgb.shape[:2]

    green_mask, branch_mask = classify_masks(base_rgb, twig_rgb)
    union_mask = green_mask | branch_mask

    green_px = int(np.count_nonzero(green_mask))
    branch_px = int(np.count_nonzero(branch_mask))
    hull_px = _convex_hull_px_count(union_mask)
    black_hull_px = _convex_hull_px_count(branch_mask)

    crown_fill = (green_px / hull_px) if hull_px else 0.0
    crown_fill_vs_black_hull = (green_px / black_hull_px) if black_hull_px else 0.0

    _labeled, num_cc, sizes = _connected_components(green_mask)
    blob_largest_cc = (float(sizes.max()) / green_px) if green_px and num_cc else 0.0

    depth_vals = _compositing_depth(base_rgb, twig_rgb, green_mask)
    blob_saturation = float(np.mean(depth_vals)) if depth_vals.size else 0.0

    single_dot_area_px = ICON_TWIG_MARKER_PTS2 * (twig_dpi / 72.0) ** 2
    dot_count = _estimate_dot_count(sizes, single_dot_area_px)

    metrics = ViewMetrics(
        view=view,
        image_path=str(twig_path),
        base_image_path=str(base_path),
        width_px=w,
        height_px=h,
        green_px=green_px,
        branch_px=branch_px,
        hull_px=hull_px,
        black_hull_px=black_hull_px,
        crown_fill=crown_fill,
        crown_fill_vs_black_hull=crown_fill_vs_black_hull,
        blob_largest_cc=blob_largest_cc,
        blob_saturation=blob_saturation,
        connected_components=int(num_cc),
        dot_count=dot_count,
    )
    return IconPairAnalysis(
        metrics=metrics,
        base_rgb=base_rgb,
        twig_rgb=twig_rgb,
        green_mask=green_mask,
        branch_mask=branch_mask,
    )


def analyze_tree(
    tree_dir: Path, prefix: str, views: tuple[str, ...] = VIEWS
) -> tuple[dict, dict[str, IconPairAnalysis]]:
    """Analyze all available icon-pair views for one tree/prefix.

    Returns (json-serialisable result dict, {view: IconPairAnalysis}).
    A crown can be full from the front and hollow from the top, so the
    per-view breakdown is always kept alongside the plain-mean aggregate.
    """
    view_records: dict[str, dict] = {}
    analyses: dict[str, IconPairAnalysis] = {}

    for view in views:
        base_path = tree_dir / f"{prefix}_icon_{view}.png"
        twig_path = tree_dir / f"{prefix}_icon_{view}_twigs.png"
        if not base_path.exists() or not twig_path.exists():
            logger.warning(
                "Missing icon pair for view=%s prefix=%s in %s", view, prefix, tree_dir
            )
            continue
        analysis = analyze_icon_pair(base_path, twig_path, view)
        view_records[view] = analysis.metrics.to_dict()
        analyses[view] = analysis

    aggregate: dict = {}
    if view_records:
        for key in (
            "crown_fill",
            "crown_fill_vs_black_hull",
            "blob_largest_cc",
            "blob_saturation",
            "dot_count",
        ):
            vals = [v[key] for v in view_records.values()]
            aggregate[f"{key}_mean"] = float(np.mean(vals))
    aggregate["dot_count_is_lower_bound"] = True

    result = {
        "prefix": prefix,
        "tree_dir": str(tree_dir),
        "views": view_records,
        "aggregate": aggregate,
    }
    return result, analyses


def make_contact_sheet(
    analyses: dict[str, IconPairAnalysis], out_path: Path, prefix: str
) -> None:
    """Write a branch | branch+twigs | detected-overlay contact sheet.

    One row per available view; the overlay panel highlights every pixel
    this module classified as twig-covered so a human can sanity-check
    the classifier against what actually rendered.
    """
    import matplotlib.pyplot as plt

    views = list(analyses.keys())
    if not views:
        logger.warning("No views to render for contact sheet %s", out_path)
        return

    n = len(views)
    fig, axes = plt.subplots(n, 3, figsize=(9, 3.2 * n), squeeze=False)

    for row, view in enumerate(views):
        a = analyses[view]
        m = a.metrics

        axes[row][0].imshow(a.base_rgb)
        axes[row][0].set_title(f"{view}: branch", fontsize=9)
        axes[row][0].axis("off")

        axes[row][1].imshow(a.twig_rgb)
        axes[row][1].set_title(f"{view}: branch+twigs", fontsize=9)
        axes[row][1].axis("off")

        overlay = a.base_rgb.copy()
        overlay[a.green_mask] = [230, 30, 200]  # magenta = detected twig pixel
        axes[row][2].imshow(overlay)
        axes[row][2].set_title(
            f"{view}: detected (magenta)\n"
            f"fill={m.crown_fill:.2f} vs_black={m.crown_fill_vs_black_hull:.2f}\n"
            f"blob_cc={m.blob_largest_cc:.2f} sat={m.blob_saturation:.2f} "
            f"dots>={m.dot_count}",
            fontsize=8,
        )
        axes[row][2].axis("off")

    fig.suptitle(prefix, fontsize=10)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, facecolor="white")
    plt.close(fig)
    logger.info("Contact sheet: %s", out_path)


def find_icon_prefixes(root: Path) -> list[tuple[Path, str]]:
    """Recursively find (tree_dir, prefix) pairs for every icon set under root."""
    found: dict[tuple[Path, str], None] = {}
    for p in root.rglob("*_icon_*.png"):
        if p.name.endswith("_twigs.png"):
            continue
        m = _ICON_BASE_RE.match(p.name)
        if not m:
            continue
        found[(p.parent, m.group("prefix"))] = None
    return sorted(found.keys())


def resolve_targets(path: Path, views: tuple[str, ...]) -> list[tuple[Path, str]]:
    """Resolve a CLI path argument to a list of (tree_dir, prefix) pairs.

    Accepts: a directory (walked recursively), a single icon PNG file
    (base or twig variant), or a bare icon-pair prefix (no such file
    itself, but ``{prefix}_icon_{view}.png`` exists alongside it).
    """
    if path.is_dir():
        return find_icon_prefixes(path)

    if path.is_file():
        m = _ICON_ANY_RE.match(path.name)
        if not m:
            raise ValueError(f"Not an icon PNG file: {path}")
        return [(path.parent, m.group("prefix"))]

    parent = path.parent if str(path.parent) else Path(".")
    prefix = path.name
    for v in views:
        if (parent / f"{prefix}_icon_{v}.png").exists():
            return [(parent, prefix)]

    raise FileNotFoundError(f"No icon files found for path/prefix: {path}")


def main(argv: list[str] | None = None) -> int:
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    parser = argparse.ArgumentParser(
        description="Measure crown-fill and twig-blob metrics from icon image pairs."
    )
    parser.add_argument(
        "path",
        type=Path,
        help="Icon-pair prefix, icon PNG file, tree dir, or directory to "
        "walk recursively.",
    )
    parser.add_argument(
        "--json", type=Path, default=None, help="Write JSON record(s) to this file."
    )
    parser.add_argument(
        "--contact-sheet",
        type=Path,
        default=None,
        help="Write a labelled branch|twigs|overlay contact sheet PNG. In "
        "single-tree mode this is the output file path; in directory-walk "
        "mode this is treated as an output DIRECTORY, one "
        "'{prefix}_contact_sheet.png' per tree.",
    )
    parser.add_argument(
        "--views",
        type=str,
        default="front,side,top",
        help="Comma-separated views to analyze (default: front,side,top).",
    )
    args = parser.parse_args(argv)

    views = tuple(v.strip() for v in args.views.split(",") if v.strip())

    try:
        targets = resolve_targets(args.path, views)
    except (FileNotFoundError, ValueError) as e:
        print(f"Error: {e}")
        return 1

    if not targets:
        print(f"No icon pairs found under {args.path}")
        return 1

    batch_mode = len(targets) > 1
    records = []

    for tree_dir, prefix in targets:
        result, analyses = analyze_tree(tree_dir, prefix, views)
        records.append(result)

        print(f"\n{prefix}")
        for view, vm in result["views"].items():
            print(
                f"  {view}: crown_fill={vm['crown_fill']:.3f} "
                f"(vs_black_hull={vm['crown_fill_vs_black_hull']:.3f}) "
                f"blob_largest_cc={vm['blob_largest_cc']:.3f} "
                f"blob_saturation={vm['blob_saturation']:.3f} "
                f"dot_count>={vm['dot_count']}"
            )
        agg = result["aggregate"]
        if agg:
            print(
                "  aggregate: "
                f"crown_fill={agg.get('crown_fill_mean', 0):.3f} "
                f"blob_largest_cc={agg.get('blob_largest_cc_mean', 0):.3f} "
                f"blob_saturation={agg.get('blob_saturation_mean', 0):.3f}"
            )

        if args.contact_sheet is not None and analyses:
            out_path = (
                args.contact_sheet / f"{prefix}_contact_sheet.png"
                if batch_mode
                else args.contact_sheet
            )
            make_contact_sheet(analyses, out_path, prefix)
            print(f"  contact sheet: {out_path}")

    if args.json is not None:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        payload: dict = (
            {"trees": records, "count": len(records)} if batch_mode else records[0]
        )
        args.json.write_text(json.dumps(payload, indent=2))
        print(f"\nWrote JSON: {args.json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
