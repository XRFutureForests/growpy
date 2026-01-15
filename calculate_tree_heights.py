"""Calculate tree heights from USDA files in the output folder.

This script scans the data/output directory for tree USDA files and calculates
their height based on the Z coordinates of mesh points.
"""

import re
from pathlib import Path


def extract_points_from_usda(file_path: Path) -> list[tuple[float, float, float]]:
    """Extract point3f coordinates from a USDA file.

    Args:
        file_path: Path to the USDA file.

    Returns:
        List of (x, y, z) tuples representing vertex positions.
    """
    content = file_path.read_text()
    pattern = r"point3f\[\] points = \[([^\]]+)\]"
    match = re.search(pattern, content)
    if not match:
        return []

    points_str = match.group(1)
    point_pattern = r"\(([^)]+)\)"
    points = []
    for point_match in re.finditer(point_pattern, points_str):
        coords = point_match.group(1).split(",")
        if len(coords) == 3:
            x, y, z = float(coords[0]), float(coords[1]), float(coords[2])
            points.append((x, y, z))
    return points


def calculate_height(points: list[tuple[float, float, float]]) -> float:
    """Calculate tree height from points (max Z - min Z).

    Args:
        points: List of (x, y, z) coordinate tuples.

    Returns:
        Height in meters (Z-up axis).
    """
    if not points:
        return 0.0
    z_values = [p[2] for p in points]
    return max(z_values) - min(z_values)


def find_main_tree_files(output_dir: Path) -> list[Path]:
    """Find main tree skeletal USDA files (excluding twigs).

    Args:
        output_dir: Path to the output directory.

    Returns:
        List of paths to main tree USDA files.
    """
    tree_files = []
    for usda_file in output_dir.rglob("*_skeletal.usda"):
        if "twig" not in usda_file.name.lower():
            tree_files.append(usda_file)
    return sorted(tree_files)


def parse_tree_info(file_path: Path) -> dict:
    """Extract species and tree ID from file path.

    Args:
        file_path: Path to the tree USDA file.

    Returns:
        Dict with species, tree_id, and forest info.
    """
    parts = file_path.parts
    tree_folder_idx = next(
        (i for i, p in enumerate(parts) if p.startswith("tree_")), None
    )
    if tree_folder_idx is None:
        return {"species": "unknown", "tree_id": "unknown", "forest": "unknown"}

    tree_id = parts[tree_folder_idx]
    species = parts[tree_folder_idx - 1] if tree_folder_idx > 0 else "unknown"
    forest = parts[tree_folder_idx - 2] if tree_folder_idx > 1 else "unknown"
    return {"species": species, "tree_id": tree_id, "forest": forest}


def main():
    project_root = Path(__file__).parent.parent.parent.parent
    output_dir = project_root / "data" / "output"

    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}")
        return

    tree_files = find_main_tree_files(output_dir)
    if not tree_files:
        print("No tree files found.")
        return

    print(f"Found {len(tree_files)} tree files\n")
    print(f"{'Species':<20} {'Tree ID':<12} {'Height (m)':<12} {'Forest'}")
    print("-" * 60)

    results = []
    for file_path in tree_files:
        info = parse_tree_info(file_path)
        points = extract_points_from_usda(file_path)
        height = calculate_height(points)

        results.append({**info, "height": height, "file": file_path})
        print(
            f"{info['species']:<20} {info['tree_id']:<12} {height:<12.2f} {info['forest']}"
        )

    print("\n" + "=" * 60)
    print("Summary by Species:")
    print("-" * 60)

    species_heights = {}
    for r in results:
        species = r["species"]
        if species not in species_heights:
            species_heights[species] = []
        species_heights[species].append(r["height"])

    for species, heights in sorted(species_heights.items()):
        avg = sum(heights) / len(heights)
        min_h = min(heights)
        max_h = max(heights)
        print(
            f"{species:<20} Count: {len(heights):<3} "
            f"Avg: {avg:<8.2f} Min: {min_h:<8.2f} Max: {max_h:.2f}"
        )


if __name__ == "__main__":
    main()
