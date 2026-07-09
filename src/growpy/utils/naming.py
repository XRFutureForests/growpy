"""Naming utilities for species, twigs, and textures.

Consolidates CamelCase-to-snake_case conversion, species name standardization,
and twig name parsing used across the pipeline.
"""

import re


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case with number separation.

    Args:
        name: CamelCase string

    Returns:
        snake_case string with numbers separated by underscores

    Examples:
        "Beech60" -> "beech_60"
        "BaldCypress80" -> "bald_cypress_80"
        "NorthernRedOak60" -> "northern_red_oak_60"
        "EuropeanBeechTwig" -> "european_beech_twig"
    """
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    s3 = re.sub("([a-z])([0-9])", r"\1_\2", s2)
    return s3.lower()


def standardize_species_name(common_name: str) -> str:
    """Convert species common name to standardized snake_case.

    Args:
        common_name: Species common name (e.g., "European beech", "Red oak")

    Returns:
        Standardized snake_case name (e.g., "european_beech", "red_oak")

    Examples:
        "European beech" -> "european_beech"
        "Red oak" -> "red_oak"
        "Norway spruce" -> "norway_spruce"
    """
    name = re.sub(r"[^\w\s-]", "", common_name.lower())
    name = re.sub(r"[-\s]+", "_", name)
    return name.strip("_")


def filename_safe_species_slug(species_name: str) -> str:
    """Convert a species name to a filename-safe slug.

    Like :func:`standardize_species_name` but also converts hyphens to
    underscores and strips every character that is not alphanumeric,
    space, hyphen, or underscore before slugifying. Use this for
    export filenames where hyphens would collide with file naming
    conventions.

    Examples:
        "European beech" -> "european_beech"
        "Fagaceae - European oak" -> "fagaceae_european_oak"
    """
    cleaned = "".join(c for c in species_name if c.isalnum() or c in (" ", "-", "_"))
    return cleaned.strip().replace(" ", "_").replace("-", "_").lower()


# Standardized twig type mapping
TWIG_NAME_MAPPINGS = {
    "apical": ["apical", "end", "long", "terminal", "tip"],
    "lateral": ["lateral", "side", "short", "laterall"],
    "upward": ["upward", "up"],
    "dead": ["dead", "fall", "winter", "bare"],
    "summer": ["summer", "spring", "green"],
}

# Texture type classifications with extended keywords
TEXTURE_CLASSIFICATIONS = {
    "diffuse": ["diffuse", "albedo", "color", "basecolor", "base", "diff", "col"],
    "alpha": ["alpha", "opacity", "mask", "transparent", "cutout"],
    "normal": ["normal", "norm", "nrm", "bump", "height"],
    "translucent": [
        "translucent",
        "translucency",
        "transmission",
        "sss",
        "subsurface",
    ],
    "roughness": ["roughness", "rough", "gloss", "glossiness"],
    "metallic": ["metallic", "metal", "metalness"],
    "ao": ["ao", "ambient", "occlusion", "ambientocclusion"],
    "emissive": ["emissive", "emission", "glow"],
}

# Special texture patterns (top/bottom for leaves)
TEXTURE_MODIFIERS = {
    "top": ["top", "upper", "face"],
    "bottom": ["bottom", "lower", "back", "underside"],
}


def standardize_twig_name(
    original_name: str, species_name: str
) -> tuple[str, dict]:
    """Convert Grove's CamelCase .blend filenames to snake_case USD output names.

    Parses semantic meaning from Grove's .blend file naming (e.g., type, variation)
    and combines with clean species name to produce standardized output names.

    Args:
        original_name: Original .blend filename (e.g., 'BeechApicalTwig.blend')
        species_name: Clean species name from directory (e.g., 'beech')

    Returns:
        (standardized_name, metadata_dict)

    Examples:
        "BeechApicalTwig" -> ("beech_apical", {"type": "apical", "species": "beech"})
        "ScotsPineVariationCLateralTwig" -> ("scots_pine_lateral", {...})
        "OakEuropeanLongTwig" -> ("european_oak_apical", {"type": "apical"})
    """
    name_lower = original_name.lower()

    metadata = {
        "original_name": original_name,
        "species": species_name,
        "type": "generic",
        "variation": None,
        "season": None,
        "is_standardized": True,
    }

    # Detect twig type
    for standard_type, keywords in TWIG_NAME_MAPPINGS.items():
        if any(kw in name_lower for kw in keywords):
            metadata["type"] = standard_type
            break

    # Detect variation (A, B, C, Var, Variation)
    for letter in ["a", "b", "c", "d", "e"]:
        if f"var{letter}" in name_lower or f"variation{letter}" in name_lower:
            metadata["variation"] = letter
            break
        # Match single letter before/after "twig" only if it's a standalone
        # variation letter (preceded by non-alpha), not part of a word like "dead"
        if name_lower.endswith(f"twig{letter}"):
            metadata["variation"] = letter
            break
        suffix = f"{letter}twig"
        if name_lower.endswith(suffix):
            pos = len(name_lower) - len(suffix)
            if pos == 0 or not name_lower[pos - 1].isalpha():
                metadata["variation"] = letter
                break

    # Detect season
    for season_type, keywords in TWIG_NAME_MAPPINGS.items():
        if season_type in ["summer", "dead"] and any(
            kw in name_lower for kw in keywords
        ):
            metadata["season"] = season_type

    # Build standardized name
    parts = []

    species_clean = species_name.lower().replace(" ", "_")
    parts.append(species_clean)

    if metadata["type"] != "generic":
        parts.append(str(metadata["type"]))

    # Include variation to distinguish multiple .blend files with same type
    # e.g., FieldElmTwig.blend vs FieldElmVarATwig.blend both with apical
    if metadata["variation"]:
        parts.append(str(metadata["variation"]))

    if metadata["season"] and metadata["season"] != metadata["type"]:
        parts.append(str(metadata["season"]))

    standardized = "_".join(parts)
    return standardized, metadata
