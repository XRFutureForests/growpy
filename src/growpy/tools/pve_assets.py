"""Generate the UE Python script that imports a species' PVE assets.

The twig palette and the bark material are the two Content Browser pieces a PVE
graph needs that the pipeline did not own (XRFF-440). This writes the script;
``growpy-ue-exec`` runs it in the open editor.

**A forest export emits this script already**, beside the graph script, for the
species that run produced -- see ``[unreal] generate_pve_graphs``. This CLI is
the manual override: importing a species the current run did not export,
re-importing after a texture change, or preparing a project before any export
exists::

    growpy-pve-assets european_beech silver_fir
    growpy-ue-exec data/output/pve/growpy_pve_assets.py --restart-ram-limit 0

With no species named it resolves every species marked for the dataset in
``config/tree_asset_lookup.csv``, and reports the ones whose source assets are
missing rather than quietly importing a partial set -- an unowned step that
fails quietly is exactly how a bark material stayed a USD import stub for weeks.
"""

from __future__ import annotations

import argparse
import csv
import logging
import sys
from pathlib import Path

from growpy.io.unreal.pve_asset_script import (
    DEFAULT_MASTER_MATERIAL,
    PVEAssetPlan,
    build_species_asset_spec,
    generate_pve_asset_script,
)

logger = logging.getLogger(__name__)


def _dataset_species(lookup: Path) -> list[str]:
    with open(lookup, newline="", encoding="utf-8") as handle:
        return [
            row["Standardized Name"].strip()
            for row in csv.DictReader(handle)
            if row.get("Dataset", "").strip().lower() == "yes"
        ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "species",
        nargs="*",
        help="standardized species names; default is every dataset species",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output/pve"),
        help="where to write the generated script (default: data/output/pve)",
    )
    parser.add_argument(
        "--content-root",
        default="/Game/PVE",
        help="UE package path to import under (default: /Game/PVE)",
    )
    parser.add_argument(
        "--master-material",
        default=DEFAULT_MASTER_MATERIAL,
        help="material to parent bark instances to; the /Game/Templates copy "
        "of MA_Foliage_Trees is refused",
    )
    parser.add_argument(
        "--lookup",
        type=Path,
        default=Path("config/tree_asset_lookup.csv"),
        help="species table to read when no species are named",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    names = args.species or _dataset_species(args.lookup)
    if not names:
        logger.error("no species to import")
        return 1

    specs, skipped = [], []
    for name in names:
        try:
            specs.append(
                build_species_asset_spec(name, content_root=args.content_root)
            )
        except FileNotFoundError as err:
            skipped.append((name, str(err)))

    for name, reason in skipped:
        logger.warning("skipped %s: %s", name, reason)

    if not specs:
        logger.error("no species had importable assets")
        return 1

    script = generate_pve_asset_script(
        args.output_dir,
        PVEAssetPlan(
            species=tuple(specs), master_material=args.master_material
        ),
    )

    for spec in specs:
        logger.info(
            "%-22s %d prototype(s) -> %s",
            spec.species,
            len(spec.prototypes),
            spec.content_folder,
        )
    logger.info("")
    logger.info("wrote %s", script)
    logger.info("run it with: growpy-ue-exec %s --restart-ram-limit 0", script)
    # A skipped species is a real gap -- a missing normal map means an
    # untextured trunk -- so it is reported in the exit code, not just logged.
    return 2 if skipped else 0


if __name__ == "__main__":
    sys.exit(main())
