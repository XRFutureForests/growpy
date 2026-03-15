#!/usr/bin/env python3
"""Visualize tree geometry from USDA stems files as 2D side-view images.

Reads exported USDA stems files and renders branch structure as 2D projections
for quick visual evaluation without Unreal Engine.

Usage:
    python src/growpy/tools/visualize_tree.py                     # All trees in output dir
    python src/growpy/tools/visualize_tree.py data/output/forest   # Specific output dir
    python src/growpy/tools/visualize_tree.py path/to/stems.usda   # Single file
"""

import re
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def parse_usda_points(usda_path: Path) -> np.ndarray:
    """Extract vertex positions from a USDA stems file.

    Returns:
        Nx3 numpy array of (x, y, z) positions in meters.
    """
    content = usda_path.read_text(encoding="utf-8")

    match = re.search(r'point3f\[\] points\s*=\s*\[', content)
    if not match:
        return np.empty((0, 3))

    start = match.end()
    # Find matching closing bracket (skip nested)
    depth = 1
    pos = start
    while depth > 0 and pos < len(content):
        if content[pos] == '[':
            depth += 1
        elif content[pos] == ']':
            depth -= 1
        pos += 1

    points_str = content[start:pos - 1]

    # Parse tuples: (x, y, z)
    coords = re.findall(r'\(\s*([^)]+)\)', points_str)
    if not coords:
        return np.empty((0, 3))

    points = []
    for c in coords:
        vals = c.split(',')
        if len(vals) >= 3:
            points.append([float(v.strip()) for v in vals[:3]])

    return np.array(points) if points else np.empty((0, 3))


def parse_usda_faces(usda_path: Path) -> list:
    """Extract face vertex indices from a USDA stems file.

    Returns:
        List of face index tuples.
    """
    content = usda_path.read_text(encoding="utf-8")

    match = re.search(r'int\[\] faceVertexIndices\s*=\s*\[([^\]]+)\]', content)
    if not match:
        return []

    indices = [int(x.strip()) for x in match.group(1).split(',')]

    # All faces are triangles (faceVertexCounts all = 3)
    faces = []
    for i in range(0, len(indices), 3):
        if i + 2 < len(indices):
            faces.append((indices[i], indices[i + 1], indices[i + 2]))

    return faces


def render_tree_side_view(
    points: np.ndarray,
    faces: list,
    title: str = "Tree Side View",
    output_path: Path = None,
    figsize: tuple = (8, 12),
) -> None:
    """Render a 2D side view of tree geometry.

    Projects onto XZ plane (side view, Z = up).
    Draws triangle edges as thin lines for branch structure.
    """
    if len(points) == 0:
        print(f"  No points to render for {title}")
        return

    fig, axes = plt.subplots(1, 2, figsize=figsize)

    # Side view: X vs Z
    ax_side = axes[0]
    ax_side.set_title(f"{title}\nSide View (XZ)")
    ax_side.set_xlabel("X (m)")
    ax_side.set_ylabel("Z / Height (m)")
    ax_side.set_aspect("equal")

    # Draw triangle edges
    edges = set()
    for f in faces:
        for i in range(3):
            edge = tuple(sorted([f[i], f[(i + 1) % 3]]))
            edges.add(edge)

    # Draw edges as line segments (batched for performance)
    x_coords = points[:, 0]
    z_coords = points[:, 2]

    # For large meshes, subsample edges for performance
    edge_list = list(edges)
    max_edges = 50000
    if len(edge_list) > max_edges:
        rng = np.random.default_rng(42)
        indices = rng.choice(len(edge_list), max_edges, replace=False)
        edge_list = [edge_list[i] for i in indices]

    segments_xz = []
    for e0, e1 in edge_list:
        if e0 < len(points) and e1 < len(points):
            segments_xz.append([(x_coords[e0], z_coords[e0]),
                                (x_coords[e1], z_coords[e1])])

    from matplotlib.collections import LineCollection
    lc_side = LineCollection(segments_xz, linewidths=0.15, colors='#2d5016', alpha=0.6)
    ax_side.add_collection(lc_side)
    ax_side.autoscale()

    # Front view: Y vs Z
    ax_front = axes[1]
    ax_front.set_title(f"{title}\nFront View (YZ)")
    ax_front.set_xlabel("Y (m)")
    ax_front.set_ylabel("Z / Height (m)")
    ax_front.set_aspect("equal")

    y_coords = points[:, 1]
    segments_yz = []
    for e0, e1 in edge_list:
        if e0 < len(points) and e1 < len(points):
            segments_yz.append([(y_coords[e0], z_coords[e0]),
                                (y_coords[e1], z_coords[e1])])

    lc_front = LineCollection(segments_yz, linewidths=0.15, colors='#2d5016', alpha=0.6)
    ax_front.add_collection(lc_front)
    ax_front.autoscale()

    # Add stats
    height = z_coords.max() - z_coords.min()
    width_x = x_coords.max() - x_coords.min()
    width_y = y_coords.max() - y_coords.min()
    stats_text = (
        f"Verts: {len(points):,}  Faces: {len(faces):,}\n"
        f"Height: {height:.1f}m  Width: {max(width_x, width_y):.1f}m"
    )
    fig.text(0.5, 0.02, stats_text, ha="center", fontsize=9, family="monospace")

    plt.tight_layout(rect=[0, 0.05, 1, 0.98])

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fig.savefig(output_path, dpi=150, bbox_inches="tight")
        print(f"  Saved: {output_path}")
        plt.close(fig)
    else:
        plt.show()


def visualize_stems_file(usda_path: Path, output_dir: Path = None) -> None:
    """Visualize a single stems USDA file."""
    print(f"Processing: {usda_path.name}")

    points = parse_usda_points(usda_path)
    faces = parse_usda_faces(usda_path)

    if len(points) == 0:
        print(f"  No geometry found in {usda_path}")
        return

    # Build title from filename
    name = usda_path.stem.replace("_stems_skeletal", "").replace("_stems_static", "")
    title = name.replace("_", " ").title()

    # Output path
    if output_dir:
        png_path = output_dir / f"{name}_preview.png"
    else:
        png_path = usda_path.parent / f"{name}_preview.png"

    render_tree_side_view(points, faces, title=title, output_path=png_path)


def main():
    """Main entry point for tree visualization."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Visualize tree geometry from USDA stems files",
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to USDA file or output directory (default: data/output/forest)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Directory to save PNG previews (default: alongside USDA files)",
    )

    args = parser.parse_args()

    # Resolve path
    script_dir = Path(__file__).parent.parent.parent.parent
    target = args.path or script_dir / "data" / "output" / "forest"
    if not target.is_absolute():
        target = script_dir / target

    if not target.exists():
        print(f"Path not found: {target}")
        return

    if target.is_file() and target.suffix == ".usda":
        # Single file
        visualize_stems_file(target, args.output_dir)
    else:
        # Directory: find all stems files
        stems_files = sorted(target.rglob("*_stems_skeletal.usda"))
        if not stems_files:
            stems_files = sorted(target.rglob("*_stems_static.usda"))
        if not stems_files:
            print(f"No stems USDA files found in {target}")
            return

        print(f"Found {len(stems_files)} stems files\n")
        for sf in stems_files:
            visualize_stems_file(sf, args.output_dir)

    print("\nDone.")


if __name__ == "__main__":
    main()
