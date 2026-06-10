#!/usr/bin/env python3
"""Convert Grove twig .blend files to USD with skeletal and static mesh variants.

Step 2 of the pipeline. Defaults from config/twigs.toml. See docs/cli-reference.md.
"""

import bpy

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

import logging
import sys
from pathlib import Path

from tqdm import tqdm

from growpy.utils.naming import (
    TEXTURE_CLASSIFICATIONS,
    TEXTURE_MODIFIERS,
    camel_to_snake,
)

logger = logging.getLogger(__name__)


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
) -> dict[str, Path]:
    """
    Find all available textures for a material with intelligent matching.

    Returns:
        Dict mapping texture type to file path
        e.g., {'diffuse': Path(...), 'alpha': Path(...), 'normal': Path(...)}
    """
    texture_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".exr", ".bmp"]
    scored_map: dict[str, tuple[Path, int]] = {}

    # Search locations
    search_dirs = [blend_dir / "textures", blend_dir]
    if search_parent:
        search_dirs.extend([blend_dir.parent / "textures", blend_dir.parent])

    # Find all textures
    available_textures: list[Path] = []
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
        return {}

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
            if tex_type not in scored_map:
                scored_map[tex_type] = (texture, match_score)
            elif match_score > scored_map[tex_type][1]:
                scored_map[tex_type] = (texture, match_score)

    # Extract paths from (path, score) tuples
    texture_map: dict[str, Path] = {k: v[0] for k, v in scored_map.items()}

    return texture_map


def process_twig_directory(
    twig_dir: Path,
    formats: list[str] | None = None,
    minimal_export: bool = True,
    twig_filter: list[str] | None = None,
    include_skeleton: bool = True,
    *,
    densify: bool = True,
    alpha_trim_threshold: float = 0.5,
    alpha_trim_method: str = "all",
    boundary_edge_mm: float = 0.5,
    interior_decimate_ratio: float = 0.0,
    interior_edge_mm: float = 0.0,
    interior_boundary_rings: int = 1,
) -> dict[str, list[Path]]:
    """Process all twig blend files in a directory.

    Each .blend file is converted exactly once using the twig's native name
    (derived from directory, e.g. pacific_silver_fir from pacific_silver_fir_twig).
    Species that share a twig all reference the same converted files.

    Args:
        twig_dir: Directory containing .blend twig files
        formats: Export formats to create
        twig_filter: Optional list of twig directory names to process (snake_case)
        densify: Enable boundary densification (default: True)
        alpha_trim_threshold: Alpha threshold for silhouette trimming (default: 0.5)
        boundary_edge_mm: Target leaf edge length in millimeters for pre-densification
            before alpha contour cut (default: 0.5)
        interior_decimate_ratio: Fallback decimation ratio for interior faces (0-1).
            Ignored when interior_edge_mm > 0.
        interior_edge_mm: Target interior edge length in millimeters (default: 0).
            When > 0, derives decimation ratio automatically.
    """

    if formats is None:
        formats = ["usda"]

    blend_files = list(twig_dir.rglob("*.blend"))

    # Filter blend files if twig_filter provided
    if twig_filter:
        # Convert filter to snake_case to match standardized directory names
        twig_filter_snake = []
        for twig in twig_filter:
            # Check if CamelCase (contains uppercase) and convert
            if any(c.isupper() for c in twig):
                twig_filter_snake.append(camel_to_snake(twig))
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
    from growpy.io.usd.twig_export import process_twig_file

    results: dict[str, list[Path]] = {}

    from growpy.utils.log import is_verbose

    for blend_file in tqdm(
        blend_files, desc="Converting twigs", disable=not is_verbose()
    ):
        try:
            twig_dir_name = blend_file.parent.name
            output_dir = blend_file.parent

            # Always use the twig's native name (directory without _twig suffix).
            # Species that share a twig (e.g. Norway spruce using PacificSilverFirTwig)
            # all reference the same converted files instead of creating duplicates.
            species_name = twig_dir_name.replace("_twig", "").replace("_", " ")

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
                boundary_edge_mm=boundary_edge_mm,
                interior_decimate_ratio=interior_decimate_ratio,
                interior_edge_mm=interior_edge_mm,
                interior_boundary_rings=interior_boundary_rings,
            )

            if exported_files:
                if species_name not in results:
                    results[species_name] = []
                results[species_name].extend(exported_files)

        except Exception as e:
            logger.error("Failed to process %s: %s", blend_file.name, e, exc_info=True)

    return results


def main():
    import argparse

    from growpy.config import get_config
    from growpy.config.paths import get_project_root
    from growpy.utils.log import setup_logging

    project_root = get_project_root()

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
    python src/growpy/cli/convert_twigs.py data/assets/twigs --csv config/tree_asset_lookup.csv

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
    # Edge densification parameters
    parser.add_argument(
        "--boundary-edge-mm",
        type=float,
        default=None,
        help="Target edge as fraction of avg edge (default: from config). "
        "1.0=no subdivision, 0.5=50%% of avg, 0.25=25%%. "
        "Only transition edges (opaque->transparent) are subdivided.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output (INFO-level logging)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress INFO-level logging (only show warnings and errors)",
    )
    args = parser.parse_args()

    # Resolve config: TOML defaults + CLI overrides
    config.resolve(args)
    if args.quiet:
        config.verbose = False
    setup_logging(verbose=config.verbose)

    # Resolve twig path: CLI arg or config default
    twig_path = args.path if args.path is not None else config.twigs_path
    if not twig_path.is_absolute():
        twig_path = project_root / twig_path

    # Resolve CSV path
    csv_path = config.csv_file
    if not csv_path.is_absolute():
        csv_path = project_root / csv_path

    if not twig_path.exists():
        logger.error("Path not found: %s", twig_path)
        return 1

    # Load CSV filter if provided
    twig_filter = None
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

                    from growpy.config.paths import _find_species_row

                    twig_filter = []
                    for species in unique_species:
                        try:
                            row = _find_species_row(species)
                            candidate = str(row.get("Twig", ""))
                            if candidate not in ["—", "", "nan"] and not pd.isna(
                                candidate
                            ):
                                twig_filter.append(candidate.strip())
                        except ValueError:
                            logger.warning(
                                "Species '%s' not found in lookup table", species
                            )

                    twig_filter = list(set(twig_filter))
                else:
                    # Direct asset lookup CSV - get unique twig names
                    twig_filter = []
                    for _, row in df.iterrows():
                        twig_name = str(row.get("Twig", ""))
                        if twig_name in ["—", "", "nan"] or pd.isna(row.get("Twig")):
                            continue

                        twig_filter.append(twig_name.strip())

                    twig_filter = list(set(twig_filter))  # Remove duplicates

            except Exception as e:
                logger.error("Error processing CSV file: %s", e)
                return 1

    if twig_path.is_file() and twig_path.suffix == ".blend":
        # Single file
        process_twig_directory(
            twig_path.parent,
            ["usda"],
            True,
            twig_filter,
            include_skeleton=True,
            densify=config.twigs_densify,
            alpha_trim_threshold=min(max(0.0, config.twigs_alpha_trim), 1.0),
            boundary_edge_mm=max(0.01, config.twigs_boundary_edge_mm),
            interior_decimate_ratio=min(
                max(0.0, config.twigs_interior_decimate_ratio), 1.0
            ),
            interior_edge_mm=max(0.0, config.twigs_interior_edge_mm),
            interior_boundary_rings=max(0, int(config.twigs_interior_boundary_rings)),
        )
    elif twig_path.is_dir():
        # Directory
        process_twig_directory(
            twig_path,
            ["usda"],
            True,
            twig_filter,
            include_skeleton=True,
            densify=config.twigs_densify,
            alpha_trim_threshold=min(max(0.0, config.twigs_alpha_trim), 1.0),
            boundary_edge_mm=max(0.01, config.twigs_boundary_edge_mm),
            interior_decimate_ratio=min(
                max(0.0, config.twigs_interior_decimate_ratio), 1.0
            ),
            interior_edge_mm=max(0.0, config.twigs_interior_edge_mm),
            interior_boundary_rings=max(0, int(config.twigs_interior_boundary_rings)),
        )
    else:
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
