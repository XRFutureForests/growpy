"""Re-plan the PVE graphs of a finished forest export, without re-running step 4.

Step 4 plans the graphs itself at the end of a run (``[unreal]
generate_pve_graphs``). Every later change that only touches the FOLIAGE --
a species' ``fullness``, its palette tier, a pose, a ladder or compound
setting in ``config/pve_calibration.toml`` -- is a plan change: the growth
JSONs are unchanged, so this re-solves and re-authors the scripts in place.
Run the scripts with ``growpy-ue-exec`` afterwards (asset script first, then
the graph script) and export with ``growpy-pve-export``.

Usage::

    growpy-pve-plan                              # data/output/forest, all species
    growpy-pve-plan --species silver_fir         # one species' graphs only
    growpy-pve-plan --shape NONE                 # a fast wiring/count probe
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

logger = logging.getLogger("growpy.pve_plan")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--forest-root",
        type=Path,
        default=None,
        help="the export root (default: [general] output_dir, data/output/forest)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="where the scripts and manifest go (default: <root>/unreal_scripts)",
    )
    parser.add_argument(
        "--species",
        nargs="*",
        default=None,
        help="standardized names to plan; default: every species under the root",
    )
    parser.add_argument(
        "--shape",
        default="PRESERVE_AREA",
        choices=("PRESERVE_AREA", "VOXELIZE", "NONE"),
        help=(
            "Nanite shape preservation on the Export nodes (default PRESERVE_AREA; "
            "VOXELIZE has no voxel-size knob and erased the card foliage of every "
            "tree in the 2026-09-16 run)"
        ),
    )
    parser.add_argument(
        "--collision",
        default="ALL_GENERATIONS",
        choices=("ALL_GENERATIONS", "TRUNK_ONLY", "NONE"),
    )
    parser.add_argument("--calibration", type=Path, default=None)
    parser.add_argument(
        "--max-instances",
        type=int,
        default=60_000,
        help=(
            "cap on foliage instances per tree (default 60000). The Nanite "
            "build of a Voxelize export asserts (Bits <= Mask, "
            "NaniteResources.h:93) above roughly 40k instances of a 2-material "
            "palette -- linden r16_h25m at 57.6k, 2026-09-16 -- so a species "
            "that trips it is re-planned lower"
        ),
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    from growpy.config.core import get_config
    from growpy.config.paths import get_project_root
    from growpy.io.unreal.pve_graph_plan import plan_pve_graphs

    config = get_config()
    forest_root = args.forest_root or config.output_dir
    if not forest_root.is_absolute():
        forest_root = get_project_root() / forest_root
    output_dir = args.output_dir or forest_root / "unreal_scripts"

    plan = plan_pve_graphs(
        output_dir,
        forest_root,
        content_root=config.unreal_pve_content_root,
        graph_folder=f"{config.unreal_pve_content_root}/Graphs",
        triangle_cap=config.unreal_pve_triangle_cap,
        nanite_shape_preservation=args.shape,
        collision_generation=args.collision,
        calibration_path=args.calibration,
        species=args.species or None,
        max_assembly_instances=args.max_instances,
    )
    if plan.script is None:
        logger.error(
            "nothing planned: %s", "; ".join(plan.skipped) or "no growth JSONs"
        )
        return 1
    logger.info("asset script:  %s", plan.asset_script)
    logger.info(
        "graph script:  %s (%d graph(s), %d chain(s))",
        plan.script,
        len(plan.graphs),
        plan.chain_count,
    )
    logger.info("manifest:      %s", plan.manifest)
    for line in plan.skipped:
        logger.warning("skipped %s", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
