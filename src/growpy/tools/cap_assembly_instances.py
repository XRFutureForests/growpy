"""Post-process assembly USD files to cap PointInstancer instances.

Re-running the full Grove simulation is expensive. This script reads existing
assembly USD files, detects oversized PointInstancers, and trims them down to
``max_assembly_instances`` from growpy.toml (default 5000). Arrays trimmed in
parallel: positions, orientations, scales, protoIndices, bindJoints,
bindJointWeights.

Usage:
    conda activate growpy
    python src/growpy/tools/cap_assembly_instances.py [--max N] [--dry-run]
"""

import argparse
import logging
import random
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def cap_assembly(assembly_path: Path, max_instances: int, dry_run: bool = False):
    """Trim PointInstancer in a single assembly if it exceeds max_instances."""
    from growpy.utils.pxr_init import ensure_pxr_with_unreal_schema

    ensure_pxr_with_unreal_schema()
    from pxr import Sdf, Usd, UsdGeom

    stage = Usd.Stage.Open(str(assembly_path))
    if not stage:
        logger.warning("Cannot open %s", assembly_path.name)
        return False

    # Find PointInstancer
    instancer_prim = None
    for prim in stage.Traverse():
        if prim.GetTypeName() == "PointInstancer":
            instancer_prim = prim
            break

    if not instancer_prim:
        return False

    instancer = UsdGeom.PointInstancer(instancer_prim)
    positions = instancer.GetPositionsAttr().Get()
    if not positions:
        return False

    n = len(positions)
    if n <= max_instances:
        logger.info("  %s: %d instances (OK)", assembly_path.name, n)
        return False

    logger.info("  %s: %d -> %d instances", assembly_path.name, n, max_instances)
    if dry_run:
        return True

    # Select random subset (deterministic)
    random.seed(42)
    keep = sorted(random.sample(range(n), max_instances))

    # Trim parallel arrays
    orientations = instancer.GetOrientationsAttr().Get()
    scales = instancer.GetScalesAttr().Get()
    proto_indices = instancer.GetProtoIndicesAttr().Get()

    instancer.GetPositionsAttr().Set([positions[i] for i in keep])
    instancer.GetOrientationsAttr().Set([orientations[i] for i in keep])
    instancer.GetScalesAttr().Set([scales[i] for i in keep])
    instancer.GetProtoIndicesAttr().Set([proto_indices[i] for i in keep])

    # Trim bind joints/weights (may have elementSize > 1)
    bind_joints_attr = instancer_prim.GetAttribute(
        "primvars:unreal:naniteAssembly:bindJoints"
    )
    bind_weights_attr = instancer_prim.GetAttribute(
        "primvars:unreal:naniteAssembly:bindJointWeights"
    )

    if bind_joints_attr and bind_joints_attr.Get():
        joints = list(bind_joints_attr.Get())
        weights = list(bind_weights_attr.Get())
        elem_size = bind_joints_attr.GetMetadata("elementSize") or 1

        new_joints = []
        new_weights = []
        for i in keep:
            start = i * elem_size
            new_joints.extend(joints[start : start + elem_size])
            new_weights.extend(weights[start : start + elem_size])

        bind_joints_attr.Set(new_joints)
        bind_weights_attr.Set(new_weights)

    stage.GetRootLayer().Save()
    return True


def main():
    parser = argparse.ArgumentParser(description="Cap assembly twig instances")
    parser.add_argument(
        "--max", type=int, default=0, help="Max instances (0 = from config)"
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    max_inst = args.max
    if max_inst <= 0:
        from growpy.config import get_config

        max_inst = get_config().export_max_assembly_instances
    if max_inst <= 0:
        logger.error("max_assembly_instances is 0 (unlimited). Use --max N.")
        return

    forest_dir = Path("data/output/forest")
    assemblies = sorted(forest_dir.rglob("*_assembly.usda"))
    if not assemblies:
        logger.error("No assembly files found in %s", forest_dir)
        return

    logger.info("Capping assemblies to %d instances:", max_inst)
    trimmed = 0
    for f in assemblies:
        if cap_assembly(f, max_inst, dry_run=args.dry_run):
            trimmed += 1

    action = "would trim" if args.dry_run else "trimmed"
    logger.info("Done: %s %d of %d assemblies", action, trimmed, len(assemblies))


if __name__ == "__main__":
    main()
