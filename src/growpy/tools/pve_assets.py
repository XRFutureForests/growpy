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

from growpy.config.ue_layout import SCHEMA_ROOT, TREES_ROOT
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


def bark_pair_sources(species_cal, catalog: Path | None = None) -> tuple[str, str]:
    """UE paths of the trunk and branch bark sources of a tile pair (XRFF-679).

    An intake id resolves to its instance in the material catalog; an atlas
    strip names its material directly. ("", "") when the species has no pair.

    Raises:
        KeyError: If an intake id is not in the catalog -- the branch bark
            would silently be missing and the graph build fail later.
    """
    from growpy.config.pve_calibration import BarkAtlasStrip
    from growpy.tools.material_intake import CATALOG

    trunk, branch = species_cal.bark_trunk_source, species_cal.bark_branch_source
    if trunk is None:
        return "", ""
    import tomllib

    path = catalog or CATALOG
    materials = (
        tomllib.loads(path.read_text(encoding="utf-8")).get("materials", {})
        if path.is_file()
        else {}
    )

    def instance(material_id: str) -> str:
        if material_id not in materials:
            raise KeyError(f"intake id {material_id!r} not in {path}")
        return str(materials[material_id]["instance"])

    if isinstance(trunk, BarkAtlasStrip):
        return trunk.material, instance(branch)
    return instance(trunk), instance(branch)


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
        default=TREES_ROOT,
        help=f"UE package path to import under (default: {TREES_ROOT})",
    )
    parser.add_argument(
        "--master-material",
        default=DEFAULT_MASTER_MATERIAL,
        help=f"material to parent bark instances to; the {SCHEMA_ROOT} copy "
        "of MA_Foliage_Trees is refused",
    )
    parser.add_argument(
        "--bark-master-material",
        default="",
        help="material to parent bark instances to when it is not the master, "
        "e.g. a project copy of MA_Foliage_Trees with a trunk-DBH offset "
        "(XRFF_Twin: /Game/00_XRFF/30_Forest/Materials/MA_Foliage_Trees_TrunkDBH)",
    )
    parser.add_argument(
        "--lookup",
        type=Path,
        default=Path("config/tree_asset_lookup.csv"),
        help="species table to read when no species are named",
    )
    parser.add_argument(
        "--calibration",
        type=Path,
        default=None,
        help="PVE calibration to read (default: config/pve_calibration.toml); "
        "a sandbox copy keeps test bark sources off the catalog",
    )
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(message)s")

    names = args.species or _dataset_species(args.lookup)
    if not names:
        logger.error("no species to import")
        return 1

    from growpy.config.paths import get_species_growth_habit
    from growpy.config.pve_calibration import load_pve_calibration

    calibration = load_pve_calibration(args.calibration)
    specs, skipped = [], []
    for name in names:
        try:
            habit = get_species_growth_habit(name)
            species_cal = calibration.for_species(name, habit)
            trunk, branch = bark_pair_sources(species_cal)
            specs.append(
                build_species_asset_spec(
                    name,
                    content_root=args.content_root,
                    bark_source_material=(
                        trunk or species_cal.bark_material_source or ""
                    ),
                    bark_source_textures=species_cal.bark_source_textures,
                    bark_branch_source_material=branch,
                )
            )
        except (FileNotFoundError, KeyError) as err:
            skipped.append((name, str(err)))

    for name, reason in skipped:
        logger.warning("skipped %s: %s", name, reason)

    if not specs:
        logger.error("no species had importable assets")
        return 1

    script = generate_pve_asset_script(
        args.output_dir,
        PVEAssetPlan(
            species=tuple(specs),
            master_material=args.master_material,
            bark_master_material=args.bark_master_material,
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
