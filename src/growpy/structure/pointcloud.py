"""L2 structure metrics straight from a single-tree point cloud, without a QSM (XRFF-577).

The same code runs on real scans (BioDiv-3DTrees TLS, Ecosense TLS) and on synthetic
scans of generated trees (HELIOS++), so the two are compared metric by metric. Input is
an ``(N, 3)`` array in metres with z up; the tree base is the lowest point and the height
is ``max z - min z``. Clouds should be leaf-off and single-tree (segmented).

Metrics (``metrics`` returns one flat dict, keys ``L2.*``):

* **vertical profile**: share of points and of occupied voxels in ``N_BINS`` height-
  normalised bins (0 = base, 1 = top). The voxel profile is the scan-robust one: point
  counts follow scanner distance and occlusion.
* **stem and crown**: DBH from a RANSAC stem circle at 1.2-1.4 m (densest cluster,
  2 cm inlier band, least-squares refit), robust to branches and flare in the slice; crown base as the
  lowest 0.5 m slice from which every slice over the next ``CROWN_RUN_M`` reaches out
  beyond ``max(CROWN_R_MIN_M, CROWN_R_STEMS * stem radius)`` (p95 horizontal distance
  from the stem centre). Not the QSM ``L1.crown_base_m`` (lowest branch attachment):
  compare the two only with that in mind.
* **crown envelope** (points at and above the crown base): convex hull volume; alpha-
  shape volume (Delaunay tetrahedra with circumradius below ``alpha``, on a voxel-
  thinned cloud); layered hull volume (2D hull area per 0.5 m slice); crown projection
  area and diameter, maximum width, crown height and length ratio; asymmetry as the
  offset of the crown-projection centroid from the stem over the crown radius, and as
  the min/max ratio of the crown radius over eight azimuth sectors.
* **box dimension** (Seidel 2018, doi 10.1016/j.agrformet.2018.04.006): slope of
  ``log N(s)`` over ``log(1/s)`` for boxes halved from the tree's bounding extent down to
  ``min_box``; also the intercept (box sizes in metres) and the fit r2.
* **voxel occupancy and gap fraction**: occupied crown voxels over the crown convex hull
  volume in voxels; vertical gap fraction (crown-projection cells with no occupied voxel
  above them) and side gap fraction (the same for the x-z and y-z projections).

``keep_connected`` optionally drops points not connected to the stem (0.2 m voxels,
26-connected), for instance clouds cut from a plot-wide segmentation.

Branch-point density from a skeleton is not computed: it needs a skeleton, which is
the QSM fitter's job (XRFF-575).
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
from scipy import ndimage
from scipy.optimize import least_squares
from scipy.spatial import ConvexHull, Delaunay, QhullError

N_BINS = 10
VOXEL_M = 0.1  # occupancy, voxel profile
GAP_CELL_M = 0.1  # gap-fraction raster
SLICE_M = 0.5  # crown base, layered hull
ALPHA_M = 1.0  # alpha shape: keep tetrahedra with circumradius below this
ALPHA_THIN_M = 0.1  # voxel thinning before the alpha-shape Delaunay
MIN_BOX_M = 0.1  # smallest box of the box dimension
CROWN_R_MIN_M = 0.75
CLEAN_VOXEL_M = 0.2  # keep_connected
STEM_BAND_M = 0.02  # RANSAC inlier band of the stem circle
STEM_R_MAX_M = 1.0  # largest stem radius and the search window around the stem seed
CROWN_R_STEMS = 4.0
CROWN_RUN_M = 2.0
SECTORS = 8


# --- reading ------------------------------------------------------------------------


def read_points(path: str | Path) -> np.ndarray:
    """``(N, 3)`` float64 xyz from ``.npy``, ``.xyz``/``.txt``/``.csv`` (first three
    columns), ``.ply`` (ascii or binary vertex x, y, z) or ``.las``/``.laz`` (needs
    ``laspy`` with a LAZ backend; growpy does not depend on it)."""
    path = Path(path)
    ext = path.suffix.lower()
    if ext == ".npy":
        pts = np.load(path, allow_pickle=False)
    elif ext in (".xyz", ".txt", ".csv", ".asc", ".pts"):
        with open(path, encoding="utf-8") as f:
            first = f.readline()
        delim = "," if "," in first else None
        skip = 0 if _is_numeric_row(first, delim) else 1
        pts = np.loadtxt(
            path, delimiter=delim, skiprows=skip, usecols=(0, 1, 2), ndmin=2
        )
    elif ext == ".ply":
        pts = _read_ply(path)
    elif ext in (".las", ".laz"):
        try:
            import laspy
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise ImportError(
                "reading LAS/LAZ needs laspy (and lazrs for LAZ); convert to .npy or "
                "install laspy[lazrs]"
            ) from exc
        las = laspy.read(path)
        pts = np.column_stack([las.x, las.y, las.z])
    else:
        raise ValueError(f"unsupported point cloud format: {path.name}")
    pts = np.asarray(pts, dtype=np.float64)[:, :3]
    return pts[np.isfinite(pts).all(axis=1)]


def _is_numeric_row(line: str, delim: str | None) -> bool:
    try:
        [float(v) for v in line.strip().split(delim)[:3]]
        return True
    except ValueError:
        return False


_PLY_TYPES = {
    "char": "i1", "int8": "i1", "uchar": "u1", "uint8": "u1",
    "short": "i2", "int16": "i2", "ushort": "u2", "uint16": "u2",
    "int": "i4", "int32": "i4", "uint": "u4", "uint32": "u4",
    "float": "f4", "float32": "f4", "double": "f8", "float64": "f8",
}  # fmt: skip


def _read_ply(path: Path) -> np.ndarray:
    with open(path, "rb") as f:
        if f.readline().strip() != b"ply":
            raise ValueError(f"{path.name}: not a PLY file")
        fmt, n_vert, props, element = None, 0, [], None
        while True:
            line = f.readline()
            if not line:
                raise ValueError(f"{path.name}: PLY header without end_header")
            words = line.decode("ascii").split()
            if not words:
                continue
            if words[0] == "format":
                fmt = words[1]
            elif words[0] == "element":
                element = words[1]
                if element == "vertex":
                    n_vert = int(words[2])
            elif words[0] == "property" and element == "vertex":
                if words[1] == "list":
                    raise ValueError(f"{path.name}: list properties on vertices")
                props.append((words[2], _PLY_TYPES[words[1]]))
            elif words[0] == "end_header":
                break
        names = [p[0] for p in props]
        if fmt == "ascii":
            data = np.loadtxt(f, max_rows=n_vert, ndmin=2)
            return data[:, [names.index(c) for c in "xyz"]]
        order = "<" if fmt == "binary_little_endian" else ">"
        dtype = np.dtype([(n, order + t) for n, t in props])
        data = np.fromfile(f, dtype=dtype, count=n_vert)
    return np.column_stack([data[c] for c in "xyz"])


# --- helpers ------------------------------------------------------------------------


def voxel_keys(
    points: np.ndarray, size: float, origin: np.ndarray | None = None
) -> np.ndarray:
    """Unique integer voxel indices ``(M, 3)`` of the occupied voxels."""
    origin = points.min(axis=0) if origin is None else origin
    return np.unique(np.floor((points - origin) / size).astype(np.int64), axis=0)


def thin(points: np.ndarray, size: float) -> np.ndarray:
    """One point per occupied voxel (the voxel centroid)."""
    idx = np.floor((points - points.min(axis=0)) / size).astype(np.int64)
    _, inv, counts = np.unique(idx, axis=0, return_inverse=True, return_counts=True)
    inv = inv.ravel()
    out = np.zeros((len(counts), 3))
    np.add.at(out, inv, points)
    return out / counts[:, None]


def fit_circle(xy: np.ndarray) -> tuple[float, float, float]:
    """Least-squares circle: centre x, centre y, radius. An algebraic (Kasa) fit starts a
    geometric fit; Kasa alone runs about 25 % small on a noisy stem ring."""
    a = np.column_stack([xy, np.ones(len(xy))])
    b = (xy**2).sum(axis=1)
    (cx2, cy2, c), *_ = np.linalg.lstsq(a, b, rcond=None)
    cx, cy = cx2 / 2, cy2 / 2
    r0 = math.sqrt(max(c + cx**2 + cy**2, 0.0))
    fit = least_squares(
        lambda q: np.hypot(xy[:, 0] - q[0], xy[:, 1] - q[1]) - q[2], [cx, cy, r0]
    )
    return float(fit.x[0]), float(fit.x[1]), float(abs(fit.x[2]))


def fit_stem_circle(
    xy: np.ndarray, band: float = STEM_BAND_M, n_iter: int = 400, seed: int = 0
) -> tuple[float, float, float]:
    """Stem circle in a horizontal slice cluttered by branches, flare or a neighbour:
    restrict to the densest stem cluster, RANSAC circles through three points (score:
    inliers within ``band`` of the circle minus twice the points inside it), keep points within 1.5 x that radius of its centre,
    RANSAC again and refit the inliers by least squares. NaN radius if nothing fits."""
    rng = np.random.default_rng(seed)
    # densest 5 cm cell (3 x 3 smoothed) as the stem seed
    lo = xy.min(axis=0)
    cells = np.floor((xy - lo) / 0.05).astype(np.int64)
    n = cells.max(axis=0) + 3
    grid = np.zeros(n)
    np.add.at(grid, (cells[:, 0] + 1, cells[:, 1] + 1), 1)
    smooth = sum(
        np.roll(np.roll(grid, i, 0), j, 1) for i in (-1, 0, 1) for j in (-1, 0, 1)
    )
    ci, cj = np.unravel_index(np.argmax(smooth), n)
    seed_xy = lo + (np.array([ci, cj]) - 0.5) * 0.05
    pts = xy[np.hypot(*(xy - seed_xy).T) < STEM_R_MAX_M]
    best = None
    for _ in range(2):
        best = _ransac_circle(pts, band, n_iter, rng)
        if best is None:
            return float("nan"), float("nan"), float("nan")
        cx, cy, r = best
        pts = pts[np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) < 1.5 * r]
    cx, cy, r = best
    inl = pts[np.abs(np.hypot(pts[:, 0] - cx, pts[:, 1] - cy) - r) < band]
    if len(inl) < 5:
        return cx, cy, r
    return fit_circle(inl)


def _ransac_circle(pts, band, n_iter, rng):
    if len(pts) < 5:
        return None
    score = pts if len(pts) <= 4000 else pts[rng.choice(len(pts), 4000, replace=False)]
    tri = pts[rng.integers(0, len(pts), size=(n_iter, 3))]  # (n, 3, 2)
    a, b, c = tri[:, 0], tri[:, 1], tri[:, 2]
    d = 2 * (
        a[:, 0] * (b[:, 1] - c[:, 1])
        + b[:, 0] * (c[:, 1] - a[:, 1])
        + c[:, 0] * (a[:, 1] - b[:, 1])
    )
    sa, sb, sc = (a**2).sum(1), (b**2).sum(1), (c**2).sum(1)
    with np.errstate(divide="ignore", invalid="ignore"):
        ux = (
            sa * (b[:, 1] - c[:, 1])
            + sb * (c[:, 1] - a[:, 1])
            + sc * (a[:, 1] - b[:, 1])
        ) / d
        uy = (
            sa * (c[:, 0] - b[:, 0])
            + sb * (a[:, 0] - c[:, 0])
            + sc * (b[:, 0] - a[:, 0])
        ) / d
    r = np.hypot(a[:, 0] - ux, a[:, 1] - uy)
    ok = np.isfinite(r) & (r > 0.01) & (r < STEM_R_MAX_M)
    if not ok.any():
        return None
    ux, uy, r = ux[ok], uy[ok], r[ok]
    dist = np.hypot(score[None, :, 0] - ux[:, None], score[None, :, 1] - uy[:, None])
    # a stem section is hollow in a scan: points inside a candidate circle count against it,
    # which rejects large circles strung through branch clutter or two stems
    inliers = (np.abs(dist - r[:, None]) < band).sum(1)
    inside = (dist < r[:, None] - band).sum(1)
    k = int(np.argmax(inliers - 2 * inside))
    return float(ux[k]), float(uy[k]), float(r[k])


def _hull_volume(points: np.ndarray) -> float:
    try:
        return float(ConvexHull(points).volume) if len(points) >= 4 else 0.0
    except QhullError:
        return 0.0


def _hull_2d(xy: np.ndarray) -> ConvexHull | None:
    try:
        return ConvexHull(xy) if len(xy) >= 3 else None
    except QhullError:
        return None


def _polygon_centroid(v: np.ndarray) -> np.ndarray:
    x, y = v[:, 0], v[:, 1]
    xn, yn = np.roll(x, -1), np.roll(y, -1)
    cross = x * yn - xn * y
    area = cross.sum() / 2
    if abs(area) < 1e-12:
        return v.mean(axis=0)
    return np.array([((x + xn) * cross).sum(), ((y + yn) * cross).sum()]) / (6 * area)


def _inside_hull_2d(hull: ConvexHull, pts: np.ndarray) -> np.ndarray:
    # hull.equations: a x + b y + c <= 0 inside
    return (pts @ hull.equations[:, :2].T + hull.equations[:, 2] <= 1e-9).all(axis=1)


# --- metric groups ------------------------------------------------------------------


def vertical_profile(
    points: np.ndarray, n_bins: int = N_BINS, voxel: float = VOXEL_M
) -> dict:
    """Share of points and of occupied voxels per height-normalised bin."""
    z0, height = points[:, 2].min(), np.ptp(points[:, 2])
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    zp = (points[:, 2] - z0) / height
    pts_hist = np.histogram(zp, edges)[0] / len(points)
    keys = voxel_keys(points, voxel)
    zv = ((keys[:, 2] + 0.5) * voxel) / height
    vox_hist = np.histogram(np.clip(zv, 0, 1), edges)[0] / len(keys)
    out = {}
    for k in range(n_bins):
        out[f"L2.points_z{k + 1:02d}"] = float(pts_hist[k])
    for k in range(n_bins):
        out[f"L2.voxels_z{k + 1:02d}"] = float(vox_hist[k])
    out["L2.points_z_mean_rel"] = float(zp.mean())
    out["L2.voxels_z_mean_rel"] = float(np.clip(zv, 0, 1).mean())
    return out


def stem_and_crown_base(points: np.ndarray) -> dict:
    """Stem centre and DBH (1.2-1.4 m), crown base from horizontal slice extents."""
    z = points[:, 2] - points[:, 2].min()
    height = float(z.max())
    ring = points[(z >= 1.2) & (z < 1.4), :2]
    low = points[(z >= 0.5) & (z < 2.0), :2]
    r = float("nan")
    if len(ring) >= 10:
        cx, cy, r = fit_stem_circle(ring)
    if not np.isfinite(r) and len(low):
        cx, cy = np.median(low, axis=0)
    elif not np.isfinite(r):
        cx, cy = np.median(points[:, :2], axis=0)
    radial = np.hypot(points[:, 0] - cx, points[:, 1] - cy)
    thresh = max(CROWN_R_MIN_M, CROWN_R_STEMS * r) if np.isfinite(r) else CROWN_R_MIN_M
    n_sl = max(int(math.ceil(height / SLICE_M)), 1)
    sl = np.minimum((z / SLICE_M).astype(int), n_sl - 1)
    reach = np.zeros(n_sl)
    for k in range(n_sl):
        r_k = radial[sl == k]
        reach[k] = np.quantile(r_k, 0.95) if len(r_k) else 0.0
    is_crown = reach > thresh
    run = max(int(round(CROWN_RUN_M / SLICE_M)), 1)
    base_k = next(
        (k for k in range(n_sl) if is_crown[k : min(k + run, n_sl)].all()),
        n_sl - 1,
    )
    return {
        "stem_xy": (float(cx), float(cy)),
        "L2.dbh_m": 2 * r if np.isfinite(r) else float("nan"),
        "L2.crown_base_m": base_k * SLICE_M,
        "L2.crown_reach_threshold_m": thresh,
    }


def alpha_volume(points: np.ndarray, alpha: float = ALPHA_M) -> float:
    """Volume of the Delaunay tetrahedra whose circumradius is below ``alpha``."""
    if len(points) < 5:
        return 0.0
    try:
        tri = Delaunay(points)
    except QhullError:
        return 0.0
    total = 0.0
    for lo in range(0, len(tri.simplices), 500_000):  # chunks bound the memory
        t = points[tri.simplices[lo : lo + 500_000]]  # (M, 4, 3)
        a, b, c = t[:, 1] - t[:, 0], t[:, 2] - t[:, 0], t[:, 3] - t[:, 0]
        bxc, cxa, axb = np.cross(b, c), np.cross(c, a), np.cross(a, b)
        det = np.einsum("ij,ij->i", a, bxc)
        # circumcentre offset from vertex 0: (|a|^2 bxc + |b|^2 cxa + |c|^2 axb) / 2 det
        num = (
            (a * a).sum(1)[:, None] * bxc
            + (b * b).sum(1)[:, None] * cxa
            + (c * c).sum(1)[:, None] * axb
        )
        with np.errstate(divide="ignore", invalid="ignore"):
            radius = np.linalg.norm(num, axis=1) / np.abs(2 * det)
        keep = np.isfinite(radius) & (radius < alpha)
        total += float(np.abs(det[keep]).sum() / 6)
    return total


def crown_envelope(
    points: np.ndarray,
    stem_xy: tuple[float, float],
    crown_base_m: float,
    alpha: float = ALPHA_M,
) -> dict:
    """Hull, alpha and layered volumes, projection, width, asymmetry of the crown."""
    z0 = points[:, 2].min()
    height = float(np.ptp(points[:, 2]))
    crown = points[points[:, 2] - z0 >= crown_base_m]
    out = {
        "L2.crown_height_m": height - crown_base_m,
        "L2.crown_ratio": (height - crown_base_m) / height
        if height > 0
        else float("nan"),
    }
    out["L2.hull_volume_m3"] = _hull_volume(crown)
    out["L2.alpha_volume_m3"] = (
        alpha_volume(thin(crown, ALPHA_THIN_M), alpha) if len(crown) else 0.0
    )
    layered = 0.0
    zc = crown[:, 2] - z0
    for k in range(int(crown_base_m / SLICE_M), int(math.ceil(height / SLICE_M)) + 1):
        h = _hull_2d(crown[(zc >= k * SLICE_M) & (zc < (k + 1) * SLICE_M), :2])
        layered += h.volume * SLICE_M if h is not None else 0.0
    out["L2.layered_hull_volume_m3"] = layered
    hull = _hull_2d(crown[:, :2])
    if hull is None:
        return out | {"L2.cpa_m2": 0.0}
    v = crown[hull.vertices, :2]
    cpa = float(hull.volume)  # 2D: volume is the area
    radius = math.sqrt(cpa / math.pi)
    out["L2.cpa_m2"] = cpa
    out["L2.crown_diameter_m"] = 2 * radius
    out["L2.crown_width_max_m"] = float(
        np.sqrt(((v[:, None, :] - v[None, :, :]) ** 2).sum(-1)).max()
    )
    out["L2.crown_width_over_height"] = out["L2.crown_diameter_m"] / height
    centroid = _polygon_centroid(v)
    out["L2.crown_offset_rel"] = float(
        np.hypot(*(centroid - np.asarray(stem_xy))) / radius
    )
    d = crown[:, :2] - np.asarray(stem_xy)
    az = ((np.arctan2(d[:, 1], d[:, 0]) + math.pi) / (2 * math.pi) * SECTORS).astype(
        int
    ) % SECTORS
    r = np.hypot(d[:, 0], d[:, 1])
    reach = np.array(
        [
            np.quantile(r[az == s], 0.95) if (az == s).any() else 0.0
            for s in range(SECTORS)
        ]
    )
    out["L2.crown_sector_ratio"] = (
        float(reach.min() / reach.max()) if reach.max() > 0 else 0.0
    )
    return out


def box_dimension(points: np.ndarray, min_box: float = MIN_BOX_M) -> dict:
    """Box-counting dimension: boxes halved from the bounding extent to ``min_box``."""
    span = np.ptp(points, axis=0)
    rel = points - points.min(axis=0)
    sizes, counts = [], []
    s = float(span.max())
    while s >= min_box:
        # boxes tile [min, max] exactly: a point on the far face joins the last box
        last = np.maximum(np.ceil(span / s).astype(np.int64) - 1, 0)
        idx = np.minimum(np.floor(rel / s).astype(np.int64), last)
        sizes.append(s)
        counts.append(len(np.unique(idx, axis=0)))
        s /= 2
    if len(sizes) < 3:
        return {"L2.box_dimension": float("nan")}
    x = np.log(1 / np.asarray(sizes))
    y = np.log(np.asarray(counts, dtype=float))
    slope, intercept = np.polyfit(x, y, 1)
    resid = y - (slope * x + intercept)
    r2 = 1 - (resid**2).sum() / ((y - y.mean()) ** 2).sum()
    return {
        "L2.box_dimension": float(slope),
        "L2.box_intercept": float(intercept),
        "L2.box_r2": float(r2),
        "L2.box_n_sizes": len(sizes),
    }


def occupancy_and_gaps(
    points: np.ndarray,
    crown_base_m: float,
    voxel: float = VOXEL_M,
    cell: float = GAP_CELL_M,
) -> dict:
    """Voxel occupancy inside the crown hull; vertical and side gap fractions."""
    z0 = points[:, 2].min()
    crown = points[points[:, 2] - z0 >= crown_base_m]
    out = {"L2.n_voxels": int(len(voxel_keys(points, voxel)))}
    if len(crown) < 5:
        return out
    # voxels inside the hull ~ hull volume / voxel volume (boundary voxels are a small share)
    n_crown = len(voxel_keys(crown, voxel))
    hull_vox = _hull_volume(crown) / voxel**3
    out["L2.voxel_occupancy"] = (
        float(min(n_crown / hull_vox, 1.0)) if hull_vox > 0 else float("nan")
    )
    for name, (i, j) in {
        "vertical": (0, 1),
        "side_xz": (0, 2),
        "side_yz": (1, 2),
    }.items():
        out[f"L2.gap_fraction_{name}"] = _gap_fraction(crown[:, [i, j]], cell)
    out["L2.gap_fraction_side"] = (
        out["L2.gap_fraction_side_xz"] + out["L2.gap_fraction_side_yz"]
    ) / 2
    return out


def _gap_fraction(xy: np.ndarray, cell: float) -> float:
    """Share of raster cells inside the 2D hull of ``xy`` that no point falls in."""
    hull = _hull_2d(xy)
    if hull is None:
        return float("nan")
    lo = xy.min(axis=0)
    filled = np.unique(np.floor((xy - lo) / cell).astype(np.int64), axis=0)
    n = filled.max(axis=0) + 1
    gx, gy = np.meshgrid(np.arange(n[0]), np.arange(n[1]), indexing="ij")
    centres = lo + (np.column_stack([gx.ravel(), gy.ravel()]) + 0.5) * cell
    inside = _inside_hull_2d(hull, centres)
    occupied = np.zeros(n, dtype=bool)
    occupied[filled[:, 0], filled[:, 1]] = True
    n_in = int(inside.sum())
    return float((inside & ~occupied.ravel()).sum() / n_in) if n_in else float("nan")


def keep_connected(
    points: np.ndarray, voxel: float = CLEAN_VOXEL_M, seed_radius: float = 1.0
) -> np.ndarray:
    """Drop points not connected to the stem: 26-connected components of ``voxel`` cubes
    are kept when they hold a voxel within ``seed_radius`` of the stem axis between 0.5 and
    3 m above the base. For instance clouds cut from a plot-wide segmentation (Ecosense),
    which carry fragments of neighbouring crowns. Not for sparse single-tree clouds: at
    0.2 m the thin upper crown of a sparse scan comes apart (3 of 30 BioDiv beech lost
    14-24 % of their height), while 0.5 m keeps neighbour fragments on Ecosense."""
    z = points[:, 2] - points[:, 2].min()
    ring = points[(z >= 1.2) & (z < 1.4), :2]
    cx, cy, r = fit_stem_circle(ring) if len(ring) >= 10 else (np.nan, np.nan, np.nan)
    if not np.isfinite(r):
        low = points[(z >= 0.5) & (z < 2.0), :2]
        cx, cy = np.median(low if len(low) else points[:, :2], axis=0)
    idx = np.floor((points - points.min(axis=0)) / voxel).astype(np.int64)
    grid = np.zeros(idx.max(axis=0) + 1, dtype=bool)
    grid[idx[:, 0], idx[:, 1], idx[:, 2]] = True
    labels, _ = ndimage.label(grid, structure=np.ones((3, 3, 3), dtype=bool))
    lab = labels[idx[:, 0], idx[:, 1], idx[:, 2]]
    seed = (
        (np.hypot(points[:, 0] - cx, points[:, 1] - cy) < seed_radius)
        & (z >= 0.5)
        & (z < 3.0)
    )
    keep = np.isin(lab, np.unique(lab[seed]))
    return points[keep] if seed.any() else points


def metrics(
    points: np.ndarray,
    voxel: float = VOXEL_M,
    alpha: float = ALPHA_M,
    min_box: float = MIN_BOX_M,
    n_bins: int = N_BINS,
) -> dict:
    """All L2 metrics of one single-tree cloud as one flat dict."""
    points = np.asarray(points, dtype=np.float64)
    if points.ndim != 2 or points.shape[1] < 3 or len(points) < 10:
        raise ValueError("need an (N, 3) cloud with at least 10 points")
    points = points[:, :3]
    out = {
        "L2.n_points": int(len(points)),
        "L2.height_m": float(np.ptp(points[:, 2])),
    }
    base = stem_and_crown_base(points)
    stem_xy = base.pop("stem_xy")
    out |= base
    out |= vertical_profile(points, n_bins, voxel)
    out |= crown_envelope(points, stem_xy, out["L2.crown_base_m"], alpha)
    out |= box_dimension(points, min_box)
    out |= occupancy_and_gaps(points, out["L2.crown_base_m"], voxel)
    return out
