#!/usr/bin/env python3
"""
Convert Grove twig .blend files to USD with skeletal or static mesh variants.

This is a pure Blender-to-format conversion that produces mesh assets for
Unreal Engine in USD format. No Grove functions are required - only Blender
Python API (bpy).

Key Features:
    - Dual export modes: skeletal (with skeleton) or static (with materials)
    - Material/texture mapping optimized for USD (static variants)
    - Textures copied to output directory with relative path references
    - Coordinate system: Z-up (Blender right-handed to Unreal left-handed)
    - Standardized naming convention for twig types
    - Original .blend files preserved for regeneration

Export Variants (both created by default):
    Skeletal (_skeletal.usda):
        - Single root joint skeleton for animation support
        - No materials or textures (clean geometry only)
        - Used in skeletal Nanite assemblies
        - Supports wind animation and procedural placement

    Static (_static.usda):
        - Full PBR materials with textures from The Grove 2.2
        - No skeleton (static geometry)
        - Used in static Nanite assemblies
        - Better visual quality, smaller file size

Supports two CSV formats:
  1. Forest placement CSV (x, y, species, height) - auto-extracts unique species
  2. Asset lookup CSV (Common Name, Preset, Twig, Bark Texture) - direct asset reference

Quick Start:
    # Convert twigs (creates both skeletal and static variants)
    # Output: aspen_twig_apical_skeletal.usda + aspen_twig_apical_static.usda
    python src/growpy/cli/convert_twigs.py data/assets/twigs

Common Flags:
    --formats {usd,usda}  Export formats (default: usda)
    --csv PATH            Species CSV filter (default: data/input/test.csv)

Output per twig:
    - {species}_twig_{type}_skeletal.usda  # Skeletal mesh with skeleton
    - {species}_twig_{type}_static.usda    # Static mesh with materials/textures
    - textures/                            # Textures for static variants
    - {TwigName}.blend                     # Original source file (PRESERVED)

Twig Type Mapping:
    apical/long/end/terminal -> twig_long attribute (terminal twigs)
    lateral/short/side -> twig_short attribute (side branches)
    upward/up -> twig_upward attribute (upward-facing twigs)
    dead/fall/winter -> twig_dead attribute (dead/bare twigs)

Coordinate Systems:
    - Both Blender and Unreal use Z-up coordinate systems
    - Blender: Z-up, right-handed (X-right, Y-forward, Z-up)
    - Unreal: Z-up, left-handed (X-forward, Y-right, Z-up)
    - USD preserves Z-up, handedness handled on Unreal import

File Preservation:
    Original .blend files are PRESERVED after conversion. This allows:
    - Regeneration of both skeletal and static variants from same source
    - Version control of original assets
    - Future re-export with different settings
    Only auxiliary files are cleaned (ReadMe.txt, duplicate textures)

Full Documentation:
    See docs/guides/cli-reference.md for complete flag reference and examples

Usage:
    python convert_twigs.py <path> [options]
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
    clean_export: bool = True,
    twig_filter: Optional[List[str]] = None,
    export_static: bool = True,
    *,
    densify: bool = True,
    subdiv_levels: int = 4,
    alpha_trim_threshold: float = 0.5,
    edge_adaptive: bool = False,
    edge_subdiv_levels: Optional[int] = None,
    interior_decimate: bool = False,
    decimate_ratio: float = 0.5,
    boundary_rings: int = 1,
) -> Dict[str, List[Path]]:
    """Process all twig blend files in a directory.

    CRITICAL: clean_export is forced to True for Nanite compatibility.
    Materials and textures cause import failures with skeletal Nanite assemblies.

    Args:
        twig_dir: Directory containing .blend twig files
        formats: Export formats to create
        clean_export: ALWAYS True - materials/textures disabled for Nanite
        twig_filter: Optional list of twig directory names to process (snake_case)
    """
    # Force clean export for Nanite compatibility
    clean_export = True
    """Process all twig blend files in a directory.

    Args:
        twig_dir: Directory containing .blend twig files
        formats: Export formats to create
        clean_export: If True, creates minimal USD without materials/textures (default for Nanite)
        twig_filter: Optional list of twig directory names to process (snake_case)
        export_static: Always True - exports both skeletal and static variants (default: True)

    """

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
                clean_export=clean_export,
                export_static=export_static,
                densify=densify,
                alpha_trim_threshold=alpha_trim_threshold,
                subdiv_levels=subdiv_levels,
                edge_adaptive=edge_adaptive,
                edge_subdiv_levels=edge_subdiv_levels,
                interior_decimate=interior_decimate,
                decimate_ratio=decimate_ratio,
                boundary_rings=boundary_rings,
            )

            # Collect results
            if exported_files:
                if species_name not in results:
                    results[species_name] = []
                results[species_name].extend(exported_files)

        except Exception:
            # Silently fail - export validation is optional
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
        "--subdiv",
        type=int,
        default=4,
        help="Subdivision levels for densification (default: 4)",
    )
    parser.add_argument(
        "--alpha-trim",
        type=float,
        default=0.5,
        help="Alpha threshold for edge trimming (default: 0.5)",
    )
    parser.add_argument(
        "--edge-adaptive",
        action="store_true",
        help="Enable edge-adaptive leaf densification using alpha mask (default: off)",
    )
    parser.add_argument(
        "--edge-subdiv",
        type=int,
        default=None,
        help="Additional edge-only subdivision cuts near alpha edges (default: none)",
    )
    parser.add_argument(
        "--interior-decimate",
        action="store_true",
        help="Reduce interior leaf density while preserving alpha silhouette (default: off)",
    )
    parser.add_argument(
        "--decimate-ratio",
        type=float,
        default=0.5,
        help="Collapse decimate ratio for interior (0..1, lower = stronger, default: 0.5)",
    )
    parser.add_argument(
        "--boundary-rings",
        type=int,
        default=1,
        help="Edge protection width in vertex rings around silhouette (default: 1)",
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
            export_static=True,
            densify=(not args.no_densify),
            subdiv_levels=max(1, args.subdiv),
            alpha_trim_threshold=min(max(0.0, args.alpha_trim), 1.0),
            edge_adaptive=args.edge_adaptive,
            edge_subdiv_levels=(
                int(args.edge_subdiv)
                if args.edge_subdiv and args.edge_subdiv > 0
                else None
            ),
            interior_decimate=args.interior_decimate,
            decimate_ratio=float(args.decimate_ratio),
            boundary_rings=max(0, int(args.boundary_rings)),
        )
    elif args.path.is_dir():
        # Directory
        results = process_twig_directory(
            args.path,
            ["usda"],
            True,
            twig_filter,
            export_static=True,
            densify=(not args.no_densify),
            subdiv_levels=max(1, args.subdiv),
            alpha_trim_threshold=min(max(0.0, args.alpha_trim), 1.0),
            edge_adaptive=args.edge_adaptive,
            edge_subdiv_levels=(
                int(args.edge_subdiv)
                if args.edge_subdiv and args.edge_subdiv > 0
                else None
            ),
            interior_decimate=args.interior_decimate,
            decimate_ratio=float(args.decimate_ratio),
            boundary_rings=max(0, int(args.boundary_rings)),
        )
    else:
        return 1

    # Summary

    total_files = sum(len(files) for files in results.values())

    # Validation removed - no longer needed for production

    return 0


if __name__ == "__main__":
    sys.exit(main())
