"""Helios++ 2-digit classification codes for labeled point clouds.

Encodes material type and tree instance into a single integer (11-29)
that fits within the helios++ LAS classification range (0-31).

Code format in OBJ/MTL: [material][fid]
    material: 1=leaf, 2=wood (bark, twig/wood, fruit)
    fid:      1-9 from CSV fid column (max 9 trees; 0 is reserved for ground)

Ground plane uses helios_classification = 0 (material=0, fid=0).

Species is added in post-processing by joining on fid with the input CSV,
producing a 3-digit code: [material][fid][species]
    species:  1=beech, 2=oak, 3=birch, 4=maple, 5=fir, 6=pine
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Set

MAX_TREES = 9  # fid 1-9; fid 0 is reserved for ground

MATERIAL_CODES = {
    "leaf": 1,
    "wood": 2,
    "bark": 2,
    "fruit": 2,
}

SPECIES_CODES = {
    "selected_european_beech": 1,
    "selected_european_oak": 2,
    "selected_paper_birch": 3,
    "selected_sycamore_maple": 4,
    "selected_silver_fir": 5,
    "selected_scots_pine": 6,
}


def compute_classification_code(
    material_class: str, tree_fid: int,
) -> int:
    """Compute the 2-digit classification code.

    Args:
        material_class: One of "leaf", "wood", "bark", "fruit"
        tree_fid: Tree instance ID from CSV (1-9; 0 is reserved for ground)

    Returns:
        Integer classification code (11-29, fits in 0-31)

    Raises:
        ValueError: If tree_fid is 0 (reserved for ground) or > 9.
    """
    if tree_fid < 1 or tree_fid > 9:
        raise ValueError(
            f"tree_fid must be 1-9 (got {tree_fid}). "
            f"fid 0 is reserved for ground."
        )
    material_digit = MATERIAL_CODES[material_class]
    return material_digit * 10 + tree_fid


def build_classification_codes(tree_fid: int) -> Dict[str, int]:
    """Build classification code lookup for all material classes.

    Args:
        tree_fid: Tree FID from CSV (1-9; 0 is reserved for ground).

    Returns:
        Dict mapping material_class -> classification code
    """
    return {
        mat_class: compute_classification_code(mat_class, tree_fid)
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


def validate_classification_fids(fids: List[int]) -> tuple[List[str], List[str]]:
    """Check that tree fids are valid (0-9, warning if >MAX_TREES).

    Returns:
        Tuple of (errors, warnings). Errors are fatal, warnings are informational.
    """
    errors = []
    warnings = []
    for fid in fids:
        if fid < 1 or fid > 9:
            errors.append(
                f"Tree fid {fid} is out of range for classification (valid: 1-9; 0 is reserved for ground)"
            )
    if len(fids) > MAX_TREES:
        warnings.append(
            f"{len(fids)} trees exceed max {MAX_TREES} for "
            f"classification (fid 1-9). Reduce tree count or adjust fid assignment."
        )
    return errors, warnings
