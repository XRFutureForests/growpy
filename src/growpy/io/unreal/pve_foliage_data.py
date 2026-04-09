"""
Generate FoliageData.json for PVE presets.

Reads PVE recipe JSON files in a directory and extracts unique twig mesh
names from instancer_name arrays. Produces a FoliageData.json that maps
each variation (= JSON basename) to its twig meshes with distribution rules.

This file is required by UProceduralVegetationPreset::UpdateDataAsset() to
populate FoliageMeshes and resolve twig Static Mesh references.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

PVE_RECIPE_SUFFIX = "_stems_unreal_pve.json"

# Default distribution rules matching the PVE editor defaults.
_DEFAULT_RULES = [
    {"name": "scale", "weight": 1.0, "offset": 0.0},
    {"name": "light", "weight": 1.0, "offset": 0.0},
    {"name": "upAlignment", "weight": 0.0, "offset": 0.0},
    {"name": "health", "weight": 0.0, "offset": 0.0},
    {"name": "tip", "weight": 0.0, "offset": 0.0},
]


def _extract_twig_names(pve_json_path: Path) -> list[str]:
    """Return sorted unique twig mesh names from a PVE recipe JSON."""
    with open(pve_json_path, "r") as f:
        data = json.load(f)

    instancer_name = (
        data.get("primitives", {}).get("attributes", {}).get("instancer_name", {})
    )
    values = instancer_name.get("values", [])

    unique = set()
    for branch_names in values:
        for name in branch_names:
            if name:
                unique.add(name)

    return sorted(unique)


def generate_foliage_data(directory: Path) -> Path:
    """Generate FoliageData.json for a directory of PVE recipe files.

    Scans *_stems_unreal_pve.json files, extracts twig names from
    instancer_name attributes, and writes a FoliageData.json that UE's
    UpdateDataAsset can use to populate FoliageMeshes on the preset.

    Args:
        directory: Path containing PVE recipe JSON files.

    Returns:
        Path to the written FoliageData.json.
    """
    directory = Path(directory)
    recipes = sorted(directory.glob(f"*{PVE_RECIPE_SUFFIX}"))

    variations = []
    for recipe_path in recipes:
        variant_name = recipe_path.stem  # filename without .json
        twig_names = _extract_twig_names(recipe_path)

        if not twig_names:
            logger.warning("No twig names found in %s", recipe_path.name)
            continue

        foliage_data_entries = []
        for twig_name in twig_names:
            foliage_data_entries.append(
                {
                    "Name": twig_name,
                    "scale": 0.0,
                    "upAlignment": 0.0,
                    "light": 0.0,
                    "health": 0.0,
                    "tip": 0.0,
                }
            )

        variations.append(
            {
                "name": variant_name,
                "Data": foliage_data_entries,
                "Rules": list(_DEFAULT_RULES),
            }
        )

    foliage_data = {"Variations": variations}
    out_path = directory / "FoliageData.json"
    with open(out_path, "w") as f:
        json.dump(foliage_data, f, indent=2)

    logger.info(
        "Generated FoliageData.json: %d variation(s), %s",
        len(variations),
        out_path,
    )
    return out_path


def generate_all_foliage_data(forest_root: Path) -> list[Path]:
    """Generate FoliageData.json for all species/scene directories.

    Walks the forest output tree looking for directories containing
    PVE recipe files and generates a FoliageData.json in each.

    Args:
        forest_root: Root of the forest output directory.

    Returns:
        List of paths to generated FoliageData.json files.
    """
    forest_root = Path(forest_root)
    generated = []

    for dirpath in sorted(forest_root.rglob("*")):
        if not dirpath.is_dir():
            continue
        recipes = list(dirpath.glob(f"*{PVE_RECIPE_SUFFIX}"))
        if recipes:
            path = generate_foliage_data(dirpath)
            generated.append(path)

    logger.info("Generated %d FoliageData.json file(s)", len(generated))
    return generated
