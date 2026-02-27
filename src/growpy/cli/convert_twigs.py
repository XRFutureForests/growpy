#!/usr/bin/env python3
"""Convert Grove twig .blend files to USD with skeletal and static mesh variants.

Step 2 of the pipeline. Defaults from growpy.toml [twigs]. See docs/growpy/cli-reference.md.
"""

import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tqdm import tqdm

# USD validation removed - was only for development/testing


def _standardize_species_name(name: str) -> str:
    """Convert species common name to standardized snake_case.

    Mirrors prepare_assets.py:standardize_species_name so names match across pipeline.
    """
    name = re.sub(r"[^\w\s-]", "", name.lower())
    name = re.sub(r"[-\s]+", "_", name)
    return name.strip("_")


# Standardized twig type mapping
TWIG_NAME_MAPPINGS = {
    # Apical/Terminal/End twigs (twig_long attribute)
    "apical": ["apical", "end", "long", "terminal", "tip"],
    # Lateral/Side twigs (twig_short attribute)
    "lateral": ["lateral", "side", "short", "laterall"],  # note: typo in some files
    # Upward-facing twigs (twig_upward attribute)
    "upward": ["upward", "up"],
    # Dead/Fall/Winter twigs (twig_dead attribute)
    "dead": ["dead", "fall", "winter", "bare"],
    # Summer/Spring variants
    "summer": ["summer", "spring", "green"],
}

# Texture type classifications with extended keywords
TEXTURE_CLASSIFICATIONS = {
    "diffuse": ["diffuse", "albedo", "color", "basecolor", "base", "diff", "col"],
    "alpha": ["alpha", "opacity", "mask", "transparent", "cutout"],
    "normal": ["normal", "norm", "nrm", "bump", "height"],
    "translucent": ["translucent", "translucency", "transmission", "sss", "subsurface"],
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


def standardize_twig_name(original_name: str, species_name: str) -> Tuple[str, Dict]:
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
        "ScotsPineVariationCLateralTwig" -> ("scots_pine_lateral_c", {...})
        "OakEuropeanLongTwig" -> ("european_oak_apical", {"type": "apical"})
    """
    name_lower = original_name.lower()

    # Extract metadata
    metadata = {
        "original_name": original_name,
        "species": species_name,
        "type": "generic",  # Default
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
        # Single letter patterns like "TwigA", "TwigB"
        if name_lower.endswith(f"twig{letter}") or name_lower.endswith(f"{letter}twig"):
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

    # Species name (clean)
    species_clean = species_name.lower().replace(" ", "_")
    parts.append(species_clean)

    # Twig type
    if metadata["type"] != "generic":
        parts.append(metadata["type"])

    # Variation
    if metadata["variation"]:
        parts.append(metadata["variation"])

    # Season modifier
    if metadata["season"] and metadata["season"] != metadata["type"]:
        parts.append(metadata["season"])

    standardized = "_".join(parts)

    return standardized, metadata


def classify_texture_type(texture_path: Path, material_name: str = "") -> str:
    """
    Classify texture type from filename with context awareness.

    Handles:
    - Standard PBR naming (diffuse, normal, etc.)
    - Top/bottom variants for leaves
    - Compound names with duplicates
    """
    name_lower = texture_path.stem.lower()

    # Check for modifiers first (top/bottom)
    modifier = None
    for mod_type, keywords in TEXTURE_MODIFIERS.items():
        if any(kw in name_lower for kw in keywords):
            modifier = mod_type
            break

    # Classify base type
    base_type = "diffuse"  # Default
    for tex_type, keywords in TEXTURE_CLASSIFICATIONS.items():
        if any(kw in name_lower for kw in keywords):
            base_type = tex_type
            break

    # Combine with modifier if present
    if modifier and base_type == "diffuse":
        return f"diffuse_{modifier}"

    return base_type


def find_textures_for_material(
    blend_dir: Path, material_name: str, search_parent: bool = True
) -> Dict[str, Path]:
    """
    Find all available textures for a material with intelligent matching.

    Returns:
        Dict mapping texture type to file path
        e.g., {'diffuse': Path(...), 'alpha': Path(...), 'normal': Path(...)}
    """
    texture_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".exr", ".bmp"]
    texture_map = {}

    # Search locations
    search_dirs = [blend_dir / "textures", blend_dir]
    if search_parent:
        search_dirs.extend([blend_dir.parent / "textures", blend_dir.parent])

    # Find all textures
    available_textures = []
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ext in texture_extensions:
            available_textures.extend(search_dir.glob(f"*{ext}"))
            available_textures.extend(search_dir.glob(f"*{ext.upper()}"))

    # Remove duplicates and HDR placeholders
    available_textures = list(set(available_textures))
    available_textures = [
        t
        for t in available_textures
        if not t.stem.startswith("color_") or not t.suffix == ".hdr"
    ]

    if not available_textures:
        return texture_map

    # Match textures to material
    material_lower = material_name.lower()
    material_words = set(material_lower.replace("_", " ").split())

    for texture in available_textures:
        tex_name_lower = texture.stem.lower()
        tex_type = classify_texture_type(texture, material_name)

        # Scoring system for texture matching
        match_score = 0

        # Direct name match
        if material_lower in tex_name_lower or tex_name_lower in material_lower:
            match_score += 10

        # Word overlap
        tex_words = set(tex_name_lower.replace("_", " ").split())
        overlap = len(material_words & tex_words)
        match_score += overlap * 3

        # Species name in texture
        species_words = {"beech", "oak", "pine", "maple", "birch", "alder"}
        if any(word in tex_name_lower for word in material_words & species_words):
            match_score += 5

        # If few textures, be permissive
        if len(available_textures) <= 5:
            match_score += 2

        # Accept if reasonable match
        if match_score > 0:
            # Keep best match for each type
            if tex_type not in texture_map:
                texture_map[tex_type] = (texture, match_score)
            elif match_score > texture_map[tex_type][1]:
                texture_map[tex_type] = (texture, match_score)

    # Extract paths from (path, score) tuples
    texture_map = {k: v[0] for k, v in texture_map.items()}

    return texture_map


def process_twig_directory(
    twig_dir: Path,
    formats: List[str] = ["usda"],
    minimal_export: bool = True,
    twig_filter: Optional[List[str]] = None,
    include_skeleton: bool = True,
    *,
    twig_to_species_map: Optional[Dict[str, List[str]]] = None,
    densify: bool = True,
    alpha_trim_threshold: float = 0.5,
    alpha_trim_method: str = "all",
    smooth_boundary: bool = False,
    smooth_iterations: int = 3,
    smooth_factor: float = 0.5,
    boundary_edge_mm: float = 0.5,
) -> Dict[str, List[Path]]:
    """Process all twig blend files in a directory.

    Uses boundary-only densification to preserve interior mesh topology while
    creating high-detail silhouettes. Parameters are mm-based for consistency
    across different leaf sizes.

    Args:
        twig_dir: Directory containing .blend twig files
        formats: Export formats to create
        twig_filter: Optional list of twig directory names to process (snake_case)
        twig_to_species_map: Optional mapping from twig dir name to species name list.
            When provided, output files are named after the species from the CSV
            rather than the twig directory (fixes shared-twig naming, e.g. Norway
            spruce borrowing PacificSilverFirTwig).
        densify: Enable boundary densification (default: True)
        alpha_trim_threshold: Alpha threshold for silhouette trimming (default: 0.5)
        boundary_edge_mm: Target edge as fraction of avg edge (default: 0.5)
        smooth_boundary: Enable boundary edge smoothing (default: False)
    """
    # Force clean export for Nanite compatibility
    clean_export = True

    blend_files = list(twig_dir.rglob("*.blend"))

    # Filter blend files if twig_filter provided
    if twig_filter:
        # Convert filter to snake_case to match standardized directory names
        twig_filter_snake = []
        for twig in twig_filter:
            # Check if CamelCase (contains uppercase) and convert
            if any(c.isupper() for c in twig):
                s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", twig)
                s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
                twig_filter_snake.append(s2.lower())
            else:
                twig_filter_snake.append(twig)

        filtered_files = []
        for blend_file in blend_files:
            twig_dir_name = blend_file.parent.name
            # Check both original filter and snake_case filter
            if twig_dir_name in twig_filter or twig_dir_name in twig_filter_snake:
                filtered_files.append(blend_file)
        blend_files = filtered_files

    if not blend_files:
        return {}

    # Import twig_export module directly
    from growpy.io.twig_export import process_twig_file

    results = {}

    for blend_file in tqdm(blend_files, desc="Converting twigs"):
        try:
            twig_dir_name = blend_file.parent.name
            output_dir = blend_file.parent

            # Use CSV-derived species names when available so that shared twigs
            # (e.g. PacificSilverFirTwig used by Norway spruce) produce files
            # named after the actual species, not the donor twig species.
            if twig_to_species_map and twig_dir_name in twig_to_species_map:
                species_names = twig_to_species_map[twig_dir_name]
            else:
                # Fall back to deriving name from directory
                fallback = twig_dir_name.replace("_twig", "").replace("_", " ")
                species_names = [fallback]

            for species_name in species_names:
                exported_files = process_twig_file(
                    blend_file=blend_file,
                    output_dir=output_dir,
                    formats=formats,
                    species_name=species_name,
                    minimal_export=minimal_export,
                    include_skeleton=include_skeleton,
                    densify=densify,
                    alpha_trim_threshold=alpha_trim_threshold,
                    alpha_trim_method=alpha_trim_method,
                    smooth_boundary=smooth_boundary,
                    smooth_iterations=smooth_iterations,
                    smooth_factor=smooth_factor,
                    boundary_edge_mm=boundary_edge_mm,
                )

                if exported_files:
                    if species_name not in results:
                        results[species_name] = []
                    results[species_name].extend(exported_files)

        except Exception as e:
            print(f"  [ERROR] Failed to process {blend_file.name}: {e}")
            import traceback

            traceback.print_exc()

    return results


def main():
    import argparse

    from growpy.config import get_config

    # Get script directory for default paths
    script_dir = Path(__file__).parent.parent.parent.parent

    config = get_config()

    parser = argparse.ArgumentParser(
        description="Convert Grove twig files with robust texture handling and standardized naming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Convert twigs for 5 species from forest placement CSV (auto-extracts from data/input/test.csv)
    # Creates both skeletal and static variants:
    #   - aspen_foliage_apical_skeletal.usda (no materials, with skeleton)
    #   - aspen_foliage_apical_static.usda (with materials, no skeleton)
    #   - aspen_foliage_lateral_skeletal.usda
    #   - aspen_foliage_lateral_static.usda
    python src/growpy/cli/convert_twigs.py data/assets/twigs --formats usda

    # Convert specific species twig directory (no CSV filtering)
    python src/growpy/cli/convert_twigs.py data/assets/twigs/european_beech_twig --formats usda --csv ""

    # Convert ALL 57 available twigs using comprehensive lookup table
    python src/growpy/cli/convert_twigs.py data/assets/twigs --csv src/growpy/config/tree_asset_lookup.csv

CSV Format Support:
    Automatically handles forest placement CSV (x,y,species) or asset lookup CSV (Common Name,Twig)

Output per twig:
    - standard_name_skeletal.usda          # Skeletal mesh USD (root joint at origin)
    - standard_name_static.usda            # Static mesh USD (with materials)
        """,
    )
    parser.add_argument(
        "path",
        type=Path,
        nargs="?",
        default=None,
        help="Path to twig directory or single .blend file (default: from config)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to species CSV - only twigs for CSV species will be converted (default: from config)",
    )
    # Geometry processing flags (enabled by default for Nanite-friendly high poly twigs)
    parser.add_argument(
        "--no-densify",
        action="store_true",
        help="Disable mesh densification (subdivision)",
    )
    parser.add_argument(
        "--alpha-trim",
        type=float,
        default=None,
        help="Alpha threshold for trimming (default: from config). "
        "0.1-0.3=minimal (~0.3%% faces), 0.5=moderate (~7%%), 0.7=aggressive (~12-65%%).",
    )
    parser.add_argument(
        "--smooth-boundary",
        action="store_true",
        default=None,
        help="Smooth boundary edges to follow texture curves more naturally (default: from config)",
    )
    parser.add_argument(
        "--smooth-iterations",
        type=int,
        default=None,
        help="Number of Laplacian smoothing passes for boundary edges (default: from config)",
    )
    parser.add_argument(
        "--smooth-factor",
        type=float,
        default=None,
        help="Smoothing strength per iteration (0.0-1.0, default: from config)",
    )
    # Edge densification parameters
    parser.add_argument(
        "--boundary-edge-mm",
        type=float,
        default=None,
        help="Target edge as fraction of avg edge (default: from config). "
        "1.0=no subdivision, 0.5=50%% of avg, 0.25=25%%. "
        "Only transition edges (opaque->transparent) are subdivided.",
    )
    args = parser.parse_args()

    # Resolve config: TOML defaults + CLI overrides
    config.resolve(args)

    # Resolve twig path: CLI arg or config default
    twig_path = args.path if args.path is not None else config.twigs_path
    if not twig_path.is_absolute():
        twig_path = script_dir / twig_path

    # Resolve CSV path
    csv_path = config.csv_file
    if not csv_path.is_absolute():
        csv_path = script_dir / csv_path

    if not twig_path.exists():
        print(f"Path not found: {twig_path}")
        return 1

    # Load CSV filter if provided
    twig_filter = None
    twig_to_species_map: Dict[str, List[str]] = {}
    if csv_path and str(csv_path) != "":
        if not csv_path.exists():
            # If using default CSV and it doesn't exist, skip filtering
            pass
        else:
            import pandas as pd

            try:
                df = pd.read_csv(csv_path)

                # Check if this is a forest placement CSV (has "species" column)
                if "species" in df.columns and "Twig" not in df.columns:
                    unique_species = df["species"].dropna().unique().tolist()

                    # Load the asset lookup table
                    asset_lookup_path = (
                        script_dir
                        / "src"
                        / "growpy"
                        / "config"
                        / "tree_asset_lookup.csv"
                    )
                    if not asset_lookup_path.exists():
                        return 1

                    lookup_df = pd.read_csv(asset_lookup_path)

                    # Filter lookup table by species names and extract twig names.
                    # Also build twig_to_species_map so shared twigs produce
                    # correctly named output files for each species that uses them.
                    twig_filter = []
                    for species in unique_species:
                        # Try matching Common Name
                        match = lookup_df[
                            lookup_df["Common Name"].str.lower() == species.lower()
                        ]

                        twig_name = None

                        # Try matching aliases if no direct match
                        if match.empty and "Aliases" in lookup_df.columns:
                            for _, row in lookup_df.iterrows():
                                aliases = str(row.get("Aliases", "")).lower()
                                if species.lower() in [
                                    a.strip() for a in aliases.split(",")
                                ]:
                                    candidate = str(row.get("Twig", ""))
                                    if candidate not in [
                                        "—",
                                        "",
                                        "nan",
                                    ] and not pd.isna(candidate):
                                        twig_name = candidate.strip()
                                    break
                        elif not match.empty:
                            candidate = str(match.iloc[0].get("Twig", ""))
                            if candidate not in ["—", "", "nan"] and not pd.isna(
                                candidate
                            ):
                                twig_name = candidate.strip()

                        if twig_name:
                            twig_filter.append(twig_name)
                            # Map twig directory name → species so output files
                            # are named after the species, not the donor twig.
                            s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", twig_name)
                            s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
                            twig_dir_key = s2.lower()
                            species_std = _standardize_species_name(species)
                            if twig_dir_key not in twig_to_species_map:
                                twig_to_species_map[twig_dir_key] = []
                            if species_std not in twig_to_species_map[twig_dir_key]:
                                twig_to_species_map[twig_dir_key].append(species_std)

                    twig_filter = list(set(twig_filter))  # Remove duplicates
                else:
                    # Direct asset lookup CSV - get unique twig names
                    twig_filter = []
                    for twig_name in df["Twig"].dropna():
                        if twig_name not in ["—", ""]:
                            twig_filter.append(str(twig_name).strip())

                    twig_filter = list(set(twig_filter))  # Remove duplicates

            except Exception as e:
                print(f"Error processing CSV file: {e}")
                return 1

    if twig_path.is_file() and twig_path.suffix == ".blend":
        # Single file
        results = process_twig_directory(
            twig_path.parent,
            ["usda"],
            True,
            twig_filter,
            include_skeleton=True,
            twig_to_species_map=twig_to_species_map or None,
            densify=config.twigs_densify,
            alpha_trim_threshold=min(max(0.0, config.twigs_alpha_trim), 1.0),
            smooth_boundary=config.twigs_smooth_boundary,
            smooth_iterations=max(1, config.twigs_smooth_iterations),
            smooth_factor=min(max(0.0, config.twigs_smooth_factor), 1.0),
            boundary_edge_mm=max(0.1, config.twigs_boundary_edge_mm),
        )
    elif twig_path.is_dir():
        # Directory
        results = process_twig_directory(
            twig_path,
            ["usda"],
            True,
            twig_filter,
            include_skeleton=True,
            twig_to_species_map=twig_to_species_map or None,
            densify=config.twigs_densify,
            alpha_trim_threshold=min(max(0.0, config.twigs_alpha_trim), 1.0),
            smooth_boundary=config.twigs_smooth_boundary,
            smooth_iterations=max(1, config.twigs_smooth_iterations),
            smooth_factor=min(max(0.0, config.twigs_smooth_factor), 1.0),
            boundary_edge_mm=max(0.1, config.twigs_boundary_edge_mm),
        )
    else:
        return 1

    # Summary

    total_files = sum(len(files) for files in results.values())

    # Validation removed - no longer needed for production

    return 0


if __name__ == "__main__":
    sys.exit(main())
