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

def _derive_ladder_if_single_object(blend_file: Path) -> None:
    """Split a one-object twig .blend into a foliage size ladder (XRFF-412).

    growpy builds one USD variant per mesh OBJECT in a twig .blend, so an asset
    modelled as a single spray gives the whole crown one leaf size. Most assets
    ship several -- PaperBirchTwig 18, EuropeanBeechTwig 5 -- but
    PacificSilverFirTwig ships exactly one 0.109 m2 spray, shared by silver fir,
    Norway spruce, Douglas fir and Sitka spruce, and that single size is what
    forced those species to crown densities an order of magnitude below the
    broadleaves.

    Derived here, in the conversion, rather than by hand: step 1 of the dataset
    pipeline re-copies the pristine Grove assets, so a `--clean` run would
    otherwise silently drop the ladder and revert those species to the one
    spray -- taking the crown densities calibrated against the ladder with it.

    Only fires on a genuinely single-object asset, so an artist who ships their
    own variants keeps them untouched.
    """
    import bpy

    from growpy.tools.derive_twig_ladder import main as derive_main

    bpy.ops.wm.open_mainfile(filepath=str(blend_file))
    meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    if len(meshes) != 1:
        return

    logger.info(
        "%s ships one mesh object -- deriving a foliage size ladder from it",
        blend_file.name,
    )
    if derive_main([str(blend_file)]) != 0:
        logger.warning("ladder derivation failed for %s, converting as-is", blend_file)




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
    boundary_edge_mm_per_twig: dict[str, float] | None = None,
    interior_decimate_ratio: float = 0.0,
    interior_edge_mm: float = 0.0,
    interior_boundary_rings: int = 1,
    planar_angle: float = 1.0,
    planar_angle_per_twig: dict[str, float] | None = None,
    output_root: Path | None = None,
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

    for blend_file in blend_files:
        _derive_ladder_if_single_object(blend_file)
    # Import twig_export module directly
    from growpy.io.usd.twig_export import process_twig_file

    results: dict[str, list[Path]] = {}

    from growpy.utils.log import is_verbose

    for blend_file in tqdm(
        blend_files, desc="Converting twigs", disable=not is_verbose()
    ):
        try:
            twig_dir_name = blend_file.parent.name
            # Default: write beside the .blend, which is where every consumer
            # looks. `output_root` mirrors the per-twig folder underneath it
            # instead, so a second conversion profile cannot overwrite the
            # dataset's own assets (XRFF-359).
            if output_root is None:
                output_dir = blend_file.parent
            else:
                output_dir = output_root / twig_dir_name
                output_dir.mkdir(parents=True, exist_ok=True)

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
                boundary_edge_mm_per_twig=boundary_edge_mm_per_twig,
                interior_decimate_ratio=interior_decimate_ratio,
                interior_edge_mm=interior_edge_mm,
                interior_boundary_rings=interior_boundary_rings,
                planar_angle=planar_angle,
                planar_angle_per_twig=planar_angle_per_twig,
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
        # NOT --profile: CLI_MAPPINGS already binds "profile" to the profiling
        # flag, so that name would set config.profile to "twig".
        "--conversion-profile",
        choices=["twig", "compound"],
        default="twig",
        help=(
            "Conversion profile (XRFF-359). 'twig' is the close-range default "
            "used for the dataset's own twig assets. 'compound' applies the "
            "coarser [twigs] compound_* settings, for twigs that will be welded "
            "into a compound foliage part where each leaf is far smaller on "
            "screen. The trimming and densification still happen here, per "
            "twig -- welding comes afterwards and cannot do them, because a "
            "welded part has lost the per-leaf alpha texture association the "
            "contour cut needs."
        ),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=None,
        help=(
            "Write converted twigs under this directory (one folder per twig) "
            "instead of beside each .blend. Required with "
            "--conversion-profile compound, whose coarser output would "
            "otherwise overwrite the dataset's own close-range assets, so it "
            "must be OUTSIDE the twig source tree."
        ),
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to species CSV - only twigs for CSV species will be converted (default: from config)",
    )
    parser.add_argument(
        "--dataset",
        action="store_true",
        help="Filter to species marked in tree_asset_lookup.csv's Dataset column "
        "(config-driven, no CSV file needed). Takes precedence over --csv.",
    )
    # Geometry processing flags (enabled by default for Nanite-friendly high poly twigs)
    parser.add_argument(
        "--densify",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable/disable mesh densification (subdivision). Default: from config.",
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
        "--interior-edge-mm",
        type=float,
        default=None,
        help="Target interior edge length in mm (default: from config, 0=disabled). "
        "When > 0, derives interior-face decimation ratio automatically.",
    )
    parser.add_argument(
        "--verbose",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable verbose output (INFO-level logging)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress INFO-level logging (only show warnings and errors)",
    )
    args = parser.parse_args()

    if args.conversion_profile != "twig" and args.output_root is None:
        logger.error(
            "--conversion-profile %s needs --output-root: converted twigs are "
            "written beside their .blend under the same names, so a second "
            "profile would overwrite the dataset's close-range assets.",
            args.conversion_profile,
        )
        return 1


    # Resolve config: TOML defaults + CLI overrides
    config.resolve(args)
    if args.quiet:
        config.verbose = False
    setup_logging(verbose=config.verbose)

    # Resolve twig path: CLI arg or config default
    twig_path = args.path if args.path is not None else config.twigs_path
    if not twig_path.is_absolute():
        twig_path = project_root / twig_path

    # Presence of --output-root is not enough. `process_twig_directory` writes to
    # `output_root / <twig folder>`, which for --output-root data/assets/twigs is
    # byte-identical to the default "beside the .blend" path -- so the most
    # natural-looking value silently defeats the guard above. The coarse assets
    # would also land inside the tree that three consumers discover twigs in by
    # rglob (analyze_usda, leaf_geometry, twig_silhouette), where a duplicate
    # basename is resolved by filesystem order.
    if args.output_root is not None:
        output_root = args.output_root
        if not output_root.is_absolute():
            output_root = project_root / output_root
        resolved_root = output_root.resolve()
        resolved_source = twig_path.resolve()
        if resolved_root == resolved_source or resolved_source in resolved_root.parents:
            logger.error(
                "--output-root %s is inside the twig source tree %s: converted "
                "twigs would land on the assets being read from. Choose a "
                "directory outside it.",
                resolved_root,
                resolved_source,
            )
            return 1
        args.output_root = output_root


    # Resolve CSV path
    csv_path = config.csv_file
    if not csv_path.is_absolute():
        csv_path = project_root / csv_path

    if not twig_path.exists():
        logger.error("Path not found: %s", twig_path)
        return 1

    # Resolve twig filter: config-driven dataset species, an explicit CSV, or none
    twig_filter = None
    if args.dataset:
        # Species marked in tree_asset_lookup.csv's Dataset column. Only the Twig
        # column is needed -- species identity itself is never used past this.
        import pandas as pd

        from growpy.pipelines.dataset_csv_planner import _get_dataset_species

        dataset_df = _get_dataset_species()
        twig_filter = []
        for _, row in dataset_df.iterrows():
            twig_name = str(row.get("Twig", ""))
            if twig_name in ["—", "", "nan"] or pd.isna(row.get("Twig")):
                continue
            twig_filter.append(twig_name.strip())
        twig_filter = list(set(twig_filter))
    elif csv_path and str(csv_path) != "":
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

    # The two profiles differ only in these four knobs; everything else about
    # the conversion, including the alpha contour cut and the densification it
    # depends on, is identical (XRFF-359).
    # Flags the user actually typed. argparse leaves these None otherwise, and
    # resolve() has already written them onto the base fields, so the compound
    # profile must not override them.
    typed = {
        key
        for key, value in (
            ("alpha_trim", args.alpha_trim),
            ("boundary_edge_mm", args.boundary_edge_mm),
            ("interior_edge_mm", args.interior_edge_mm),
        )
        if value is not None
    }
    profile = config.get_twig_conversion_profile(args.conversion_profile, typed)
    if args.conversion_profile != "twig":
        logger.info(
            "Conversion profile '%s': boundary_edge_mm=%.3f planar_angle=%.3f "
            "alpha_trim=%.3f interior_edge_mm=%.3f",
            args.conversion_profile,
            profile["boundary_edge_mm"],
            profile["planar_angle"],
            profile["alpha_trim"],
            profile["interior_edge_mm"],
        )

    convert_kwargs = {
        "include_skeleton": True,
        "densify": config.twigs_densify,
        "alpha_trim_threshold": min(max(0.0, profile["alpha_trim"]), 1.0),
        "boundary_edge_mm": max(0.01, profile["boundary_edge_mm"]),
        "boundary_edge_mm_per_twig": config.twigs_boundary_edge_mm_per_twig,
        "interior_decimate_ratio": 0.000001,
        "interior_edge_mm": max(0.0, profile["interior_edge_mm"]),
        "interior_boundary_rings": max(0, int(config.twigs_interior_boundary_rings)),
        "planar_angle": max(0.0, profile["planar_angle"]),
        "planar_angle_per_twig": config.twigs_planar_angle_per_twig,
        "output_root": args.output_root,
    }

    if twig_path.is_file() and twig_path.suffix == ".blend":
        # Single file
        process_twig_directory(
            twig_path.parent,
            ["usda"],
            True,
            twig_filter,
            **convert_kwargs,
        )
    elif twig_path.is_dir():
        # Directory
        process_twig_directory(
            twig_path,
            ["usda"],
            True,
            twig_filter,
            **convert_kwargs,
        )
    else:
        return 1

    _write_leaf_geometry_sidecars(twig_path)
    return 0


def _write_leaf_geometry_sidecars(twig_path: Path) -> None:
    """Measure each converted prototype's leaf/wood split (XRFF-274).

    The `<prototype>_leaf_area.json` sidecar `twig_export` writes tags leaves by
    MATERIAL, so on an asset that ships one material for the whole twig it
    reports the woody shoot as leaf: every fir ladder variant came out with
    `leaf_faces == total_faces`, overstating leaf area by 8-35%. The split here
    is topological instead, and lands beside it as
    `<prototype>_leaf_area_geom.json` -- it does not overwrite the material one,
    so a caller chooses which basis it wants (see `crown_geometry.compute_lai`'s
    `leaf_area_provisional` flag).

    Written here rather than left to a separate tool because a crown density
    calibrated against leaf area is only reproducible if a clean run of the
    pipeline regenerates the number it was calibrated on.
    """
    from growpy.utils.leaf_geometry import run_over_all_twigs

    root = twig_path.parent if twig_path.is_file() else twig_path
    try:
        results = run_over_all_twigs(root)
    except Exception as exc:  # noqa: BLE001 -- diagnostic, never fatal
        # The conversion itself has already succeeded and been written; a
        # measurement failure must not discard it.
        logger.warning("leaf/wood split not measured for %s: %s", root, exc)
        return
    if not results:
        return
    wood = sum(r.get("wood_area_m2", 0.0) or 0.0 for r in results)
    leaf = sum(r.get("leaf_area_m2", 0.0) or 0.0 for r in results)
    total = leaf + wood
    logger.info(
        "leaf/wood split: %d prototype(s), %.5f m2 leaf + %.5f m2 wood "
        "(%.1f%% wood) -> *_leaf_area_geom.json",
        len(results),
        leaf,
        wood,
        100.0 * wood / total if total else 0.0,
    )


if __name__ == "__main__":
    sys.exit(main())
