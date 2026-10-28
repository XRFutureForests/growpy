"""Icon-style drawings of real trees, prototypes and occupancy maps.

Every tile copies the growpy catalog icon (``io/usd/preview.py::generate_icon_image``) so the
two can be laid side by side or alpha-composited: 512 px square at 150 dpi, white, no axes;
branches as a ``LineCollection`` in the catalog brown with round caps; line width =
radius x 2 in points at a fixed 30 m reference (absolute metres, not rescaled per tree);
segments below the 25th-percentile radius (floor 1 mm) dropped; square extent with a 5 %
margin. QSMs have no twigs, so there is no twig layer.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from growpy.io.usd.preview import _BRANCH_COLOR, _VIEW_AXES, _square_limits
from growpy.structure.prototypes import OCC_X, Geometry, leading

ICON_PX = 512
DPI = 150
REFERENCE_HEIGHT_M = 30.0  # generate_icon_image's line-width reference
ACCENT = "#2a6fdb"  # real median / band / outline; not green, which means twigs
FRAME_SHARE = 0.1  # occupancy tiles frame on cells at least 10 % of trees reach


def _pts_per_meter(size_px: int = ICON_PX) -> float:
    return size_px / DPI * 72 / REFERENCE_HEIGHT_M


def branch_segments(
    geo: Geometry, radius: np.ndarray, view: str = "front", size_px: int = ICON_PX
) -> tuple[np.ndarray, np.ndarray]:
    """Projected segments and line widths after the icon's 25th-percentile radius drop."""
    keep = radius >= max(float(np.percentile(radius, 25)), 0.001)
    ah, av = _VIEW_AXES[view]
    segs = np.stack([geo.start[keep][:, [ah, av]], geo.end[keep][:, [ah, av]]], axis=1)
    return segs, radius[keep] * 2 * _pts_per_meter(size_px)


def limits_of(*point_sets: np.ndarray):
    pts = np.concatenate([p.reshape(-1, 2) for p in point_sets])
    return _square_limits(pts[:, 0], pts[:, 1])


def _canvas(size_px: int = ICON_PX):
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(1, 1, figsize=(size_px / DPI, size_px / DPI))
    return plt, fig, ax


def _draw(ax, segs, widths, color=_BRANCH_COLOR, alpha=1.0, zorder=2):
    from matplotlib.collections import LineCollection

    ax.add_collection(
        LineCollection(
            segs,
            linewidths=widths,
            colors=color,
            alpha=alpha,
            capstyle="round",
            joinstyle="round",
            zorder=zorder,
        )
    )


def _save(plt, fig, ax, xlim, ylim, path: Path) -> Path:
    ax.set_aspect("equal")
    ax.set_xlim(*xlim)
    ax.set_ylim(*ylim)
    ax.axis("off")
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=DPI, facecolor="white")
    plt.close(fig)
    return path


def _scale_figure(ax, segs: np.ndarray, height_m: float) -> np.ndarray:
    """A grey standing person ``height_m`` tall, in the tree's metre frame: feet on the
    lowest drawn point, a fixed gap right of the widest drawn point, plus a ground line under
    tree and figure. A neutral pictogram (straight rounded torso, two legs, round head) so it
    reads as a person, not as a man or a woman. Returns the corner points so the frame takes
    the figure in."""
    from matplotlib.patches import Circle, FancyBboxPatch

    x_min, x_max = float(segs[..., 0].min()), float(segs[..., 0].max())
    z0 = float(segs[..., 1].min())
    h = height_m
    x = x_max + max(1.0, 0.04 * (x_max - x_min)) + 0.25 * h
    grey = "#8a918c"

    def block(x0, z_lo, width, z_hi, round_frac):
        ax.add_patch(
            FancyBboxPatch(
                (x + x0 * h, z0 + z_lo * h),
                width * h,
                (z_hi - z_lo) * h,
                boxstyle=f"round,pad=0,rounding_size={round_frac * h}",
                color=grey,
                lw=0,
                zorder=1,
            )
        )

    block(-0.090, 0.44, 0.18, 0.81, 0.06)  # torso
    # arms, hanging with a small gap to the torso
    block(-0.150, 0.47, 0.050, 0.80, 0.025)
    block(0.100, 0.47, 0.050, 0.80, 0.025)
    block(-0.085, 0.0, 0.075, 0.50, 0.03)  # legs
    block(0.010, 0.0, 0.075, 0.50, 0.03)
    ax.add_patch(Circle((x, z0 + 0.905 * h), 0.085 * h, color=grey, lw=0, zorder=1))
    ax.plot([x_min, x + 0.3 * h], [z0, z0], color=grey, lw=0.6, zorder=0)
    return np.array([(x_min, z0), (x + 0.3 * h, z0 + h)])


def tree_icon(
    path: Path,
    geo: Geometry,
    radius: np.ndarray,
    view: str = "front",
    figure_m: float | None = None,
) -> Path:
    """One tree, drawn exactly like a catalog branch icon; ``figure_m`` (survey cards) adds a
    person of that height at the tree's scale and draws line widths true to the frame, not
    at the icon's fixed 30 m reference, so stem and branches are as thick as they are."""
    segs, widths = branch_segments(geo, radius, view)
    plt, fig, ax = _canvas()
    if not figure_m:
        _draw(ax, segs, widths)
        return _save(plt, fig, ax, *limits_of(segs), path)
    limits = limits_of(segs, _scale_figure(ax, segs, figure_m))
    span = limits[0][1] - limits[0][0]
    _draw(ax, segs, widths * REFERENCE_HEIGHT_M / span)
    return _save(plt, fig, ax, *limits, path)


def overlay_icon(
    path: Path,
    reference: tuple[Geometry, np.ndarray],
    tree: tuple[Geometry, np.ndarray],
    view: str = "front",
    outline: tuple[np.ndarray, np.ndarray] | None = None,
) -> Path:
    """``tree`` in the branch colour over ``reference`` in the accent, plus an optional
    crown outline (z, half width, in metres) as an accent line on top; one shared extent
    (the union of all, as the catalog's component layers share theirs)."""
    ref_segs, ref_w = branch_segments(*reference, view)
    segs, widths = branch_segments(*tree, view)
    plt, fig, ax = _canvas()
    _draw(ax, ref_segs, ref_w, color=ACCENT, alpha=0.55, zorder=1)
    _draw(ax, segs, widths, zorder=2)
    pts = [ref_segs, segs]
    if outline is not None:
        z, half = outline
        for sign in (1, -1):
            ax.plot(sign * half, z, color=ACCENT, lw=1.2, zorder=3)
            pts.append(np.column_stack([sign * half, z]))
    return _save(plt, fig, ax, *limits_of(*pts), path)


def occupancy_icon(
    path: Path,
    occupancy: np.ndarray,
    height_m: float,
    outline: tuple[np.ndarray, np.ndarray] | None = None,
) -> Path:
    """Mirrored side-plane occupancy (share of the group's trees reaching each cell, see
    ``prototypes.group_occupancy``) as alpha over white in the branch colour, with the
    median crown outline (z, half width, in metres) as a thin accent line. Framed on the
    cells at least ``FRAME_SHARE`` of the trees reach."""
    from matplotlib.colors import to_rgb

    full = np.vstack([occupancy[::-1], occupancy]).T  # rows = z, columns = -x .. +x
    alpha = np.clip(full, 0, 1)
    rgba = np.zeros((*full.shape, 4))
    rgba[..., :3] = to_rgb(_BRANCH_COLOR)
    rgba[..., 3] = alpha
    x_max = OCC_X * height_m
    nz, nx = full.shape
    xs = (np.arange(nx) + 0.5) / nx * 2 * x_max - x_max
    zs = (np.arange(nz) + 0.5) / nz * height_m
    seen = alpha >= FRAME_SHARE
    pts = [np.column_stack([xs[np.where(seen)[1]], zs[np.where(seen)[0]]])]
    plt, fig, ax = _canvas()
    ax.imshow(
        rgba,
        origin="lower",
        extent=(-x_max, x_max, 0, height_m),
        interpolation="bilinear",
        zorder=1,
    )
    if outline is not None:
        z, half = outline
        ax.plot(half, z, color=ACCENT, lw=1.0, zorder=3)
        ax.plot(-half, z, color=ACCENT, lw=1.0, zorder=3)
        pts.append(np.column_stack([half, z]))
        pts.append(np.column_stack([-half, z]))
    pts.append(np.array([[0.0, 0.0], [0.0, height_m]]))
    return _save(plt, fig, ax, *limits_of(*pts), path)


def curves_figure(
    path: Path,
    curves: pd.DataFrame,
    title: str,
    trees: list[tuple[str, dict]] | None = None,
) -> Path:
    """Small multiples, one per crown decile (1 = crown base): the real median unrolled
    branch with its p25-p75 band in the accent, and optionally the first-order branches of
    other trees (``(label, profile)``, leading branches only) in the branch colour. Units are branch lengths:
    right = away from the trunk, up = up."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(2, 5, figsize=(12.5, 5.6), sharex=True, sharey=True)
    styles = ["-", "--", ":", "-."]
    for d in range(1, 11):
        ax = axes[0 if d > 5 else 1, (d - 1) % 5]
        dec = curves[curves["decile"] == d].sort_values("point")
        ax.axhline(0, color="#cccccc", lw=0.6, zorder=0)
        if len(dec):
            ax.fill_between(
                dec["h_p50"], dec["v_p25"], dec["v_p75"], color=ACCENT, alpha=0.18, lw=0
            )
            ax.plot(dec["h_p50"], dec["v_p50"], color=ACCENT, lw=2.0)
            n = int(dec["n_branches"].iloc[0])
            t = int(dec["n_trees"].iloc[0])
            ax.set_title(f"decile {d}  ({n} br., {t} trees)", fontsize=8)
        else:
            ax.set_title(f"decile {d}  (none)", fontsize=8)
        for k, (_, prof) in enumerate(trees or []):
            sel = leading(prof, d - 1)
            for c in prof["curves"][sel]:
                ax.plot(
                    c[:, 0],
                    c[:, 1],
                    color=_BRANCH_COLOR,
                    lw=0.8,
                    alpha=0.7,
                    ls=styles[k % len(styles)],
                )
        ax.set_aspect("equal")
        ax.set_xlim(-0.05, 1.05)
        ax.set_ylim(-1.0, 0.75)
        ax.tick_params(labelsize=7)
    note = "accent = real median and p25-p75 band"
    if trees:
        note += "; brown = " + ", ".join(
            f"{lbl} ({styles[k % len(styles)]})" for k, (lbl, _) in enumerate(trees)
        )
    fig.suptitle(f"{title}\n{note}", fontsize=9)
    fig.supxlabel("horizontal offset from attachment / branch length", fontsize=8)
    fig.supylabel("vertical offset / branch length", fontsize=8)
    fig.tight_layout()
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=110, facecolor="white")
    plt.close(fig)
    return path


# --- composition (PIL, tiles pasted 1:1 or uniformly scaled) ------------------------------


def compose(
    path: Path,
    rows: list[tuple[str, list[tuple[Path | None, str]]]],
    columns: list[str],
    tile_px: int = ICON_PX,
    title: str = "",
) -> Path:
    """A grid of tiles: ``rows`` = (row label, [(tile or None, caption) per column]).
    Labels and captions sit outside the tiles, never on them."""
    from PIL import Image, ImageDraw, ImageFont

    try:
        font = ImageFont.truetype("arial.ttf", max(12, tile_px // 26))
        small = ImageFont.truetype("arial.ttf", max(10, tile_px // 34))
    except OSError:
        font = small = ImageFont.load_default()
    label_w, head_h, cap_h = max(140, tile_px // 2), 34 + (30 if title else 0), 22
    width = label_w + tile_px * len(columns)
    height = head_h + (tile_px + cap_h) * len(rows)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    if title:
        draw.text((8, 6), title, fill="black", font=font)
    for j, col in enumerate(columns):
        draw.text(
            (label_w + j * tile_px + 6, head_h - 26), col, fill="black", font=font
        )
    for i, (label, tiles) in enumerate(rows):
        y = head_h + i * (tile_px + cap_h)
        draw.multiline_text((6, y + 8), label, fill="black", font=small)
        for j, (tile, caption) in enumerate(tiles):
            x = label_w + j * tile_px
            if tile is not None and Path(tile).exists():
                im = Image.open(tile).convert("RGBA")
                bg = Image.new("RGBA", im.size, "white")
                im = Image.alpha_composite(bg, im).convert("RGB")
                if im.size != (tile_px, tile_px):
                    im = im.resize((tile_px, tile_px), Image.LANCZOS)
                sheet.paste(im, (x, y))
                draw.rectangle(
                    [x, y, x + tile_px - 1, y + tile_px - 1], outline="#e4e4e4"
                )
            if caption:
                draw.text((x + 4, y + tile_px + 3), caption, fill="#444444", font=small)
    path.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(path)
    return path
