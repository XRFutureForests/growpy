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


def _resolve_twig_asset_name(
    pve_twig_name: str,
    species: str,
    species_twig_map: dict[str, str],
    instances_dir: Path | None,
) -> str:
    """Resolve a PVE instancer name to the actual twig asset name.

    Handles shared twigs where the PVE recipe uses the tree species name
    (e.g. SK_norway_spruce_foliage_a) but the actual twig asset uses the
    twig source species name (e.g. SK_pacific_silver_fir_foliage).
    """
    twig_folder = species_twig_map.get(species, f"{species}_twigs_combined_skeletal")
    twig_source = twig_folder.replace("_twigs_combined_skeletal", "")

    if species == twig_source:
        return pve_twig_name

    bare = pve_twig_name.removeprefix("SK_")
    species_prefix = f"{species}_foliage"
    variant_suffix = (
        bare[len(species_prefix) :] if bare.startswith(species_prefix) else ""
    )

    candidate_with_variant = f"{twig_source}_foliage{variant_suffix}"
    candidate_base = f"{twig_source}_foliage"

    if instances_dir is not None:
        if (instances_dir / f"{candidate_with_variant}_skeletal.usda").exists():
            return f"SK_{candidate_with_variant}"
        if (instances_dir / f"{candidate_base}_skeletal.usda").exists():
            return f"SK_{candidate_base}"

    return f"SK_{candidate_with_variant}"


def _compute_twig_asset_path(
    twig_name: str,
    species: str,
    import_base: str,
    species_twig_map: dict[str, str],
    instances_dir: Path | None = None,
) -> str:
    """Compute the full UE Content Browser path for a twig SkeletalMesh.

    UE USD import creates assets with an SK_ prefix inside a
    SkeletalMeshes/ subfolder under the combined twig wrapper folder.
    The combined wrapper strips the _skeletal suffix from prim names,
    so the UE asset name matches the bare twig name with SK_ prefix.

    For shared twigs (e.g. norway_spruce using pacific_silver_fir twig),
    resolves the PVE instancer name to the actual twig asset name.

    Returns a Soft Object Reference: ``PackagePath/SK_Name.SK_Name``
    """
    twig_folder = species_twig_map.get(species, f"{species}_twigs_combined_skeletal")
    sk_folder = f"{import_base}/Instances/{twig_folder}/SkeletalMeshes"
    sk_name = _resolve_twig_asset_name(
        twig_name,
        species,
        species_twig_map,
        instances_dir,
    )
    if not sk_name.startswith("SK_"):
        sk_name = f"SK_{sk_name}"
    return f"{sk_folder}/{sk_name}.{sk_name}"


def generate_foliage_data(
    directory: Path,
    forest_root: Path | None = None,
    import_base: str = "",
    species_twig_map: dict[str, str] | None = None,
) -> Path:
    """Generate FoliageData.json for a directory of PVE recipe files.

    Scans *_stems_unreal_pve.json files, extracts twig names from
    instancer_name attributes, and writes a FoliageData.json that UE's
    UpdateDataAsset can use to populate FoliageMeshes on the preset.

    When ``import_base`` and ``species_twig_map`` are provided, each twig
    entry includes an ``AssetPath`` field with the full UE Content Browser
    reference so the PVE graph builder can resolve foliage meshes directly.

    Args:
        directory: Path containing PVE recipe JSON files.
        forest_root: Root of the forest output directory (for species inference).
        import_base: UE Content Browser base path (e.g. ``/Game/Assets/TheGrove``).
        species_twig_map: Maps species name to combined twig instance folder name.

    Returns:
        Path to the written FoliageData.json.
    """
    directory = Path(directory)
    recipes = sorted(directory.glob(f"*{PVE_RECIPE_SUFFIX}"))

    # Infer species from directory relative to forest_root
    species = ""
    can_resolve_paths = bool(import_base and species_twig_map and forest_root)
    if can_resolve_paths and forest_root is not None and species_twig_map is not None:
        try:
            species = directory.relative_to(forest_root).parts[0]
        except (ValueError, IndexError):
            can_resolve_paths = False

    # Resolve Instances directory for shared twig name resolution
    instances_dir = forest_root / "Instances" if forest_root else None

    variations = []
    for recipe_path in recipes:
        variant_name = recipe_path.stem  # filename without .json
        twig_names = _extract_twig_names(recipe_path)

        if not twig_names:
            logger.warning("No twig names found in %s", recipe_path.name)
            continue

        foliage_data_entries = []
        for twig_name in twig_names:
            resolved_name = twig_name
            if can_resolve_paths and species_twig_map is not None:
                resolved_name = _resolve_twig_asset_name(
                    twig_name,
                    species,
                    species_twig_map,
                    instances_dir,
                )
            entry: dict = {
                "Name": resolved_name,
                "scale": 0.0,
                "upAlignment": 0.0,
                "light": 0.0,
                "health": 0.0,
                "tip": 0.0,
            }
            if can_resolve_paths and species_twig_map is not None:
                entry["AssetPath"] = _compute_twig_asset_path(
                    twig_name,
                    species,
                    import_base,
                    species_twig_map,
                    instances_dir=instances_dir,
                )
            foliage_data_entries.append(entry)

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


def generate_all_foliage_data(
    forest_root: Path,
    import_base: str = "",
    species_twig_map: dict[str, str] | None = None,
) -> list[Path]:
    """Generate FoliageData.json for all species/scene directories.

    Walks the forest output tree looking for directories containing
    PVE recipe files and generates a FoliageData.json in each.

    Args:
        forest_root: Root of the forest output directory.
        import_base: UE Content Browser base path for twig asset resolution.
        species_twig_map: Maps species name to combined twig instance folder.

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
            path = generate_foliage_data(
                dirpath,
                forest_root=forest_root,
                import_base=import_base,
                species_twig_map=species_twig_map,
            )
            generated.append(path)

    logger.info("Generated %d FoliageData.json file(s)", len(generated))
    return generated
