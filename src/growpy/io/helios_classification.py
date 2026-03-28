"""Helios++ 4-digit classification codes for labeled point clouds.

Encodes material type, tree species, and tree instance into a single
integer that Helios++ writes as helios_classification per point.

Code format: [material][species][id_digit1][id_digit2]
    material: 1=leaf, 2=twig, 3=bark, 4=fruit
    species:  1=beech, 2=oak, 3=birch, 4=maple, 5=fir, 6=pine
    id:       01-99 from CSV fid column
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set

MATERIAL_CODES = {
    "leaf": 1,
    "wood": 2,
    "bark": 3,
    "fruit": 4,
}

SPECIES_CODES = {
    "selected_european_beech": 1,
    "selected_european_oak": 2,
    "selected_paper_birch": 3,
    "selected_sycamore_maple": 4,
    "selected_silver_fir": 5,
    "selected_scots_pine": 6,
}


def compute_classification_code(material_class: str, species_clean: str, tree_fid: int) -> int:
    """Compute the 4-digit classification code.

    Args:
        material_class: One of "leaf", "wood", "bark", "fruit"
        species_clean: Standardized species name (e.g. "selected_european_beech")
        tree_fid: Tree instance ID from CSV (1-99)

    Returns:
        4-digit integer classification code
    """
    material_digit = MATERIAL_CODES[material_class]
    species_digit = SPECIES_CODES[species_clean]
    return material_digit * 1000 + species_digit * 100 + tree_fid


def build_classification_codes(species_clean: str, tree_fid: int) -> Dict[str, int]:
    """Build classification code lookup for all material classes.

    Returns:
        Dict mapping material_class -> classification code
    """
    return {
        mat_class: compute_classification_code(mat_class, species_clean, tree_fid)
        for mat_class in MATERIAL_CODES
    }


def build_material_prefix(tree_fid: int) -> str:
    """Build material name prefix for per-tree uniqueness in combined OBJ."""
    return f"t{tree_fid:02d}_"


def validate_classification_species(species_list: List[str]) -> List[str]:
    """Check that all species are supported 'selected' variants.

    Args:
        species_list: List of species_clean names from CSV

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    unique_species = set(species_list)
    for sp in sorted(unique_species):
        if sp not in SPECIES_CODES:
            errors.append(
                f"Species '{sp}' is not a supported 'selected' variant. "
                f"Supported: {', '.join(sorted(SPECIES_CODES.keys()))}"
            )
    return errors


def validate_classification_materials(
    species_clean: str, twig_dir: Path
) -> List[str]:
    """Check that a species has at least leaf and twig (wood) materials.

    Reads face_materials.json sidecar files from the twig directory and
    classifies each Blender material name.

    Args:
        species_clean: Standardized species name
        twig_dir: Path to the species twig directory containing sidecar JSONs

    Returns:
        List of error messages (empty if valid)
    """
    from .mesh_simplify import classify_material

    if not twig_dir.exists():
        return [f"Twig directory not found for '{species_clean}': {twig_dir}"]

    found_classes: Set[str] = set()
    sidecar_files = list(twig_dir.glob("*_face_materials.json"))

    if not sidecar_files:
        return [f"No face_materials.json sidecar files found in {twig_dir}"]

    for sidecar in sidecar_files:
        with open(sidecar) as f:
            data = json.load(f)
        for mat_name in data.get("materials", []):
            mat_class = classify_material(mat_name)
            found_classes.add(mat_class)

    errors = []
    if "leaf" not in found_classes:
        errors.append(f"Species '{species_clean}' has no leaf materials in twigs")
    if "wood" not in found_classes:
        errors.append(f"Species '{species_clean}' has no twig (wood) materials in twigs")

    return errors


def validate_classification_fids(fids: List[int]) -> List[str]:
    """Check that all tree fids are in the valid range 1-99.

    Returns:
        List of error messages (empty if valid)
    """
    errors = []
    for fid in fids:
        if fid < 1 or fid > 99:
            errors.append(
                f"Tree fid {fid} is out of range for classification (valid: 1-99)"
            )
    return errors
