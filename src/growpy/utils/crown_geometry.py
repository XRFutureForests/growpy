"""Crown bounds -- projected hull area and vertical extent -- from Grove geometry.

XRFF-276: the per-tree twig-density resolver (XRFF-273) needs to hit a
*visual* crown-fill target::

    crown_fill ~= instances * prototype_silhouette_area / crown_hull_area

``instances`` is what the resolver solves for; another builder measures
``prototype_silhouette_area``. This module supplies ``crown_hull_area`` --
nothing else in growpy computes crown bounds today.

Units
-----
Every length returned by this module is in **metres** and every area is
in **square metres (m^2)** -- the world-space units a Grove skeleton's
``points`` are already expressed in. This is the OPPOSITE unit system
from ``growpy.tools.icon_crown_metrics.ViewMetrics``, whose
``hull_px``/``branch_px``/``green_px`` are raster PIXEL counts on a
``size_px``-square icon canvas. See "Relation to the icon metric" below
for how the two connect.

Axis convention
----------------
``view``/``axis_h``/``axis_v`` reuse
``growpy.io.usd.preview._VIEW_AXES`` verbatim (front = X vs Z, side = Y
vs Z, top = X vs Y) so results project onto the same planes
``icon_crown_metrics`` measures ``crown_fill`` against.

Relation to the icon metric
----------------------------
``icon_crown_metrics.analyze_icon_pair`` measures::

    crown_fill = green_px / hull_px

where ``hull_px`` is the convex hull, in RASTER PIXELS, of the union of
branch pixels and twig ("green") pixels on a 512 px icon canvas. That
canvas is built by ``generate_icon_image`` via an ISOTROPIC (equal x/y
scale, no shear, no rotation) affine map from world coordinates for that
one tree+view: autoscale to the branch geometry's bounding box, then pad
to a square with a 5% margin. An isotropic affine map preserves convex
hull membership, so the pixel-space hull's vertices are the image, under
that one map, of the *same point set's* hull in world space -- the two
hulls are the same shape, differing only by one scalar
(``pixels-per-metre``) squared. Concretely::

    hull_px ~= hull_area_m2 * (pixels_per_metre_for_that_icon) ** 2

This module computes the world-unit side of that equivalence, from the
skeleton's own point cloud, so a caller with an independent measurement
of ``pixels_per_metre`` (or who only needs the *ratio*
``instances / crown_hull_area``, which is unit-scale-invariant against a
per-tree constant) can relate the two directly.

Two definitional differences from the icon metric to keep in mind:

1. **Filtering.** ``generate_icon_image`` drops every skeleton segment
   below the 25th-percentile radius before drawing (thin branch tips
   are invisible in the icon). This module deliberately does NOT apply
   that filter -- it uses the full, unfiltered point cloud -- because
   filtering by a drawn image's bias (trap noted in the XRFF-276 brief)
   would make ``crown_hull_area`` inherit an UNDERSTATEMENT of the true
   crown envelope. So ``hull_area_m2`` here is expected to run larger
   than the pixel-space ``black_hull_px`` (the icon's branch-only hull)
   would predict, and is the more honest quantity for a resolver to
   divide by.
2. **What's unioned.** The icon's ``hull_px`` is the hull of
   (branch pixels UNION twig/green pixels). This module's hull is of
   BRANCH/skeleton geometry alone -- twig instance placement is another
   builder's concern (``prototype_silhouette_area`` / instance
   placement) and out of this module's scope. In practice twigs attach
   at or near branch tips, so the branch-only hull should track the
   branch+twig union hull closely; it can only run SMALLER in the
   (expected to be rare) case where twig placement extends past the
   outermost modelled branch node.

See ``crown_geometry_validation.py`` (scratchpad, not part of this
module) for the empirical correlation check against measured
``crown_fill`` values on real exported trees.

Convex vs. concave hull -- forestry convention and validation result
----------------------------------------------------------------------
The convex hull above was validated against nine measured trees (three
height stages each of silver_fir, european_beech, common_ash) and
correlates with measured ``crown_fill`` at Spearman +1.000 for
silver_fir but -1.000 for european_beech -- a perfect INVERSION for the
broadleaf species. Trimming the outermost 1-20% of points does not fix
it. The cause: broadleaves put out long, sparsely-foliaged leader shoots
early, and a convex hull is inflated by a handful of such outlying
shoots, overstating available crown space at young stages.

This is not just an artefact of this dataset -- it matches published
forest-mensuration practice:

- **The traditional field method never computes a global convex hull.**
  Crown projection area is conventionally measured as a polygon through
  crown-edge points found along a small, fixed number of compass
  bearings from the stem (4 or 8), which by construction can be
  concave/star-shaped around the stem. Fleck et al. (2011, "Comparison
  of conventional eight-point crown projections with LiDAR-based virtual
  crown projections in a temperate old-growth forest", Annals of Forest
  Science 68(7):1173-1185, doi:10.1007/s13595-011-0067-1) compared this
  eight-point field method against a LiDAR "virtual" projection in an
  11-species old-growth stand and found deviations of +10.2% (variable
  angles) to -17.1% (fixed angles), worst for irregular, asymmetric
  crowns -- exactly the shape broadleaves produce.
- **Point-cloud studies that DO use a hull explicitly warn convex
  overestimates.** Yan et al. (2019, "A Concave Hull Methodology for
  Calculating the Crown Volume of Individual Trees Based on Vehicle-Borne
  LiDAR Data", Remote Sensing 11(6):623, doi:10.3390/rs11060623) show
  that a convex hull bridges the real gaps/holes in a crown point cloud
  and systematically overestimates area/volume relative to manual and
  concave-hull/alpha-shape measurement; their concave-hull-by-slices
  method produced the smallest (least biased) volume of six methods
  compared.
- Zhang, Bi, Jin & McLean (2024, "A new method of calculating crown
  projection area and its comparative accuracy with conventional
  calculations for asymmetric tree crowns", Journal of Forestry Research
  35, doi:10.1007/s11676-024-01719-5) and Owen & Lines (2024, "Common
  field measures and geometric assumptions of tree shape produce
  consistently biased estimates of tree and canopy structure in mixed
  Mediterranean forests", Ecological Indicators 165:112219,
  doi:10.1016/j.ecolind.2024.112219) both document the same direction of
  bias for asymmetric/irregular crowns under convex-hull-like
  assumptions.

The literature's own convention is closer to a concave hull than a
convex one, particularly for irregular broadleaf crowns -- so this
module computes BOTH (the convex hull is kept as the validated
comparison baseline, per XRFF-276's original result above) and defaults
callers who need one answer (e.g. ``compute_lai``) to the **concave**
hull, consistent with the project owner's instruction to prefer concave
hulls for crown/LAI area unless forestry practice says otherwise.

**Empirical result: the concave hull does NOT fix the broadleaf
inversion.** Re-running the same nine-tree Spearman check with
``instances / concave_hull_area_m2("top")`` in place of the convex
ratio gives (see ``crown_geometry_validation.py``, scratchpad):
european_beech stays at exactly -1.000 and common_ash at -0.500 --
IDENTICAL to their convex-hull values -- across every alpha scale tested
(k = 1, 5, 10, 25, 50, 100 nearest-neighbours, multiplier fixed at 3.0).
Only silver_fir's own correlation is alpha-sensitive: it degrades from
convex's +1.000 to -0.500 at k=1 (an artefact of that k being the wrong
characteristic scale for this module's actual dense-point-cloud input,
not a hull-shape effect -- see ``_nn_median_spacing``), then recovers to
+1.000 for every k>=5. So swapping convex for concave hull area, by
itself, does not resolve the broadleaf mismatch this module was written
to fix -- the inversion appears NOT to be a hull-convexity artefact.
Plausible remaining explanations (untested here, out of this module's
scope): the ``instances`` numerator itself may not be the right
predictor once foliage-driven visual density and skeleton-derived area
grow at different rates across height stages, or the dense
skinned-mesh-vertex point cloud (a proxy for the unavailable Grove
``skeleton.points`` -- see below) may not represent branch/crown
structure faithfully enough for area-based ratios of any hull shape to
track ``crown_fill``. n=3 per species is also very low power (see
module docstring's honest caveat on this elsewhere) -- but note the
INSENSITIVITY of the beech/ash result to hull shape and alpha choice
argues this specific finding is not merely a small-n coincidence in the
way a lone Spearman +-1.0 would be.

This module still keeps the concave hull as the default for new callers
(the forestry-literature case for it stands on its own, independent of
whether it happens to fix this particular correlation check), but a
caller relying on XRFF-276's crown_fill-matching motivation specifically
should not assume switching hull shape alone resolves it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np

# Single source of truth for the view->axis-pair convention, shared with
# icon_crown_metrics (via generate_icon_image, which draws the icons that
# metric measures). Importing this dict costs nothing: preview.py only
# imports `logging` and `pathlib.Path` at module scope -- matplotlib/pxr
# stay import-lazy inside its functions -- so this import does not pull in
# bpy, pxr, or matplotlib.
from ..io.usd.preview import _VIEW_AXES

VIEWS: tuple[str, ...] = tuple(_VIEW_AXES.keys())  # ("front", "side", "top")

# --- crown-base heuristic defaults -------------------------------------
# Uncalibrated but documented: no ground-truth crown-base dataset exists
# to fit these against, so they are chosen to be conservative (favour a
# HIGHER crown base -- i.e. requiring persistent lateral spread -- over a
# false positive from one stray low branch stub).

# Bottom fraction of the tree's height range used to estimate the trunk's
# vertical axis (its horizontal centroid).
_DEFAULT_TRUNK_HEIGHT_FRAC = 0.1
# A point counts as "crown" once its radial spread from the trunk axis
# exceeds this fraction of the tree's overall max radial spread.
_DEFAULT_CROWN_BASE_RADIUS_FRAC = 0.15
# The crown base is the lowest above-threshold point from which at least
# this fraction of the next local window of points (see
# _estimate_crown_base_height) are also above threshold -- guards against
# a single low branch spike being mistaken for the crown base.
_DEFAULT_CROWN_BASE_PERSISTENCE_FRAC = 0.6
# Translated into a point-count window size (n_points // n_bins, floored
# at 10) rather than used as a literal height-bin count -- see
# _estimate_crown_base_height for why bins were dropped in favour of a
# point-order window.
_DEFAULT_HEIGHT_BINS = 40

# --- concave-hull (alpha-shape) defaults --------------------------------
# See module docstring "Convex vs. concave hull" section for the forestry
# literature backing this default and the empirical convex-hull inversion
# it responds to.
#
# alpha_radius is a circumradius threshold in the SAME world units as the
# input points (metres): a Delaunay triangle is kept (counted toward hull
# area) only if its circumscribed-circle radius is <= alpha_radius, i.e.
# only if it does not have to "reach across" a gap wider than that radius
# to connect its three vertices. alpha_radius -> infinity keeps every
# Delaunay triangle, which is exactly the convex hull's filled interior
# (this is the standard Edelsbrunner alpha-shape family, parameterised by
# a radius rather than the reciprocal "alpha value" some libraries use).
#
# No single alpha_radius is meaningful across trees of very different
# size and point density, so the default is DERIVED per point cloud: a
# multiple of that point cloud's own median k-th-nearest-neighbour
# spacing (see ``_nn_median_spacing``; k defaults to
# _DEFAULT_ALPHA_SPACING_K, not 1 -- see that function's docstring for
# why the naive 1st-nearest-neighbour distance is the wrong scale for
# the dense skinned-mesh-vertex point clouds this module actually
# receives today). Small multiplier -> only very tight, locally-dense
# triangles survive (risk: fragments into disconnected islands, losing
# real crown area). Large multiplier -> nearly every triangle survives
# (degenerates toward the convex hull, reintroducing the inversion this
# feature exists to fix).
#
# Empirical sweep (crown_geometry_validation.py, scratchpad, XRFF-276
# nine-tree dataset, multiplier fixed at 3.0, k swept 1/5/10/25/50/100):
# concave hull area rises smoothly from ~1-6% of the convex hull area at
# k=1 to a stable ~75-90% plateau by k>=25, with k=10 already inside
# that plateau's shoulder. This is a REASONABLE hull (neither collapsed
# nor indistinguishable from convex), not a "correlation was best here"
# fit -- the headline Spearman result below is INSENSITIVE to the choice
# of k or multiplier across this entire tested range (see next constant's
# comment).
_DEFAULT_ALPHA_SPACING_K = 10
_DEFAULT_ALPHA_NEIGHBOR_MULTIPLIER = 3.0


@dataclass(frozen=True)
class ViewCrownHull:
    """Convex AND concave (alpha-shape) hull of the crown point cloud, one
    view plane at a time.

    ``view``/``axis_h``/``axis_v`` match ``_VIEW_AXES`` exactly (see
    module docstring). ``hull_area_m2`` is the CONVEX hull AREA in square
    metres of the point cloud projected onto (axis_h, axis_v) -- e.g. for
    ``view="top"`` this is the crown's footprint area looking straight
    down. It is kept as the validated XRFF-276 comparison baseline (see
    module docstring "Convex vs. concave hull" section) -- prefer
    ``concave_hull_area_m2`` for new call sites unless you specifically
    need the convex baseline.

    ``concave_hull_area_m2`` is the alpha-shape hull area over the same
    projected points -- see ``_alpha_shape_area_2d`` and the module
    docstring for why this is the literature-backed default. It is always
    <= ``hull_area_m2`` (alpha-shapes only remove Delaunay triangles from
    the convex hull's triangulation, never add area). ``alpha_radius_m``
    records the actual per-view radius used (see
    ``_DEFAULT_ALPHA_NEIGHBOR_MULTIPLIER``), since it is derived from each
    view's own point spacing and therefore differs by view/tree/stage.
    """

    view: str
    axis_h: int
    axis_v: int
    hull_area_m2: float
    n_points: int
    is_degenerate: bool  # <3 non-collinear points; hull_area_m2 is a bbox fallback
    concave_hull_area_m2: float
    alpha_radius_m: float
    concave_is_degenerate: bool  # alpha shape collapsed to zero triangles


@dataclass(frozen=True)
class CrownGeometry:
    """Crown bounds derived from a Grove skeleton's point cloud.

    All lengths are metres, all areas square metres (m^2) -- see module
    docstring. ``views`` has one entry per requested view (default:
    front, side, top).
    """

    crown_base_height_m: float
    crown_tip_height_m: float
    crown_vertical_extent_m: float
    views: dict[str, ViewCrownHull]

    def hull_area_m2(self, view: str) -> float:
        """Convenience accessor for the CONVEX hull:
        ``geometry.hull_area_m2("top")``. See ``concave_hull_area_m2`` for
        the literature-backed default; this convex accessor is kept as
        the validated XRFF-276 comparison baseline."""
        return self.views[view].hull_area_m2

    def concave_hull_area_m2(self, view: str) -> float:
        """Convenience accessor: ``geometry.concave_hull_area_m2("top")``."""
        return self.views[view].concave_hull_area_m2


def _points_array(skeleton_or_points: object) -> np.ndarray:
    """Extract an (N, 3) float array from a skeleton-like object or raw data.

    Accepts anything with a ``.points`` attribute (Grove's skeleton duck
    type, as consumed directly by ``io/usd/preview.py`` without importing
    a concrete Skeleton class) or a raw (N, 3) array/sequence of
    (x, y, z) points.
    """
    points = getattr(skeleton_or_points, "points", skeleton_or_points)
    arr = np.asarray(points, dtype=float)
    if arr.ndim != 2 or arr.shape[1] != 3:
        raise ValueError(
            f"Expected an (N, 3) point array (or an object with a `.points` "
            f"attribute shaped that way), got array of shape {arr.shape}"
        )
    return arr


def _hull_area_2d(xy: np.ndarray) -> tuple[float, bool]:
    """Convex hull area of a 2D point set. Returns (area_m2, is_degenerate).

    Mirrors ``icon_crown_metrics._convex_hull_px_count``'s degenerate-case
    handling (too few / collinear points -> bounding-box fallback), but
    computes a continuous world-unit AREA via ``scipy.spatial.ConvexHull``
    (its ``.volume`` attribute is the hull's area for 2D input) instead of
    rasterising and counting pixels.
    """
    n = xy.shape[0]
    if n <= 2:
        return 0.0, True

    try:
        from scipy.spatial import ConvexHull

        hull = ConvexHull(xy)
        return float(hull.volume), False
    except Exception:
        # Degenerate (e.g. collinear) point set -- bounding-box area is a
        # conservative fallback, consistent with the icon metric's own
        # degenerate-case handling.
        xlo, xhi = float(xy[:, 0].min()), float(xy[:, 0].max())
        ylo, yhi = float(xy[:, 1].min()), float(xy[:, 1].max())
        return float((xhi - xlo) * (yhi - ylo)), True


def _nn_median_spacing(xy: np.ndarray, k: int = _DEFAULT_ALPHA_SPACING_K) -> float:
    """Median distance to each point's k-th nearest neighbour, in a 2D
    point set.

    Used as the characteristic length scale for deriving a per-point-cloud
    alpha radius (see ``_DEFAULT_ALPHA_NEIGHBOR_MULTIPLIER``): a tree with
    a dense point cloud should use a small alpha radius, a sparse one a
    large radius, so that the SAME relative gap size is treated as "real"
    space (excluded) rather than "sampling gap" (included) regardless of
    how densely the source geometry happened to be tessellated.

    ``k`` defaults to ``_DEFAULT_ALPHA_SPACING_K``, NOT 1: the 1st-nearest-
    neighbour distance was the original implementation here, but the
    XRFF-276 nine-tree validation (see module docstring) showed it is the
    WRONG characteristic scale for the dense skinned-mesh-vertex point
    clouds this module is actually fed today. Those clouds are a full
    cylindrical surface tessellation of every branch segment -- 37k to
    4.2M vertices per tree -- so the 1st-nearest-neighbour distance
    mostly measures CIRCUMFERENTIAL tessellation resolution around one
    branch tube, not the gap between separate branches. At k=1, the
    resulting alpha radius was so small it fragmented even a
    well-behaved conifer's hull (silver_fir's convex-hull Spearman
    correlation of +1.000 degraded to -0.500). Averaging over a wider
    neighbourhood (k=5 through k=100 all tested) recovers a scale close
    to genuine branch-to-branch spacing and restores that correlation;
    k=10 was chosen as a value already inside the stable plateau without
    requiring an unreasonably large sample of neighbours for smaller
    point clouds (e.g. a real, much sparser Grove ``skeleton.points``).
    """
    from scipy.spatial import cKDTree

    tree = cKDTree(xy)
    # index 0 of each row is the point itself (distance 0); index k is
    # its actual k-th nearest neighbour. Guard against point clouds
    # smaller than k+1.
    k_eff = max(1, min(k, xy.shape[0] - 1))
    dists, _ = tree.query(xy, k=k_eff + 1)
    if dists.ndim == 1:  # only one point in the cloud
        return 0.0
    nn = dists[:, k_eff]
    return float(np.median(nn))


def _alpha_shape_area_2d(
    xy: np.ndarray,
    alpha_radius: float | None = None,
    alpha_multiplier: float = _DEFAULT_ALPHA_NEIGHBOR_MULTIPLIER,
) -> tuple[float, bool, float]:
    """Alpha-shape (concave hull) area of a 2D point set.

    Returns ``(area_m2, is_degenerate, alpha_radius_used)``.

    Method: Delaunay-triangulate the point set, keep only triangles whose
    circumradius is <= ``alpha_radius``, and sum their areas. Because a
    Delaunay triangulation exactly tiles the convex hull with
    non-overlapping triangles, "sum of kept triangle areas" IS the
    alpha-shape's area -- no separate boundary-tracing step is needed
    (and none is exposed here; callers wanting the boundary polygon, e.g.
    for plotting, would need a different helper).

    ``alpha_radius``: explicit override, in the same units as ``xy``
    (metres). If ``None`` (the default), it is derived from THIS point
    cloud's own median nearest-neighbour spacing times
    ``alpha_multiplier`` -- see ``_DEFAULT_ALPHA_NEIGHBOR_MULTIPLIER`` for
    why a fixed absolute radius would not generalise across tree
    size/density.

    Degenerate cases (mirroring ``_hull_area_2d``'s fallback posture):
    fewer than 4 points, a failed/collinear triangulation, or an alpha
    radius small enough to reject every triangle all report
    ``is_degenerate=True`` with ``area_m2=0.0`` -- deliberately NOT a
    bounding-box fallback here (unlike the convex case), because a
    concave hull degenerating to "the bounding box" would silently
    reintroduce the same overestimation this function exists to avoid.
    """
    n = xy.shape[0]
    if n < 4:
        # Can't form a single non-degenerate 2D Delaunay triangle's worth
        # of interior structure below this; convex area is the honest
        # answer for a 3-point (or fewer) triangle/point/line -- there is
        # no "inside vs. outside" distinction left to make concave.
        area, degenerate = _hull_area_2d(xy)
        return area, degenerate, float(alpha_radius or 0.0)

    if alpha_radius is None:
        spacing = _nn_median_spacing(xy)
        if spacing <= 1e-12:
            # Degenerate/duplicated points -- fall back to convex/bbox
            # behaviour rather than dividing by (near) zero.
            area, degenerate = _hull_area_2d(xy)
            return area, degenerate, 0.0
        alpha_radius = alpha_multiplier * spacing

    try:
        from scipy.spatial import Delaunay

        tri = Delaunay(xy)
    except Exception:
        area, degenerate = _hull_area_2d(xy)
        return area, degenerate, float(alpha_radius)

    simplices = tri.simplices
    p0 = xy[simplices[:, 0]]
    p1 = xy[simplices[:, 1]]
    p2 = xy[simplices[:, 2]]

    a = np.linalg.norm(p1 - p0, axis=1)
    b = np.linalg.norm(p2 - p1, axis=1)
    c = np.linalg.norm(p0 - p2, axis=1)
    # Twice the signed triangle area (shoelace cross product); its
    # magnitude also appears in the circumradius formula R = abc / (4*Area).
    cross = (p1[:, 0] - p0[:, 0]) * (p2[:, 1] - p0[:, 1]) - (
        p2[:, 0] - p0[:, 0]
    ) * (p1[:, 1] - p0[:, 1])
    two_area = np.abs(cross)
    triangle_areas = two_area / 2.0

    valid = two_area > 1e-12  # non-collinear triangles only
    circumradius = np.full(len(simplices), np.inf)
    circumradius[valid] = (a[valid] * b[valid] * c[valid]) / (2.0 * two_area[valid])

    keep = valid & (circumradius <= alpha_radius)
    area = float(triangle_areas[keep].sum())
    degenerate = not np.any(keep)
    return area, degenerate, float(alpha_radius)


def compute_view_hulls(
    points: np.ndarray,
    views: Sequence[str] = VIEWS,
    alpha_multiplier: float = _DEFAULT_ALPHA_NEIGHBOR_MULTIPLIER,
) -> dict[str, ViewCrownHull]:
    """Per-view convex-hull AND concave-hull (alpha-shape) area of a
    world-space point cloud.

    Hull area is translation-invariant, so callers do not need to worry
    about whether ``points`` are in grove-world or tree-local coordinates
    (the two traps noted in the XRFF-276 brief) for this function
    specifically -- only functions that need absolute position (none in
    this module) would care.

    ``alpha_multiplier`` is forwarded to ``_alpha_shape_area_2d`` for
    every view; each view still derives its OWN alpha radius from its own
    projected point spacing (front/side/top project the same 3D points
    onto different planes, so their 2D densities differ).
    """
    result: dict[str, ViewCrownHull] = {}
    for view in views:
        axis_h, axis_v = _VIEW_AXES[view]
        xy = points[:, [axis_h, axis_v]]
        area, degenerate = _hull_area_2d(xy)
        concave_area, concave_degenerate, alpha_radius = _alpha_shape_area_2d(
            xy, alpha_multiplier=alpha_multiplier
        )
        result[view] = ViewCrownHull(
            view=view,
            axis_h=axis_h,
            axis_v=axis_v,
            hull_area_m2=area,
            n_points=int(xy.shape[0]),
            is_degenerate=degenerate,
            concave_hull_area_m2=concave_area,
            alpha_radius_m=alpha_radius,
            concave_is_degenerate=concave_degenerate,
        )
    return result


def _estimate_crown_base_height(
    points: np.ndarray,
    trunk_height_frac: float = _DEFAULT_TRUNK_HEIGHT_FRAC,
    radius_frac: float = _DEFAULT_CROWN_BASE_RADIUS_FRAC,
    persistence_frac: float = _DEFAULT_CROWN_BASE_PERSISTENCE_FRAC,
    n_bins: int = _DEFAULT_HEIGHT_BINS,
) -> float:
    """Heuristic crown-base height: where lateral spread from the trunk
    axis becomes -- and stays -- large relative to the tree's own scale.

    Height (vertical) is always axis index 2 (Z), matching the convention
    used throughout ``io/usd/preview.py`` (e.g.
    ``height = points[:, 2].max() - points[:, 2].min()``) and implied by
    ``_VIEW_AXES`` (every view pairs axis 2 with one horizontal axis,
    except "top" which is the horizontal plane).

    The "persistent" check uses a LOCAL window of the next few points in
    Z-sorted order (not fixed-width height bins, and not a global fraction
    measured all the way to the tip):

    - Fixed-width height bins can end up EMPTY wherever the skeleton's
      joint spacing exceeds the bin width (a real possibility -- skeleton
      points are joints, not a uniform surface sampling), which starves
      the persistence check of data exactly where it matters. Windowing
      over a fixed COUNT of points instead of a fixed height range keeps
      every window populated regardless of local point density.
    - A global from-the-tip fraction is diluted by trunk length: for a
      tree whose trunk is a large fraction of total height, a single
      stray wide point near the ground can already push the cumulative
      from-tip ratio over the persistence threshold once enough of the
      (mostly-narrow) trunk is folded in -- exactly the false positive
      this heuristic exists to avoid.

    Uncalibrated against any ground-truth crown-base dataset -- see the
    module-level defaults' docstring.
    """
    z = points[:, 2]
    z_min, z_max = float(z.min()), float(z.max())
    if z_max - z_min < 1e-6:
        return z_min

    # Trunk axis: horizontal MEDIAN (not mean -- a single stray branch
    # point in this low slice should not drag the axis toward it) of the
    # tree's lowest slice, where the point cloud should be dominated by
    # the stem rather than branches.
    trunk_cutoff = z_min + trunk_height_frac * (z_max - z_min)
    trunk_mask = z <= trunk_cutoff
    if not np.any(trunk_mask):
        trunk_mask = z <= (z_min + 1e-6)
    trunk_xy = np.median(points[trunk_mask][:, :2], axis=0)

    radial = np.sqrt(((points[:, :2] - trunk_xy) ** 2).sum(axis=1))
    max_radial = float(radial.max())
    if max_radial < 1e-9:
        # Perfectly vertical point cloud (a bare pole) -- no crown spread
        # anywhere, so there is no meaningful crown base below the tip.
        return z_max

    threshold = radius_frac * max_radial

    # n_bins is retained as a public-ish knob for backward-compatible
    # tuning granularity, translated here into a point-count window: about
    # 1/n_bins of the point cloud, with a floor so small trees still get a
    # meaningful sample.
    order = np.argsort(z, kind="stable")
    z_sorted = z[order]
    above_sorted = radial[order] > threshold

    n = len(z_sorted)
    window = max(10, n // max(n_bins, 1))
    window = min(window, n)

    for i in range(n):
        if not above_sorted[i]:
            continue  # the reported base must itself be an above-threshold point
        w = above_sorted[i : i + window]
        if w.size and float(w.mean()) >= persistence_frac:
            return float(z_sorted[i])

    # No persistently wide region found (e.g. a bare sapling) -- fall back
    # to the tip so vertical_extent reads as ~0 rather than spuriously
    # spanning the whole stem.
    return z_max


def compute_crown_geometry(
    skeleton: object,
    views: Sequence[str] = VIEWS,
    trunk_height_frac: float = _DEFAULT_TRUNK_HEIGHT_FRAC,
    crown_base_radius_frac: float = _DEFAULT_CROWN_BASE_RADIUS_FRAC,
    crown_base_persistence_frac: float = _DEFAULT_CROWN_BASE_PERSISTENCE_FRAC,
    height_bins: int = _DEFAULT_HEIGHT_BINS,
    alpha_multiplier: float = _DEFAULT_ALPHA_NEIGHBOR_MULTIPLIER,
) -> CrownGeometry:
    """Compute crown hull area (convex AND concave, per view) and vertical
    extent for one tree.

    Args:
        skeleton: A Grove skeleton (or anything duck-typing its
            ``.points`` attribute as an (N, 3) sequence of (x, y, z)
            points), or a raw (N, 3) array/sequence directly. Uses the
            FULL, unfiltered point cloud -- deliberately not the
            25th-percentile-radius-filtered subset the icon renderer
            draws (see module docstring, "Relation to the icon metric").
        views: Which view planes to compute hulls for. Defaults to all
            three (front, side, top).
        trunk_height_frac, crown_base_radius_frac,
        crown_base_persistence_frac, height_bins: Tuning knobs for the
            crown-base heuristic; see ``_estimate_crown_base_height``.
        alpha_multiplier: Concave-hull tightness knob; see
            ``_DEFAULT_ALPHA_NEIGHBOR_MULTIPLIER`` and
            ``_alpha_shape_area_2d``.

    Returns:
        A ``CrownGeometry`` with one ``ViewCrownHull`` per requested view.

    Raises:
        ValueError: if the point cloud is empty or not (N, 3) shaped.
    """
    points = _points_array(skeleton)
    if points.shape[0] == 0:
        raise ValueError("Cannot compute crown geometry from an empty point set")

    view_hulls = compute_view_hulls(
        points, views=views, alpha_multiplier=alpha_multiplier
    )

    tip = float(points[:, 2].max())
    base = _estimate_crown_base_height(
        points,
        trunk_height_frac=trunk_height_frac,
        radius_frac=crown_base_radius_frac,
        persistence_frac=crown_base_persistence_frac,
        n_bins=height_bins,
    )
    base = min(base, tip)

    return CrownGeometry(
        crown_base_height_m=base,
        crown_tip_height_m=tip,
        crown_vertical_extent_m=tip - base,
        views=view_hulls,
    )


# --- Leaf Area Index (LAI) -----------------------------------------------
# LAI = total leaf area / crown projected GROUND area. By definition this
# is a TOP-DOWN (plan-view) quantity -- leaf area per unit of ground the
# canopy shades -- so ``compute_lai`` below only ever reads the "top"
# view's hull area and has no ``view`` parameter a caller could set wrong.
# A front/side "LAI" would be a silhouette density, a different and
# non-standard quantity; this module deliberately does not offer it under
# the LAI name.


@dataclass(frozen=True)
class LAIResult:
    """Leaf Area Index for one tree, plus the inputs that produced it.

    ``leaf_area_provisional`` and ``leaf_area_source`` are carried on the
    result (not just passed as call arguments) so a downstream consumer
    that only sees the ``LAIResult`` -- e.g. serialised to JSON -- can
    still tell whether ``lai`` rests on contaminated input. See
    ``compute_lai``.
    """

    lai: float
    leaf_area_m2: float
    crown_area_m2: float
    hull_type: str  # "concave" or "convex"
    view: str  # always "top" -- see module note above
    leaf_area_provisional: bool
    leaf_area_source: str | None = None


def load_leaf_area_m2(sidecar_path: str) -> float:
    """Read ``leaf_area_m2`` out of a leaf-area sidecar JSON file.

    Deliberately takes an explicit path with no default/hardcoded
    filename convention: callers decide whether to point this at the old,
    known-contaminated ``<prototype>_leaf_area.json`` sidecars (whole-mesh
    surface area, wood included -- see XRFF-318/273 notes) or the new
    topologically-derived ``<prototype>_leaf_area_geom.json`` sidecars,
    once those exist. This function has no opinion and no fallback
    between the two -- that decision, and the resulting
    ``leaf_area_provisional`` flag passed to ``compute_lai``, is the
    caller's responsibility.
    """
    import json
    from pathlib import Path

    data = json.loads(Path(sidecar_path).read_text())
    return float(data["leaf_area_m2"])


def compute_lai(
    leaf_area_m2: float,
    crown_geometry: CrownGeometry,
    *,
    leaf_area_provisional: bool,
    hull_type: str = "concave",
    leaf_area_source: str | None = None,
) -> LAIResult:
    """Leaf Area Index: ``leaf_area_m2`` / TOP-VIEW crown projected area.

    Args:
        leaf_area_m2: Total leaf area for the tree, in square metres.
            Never read from a hardcoded sidecar path by this function --
            see ``load_leaf_area_m2`` and the module docstring's input
            caveat. Callers must supply this themselves, from whichever
            leaf-area source they trust.
        crown_geometry: Output of ``compute_crown_geometry``. Must include
            the "top" view (the default ``views=VIEWS`` always does).
        leaf_area_provisional: Required, no default -- forces every call
            site to make an explicit decision about whether
            ``leaf_area_m2`` is trustworthy. Pass ``True`` if it came from
            the old, wood-contaminated ``<prototype>_leaf_area.json``
            sidecars (or any other unverified source); pass ``False`` only
            once it is known to come from a corrected source (e.g. the
            topologically-derived ``_leaf_area_geom.json`` sidecars,
            after verifying they exist and were used).
        hull_type: "concave" (default -- see module docstring "Convex vs.
            concave hull" section) or "convex" (the XRFF-276 baseline).
        leaf_area_source: Free-text provenance note (e.g. a sidecar path
            or "analyze_triangle_budget aggregate"), carried through onto
            the result for traceability.

    Returns:
        An ``LAIResult``. ``lai`` is ``float("nan")`` if the top-view
        crown area is zero or degenerate to zero (cannot divide by it
        meaningfully) -- never silently 0.0 or inf.

    Raises:
        ValueError: if "top" is missing from ``crown_geometry.views``, or
            ``hull_type`` is not "concave"/"convex".
    """
    if "top" not in crown_geometry.views:
        raise ValueError(
            "compute_lai requires the 'top' view in CrownGeometry.views -- "
            "LAI is defined against the top-down crown projection, not "
            "front/side silhouette. Recompute with views including 'top' "
            "(the default)."
        )
    if hull_type == "concave":
        area = crown_geometry.views["top"].concave_hull_area_m2
    elif hull_type == "convex":
        area = crown_geometry.views["top"].hull_area_m2
    else:
        raise ValueError(f"hull_type must be 'concave' or 'convex', got {hull_type!r}")

    lai = (leaf_area_m2 / area) if area > 0 else float("nan")

    return LAIResult(
        lai=lai,
        leaf_area_m2=leaf_area_m2,
        crown_area_m2=area,
        hull_type=hull_type,
        view="top",
        leaf_area_provisional=leaf_area_provisional,
        leaf_area_source=leaf_area_source,
    )
