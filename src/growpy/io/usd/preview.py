"""Preview and export control image generation for tree exports.

Generates 2D orthogonal projections of tree branch structure and exported
mesh/skeleton data for visual QA.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_VIEW_AXES = {"front": (0, 2), "side": (1, 2), "top": (0, 1)}


def generate_preview_image(
    tree_dir: Path,
    species_clean: str,
    file_prefix: str,
    skeleton,
    timer,
) -> list | None:
    """Draw branch structure from skeleton polylines as 3-axis preview.

    Renders front (X vs Z), side (Y vs Z), and top (X vs Y) orthogonal
    projections. Filters out the thinnest twigs to reveal main branch
    architecture.

    Args:
        tree_dir: Directory to save preview image.
        species_clean: Snake_case species name (used for title only).
        file_prefix: Base filename prefix (e.g., 'european_beech_h15m_d10cm').
        skeleton: Grove skeleton object with points and polylines.
        timer: ProfileTimer instance.

    Returns:
        List of (xlim, ylim) tuples per view for axis matching, or None.
    """
    if skeleton is None:
        return None
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.collections import LineCollection

        with timer.track("generate_preview"):
            points = np.array(skeleton.points)
            if len(points) == 0:
                return None

            # Center XY at origin so open-grown trees at X=100 display cleanly
            points = points.copy()
            center_xy = np.mean(points[:, :2], axis=0)
            points[:, :2] -= center_xy

            radii = None
            if hasattr(skeleton, "point_attribute_radius"):
                radii = np.array(skeleton.point_attribute_radius)

            # Detect global polyline indices: Grove API may return global
            # indices for per-tree skeletons in multi-tree groves.  Remap
            # to local range when the max index exceeds the points array.
            num_points = len(points)
            offset = 0
            all_indices = set()
            for polyline in skeleton.poly_lines:
                for idx in polyline:
                    all_indices.add(idx)
            if all_indices:
                max_idx = max(all_indices)
                min_idx = min(all_indices)
                if max_idx >= num_points:
                    offset = min_idx
                    remapped_max = max_idx - offset
                    if remapped_max >= num_points:
                        logger.debug(
                            "Polyline index range [%d-%d] exceeds points (%d) "
                            "even after offset %d (remapped max=%d)",
                            min_idx, max_idx, num_points, offset, remapped_max,
                        )

            # Collect all segment radii first to compute filter threshold
            all_seg_radii = []
            seg_data = []
            for polyline in skeleton.poly_lines:
                for i in range(len(polyline) - 1):
                    idx0 = polyline[i] - offset
                    idx1 = polyline[i + 1] - offset
                    if idx0 < 0 or idx0 >= num_points or idx1 < 0 or idx1 >= num_points:
                        continue
                    if radii is not None:
                        # First segment is the junction: use the thinner
                        # (branch-side) radius so it doesn't inherit the
                        # parent stem's thickness.
                        if i == 0:
                            r = min(radii[idx0], radii[idx1])
                        else:
                            r = (radii[idx0] + radii[idx1]) * 0.5
                    else:
                        r = 0.005
                    all_seg_radii.append(r)
                    seg_data.append((idx0, idx1, r))

            if not seg_data:
                return None

            # Filter: keep segments with radius >= 25th percentile
            all_seg_radii = np.array(all_seg_radii)
            radius_threshold = max(np.percentile(all_seg_radii, 25), 0.001)

            filtered = []
            for idx0, idx1, r in seg_data:
                if r < radius_threshold:
                    continue
                filtered.append((points[idx0], points[idx1], r))

            if not filtered:
                return None

            title = species_clean.replace("_", " ").title()
            height = points[:, 2].max() - points[:, 2].min()

            views = [
                ("Front (X vs Z)", 0, 2, "X (m)", "Z height (m)"),
                ("Side (Y vs Z)", 1, 2, "Y (m)", "Z height (m)"),
                ("Top (X vs Y)", 0, 1, "X (m)", "Y (m)"),
            ]

            fig, axes = plt.subplots(1, 3, figsize=(18, 7))
            fig.suptitle(f"{title} ({height:.1f}m)", fontsize=14, fontweight="bold")

            ax_points = 7 * 72
            reference_height = 30.0
            pts_per_meter = ax_points / reference_height

            for ax, (view_name, ax_h, ax_v, xlabel, ylabel) in zip(axes, views):
                segs = []
                ws = []
                for p0, p1, r in filtered:
                    segs.append([(p0[ax_h], p0[ax_v]), (p1[ax_h], p1[ax_v])])
                    ws.append(r * 2 * pts_per_meter)

                lc = LineCollection(
                    segs, linewidths=ws, colors="#3b2a1a", alpha=1.0,
                    capstyle="round", joinstyle="round",
                )
                ax.add_collection(lc)
                ax.set_aspect("equal")
                ax.autoscale()
                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
                ax.set_title(view_name)
                ax.grid(True, alpha=0.2)

            plt.tight_layout()
            png_path = tree_dir / f"{file_prefix}_preview.png"
            fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="white")

            view_bounds = [(ax.get_xlim(), ax.get_ylim()) for ax in axes]

            plt.close(fig)
            logger.info("  Preview: %s", png_path.name)
            return view_bounds
    except Exception as e:
        logger.warning("Preview generation failed for %s: %s", file_prefix, e)
        return None


def generate_icon_image(
    tree_dir: Path,
    file_prefix: str,
    skeleton,
    timer,
    size_px: int = 512,
    view: str | None = None,
) -> None:
    """Render a minimal icon on a square canvas.

    Produces a clean silhouette suitable for catalog thumbnails. No axis,
    grid, title, or other annotations are drawn.

    Args:
        tree_dir: Directory to save icon image.
        file_prefix: Base filename prefix.
        skeleton: Grove skeleton object with points and polylines.
        timer: ProfileTimer instance.
        size_px: Icon size in pixels (square).
        view: Projection view — "front" (X vs Z), "side" (Y vs Z), or
            "top" (X vs Y). When None (default), produces side view and
            saves as ``{file_prefix}_icon.png`` for backward compatibility.
            When set, saves as ``{file_prefix}_icon_{view}.png``.
    """
    if skeleton is None:
        return
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.collections import LineCollection

        with timer.track("generate_icon"):
            points = np.array(skeleton.points)
            if len(points) == 0:
                return

            radii = None
            if hasattr(skeleton, "point_attribute_radius"):
                radii = np.array(skeleton.point_attribute_radius)

            num_points = len(points)
            offset = 0
            all_indices = set()
            for polyline in skeleton.poly_lines:
                for idx in polyline:
                    all_indices.add(idx)
            if all_indices:
                max_idx = max(all_indices)
                min_idx = min(all_indices)
                if max_idx >= num_points:
                    offset = min_idx
                    remapped_max = max_idx - offset
                    if remapped_max >= num_points:
                        logger.debug(
                            "Icon polyline index range [%d-%d] exceeds points "
                            "(%d) even after offset %d (remapped max=%d)",
                            min_idx, max_idx, num_points, offset, remapped_max,
                        )

            all_seg_radii = []
            seg_data = []
            for polyline in skeleton.poly_lines:
                for i in range(len(polyline) - 1):
                    idx0 = polyline[i] - offset
                    idx1 = polyline[i + 1] - offset
                    if idx0 < 0 or idx0 >= num_points or idx1 < 0 or idx1 >= num_points:
                        continue
                    if radii is not None:
                        if i == 0:
                            r = min(radii[idx0], radii[idx1])
                        else:
                            r = (radii[idx0] + radii[idx1]) * 0.5
                    else:
                        r = 0.005
                    all_seg_radii.append(r)
                    seg_data.append((idx0, idx1, r))

            if not seg_data:
                return

            all_seg_radii = np.array(all_seg_radii)
            radius_threshold = max(np.percentile(all_seg_radii, 25), 0.001)

            ax_h, ax_v = _VIEW_AXES.get(view, (1, 2))

            segs = []
            ws = []
            dpi = 150
            fig_inches = size_px / dpi
            ax_points = fig_inches * 72
            reference_height = 30.0
            pts_per_meter = ax_points / reference_height

            for idx0, idx1, r in seg_data:
                if r < radius_threshold:
                    continue
                p0, p1 = points[idx0], points[idx1]
                segs.append([(p0[ax_h], p0[ax_v]), (p1[ax_h], p1[ax_v])])
                ws.append(r * 2 * pts_per_meter)

            if not segs:
                return

            fig, ax = plt.subplots(1, 1, figsize=(fig_inches, fig_inches))
            lc = LineCollection(
                segs, linewidths=ws, colors="#3b2a1a", alpha=1.0,
                capstyle="round", joinstyle="round",
            )
            ax.add_collection(lc)
            ax.set_aspect("equal")
            ax.autoscale()

            # Pad axes to fill the square canvas (tree is taller than wide)
            xlo, xhi = ax.get_xlim()
            ylo, yhi = ax.get_ylim()
            xspan = xhi - xlo
            yspan = yhi - ylo
            span = max(xspan, yspan)
            xcenter = (xlo + xhi) / 2
            ycenter = (ylo + yhi) / 2
            margin = span * 0.05
            half = span / 2 + margin
            ax.set_xlim(xcenter - half, xcenter + half)
            ax.set_ylim(ycenter - half, ycenter + half)

            ax.axis("off")
            fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

            suffix = f"_icon_{view}" if view else "_icon"
            png_path = tree_dir / f"{file_prefix}{suffix}.png"
            fig.savefig(
                png_path, dpi=dpi,
                facecolor="white",
            )
            plt.close(fig)
            logger.info("  Icon: %s", png_path.name)
    except Exception as e:
        logger.warning("Icon generation failed for %s: %s", file_prefix, e)


def generate_sensitivity_preview(
    output_dir: Path,
    file_prefix: str,
    skeleton,
    timer,
    metrics: dict,
    param_labels: dict,
    size_px: int = 1800,
) -> None:
    """2×2 sensitivity preview: three orthogonal views + stats text panel.

    Saves a square PNG suitable for browsing large combo grids.

    Args:
        output_dir: Directory to save preview image.
        file_prefix: Base filename prefix (e.g., '0000_c10').
        skeleton: Grove skeleton object with points and polylines.
        timer: ProfileTimer instance (or stub with .track() context manager).
        metrics: Dict of metric name → value for the text panel.
        param_labels: Dict of swept param name → value for this combo.
        size_px: Square canvas size in pixels (1800 = 12in × 150dpi).
    """
    if skeleton is None:
        return
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.collections import LineCollection

        with timer.track("generate_sensitivity_preview"):
            points = np.array(skeleton.points)
            if len(points) == 0:
                return

            points = points.copy()
            center_xy = np.mean(points[:, :2], axis=0)
            points[:, :2] -= center_xy

            radii = None
            if hasattr(skeleton, "point_attribute_radius"):
                radii = np.array(skeleton.point_attribute_radius)

            num_points = len(points)
            offset = 0
            all_indices: set = set()
            for polyline in skeleton.poly_lines:
                for idx in polyline:
                    all_indices.add(idx)
            if all_indices:
                max_idx = max(all_indices)
                min_idx = min(all_indices)
                if max_idx >= num_points:
                    offset = min_idx

            all_seg_radii = []
            seg_data = []
            for polyline in skeleton.poly_lines:
                for i in range(len(polyline) - 1):
                    idx0 = polyline[i] - offset
                    idx1 = polyline[i + 1] - offset
                    if idx0 < 0 or idx0 >= num_points or idx1 < 0 or idx1 >= num_points:
                        continue
                    if radii is not None:
                        r = min(radii[idx0], radii[idx1]) if i == 0 else (radii[idx0] + radii[idx1]) * 0.5
                    else:
                        r = 0.005
                    all_seg_radii.append(r)
                    seg_data.append((idx0, idx1, r))

            if not seg_data:
                return

            all_seg_radii_arr = np.array(all_seg_radii)
            radius_threshold = max(np.percentile(all_seg_radii_arr, 25), 0.001)

            dpi = 150
            fig_inches = size_px / dpi  # 12.0
            subplot_pts = (fig_inches / 2) * 72
            reference_height = 30.0
            pts_per_meter = subplot_pts / reference_height

            fig, axes = plt.subplots(2, 2, figsize=(fig_inches, fig_inches))
            view_specs = [
                (axes[0, 0], "Front", 0, 2),
                (axes[0, 1], "Side", 1, 2),
                (axes[1, 0], "Top", 0, 1),
            ]

            for ax, view_name, ax_h, ax_v in view_specs:
                segs = []
                ws = []
                for idx0, idx1, r in seg_data:
                    if r < radius_threshold:
                        continue
                    p0, p1 = points[idx0], points[idx1]
                    segs.append([(p0[ax_h], p0[ax_v]), (p1[ax_h], p1[ax_v])])
                    ws.append(r * 2 * pts_per_meter)
                if segs:
                    lc = LineCollection(
                        segs, linewidths=ws, colors="#3b2a1a", alpha=1.0,
                        capstyle="round", joinstyle="round",
                    )
                    ax.add_collection(lc)
                ax.set_aspect("equal")
                ax.autoscale()
                xlo, xhi = ax.get_xlim()
                ylo, yhi = ax.get_ylim()
                span = max(xhi - xlo, yhi - ylo, 0.1)
                xcenter = (xlo + xhi) / 2
                ycenter = (ylo + yhi) / 2
                margin = span * 0.05
                half = span / 2 + margin
                ax.set_xlim(xcenter - half, xcenter + half)
                ax.set_ylim(ycenter - half, ycenter + half)
                ax.axis("off")
                ax.set_title(view_name, fontsize=9)

            ax_text = axes[1, 1]
            ax_text.axis("off")
            lines = ["Parameters:"]
            for k, v in param_labels.items():
                lines.append(f"  {k} = {v:.4g}")
            lines.append("")
            lines.append("Metrics:")
            lines.append(f"  Height:      {metrics.get('height_m', 0):.2f} m")
            lines.append(f"  DBH:         {metrics.get('dbh_m', 0) * 100:.1f} cm")
            lines.append(f"  Crown width: {metrics.get('crown_width_m', 0):.2f} m")
            lines.append(f"  Crown area:  {metrics.get('crown_area_m2', 0):.1f} m²")
            lines.append(f"  Branches:    {metrics.get('branch_count', 0)}")
            ax_text.text(
                0.05, 0.95, "\n".join(lines),
                transform=ax_text.transAxes,
                fontsize=9, verticalalignment="top", fontfamily="monospace",
            )

            plt.tight_layout(pad=0.5)
            png_path = output_dir / f"{file_prefix}_preview.png"
            fig.savefig(png_path, dpi=dpi, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            logger.info("  Sensitivity preview: %s", png_path.name)
    except Exception as e:
        logger.warning("Sensitivity preview failed for %s: %s", file_prefix, e)


def generate_export_control_image(
    tree_dir: Path,
    species_clean: str,
    file_prefix: str,
    timer,
    view_bounds: list | None = None,
    stems_file_base: str | None = None,
) -> None:
    """Render control image from the exported stems mesh and skeleton.

    Reads back the actual exported USD stage via the USD API (so this works
    for both '.usda' and '.usdc') to verify what Unreal will import. Shows
    mesh edges (green) and skeleton joints (red) in 3 orthogonal views.

    Args:
        tree_dir: Directory containing the tree's exported files.
        species_clean: Snake_case species name (used for title only).
        file_prefix: Base filename prefix (e.g., 'european_beech_h15m_d10cm').
        timer: ProfileTimer instance.
        view_bounds: Optional axis bounds from preview image for matching.
        stems_file_base: Base name for stems file lookup. When provided, uses
            this instead of file_prefix to locate the stems USD (e.g.,
            'european_beech_h15m_d10cm' when file_prefix includes variant info).
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
        from matplotlib.collections import LineCollection
        from ...utils.pxr_init import ensure_pxr_with_unreal_schema

        ensure_pxr_with_unreal_schema()
        from pxr import Usd, UsdGeom, UsdSkel

        from ...config.core import get_config
        from ...config.paths import stems_path as _stems_path

        with timer.track("generate_export_control"):
            base = stems_file_base if stems_file_base else file_prefix
            config = get_config()
            path = _stems_path(tree_dir, base, "skeletal", config)
            if not path.exists():
                path = _stems_path(tree_dir, base, "static", config)
            if not path.exists():
                return

            stage = Usd.Stage.Open(str(path))
            if stage is None:
                return

            # Mesh points/edges from the first Mesh prim in the stage.
            mesh_points = None
            edges: set[tuple[int, int]] = set()
            for prim in stage.Traverse():
                if not prim.IsA(UsdGeom.Mesh):
                    continue
                mesh = UsdGeom.Mesh(prim)
                points = mesh.GetPointsAttr().Get()
                if not points:
                    continue
                mesh_points = np.array([[p[0], p[1], p[2]] for p in points])
                face_counts = mesh.GetFaceVertexCountsAttr().Get() or []
                face_indices = mesh.GetFaceVertexIndicesAttr().Get() or []
                offset = 0
                for count in face_counts:
                    face = face_indices[offset : offset + count]
                    offset += count
                    for i in range(len(face)):
                        edges.add(tuple(sorted((face[i], face[(i + 1) % len(face)]))))
                break  # one mesh per stems file

            if mesh_points is None:
                return

            # Skeleton joint positions (translation component of each joint's
            # world-space bind transform) from the first Skeleton prim.
            skel_points = []
            for prim in stage.Traverse():
                if not prim.IsA(UsdSkel.Skeleton):
                    continue
                bind_transforms = UsdSkel.Skeleton(prim).GetBindTransformsAttr().Get()
                for m in bind_transforms or []:
                    t = m.ExtractTranslation()
                    skel_points.append([t[0], t[1], t[2]])
                break  # one skeleton per stems file
            skel_points = np.array(skel_points) if skel_points else np.empty((0, 3))

            # Center everything at origin for clean plots.
            # Mesh and skeleton may be in world coordinates (e.g., X=100
            # for open-grown trees), which makes Front/Top views confusing.
            mesh_center_xy = np.mean(mesh_points[:, :2], axis=0)
            mesh_points[:, :2] -= mesh_center_xy
            if len(skel_points) > 0:
                skel_center_xy = np.mean(skel_points[:, :2], axis=0)
                skel_points[:, :2] -= skel_center_xy

            title = species_clean.replace("_", " ").title()
            z_vals = mesh_points[:, 2]
            height = z_vals.max() - z_vals.min()

            views = [
                ("Front (X vs Z)", 0, 2, "X (m)", "Z height (m)"),
                ("Side (Y vs Z)", 1, 2, "Y (m)", "Z height (m)"),
                ("Top (X vs Y)", 0, 1, "X (m)", "Y (m)"),
            ]

            fig, axes = plt.subplots(1, 3, figsize=(18, 7))
            fig.suptitle(
                f"{title} Export Control ({height:.1f}m) -- "
                f"{len(mesh_points):,} verts, {len(skel_points)} joints",
                fontsize=12,
                fontweight="bold",
            )

            # Subsample edges for performance
            edge_list = list(edges)
            max_edges = 50000
            if len(edge_list) > max_edges:
                rng = np.random.default_rng(42)
                idx = rng.choice(len(edge_list), max_edges, replace=False)
                edge_list = [edge_list[i] for i in idx]

            for ax, (view_name, ax_h, ax_v, xlabel, ylabel) in zip(axes, views):
                segs = []
                for e0, e1 in edge_list:
                    if e0 < len(mesh_points) and e1 < len(mesh_points):
                        p0, p1 = mesh_points[e0], mesh_points[e1]
                        segs.append([(p0[ax_h], p0[ax_v]), (p1[ax_h], p1[ax_v])])
                if segs:
                    lc = LineCollection(
                        segs, linewidths=0.15, colors="#2d5016", alpha=0.4
                    )
                    ax.add_collection(lc)

                if len(skel_points) > 0:
                    ax.scatter(
                        skel_points[:, ax_h],
                        skel_points[:, ax_v],
                        c="red",
                        s=4,
                        zorder=5,
                        alpha=0.7,
                        label=f"{len(skel_points)} joints",
                    )

                ax.set_aspect("equal")
                ax.autoscale()
                ax.set_xlabel(xlabel)
                ax.set_ylabel(ylabel)
                ax.set_title(view_name)
                ax.grid(True, alpha=0.2)
                if len(skel_points) > 0:
                    ax.legend(fontsize=8, loc="upper right")

            # Match axis bounds from preview image if available
            if view_bounds and len(view_bounds) == len(axes):
                for ax, (xlim, ylim) in zip(axes, view_bounds):
                    ax.set_xlim(xlim)
                    ax.set_ylim(ylim)

            plt.tight_layout()
            png_path = tree_dir / f"{file_prefix}_export_control.png"
            fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="white")
            plt.close(fig)
            logger.info("  Export control: %s", png_path.name)
    except Exception as e:
        logger.warning("Export control image failed for %s: %s", file_prefix, e)
