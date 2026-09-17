#!/usr/bin/env python3
"""Analyze USDA tree files for geometry debugging.

Parses USDA text files without USD libraries, extracting key metrics:
- Vertex count, bounding box, height/width
- Face count, degenerate face detection
- Twig instance count (from assembly PointInstancers)
- Radial profile at breast height (1.3m)

The text-based parsing above only works on ``.usda`` (ASCII) files. The
live default is ``[export] usd_format = "usdc"`` (binary) -- see
``config/forest.toml`` -- so ``--triangle-budget`` below uses the ``pxr``
USD API instead, which handles both formats identically and works on the
composed (reference-resolved) stage rather than raw text.

Usage:
    python src/growpy/tools/analyze_usda.py data/output/forest/norway_spruce/tree_0001/
    python src/growpy/tools/analyze_usda.py path/to/specific_stems_skeletal.usda
    python src/growpy/tools/analyze_usda.py --triangle-budget path/to/assembly.usdc \
        --json out.json
"""

import json
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
                f"  NON-TRIANGLE:  {non_tri} faces! "
                f"values={stats.get('non_triangle_values')}"
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
                    f"  {h:5.0f}m | {r['count']:5d} | {r['max_r']:10.4f} | "
                    f"{r['mean_r']:10.4f}"
                )

    elif stats["type"] == "assembly":
        print(f"  Mesh type:     {stats.get('mesh_type')}")
        print(f"  Has twigs:     {stats.get('has_twigs')}")
        print(f"  Twig instances:{stats.get('twig_instances')}")
        print(f"  Stems ref:     {stats.get('stems_ref')}")


# --- Triangle-budget report (pxr-based, works on .usda and .usdc) -------
#
# Every twig prototype ships a sidecar next to its source .usda, named
# ``<twig_asset_name>_leaf_area.json`` (produced by the XRFF-274 leaf-area
# measurement pass), e.g.:
#   {"leaf_area_m2": 0.1088, "leaf_faces": 107876, "total_faces": 107876,
#    "leaf_material_indices": [0]}
# where ``<twig_asset_name>`` is the prototype's file stem with
# "_skeletal"/"_static" stripped (see io/usd/assembly_export.py, which
# names both the reference target AND the prototype's sole child prim
# exactly this). ``total_faces`` from the sidecar is preferred over
# counting faces from the composed USD mesh (cheap, and the source of
# truth used elsewhere in the pipeline); the USD mesh is only walked as a
# fallback when a sidecar is missing.

_SIDECAR_CACHE: dict[str, dict | None] = {}


def _default_twigs_root() -> Path:
    from growpy.config.paths import get_project_root

    return get_project_root() / "data" / "assets" / "twigs"


def _find_leaf_area_sidecar(twig_asset_name: str, twigs_root: Path) -> dict | None:
    """Look up ``<twig_asset_name>_leaf_area.json`` under ``twigs_root``.

    Cached per (twigs_root, twig_asset_name) since a single triangle-budget
    run over a forest can re-encounter the same prototype across many
    assemblies (up to ~18 prototypes per species, ~97 sidecars total).
    """
    cache_key = f"{twigs_root}::{twig_asset_name}"
    if cache_key in _SIDECAR_CACHE:
        return _SIDECAR_CACHE[cache_key]

    result = None
    if twigs_root.exists():
        matches = list(twigs_root.rglob(f"{twig_asset_name}_leaf_area.json"))
        if matches:
            try:
                result = json.loads(matches[0].read_text())
            except (json.JSONDecodeError, OSError) as e:
                print(f"  Warning: could not read sidecar {matches[0]}: {e}")
                result = None

    _SIDECAR_CACHE[cache_key] = result
    return result


def _count_mesh_faces_pxr(prim) -> int:
    """Sum faceVertexCounts length across every Mesh prim under ``prim``."""
    from pxr import Usd, UsdGeom

    total = 0
    for p in Usd.PrimRange(prim):
        if p.GetTypeName() == "Mesh":
            mesh = UsdGeom.Mesh(p)
            attr = mesh.GetFaceVertexCountsAttr()
            if attr:
                counts = attr.Get()
                if counts:
                    total += len(counts)
    return total


def analyze_triangle_budget(
    assembly_path: Path, twigs_root: Path | None = None
) -> dict:
    """Report the twig-instance triangle budget for a Nanite assembly.

    Uses the ``pxr`` USD API (works for both ``.usda`` and ``.usdc``,
    unlike the regex-based helpers above) on the composed stage, so
    prototype references are already resolved.

    Requires the growpy conda env: ``pxr`` only imports safely after
    ``growpy.utils.pxr_init.ensure_pxr_with_unreal_schema()`` has run (a
    bare ``from pxr import Usd`` fails with a DLL error outside it). That
    call is made lazily inside this function so importing this module
    stays cheap for callers that only need the text-parsing helpers above.
    """
    from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()
    from pxr import Usd, UsdGeom, UsdSkel

    if twigs_root is None:
        twigs_root = _default_twigs_root()

    stage = Usd.Stage.Open(str(assembly_path))
    if stage is None:
        raise ValueError(f"Could not open USD stage: {assembly_path}")

    stats: dict = {
        "file": str(assembly_path),
        "type": "triangle_budget",
        "file_size_bytes": assembly_path.stat().st_size,
    }

    instancer_prim = None
    for prim in stage.Traverse():
        if prim.GetTypeName() == "PointInstancer":
            instancer_prim = prim
            break

    if instancer_prim is None:
        stats["twig_instances"] = 0
        stats["twig_instances_per_prototype"] = {}
        stats["prototype_faces"] = {}
        stats["prototype_face_source"] = {}
        stats["expanded_triangles"] = 0
        stats["leaf_area_m2"] = 0.0
        stats["leaf_area_m2_incomplete"] = False
    else:
        instancer = UsdGeom.PointInstancer(instancer_prim)
        proto_indices = list(instancer.GetProtoIndicesAttr().Get() or [])
        stats["twig_instances"] = len(proto_indices)

        from collections import Counter

        idx_counts = Counter(proto_indices)
        proto_targets = instancer.GetPrototypesRel().GetTargets()

        instances_per_proto: dict[str, int] = {}
        prototype_faces: dict[str, int] = {}
        prototype_face_source: dict[str, str] = {}
        expanded_triangles = 0
        leaf_area_m2 = 0.0
        leaf_area_incomplete = False

        for i, proto_path in enumerate(proto_targets):
            proto_prim = stage.GetPrimAtPath(proto_path)
            proto_name = proto_prim.GetName() if proto_prim else str(proto_path)
            n_instances = idx_counts.get(i, 0)
            instances_per_proto[proto_name] = n_instances

            # Prototype prims wrap a single child named after the twig
            # asset (see io/usd/assembly_export.py: the reference target
            # is always "{proto_name_xform}/{twig_asset_name}"). That
            # child's name IS the sidecar's key.
            children = list(proto_prim.GetChildren()) if proto_prim else []
            twig_asset_name = children[0].GetName() if children else proto_name

            sidecar = _find_leaf_area_sidecar(twig_asset_name, twigs_root)
            if sidecar is not None and "total_faces" in sidecar:
                face_count = int(sidecar["total_faces"])
                prototype_face_source[proto_name] = "sidecar"
            else:
                face_count = _count_mesh_faces_pxr(children[0]) if children else 0
                prototype_face_source[proto_name] = "usd_mesh"

            prototype_faces[proto_name] = face_count
            expanded_triangles += n_instances * face_count

            if sidecar is not None and "leaf_area_m2" in sidecar:
                leaf_area_m2 += n_instances * float(sidecar["leaf_area_m2"])
            else:
                leaf_area_incomplete = True

        stats["twig_instances_per_prototype"] = instances_per_proto
        stats["prototype_faces"] = prototype_faces
        stats["prototype_face_source"] = prototype_face_source
        stats["expanded_triangles"] = expanded_triangles
        stats["leaf_area_m2"] = leaf_area_m2
        stats["leaf_area_m2_incomplete"] = leaf_area_incomplete

    stats["leaf_area_m2_is_sanity_check_only"] = True
    stats["leaf_area_m2_caveat"] = (
        "Direction-of-error signal only, NOT a pass/fail gate. Prototypes "
        "are biased in physical size (e.g. the shared Pacific silver fir "
        "spray measures 0.109 m^2 vs 0.023 m^2 for one-leaved ash), so "
        "leaf area computed by multiplying instance counts through "
        "whichever prototypes got assigned is distorted relative to the "
        "tree's true foliage area."
    )

    # Skeleton joints: report the primary (tree) skeleton specifically,
    # since that's what drives UE skeletal-mesh import limits -- not the
    # small, shared, per-twig-prototype skeletons (usually 1 joint each).
    # Full breakdown is still included for transparency.
    skeletons = []
    for prim in stage.Traverse():
        if prim.IsA(UsdSkel.Skeleton):
            joints_attr = UsdSkel.Skeleton(prim).GetJointsAttr()
            joints = joints_attr.Get() if joints_attr else None
            skeletons.append(
                {
                    "path": str(prim.GetPath()),
                    "joint_count": len(joints) if joints else 0,
                }
            )
    tree_skeletons = [s for s in skeletons if "TwigPrototypes" not in s["path"]]
    primary = (
        tree_skeletons[0] if tree_skeletons else (skeletons[0] if skeletons else None)
    )
    stats["skeleton_joints"] = primary["joint_count"] if primary else 0
    stats["skeleton_joints_by_prim"] = skeletons

    # Referenced stems file(s): pulled from the composed stage's actual
    # used layers rather than regex, so this works for both formats and
    # doesn't depend on a particular reference-syntax convention.
    stems_files = []
    for layer in stage.GetUsedLayers():
        real_path = layer.realPath
        if not real_path:
            continue
        p = Path(real_path)
        if p.resolve() == assembly_path.resolve():
            continue
        if "stems" in p.stem.lower():
            stems_files.append(p)
    stats["stems_ref_files"] = []
    for p in stems_files:
        if not p.exists():
            continue
        stems_stage = Usd.Stage.Open(str(p))
        triangle_count = (
            _count_mesh_faces_pxr(stems_stage.GetPseudoRoot()) if stems_stage else 0
        )
        stats["stems_ref_files"].append(
            {
                "file": str(p),
                "file_size_bytes": p.stat().st_size,
                "triangle_count": triangle_count,
            }
        )

    return stats


def print_triangle_budget(stats: dict) -> None:
    """Pretty-print an ``analyze_triangle_budget`` result."""
    print(f"\n{'=' * 60}")
    print(f"File: {stats['file']}")
    print("Type: triangle_budget")
    print(f"{'=' * 60}")
    print(f"  File size:          {stats['file_size_bytes']:,} bytes")
    print(f"  Twig instances:     {stats['twig_instances']:,}")
    print(f"  Expanded triangles: {stats['expanded_triangles']:,}")
    print(f"  Skeleton joints:    {stats['skeleton_joints']}")
    print(
        f"  Leaf area (sanity check only, NOT a gate): "
        f"{stats['leaf_area_m2']:.4f} m^2"
        + (
            " [INCOMPLETE: some prototypes had no sidecar]"
            if stats.get("leaf_area_m2_incomplete")
            else ""
        )
    )

    proto_faces = stats.get("prototype_faces", {})
    if proto_faces:
        print("\n  Prototype        | Instances | Faces      | Source")
        print("  -----------------+-----------+------------+--------")
        counts = stats.get("twig_instances_per_prototype", {})
        sources = stats.get("prototype_face_source", {})
        for name, faces in proto_faces.items():
            print(
                f"  {name[:17]:<17}| {counts.get(name, 0):>9,} | {faces:>10,} | "
                f"{sources.get(name, '?')}"
            )

    for sf in stats.get("stems_ref_files", []):
        print(
            f"\n  Stems ref: {sf['file']} ({sf['file_size_bytes']:,} bytes, "
            f"{sf['triangle_count']:,} triangles)"
        )


def _find_assembly_files(target: Path) -> list[Path]:
    """Locate assembly USD files (.usda or .usdc) under ``target``."""
    if target.is_file():
        return [target] if "assembly" in target.name else []
    if target.is_dir():
        files = set(target.rglob("*assembly*.usda")) | set(
            target.rglob("*assembly*.usdc")
        )
        return sorted(files)
    return []


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
    parser.add_argument(
        "--triangle-budget",
        action="store_true",
        help="Report twig-instance triangle budget for assembly file(s) under "
        "target (.usda or .usdc). Uses pxr -- run inside the growpy conda env.",
    )
    parser.add_argument(
        "--json",
        type=Path,
        default=None,
        help="With --triangle-budget, write the record(s) to this JSON file.",
    )
    parser.add_argument(
        "--twigs-dir",
        type=Path,
        default=None,
        help="With --triangle-budget, override the twig asset root used for "
        "leaf-area/face sidecar lookup (default: <project_root>/data/assets/twigs).",
    )
    args = parser.parse_args()

    target = args.target

    if args.triangle_budget:
        assembly_files = _find_assembly_files(target)
        if not assembly_files:
            print(f"No assembly USD files found under {target}")
            return 1
        records = []
        for f in assembly_files:
            try:
                stats = analyze_triangle_budget(f, twigs_root=args.twigs_dir)
            except Exception as e:
                print(f"Error analyzing {f}: {e}")
                continue
            print_triangle_budget(stats)
            records.append(stats)
        if args.json is not None:
            args.json.parent.mkdir(parents=True, exist_ok=True)
            args.json.write_text(json.dumps(records, indent=2))
            print(f"\nWrote JSON: {args.json}")
        return 0 if records else 1

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
