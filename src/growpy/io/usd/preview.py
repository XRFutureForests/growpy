"""Preview and export control image generation for tree exports.

Generates 2D orthogonal projections of tree branch structure and exported
mesh/skeleton data for visual QA.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)

_VIEW_AXES = {"front": (0, 2), "side": (1, 2), "top": (0, 1)}

# Colours for the per-component icon layers (generate_icon_image's
# export_components path). Branch (#3b2a1a) and twig (#1f7a1f) colours match
# the pre-existing plain/twigs icon literals exactly so the merged layer reads
# consistently with them; skeleton colours are new since bone chains/joints
# are not drawn anywhere else in this module's icon output.
_BRANCH_COLOR = "#3b2a1a"
_TWIG_COLOR = "#1f7a1f"
_SKELETON_LINE_COLOR = "#b23a3a"
_SKELETON_JOINT_COLOR = "#7a1f1f"


def _square_limits(
    xs, ys, margin_frac: float = 0.05
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Square, centred (xlim, ylim) covering ``xs``/``ys`` with a margin.

    Mirrors the padding math generate_icon_image already uses to fill its
    square canvas, factored out so every per-component icon layer for a given
    tree+view can be handed the exact same limits.
    """
    xlo, xhi = float(xs.min()), float(xs.max())
    ylo, yhi = float(ys.min()), float(ys.max())
    span = max(xhi - xlo, yhi - ylo, 1e-6)
    xcenter = (xlo + xhi) / 2
    ycenter = (ylo + yhi) / 2
    margin = span * margin_frac
    half = span / 2 + margin
    return (xcenter - half, xcenter + half), (ycenter - half, ycenter + half)


def _save_icon_layer(
    path: Path,
    fig_inches: float,
    dpi: int,
    xlim: tuple[float, float],
    ylim: tuple[float, float],
    branch_segs=None,
    branch_widths=None,
    twig_xyz=None,
    ax_h: int | None = None,
    ax_v: int | None = None,
    bone_segs=None,
    joint_xy=None,
    legend: bool = False,
) -> None:
    """Render one component-icon PNG (branches / twigs / skeleton / merged).

    Draws whichever of (branch_segs, bone_segs+joint_xy, twig_xyz) are
    provided into a single square canvas at the given shared ``xlim``/
    ``ylim``, so every layer for one tree+view lands in the same pixel
    positions. ``legend`` adds a small legend proxy per drawn layer (used
    for the merged plot only).
    """
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    from matplotlib.lines import Line2D

    fig, ax = plt.subplots(1, 1, figsize=(fig_inches, fig_inches))
    handles = []

    if branch_segs:
        lc = LineCollection(
            branch_segs,
            linewidths=branch_widths,
            colors=_BRANCH_COLOR,
            alpha=1.0,
            capstyle="round",
            joinstyle="round",
        )
        ax.add_collection(lc)
        if legend:
            handles.append(
                Line2D([0], [0], color=_BRANCH_COLOR, lw=3, label="Branches")
            )

    if bone_segs:
        lc2 = LineCollection(
            bone_segs,
            linewidths=0.8,
            colors=_SKELETON_LINE_COLOR,
            alpha=0.9,
            zorder=4,
        )
        ax.add_collection(lc2)
        if joint_xy:
            jx = [p[0] for p in joint_xy]
            jy = [p[1] for p in joint_xy]
            ax.scatter(
                jx,
                jy,
                s=5,
                c=_SKELETON_JOINT_COLOR,
                zorder=5,
                linewidths=0,
            )
        if legend:
            handles.append(
                Line2D(
                    [0],
                    [0],
                    color=_SKELETON_LINE_COLOR,
                    lw=1.5,
                    marker="o",
                    markersize=4,
                    markerfacecolor=_SKELETON_JOINT_COLOR,
                    markeredgewidth=0,
                    label="Skeleton",
                )
            )

    if twig_xyz is not None and len(twig_xyz):
        ax.scatter(
            twig_xyz[:, ax_h],
            twig_xyz[:, ax_v],
            s=4,
            c=_TWIG_COLOR,
            alpha=0.5,
            linewidths=0,
            zorder=3,
        )
        if legend:
            handles.append(
                Line2D(
                    [0],
                    [0],
                    linestyle="None",
                    marker="o",
                    markerfacecolor=_TWIG_COLOR,
                    markeredgewidth=0,
                    markersize=5,
                    alpha=0.7,
                    label="Twigs",
                )
            )

    ax.set_aspect("equal")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

    if legend and handles:
        ax.legend(
            handles=handles,
            loc="upper right",
            fontsize=6,
            framealpha=0.75,
            handlelength=1.4,
            borderpad=0.4,
            labelspacing=0.4,
        )

    fig.savefig(path, dpi=dpi, facecolor="white")
    plt.close(fig)


def generate_preview_image(
    tree_dir: Path,
    species_clean: str,
    file_prefix: str,
    skeleton,
    timer,
    twig_placements=None,
) -> list | None:
    """Draw branch structure from skeleton polylines as 3-axis preview.

    Renders front (X vs Z), side (Y vs Z), and top (X vs Y) orthogonal
    projections. Filters out the thinnest twigs to reveal main branch
    architecture.

    When ``twig_placements`` is given the figure gains a second row showing the
    same three views with the twig instance positions scattered over the
    branches. The branch-only row is kept because the two answer different
    questions: row 1 is branch architecture, row 2 is where the foliage
    actually sits and how densely. Without the twig row the image is identical
    at every twig density -- the branch skeleton does not depend on it -- so it
    cannot be used to judge crown density at all.

    Args:
        tree_dir: Directory to save preview image.
        species_clean: Snake_case species name (used for title only).
        file_prefix: Base filename prefix (e.g., 'european_beech_h15m_d10cm').
        skeleton: Grove skeleton object with points and polylines.
        timer: ProfileTimer instance.
        twig_placements: Optional ``{twig_type: [TwigPlacement, ...]}`` as
            written by the assembly export, i.e. final positions after
            recovery, thinning and the instance cap. None or empty falls back
            to the single-row branch-only layout.

    Returns:
        List of (xlim, ylim) tuples per view for axis matching, or None. Always
        the three branch-row views, so the export-control render frames itself
        identically whether or not the twig row was drawn.
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

            # Center XY at origin so open-grown trees at X=100 display
            # cleanly. Use the tree's own root point (index 0 = base of
            # trunk, per Grove convention -- see pve_grove_mapper.py), not
            # the crown's XY mean: an asymmetric/wind-swept canopy pulls the
            # mean away from the trunk, which misaligns the twig-placement
            # overlay (tree-local, root-relative) against the branches.
            points = points.copy()
            center_xy = points[0, :2].copy()
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
                            min_idx,
                            max_idx,
                            num_points,
                            offset,
                            remapped_max,
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

            # Twig placements are ALREADY tree-local (near the origin), while
            # skeleton.points are in grove-world coordinates -- dataset groves
            # are split per (species, surround_radius) and sit at X ~ 0/100/200
            # so their shade shells cannot interact, which is what center_xy
            # above corrects for. Verified against the exported assembly: the
            # PointInstancer is authored from these placements verbatim (no
            # translation) and its positions are within a couple of metres of
            # the origin for r00, r08 and r16 alike.
            #
            # So twigs must NOT have center_xy applied. Doing so shifted them
            # by exactly the grove offset -- 100 m at r08 and 200 m at r16 --
            # while r00 looked correct because its offset is ~0.
            twig_xyz = None
            if twig_placements:
                _tp = [p.position for plist in twig_placements.values() for p in plist]
                if _tp:
                    twig_xyz = np.asarray(_tp, dtype=float)
                    # Sanity check rather than a silent mis-plot: if a future
                    # caller ever passes grove-world placements, say so instead
                    # of drawing them 100 m off the branches.
                    # np.ptp(), not ndarray.ptp(): the method was removed in
                    # NumPy 2.
                    _span = max(
                        float(np.ptp(points[:, 0])),
                        float(np.ptp(points[:, 1])),
                        1.0,
                    )
                    _off = max(
                        abs(float(np.median(twig_xyz[:, 0]))),
                        abs(float(np.median(twig_xyz[:, 1]))),
                    )
                    if _off > 5.0 * _span:
                        logger.warning(
                            "Twig placements for %s look like grove-world "
                            "coordinates (median XY offset %.1f m vs branch "
                            "span %.1f m); preview twig row may be misaligned",
                            file_prefix,
                            _off,
                            _span,
                        )

            n_rows = 2 if twig_xyz is not None else 1
            fig, axes = plt.subplots(n_rows, 3, figsize=(18, 7 * n_rows), squeeze=False)
            n_twigs = 0 if twig_xyz is None else len(twig_xyz)
            suptitle = f"{title} ({height:.1f}m)"
            if twig_xyz is not None:
                suptitle += f" -- {n_twigs:,} twig instances"
            fig.suptitle(suptitle, fontsize=14, fontweight="bold")

            ax_points = 7 * 72
            reference_height = 30.0
            pts_per_meter = ax_points / reference_height

            for row in range(n_rows):
                show_twigs = row == 1
                for ax, (view_name, ax_h, ax_v, xlabel, ylabel) in zip(
                    axes[row], views
                ):
                    segs = []
                    ws = []
                    for p0, p1, r in filtered:
                        segs.append([(p0[ax_h], p0[ax_v]), (p1[ax_h], p1[ax_v])])
                        ws.append(r * 2 * pts_per_meter)

                    # A LineCollection belongs to one axes, so build a fresh
                    # one per panel rather than sharing across rows.
                    lc = LineCollection(
                        segs,
                        linewidths=ws,
                        colors="#3b2a1a",
                        alpha=1.0,
                        capstyle="round",
                        joinstyle="round",
                    )
                    ax.add_collection(lc)

                    if show_twigs:
                        # Plain round points: overlapping dots read as density,
                        # which is the whole purpose of this row.
                        ax.scatter(
                            twig_xyz[:, ax_h],
                            twig_xyz[:, ax_v],
                            s=6,
                            c="#1f7a1f",
                            alpha=0.5,
                            linewidths=0,
                            zorder=3,
                        )

                    ax.set_aspect("equal")
                    ax.autoscale()
                    ax.set_xlabel(xlabel)
                    ax.set_ylabel(ylabel)
                    ax.set_title(
                        f"{view_name} + {n_twigs:,} twigs" if show_twigs else view_name
                    )
                    ax.grid(True, alpha=0.2)

            plt.tight_layout()
            png_path = tree_dir / f"{file_prefix}_preview.png"
            fig.savefig(png_path, dpi=150, bbox_inches="tight", facecolor="white")

            # Branch row only: export-control matches against these.
            view_bounds = [(ax.get_xlim(), ax.get_ylim()) for ax in axes[0]]

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
    twig_placements=None,
    bones_info=None,
    export_components: bool = False,
) -> None:
    """Render a minimal icon on a square canvas.

    Produces a clean silhouette suitable for catalog thumbnails. No axis,
    grid, title, or other annotations are drawn.

    When ``twig_placements`` is given, a SECOND file is written alongside the
    plain icon with the twig instance positions drawn over the branches
    (``..._icon_{view}_twigs.png``). The plain icon is still the same
    branches-only drawing -- the dataset deliverable that dataset_overview.csv
    points at -- just framed by the same shared canvas extent described below
    rather than its own independent autoscale.

    Note this stage stays once-per-tree, unlike the preview: icons are a
    per-tree catalog deliverable. With density variants active the twig icon
    therefore shows variant 0 only -- use the preview for per-variant density.

    Every file this call can produce for one tree+view -- the plain icon, the
    twigs variant and, when ``export_components`` is True, the four component
    layers below -- shares ONE canvas extent: the union of every layer's data
    (branches, twigs, and bones when present), padded and squared once. That
    means any two of these PNGs can be alpha-composited directly by a later
    tool with no re-registration: same pixel grid every time. It also means
    twigs that reach past the branch envelope no longer get clipped in the
    twigs icon, which the old branches-only autoscale could do.

    When ``export_components`` is True, FOUR additional files are written:
    ``..._icon_{view}_branches.png``, ``..._twigsonly.png``, ``..._skeleton.png``
    (only when ``bones_info`` is non-empty) and ``..._merged.png``. The
    branches layer keeps the same 25th-percentile-radius filter as the
    plain/twigs icons (thinnest twigs/branch tips dropped) so it matches what
    those two already show; see the module-level filter below. This is
    additive and gated purely by the caller (see forest_stages.write_icons /
    GrowPyConfig.export_icon_components) -- it costs nothing when False.

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
        twig_placements: Optional ``{twig_type: [TwigPlacement, ...]}``. These
            are tree-local while skeleton.points are grove-world, so the
            skeleton is centred on its own root point (points[0], the base of
            the trunk -- see pve_grove_mapper.py) here to put both in the same
            frame. Not the crown's XY mean: that drifts away from the trunk
            for an asymmetric/wind-swept canopy and misaligns the overlay.
        bones_info: Optional list of bone tuples from Grove's
            ``grove.tag_bone_id()`` -- ``(is_tree_root, parent_bone_id,
            start_point, end_point, radius, mass, is_branch_root,
            branch_id)`` (see core/skeleton.py). Only used when
            ``export_components`` is True, to draw the skeleton layer: one
            line segment per bone plus a marker at every joint (bone
            endpoint). Drawn from the raw, unfiltered list -- i.e. before the
            mesh-vertex-based filtering ``filter_bones_for_mesh`` applies at
            actual skeletal-mesh export time -- so the joint count/spread
            shown here is an upper bound on what ships in the skinned USD.
        export_components: When True, also write the four per-component
            files described above.
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

            # Twig placements are tree-local; skeleton.points are grove-world
            # (dataset groves sit at X ~ 0/100/200 per surround radius). Centre
            # the skeleton on its own root point (points[0], the trunk base)
            # so both share a frame -- NOT the crown's XY mean, which drifts
            # away from the trunk for an asymmetric/wind-swept canopy and
            # shifted the twig overlay off the branches.
            twig_xyz = None
            center_xy = None
            if twig_placements:
                _tp = [p.position for plist in twig_placements.values() for p in plist]
                if _tp:
                    twig_xyz = np.asarray(_tp, dtype=float)
                    points = points.copy()
                    center_xy = points[0, :2].copy()
                    points[:, :2] -= center_xy

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
                            min_idx,
                            max_idx,
                            num_points,
                            offset,
                            remapped_max,
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

            # Bone segments (skeleton overlay), computed up front even though
            # only the *_skeleton/*_merged component layers draw them: their
            # extent still needs folding into the shared canvas below so
            # every sibling file for this tree+view -- including the plain
            # icon -- is framed identically.
            bone_segs = []
            joint_xy = []
            if export_components and bones_info:
                offset_xy = center_xy if center_xy is not None else np.zeros(2)
                for bone in bones_info:
                    start_pt, end_pt = bone[2], bone[3]
                    p0 = (
                        start_pt.x - offset_xy[0],
                        start_pt.y - offset_xy[1],
                        start_pt.z,
                    )
                    p1 = (
                        end_pt.x - offset_xy[0],
                        end_pt.y - offset_xy[1],
                        end_pt.z,
                    )
                    bone_segs.append([(p0[ax_h], p0[ax_v]), (p1[ax_h], p1[ax_v])])
                    joint_xy.append((p0[ax_h], p0[ax_v]))
                    joint_xy.append((p1[ax_h], p1[ax_v]))

            # ONE canvas extent for every sibling file this call can produce
            # (plain icon, twigs and -- when export_components is on --
            # branches/twigsonly/skeleton/merged), from the union of every
            # layer any of them draws. A later, dumber tool can then overlay
            # any two of these PNGs with a plain alpha-composite: same pixel
            # grid every time, not just within one file group. Previously the
            # plain/twigs pair used their own branches-only autoscale while
            # the four component layers used this union -- two different
            # frames for the "same" tree+view, and twigs reaching past the
            # branch envelope got clipped in the twigs icon.
            union_xs = [pt[0] for seg in segs for pt in seg]
            union_ys = [pt[1] for seg in segs for pt in seg]
            for seg in bone_segs:
                union_xs.extend([seg[0][0], seg[1][0]])
                union_ys.extend([seg[0][1], seg[1][1]])
            if twig_xyz is not None and len(twig_xyz):
                union_xs.extend(twig_xyz[:, ax_h].tolist())
                union_ys.extend(twig_xyz[:, ax_v].tolist())
            xlim, ylim = _square_limits(np.array(union_xs), np.array(union_ys))

            fig, ax = plt.subplots(1, 1, figsize=(fig_inches, fig_inches))
            lc = LineCollection(
                segs,
                linewidths=ws,
                colors="#3b2a1a",
                alpha=1.0,
                capstyle="round",
                joinstyle="round",
            )
            ax.add_collection(lc)
            ax.set_aspect("equal")
            ax.set_xlim(*xlim)
            ax.set_ylim(*ylim)
            ax.axis("off")
            fig.subplots_adjust(left=0, right=1, top=1, bottom=0)

            suffix = f"_icon_{view}" if view else "_icon"
            png_path = tree_dir / f"{file_prefix}{suffix}.png"
            fig.savefig(
                png_path,
                dpi=dpi,
                facecolor="white",
            )
            logger.info("  Icon: %s", png_path.name)

            # Twig variant: same framing, foliage drawn over the branches.
            # Written as a second file so the plain icon the dataset overview
            # references stays byte-for-byte what it was.
            if twig_xyz is not None:
                ax.scatter(
                    twig_xyz[:, ax_h],
                    twig_xyz[:, ax_v],
                    s=4,
                    c="#1f7a1f",
                    alpha=0.5,
                    linewidths=0,
                    zorder=3,
                )
                twig_path = tree_dir / f"{file_prefix}{suffix}_twigs.png"
                fig.savefig(twig_path, dpi=dpi, facecolor="white")
                logger.info("  Icon: %s (%d twigs)", twig_path.name, len(twig_xyz))

            plt.close(fig)

            # Per-component layers: branches / twigs-only / skeleton / merged.
            # Additive files sharing the same xlim/ylim computed above (and
            # therefore the plain icon/twigs pair too) so every layer for
            # this tree+view lines up pixel-for-pixel. See the
            # export_components docstring section above.
            if export_components:
                _save_icon_layer(
                    tree_dir / f"{file_prefix}{suffix}_branches.png",
                    fig_inches,
                    dpi,
                    xlim,
                    ylim,
                    branch_segs=segs,
                    branch_widths=ws,
                )
                if twig_xyz is not None and len(twig_xyz):
                    _save_icon_layer(
                        tree_dir / f"{file_prefix}{suffix}_twigsonly.png",
                        fig_inches,
                        dpi,
                        xlim,
                        ylim,
                        twig_xyz=twig_xyz,
                        ax_h=ax_h,
                        ax_v=ax_v,
                    )
                if bone_segs:
                    _save_icon_layer(
                        tree_dir / f"{file_prefix}{suffix}_skeleton.png",
                        fig_inches,
                        dpi,
                        xlim,
                        ylim,
                        bone_segs=bone_segs,
                        joint_xy=joint_xy,
                    )
                _save_icon_layer(
                    tree_dir / f"{file_prefix}{suffix}_merged.png",
                    fig_inches,
                    dpi,
                    xlim,
                    ylim,
                    branch_segs=segs,
                    branch_widths=ws,
                    twig_xyz=twig_xyz,
                    ax_h=ax_h,
                    ax_v=ax_v,
                    bone_segs=bone_segs,
                    joint_xy=joint_xy,
                    legend=True,
                )
                logger.info(
                    "  Icon components: %s (%d bones)",
                    f"{file_prefix}{suffix}",
                    len(bone_segs),
                )
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
                        r = (
                            min(radii[idx0], radii[idx1])
                            if i == 0
                            else (radii[idx0] + radii[idx1]) * 0.5
                        )
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
                        segs,
                        linewidths=ws,
                        colors="#3b2a1a",
                        alpha=1.0,
                        capstyle="round",
                        joinstyle="round",
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
                0.05,
                0.95,
                "\n".join(lines),
                transform=ax_text.transAxes,
                fontsize=9,
                verticalalignment="top",
                fontfamily="monospace",
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
