#!/usr/bin/env python3
"""Analyze USDA tree files for geometry debugging.

Parses USDA text files without USD libraries, extracting key metrics:
- Vertex count, bounding box, height/width
- Face count, degenerate face detection
- Twig instance count (from assembly PointInstancers)
- Radial profile at breast height (1.3m)

Usage:
    python src/growpy/tools/analyze_usda.py data/output/forest/norway_spruce/tree_0001/
    python src/growpy/tools/analyze_usda.py path/to/specific_stems_skeletal.usda
"""

import math
import re
import sys
from pathlib import Path


def parse_vec3f_array(text: str) -> list[tuple[float, float, float]]:
    """Extract (x, y, z) tuples from a USD point3f[] or similar array."""
    pattern = r"\(([^)]+)\)"
    points = []
    for m in re.finditer(pattern, text):
        vals = m.group(1).split(",")
        if len(vals) >= 3:
            points.append((float(vals[0]), float(vals[1]), float(vals[2])))
    return points


def parse_int_array(text: str) -> list[int]:
    """Extract integers from a USD int[] array."""
    # Match the array content between [ and ]
    arr_match = re.search(r"\[([^\]]*)\]", text)
    if not arr_match:
        return []
    content = arr_match.group(1)
    return [int(x.strip()) for x in content.split(",") if x.strip()]


def extract_array_line(filepath: Path, prefix: str) -> str | None:
    """Read a specific array line from USDA by prefix (e.g. 'point3f[] points')."""
    with open(filepath) as f:
        collecting = False
        result = []
        for line in f:
            if not collecting and prefix in line:
                collecting = True
                result.append(line)
                if "]" in line:
                    return "".join(result)
                continue
            if collecting:
                result.append(line)
                if "]" in line:
                    return "".join(result)
    return "".join(result) if result else None


def analyze_stems(filepath: Path) -> dict:
    """Analyze a _stems_skeletal.usda or _stems_static.usda file."""
    stats = {"file": str(filepath), "type": "stems"}

    # Points
    points_text = extract_array_line(filepath, "point3f[] points")
    if points_text:
        points = parse_vec3f_array(points_text)
        stats["vertex_count"] = len(points)

        if points:
            xs = [p[0] for p in points]
            ys = [p[1] for p in points]  # Y = up in Grove/USD
            zs = [p[2] for p in points]
            stats["bbox_min"] = (min(xs), min(ys), min(zs))
            stats["bbox_max"] = (max(xs), max(ys), max(zs))
            stats["height"] = max(ys) - min(ys)
            stats["width_x"] = max(xs) - min(xs)
            stats["width_z"] = max(zs) - min(zs)

            # Radial profile at breast height (1.3m +/- 0.1m)
            breast_pts = [p for p in points if 1.2 <= p[1] <= 1.4]
            if breast_pts:
                bx = [p[0] for p in breast_pts]
                bz = [p[2] for p in breast_pts]
                cx = (min(bx) + max(bx)) / 2
                cz = (min(bz) + max(bz)) / 2
                radii = [
                    math.sqrt((p[0] - cx) ** 2 + (p[2] - cz) ** 2) for p in breast_pts
                ]
                stats["dbh_approx_m"] = 2 * max(radii) if radii else 0
                stats["breast_height_vertices"] = len(breast_pts)
                stats["breast_radius_mean"] = sum(radii) / len(radii)
                stats["breast_radius_max"] = max(radii)
            else:
                stats["dbh_approx_m"] = None
                stats["breast_height_vertices"] = 0

            # Check for extreme radii (branches thicker than trunk)
            # Sample radial distances at different heights
            height_slices = {}
            for p in points:
                h_bin = round(p[1], 0)
                if h_bin not in height_slices:
                    height_slices[h_bin] = []
                height_slices[h_bin].append(math.sqrt(p[0] ** 2 + p[2] ** 2))
            stats["radial_profile"] = {
                h: {"count": len(rs), "max_r": max(rs), "mean_r": sum(rs) / len(rs)}
                for h, rs in sorted(height_slices.items())
            }

    # Face counts
    counts_text = extract_array_line(filepath, "int[] faceVertexCounts")
    if counts_text:
        counts = parse_int_array(counts_text)
        stats["face_count"] = len(counts)
        non_tri = [c for c in counts if c != 3]
        stats["non_triangle_faces"] = len(non_tri)
        if non_tri:
            stats["non_triangle_values"] = sorted(set(non_tri))

    # Joint count (skeleton)
    joints_text = extract_array_line(filepath, "uniform token[] joints")
    if joints_text:
        joint_count = joints_text.count('"') // 2
        stats["joint_count"] = joint_count

    return stats


def analyze_assembly(filepath: Path) -> dict:
    """Analyze an _assembly.usda file."""
    stats = {"file": str(filepath), "type": "assembly"}

    content = filepath.read_text()

    # Check mesh type
    mesh_match = re.search(r'meshType = "(\w+)"', content)
    stats["mesh_type"] = mesh_match.group(1) if mesh_match else "unknown"

    # Check for twig prototypes
    stats["has_twigs"] = "TwigPrototypes" in content

    # Count PointInstancer instances
    pos_match = re.search(
        r"point3f\[\] positions\s*=\s*\[([^\]]*)\]", content, re.DOTALL
    )
    if pos_match:
        pos_text = pos_match.group(1)
        instance_count = pos_text.count("(")
        stats["twig_instances"] = instance_count
    else:
        stats["twig_instances"] = 0

    # Referenced stems file
    ref_match = re.search(r"references = @\./(.*?)@", content)
    stats["stems_ref"] = ref_match.group(1) if ref_match else None

    return stats


def print_stats(stats: dict) -> None:
    """Pretty-print analysis results."""
    print(f"\n{'=' * 60}")
    print(f"File: {stats['file']}")
    print(f"Type: {stats['type']}")
    print(f"{'=' * 60}")

    if stats["type"] == "stems":
        print(f"  Vertices:      {stats.get('vertex_count', '?')}")
        print(f"  Faces:         {stats.get('face_count', '?')}")
        non_tri = stats.get("non_triangle_faces", 0)
        if non_tri:
            print(
                f"  NON-TRIANGLE:  {non_tri} faces! values={stats.get('non_triangle_values')}"
            )
        print(f"  Joints:        {stats.get('joint_count', '?')}")
        print(f"  Height:        {stats.get('height', '?'):.2f} m")
        print(f"  Width X:       {stats.get('width_x', '?'):.2f} m")
        print(f"  Width Z:       {stats.get('width_z', '?'):.2f} m")
        dbh = stats.get("dbh_approx_m")
        if dbh is not None:
            print(f"  DBH (approx):  {dbh:.4f} m ({dbh * 100:.1f} cm)")
            print(f"    breast verts: {stats.get('breast_height_vertices')}")
            print(f"    mean radius:  {stats.get('breast_radius_mean', 0):.4f} m")
            print(f"    max radius:   {stats.get('breast_radius_max', 0):.4f} m")
        else:
            print("  DBH:           tree too short for breast height measurement")

        profile = stats.get("radial_profile", {})
        if profile:
            print("\n  Height | Verts | Max Radius | Mean Radius")
            print("  -------+-------+------------+------------")
            for h in sorted(profile.keys()):
                r = profile[h]
                print(
                    f"  {h:5.0f}m | {r['count']:5d} | {r['max_r']:10.4f} | {r['mean_r']:10.4f}"
                )

    elif stats["type"] == "assembly":
        print(f"  Mesh type:     {stats.get('mesh_type')}")
        print(f"  Has twigs:     {stats.get('has_twigs')}")
        print(f"  Twig instances:{stats.get('twig_instances')}")
        print(f"  Stems ref:     {stats.get('stems_ref')}")


def analyze_tree_dir(tree_dir: Path) -> None:
    """Analyze all USDA files in a tree output directory."""
    usda_files = sorted(tree_dir.glob("*.usda"))
    if not usda_files:
        print(f"No .usda files found in {tree_dir}")
        return

    for f in usda_files:
        if "assembly" in f.name:
            stats = analyze_assembly(f)
        elif "stems" in f.name:
            stats = analyze_stems(f)
        else:
            continue
        print_stats(stats)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze USDA tree export files.")
    parser.add_argument("target", type=Path, help="Path to tree dir or USDA file")
    args = parser.parse_args()

    target = args.target

    if target.is_dir():
        # Could be a tree dir or a species dir with multiple trees
        tree_dirs = sorted(target.glob("tree_*"))
        if tree_dirs:
            for td in tree_dirs:
                analyze_tree_dir(td)
        else:
            analyze_tree_dir(target)
    elif target.is_file() and target.suffix == ".usda":
        if "assembly" in target.name:
            print_stats(analyze_assembly(target))
        else:
            print_stats(analyze_stems(target))
    else:
        print(f"Not found or not a .usda file: {target}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
