#!/usr/bin/env python3
"""
Convert Grove twig .blend files to USD with skeletal or static mesh variants.

This is a pure Blender-to-format conversion that produces mesh assets for
Unreal Engine in USD format. No Grove functions are required - only Blender
Python API (bpy).

Key Features:
    - Dual export modes: skeletal (with skeleton) or static (with materials)
    - Interleaved densify+trim: subdivides only transition edges while trimming
    - Relative edge targets for consistent density across species
    - Alpha-based silhouette trimming with configurable methods
    - Coordinate system: Z-up (Blender to Unreal)

Algorithm (Interleaved Densify+Trim):
    1. Build vertex alpha map by sampling texture at UV coordinates
    2. Delete faces where ALL/AVG vertices have alpha < threshold (based on method)
    3. Find transition edges (connect opaque vertex to transparent vertex)
    4. Split transition edges at midpoint using edge_split (preserves interior)
    5. Repeat steps 2-4 until longest transition edge < target length

    Key advantages:
    - Interleaved deletion removes fully-transparent faces early
    - Only subdivides transition edges (not nearby or interior edges)
    - Uses edge_split to preserve interior mesh topology completely
    - Direct texture sampling for new vertices (not interpolation)

Export Variants (both created by default):
    Skeletal (_skeletal.usda):
        - Single root joint skeleton for animation support
        - Minimal export: geometry only (no materials/textures/attributes)
        - Used in skeletal Nanite assemblies

    Static (_static.usda):
        - Full PBR materials with textures from The Grove 2.2
        - No skeleton (static geometry)
        - Used in static Nanite assemblies

Quick Start:
    # Recommended: default settings work well for most species
    python src/growpy/cli/convert_twigs.py data/assets/twigs

    # Explicit defaults:
    python src/growpy/cli/convert_twigs.py data/assets/twigs --boundary-edge-mm 0.5 --alpha-trim 0.5

    # With boundary smoothing for natural curves
    python src/growpy/cli/convert_twigs.py data/assets/twigs --smooth-boundary

    # Skip densification (export original low-poly mesh)
    python src/growpy/cli/convert_twigs.py data/assets/twigs --no-densify

    # Convert ALL species from asset lookup table
    python src/growpy/cli/convert_twigs.py data/assets/twigs --csv src/growpy/config/tree_asset_lookup.csv

All Flags:
    path                        Path to twig directory or .blend file (required)
    --csv PATH                  Species CSV filter (default: data/input/test.csv)
    --no-densify                Disable mesh densification
    --boundary-edge-mm FLOAT    Target edge as fraction of avg edge (default: 0.5)
    --alpha-trim FLOAT          Alpha threshold for trimming (default: 0.5)
    --smooth-boundary           Enable boundary smoothing
    --smooth-iterations INT     Smoothing passes (default: 3)
    --smooth-factor FLOAT       Smoothing strength 0.0-1.0 (default: 0.5)

Edge Densification (RELATIVE sizing - robust to any mesh scale):
    --boundary-edge-mm 1.0      No subdivision (original mesh)
    --boundary-edge-mm 0.5      Subdivide to 50% of avg edge (RECOMMENDED)
    --boundary-edge-mm 0.25     Subdivide to 25% (very dense)

Alpha Trimming:
    --alpha-trim 0.05-0.3       Minimal trimming (conservative)
    --alpha-trim 0.5            Moderate trimming (RECOMMENDED)
    --alpha-trim 0.7            Aggressive trimming
    (Uses 'all' method: delete only if ALL samples < threshold)

Output per twig:
    - {species}_twig_{type}_skeletal.usda  # Skeletal mesh with skeleton
    - {species}_twig_{type}_static.usda    # Static mesh with materials

Usage:
    python src/growpy/cli/convert_twigs.py <path> [options]
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tqdm import tqdm

# USD validation removed - was only for development/testing

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
        "ScotsPineVariationCLateralTwig" -> ("scots_pine_lateral_var_c", {...})
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
        parts.append(f"var_{metadata['variation']}")

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
                # Import camel_to_snake function from prepare_assets
                import re

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
            # Determine species name from directory (already in snake_case from prepare_assets)
            # Example: aspen_twig -> aspen
            species_name = blend_file.parent.name.replace("_twig", "").replace("_", " ")
            output_dir = blend_file.parent

            # Call process_twig_file directly
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

            # Collect results
            if exported_files:
                if species_name not in results:
                    results[species_name] = []
                results[species_name].extend(exported_files)

        except Exception as e:
            # Print error for debugging
            print(f"  [ERROR] Failed to process {blend_file.name}: {e}")
            import traceback

            traceback.print_exc()
            pass

    return results


def main():
    import argparse

    # Get script directory for default paths
    script_dir = Path(__file__).parent.parent.parent.parent
    default_csv = script_dir / "data" / "input" / "test.csv"

    parser = argparse.ArgumentParser(
        description="Convert Grove twig files with robust texture handling and standardized naming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Convert twigs for 5 species from forest placement CSV (auto-extracts from data/input/test.csv)
    # Creates both skeletal and static variants:
    #   - aspen_twig_apical_skeletal.usda (no materials, with skeleton)
    #   - aspen_twig_apical_static.usda (with materials, no skeleton)
    #   - aspen_twig_lateral_skeletal.usda
    #   - aspen_twig_lateral_static.usda
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
        "path", type=Path, help="Path to twig directory or single .blend file"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=default_csv,
        help="Path to species CSV - only twigs for CSV species will be converted (default: data/input/test.csv)",
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
        default=0.5,
        help="Alpha threshold for trimming (default: 0.5). "
        "0.1-0.3=minimal (~0.3%% faces), 0.5=moderate (~7%%), 0.7=aggressive (~12-65%%).",
    )
    parser.add_argument(
        "--smooth-boundary",
        action="store_true",
        help="Smooth boundary edges to follow texture curves more naturally (default: off)",
    )
    parser.add_argument(
        "--smooth-iterations",
        type=int,
        default=3,
        help="Number of Laplacian smoothing passes for boundary edges (default: 3)",
    )
    parser.add_argument(
        "--smooth-factor",
        type=float,
        default=0.5,
        help="Smoothing strength per iteration (0.0-1.0, default: 0.5)",
    )
    # Edge densification parameters
    parser.add_argument(
        "--boundary-edge-mm",
        type=float,
        default=0.5,
        help="Target edge as fraction of avg edge (default: 0.5). "
        "1.0=no subdivision, 0.5=50%% of avg, 0.25=25%%. "
        "Only transition edges (opaque->transparent) are subdivided.",
    )
    args = parser.parse_args()

    if not args.path.exists():
        return 1

    # Load CSV filter if provided
    twig_filter = None
    if args.csv and str(args.csv) != "":
        if not args.csv.exists():
            # If using default CSV and it doesn't exist, skip filtering
            if args.csv != default_csv:
                return 1
        else:
            import pandas as pd

            try:
                df = pd.read_csv(args.csv)

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

                    # Filter lookup table by species names and extract twig names
                    twig_filter = []
                    for species in unique_species:
                        # Try matching Common Name
                        match = lookup_df[
                            lookup_df["Common Name"].str.lower() == species.lower()
                        ]

                        # Try matching aliases if no direct match
                        if match.empty and "Aliases" in lookup_df.columns:
                            for _, row in lookup_df.iterrows():
                                aliases = str(row.get("Aliases", "")).lower()
                                if species.lower() in [
                                    a.strip() for a in aliases.split(",")
                                ]:
                                    twig_name = str(row.get("Twig", ""))
                                    if twig_name not in [
                                        "—",
                                        "",
                                        "nan",
                                    ] and not pd.isna(twig_name):
                                        twig_filter.append(twig_name.strip())
                                    break
                        elif not match.empty:
                            twig_name = str(match.iloc[0].get("Twig", ""))
                            if twig_name not in ["—", "", "nan"] and not pd.isna(
                                twig_name
                            ):
                                twig_filter.append(twig_name.strip())

                    twig_filter = list(set(twig_filter))  # Remove duplicates
                else:
                    # Direct asset lookup CSV - get unique twig names
                    twig_filter = []
                    for twig_name in df["Twig"].dropna():
                        if twig_name not in ["—", ""]:
                            twig_filter.append(str(twig_name).strip())

                    twig_filter = list(set(twig_filter))  # Remove duplicates

            except Exception as e:
                return 1

    if args.path.is_file() and args.path.suffix == ".blend":
        # Single file
        results = process_twig_directory(
            args.path.parent,
            ["usda"],
            True,
            twig_filter,
            include_skeleton=True,
            densify=(not args.no_densify),
            alpha_trim_threshold=min(max(0.0, args.alpha_trim), 1.0),
            smooth_boundary=args.smooth_boundary,
            smooth_iterations=max(1, int(args.smooth_iterations)),
            smooth_factor=min(max(0.0, float(args.smooth_factor)), 1.0),
            boundary_edge_mm=max(0.1, float(args.boundary_edge_mm)),
        )
    elif args.path.is_dir():
        # Directory
        results = process_twig_directory(
            args.path,
            ["usda"],
            True,
            twig_filter,
            include_skeleton=True,
            densify=(not args.no_densify),
            alpha_trim_threshold=min(max(0.0, args.alpha_trim), 1.0),
            smooth_boundary=args.smooth_boundary,
            smooth_iterations=max(1, int(args.smooth_iterations)),
            smooth_factor=min(max(0.0, float(args.smooth_factor)), 1.0),
            boundary_edge_mm=max(0.1, float(args.boundary_edge_mm)),
        )
    else:
        return 1

    # Summary

    total_files = sum(len(files) for files in results.values())

    # Validation removed - no longer needed for production

    return 0


if __name__ == "__main__":
    sys.exit(main())
