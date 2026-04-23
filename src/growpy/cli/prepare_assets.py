#!/usr/bin/env python3
"""Copy Grove assets (presets, twigs, textures) for species in CSV.

Step 1 of the pipeline. Defaults from config/assets.toml. See docs/cli-reference.md.
"""
import argparse
import logging
import shutil
import sys
from pathlib import Path

import pandas as pd

from growpy.config import get_config
from growpy.config.pve_species_overrides import create_null_placeholder_config
from growpy.io.usd.texture_utils import (
    copy_and_resize_texture,
    ensure_power_of_2_textures,
    process_twig_textures,
)
from growpy.utils.log import setup_logging
from growpy.utils.naming import camel_to_snake, standardize_species_name

logger = logging.getLogger(__name__)


def load_species_csv(csv_path: Path, use_gbif: bool = True) -> pd.DataFrame:
    """Load and validate species CSV.

    Handles two CSV formats:
    1. Forest placement CSV (columns: species, x, y, height) - extracts unique species
    2. Asset lookup CSV (columns: Common Name, Preset, Twig, Bark Texture) - direct use

    Species matching uses GBIF fallback when local matching fails, allowing:
    - Synonym resolution (e.g., "Pedunculate oak" -> "European oak")
    - Scientific name matching (e.g., "Quercus robur" -> "European oak")
    - Misspelling tolerance via GBIF fuzzy matching

    Args:
        csv_path: Path to species CSV file
        use_gbif: Whether to use GBIF for unmatched species (default: True)

    Returns:
        DataFrame with species data in asset lookup format

    Raises:
        FileNotFoundError: If CSV doesn't exist
        ValueError: If CSV is invalid or species not found in lookup
    """
    from growpy.config.paths import _find_species_row, _get_lookup_table

    if not csv_path.exists():
        raise FileNotFoundError(f"Species CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    # Check if this is a forest placement CSV (has "species" column)
    if "species" in df.columns and "Common Name" not in df.columns:
        # Extract unique species names
        unique_species = df["species"].dropna().unique().tolist()

        lookup_df = _get_lookup_table()

        # Try GBIF-enhanced matching if available
        gbif_available = False
        if use_gbif:
            try:
                from growpy.utils.gbif_species import resolve_species_list

                gbif_available = True
            except ImportError:
                pass

        # Filter lookup table by species names
        filtered_rows = []
        unmatched = []

        if gbif_available:
            # Use GBIF-enhanced matching for all species at once
            matches = resolve_species_list(
                unique_species, lookup_df, use_gbif=True, verbose=True
            )
            for species, match in matches.items():
                if match is not None:
                    # Convert Series to single-row DataFrame for concat
                    filtered_rows.append(pd.DataFrame([match]))
                else:
                    unmatched.append(species)
        else:
            # Fallback: local matching only (no GBIF)
            for species in unique_species:
                try:
                    row = _find_species_row(species, use_gbif=False)
                    filtered_rows.append(pd.DataFrame([row]))
                except ValueError:
                    unmatched.append(species)

        if unmatched:
            logger.warning("Could not match %d species: %s", len(unmatched), unmatched)

        if not filtered_rows:
            raise ValueError(
                f"None of the species in {csv_path.name} were found in asset lookup table.\n"
                f"Species: {unique_species}"
            )

        df = pd.concat(filtered_rows, ignore_index=True)

    # Validate we have required columns (either from direct CSV or after lookup)
    required_cols = ["Common Name", "Preset", "Twig", "Bark Texture"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    return df


def main():
    """CSV-driven asset preparation - only copy assets for species in CSV."""
    parser = argparse.ArgumentParser(
        description="Copy assets from The Grove 2.3 to GrowPy assets directory (CSV-driven)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Use default forest placement CSV (auto-extracts 5 species from data/input/test.csv)
    python src/growpy/cli/prepare_assets.py

    # Copy ALL 57 available Grove assets (quick shortcut)
    python src/growpy/cli/prepare_assets.py --all

    # Specify custom Grove source directory
    python src/growpy/cli/prepare_assets.py --grove-dir /path/to/grove

    # Specify custom output directory
    python src/growpy/cli/prepare_assets.py --assets-dir data/my_assets

    # Use a custom CSV file
    python src/growpy/cli/prepare_assets.py --csv my_species.csv

CSV Format Support:
    Automatically detects and handles two CSV formats:
    1. Forest placement (x,y,species,height) → extracts unique species, maps to assets
    2. Asset lookup (Common Name,Preset,Twig,Bark Texture) → direct asset copying
        """,
    )

    from growpy.config.paths import get_project_root

    project_root = get_project_root()
    default_assets = project_root / "data" / "assets"

    parser.add_argument(
        "--grove-dir",
        type=Path,
        default=None,
        help="Path to The Grove 2.3 directory (default: from config)",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=None,
        help="Path to species CSV (default: from config)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Copy ALL available Grove assets (uses comprehensive lookup table, ignores --csv)",
    )
    parser.add_argument(
        "--resize-textures",
        action="store_true",
        default=None,
        help="Resize textures to power-of-2 for Unreal (slow, skip by default)",
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
    config = get_config()
    config.resolve(args)
    if args.quiet:
        config.verbose = False
    setup_logging(verbose=config.verbose)

    # Resolve grove_dir
    grove_dir = config.grove_dir
    if args.grove_dir is not None:
        grove_dir = args.grove_dir
    elif not grove_dir.is_absolute():
        grove_dir = project_root / grove_dir

    # Resolve CSV path
    csv_path = config.csv_file
    if args.csv is not None:
        csv_path = args.csv
    elif not csv_path.is_absolute():
        csv_path = project_root / csv_path

    resize_textures = config.resize_textures

    # Validate paths
    if not grove_dir.exists():
        logger.error("Grove directory not found: %s", grove_dir)
        return 1

    # Override CSV if --all flag is set
    if args.all:
        from growpy.config.paths import _get_lookup_table_path

        csv_path = _get_lookup_table_path()

    if not csv_path.exists():
        logger.error("CSV file not found: %s", csv_path)
        return 1

    # Load species CSV
    try:
        df = load_species_csv(csv_path)
    except Exception as e:
        logger.error("Failed to load species CSV: %s", e)
        return 1

    # Hardcode assets directory
    assets_dir = default_assets

    # Create target directories
    assets_dir.mkdir(parents=True, exist_ok=True)
    (assets_dir / "presets").mkdir(exist_ok=True)
    (assets_dir / "textures").mkdir(exist_ok=True)
    (assets_dir / "twigs").mkdir(exist_ok=True)
    (assets_dir / "pve_configs").mkdir(exist_ok=True)

    # Track statistics
    stats = {
        "presets_copied": 0,
        "presets_missing": 0,
        "twigs_copied": 0,
        "twigs_missing": 0,
        "alpha_extracted": 0,
        "textures_copied": 0,
        "textures_missing": 0,
        "pve_configs_created": 0,
    }

    # Copy presets with standardized naming
    src_presets = grove_dir / "presets"
    dst_presets = assets_dir / "presets"

    for _, row in df.iterrows():
        preset_file = row["Preset"]
        common_name = row["Common Name"]
        if pd.isna(preset_file) or str(preset_file).strip() in ["", "—"]:
            continue

        src_file = src_presets / preset_file

        # Standardize preset name: "Fagaceae - Beech.seed.json" -> "european_beech.seed.json"
        standardized_name = standardize_species_name(common_name)
        dst_file = dst_presets / f"{standardized_name}.seed.json"

        if src_file.exists():
            # Skip if destination already has calibration data embedded —
            # overwriting would destroy the yield table calibration from step 3.
            if dst_file.exists():
                try:
                    import json as _json
                    with open(dst_file) as _f:
                        _existing = _json.load(_f)
                    if "_yield_table_calibration" in _existing:
                        logger.debug(
                            "Preset %s has calibration data — skipping overwrite",
                            dst_file.name,
                        )
                        stats["presets_copied"] += 1
                        continue
                except Exception:
                    pass
            shutil.copy2(src_file, dst_file)
            stats["presets_copied"] += 1
        else:
            logger.warning("Preset not found: %s (for %s)", preset_file, common_name)
            stats["presets_missing"] += 1

    # Copy twigs (with CamelCase -> snake_case conversion)
    src_twigs = grove_dir / "twigs"
    dst_twigs = assets_dir / "twigs"

    # Build list of twig source directories: Grove first, then custom overrides
    custom_twigs_dir = config.custom_twigs_dir
    if not custom_twigs_dir.is_absolute():
        custom_twigs_dir = project_root / custom_twigs_dir

    for _, row in df.iterrows():
        twig_name = row["Twig"]
        if pd.isna(twig_name) or twig_name in ["—", ""]:
            continue

        twig_name_original = str(twig_name).strip()

        # Check if this is CamelCase (from Grove) or snake_case (already standardized)
        # If it contains uppercase letters, it's likely CamelCase from Grove
        if any(c.isupper() for c in twig_name_original):
            twig_name_snake = camel_to_snake(twig_name_original)
        else:
            twig_name_snake = twig_name_original

        # Search order: custom twigs dir (CamelCase), Grove source, Grove reverse lookup
        src_twig_dir = None

        # 1. Custom twigs directory (CamelCase match)
        if custom_twigs_dir.exists():
            candidate = custom_twigs_dir / twig_name_original
            if candidate.exists():
                src_twig_dir = candidate

        # 2. Grove source (CamelCase match)
        if src_twig_dir is None and any(c.isupper() for c in twig_name_original):
            candidate = src_twigs / twig_name_original
            if candidate.exists():
                src_twig_dir = candidate

        # 3. Grove reverse lookup (snake_case -> CamelCase)
        if src_twig_dir is None:
            for src_dir in src_twigs.iterdir():
                if src_dir.is_dir() and camel_to_snake(src_dir.name) == twig_name_snake:
                    src_twig_dir = src_dir
                    break

        if src_twig_dir is not None:
            dst_twig_dir = dst_twigs / twig_name_snake

            if dst_twig_dir.exists():
                shutil.rmtree(dst_twig_dir)
            shutil.copytree(src_twig_dir, dst_twig_dir)

            if resize_textures:
                twig_textures_dir = dst_twig_dir / "textures"
                if twig_textures_dir.exists():
                    ensure_power_of_2_textures(twig_textures_dir)
                ensure_power_of_2_textures(dst_twig_dir)

            # Process twig textures:
            # 1. Standardize texture naming to consistent pattern
            # 2. Convert bump maps to normal maps
            # 3. Extract alpha from diffuse if no dedicated alpha exists
            # 4. Strip alpha channel from diffuse textures (RGBA -> RGB)
            # 5. Validate all required textures exist
            tex_results = process_twig_textures(dst_twig_dir)
            if tex_results.get("alpha_path"):
                stats["alpha_extracted"] += 1

            if tex_results.get("copied_count", 0) > 0:
                logger.info(
                    "Standardized %d texture files", tex_results["copied_count"]
                )

            if tex_results.get("is_valid"):
                logger.info("%s", tex_results.get("validation_message", ""))
            else:
                logger.warning(
                    "%s",
                    tex_results.get("validation_message", "Texture validation failed"),
                )

            stats["twigs_copied"] += 1
        else:
            logger.warning(
                "Twig directory not found: %s (checked Grove and custom)",
                twig_name_original,
            )
            stats["twigs_missing"] += 1

    # Copy bark textures with CamelCase -> snake_case conversion (preserves age numbers)
    src_textures = grove_dir / "textures"
    dst_textures = assets_dir / "textures"

    for _, row in df.iterrows():
        texture_file = row["Bark Texture"]
        if pd.isna(texture_file) or not texture_file.strip():
            continue

        src_file = src_textures / texture_file

        # Convert CamelCase to snake_case, preserving age numbers and adding _bark suffix
        # Examples: "Beech60.jpg" -> "beech_60_bark.jpg"
        #           "BaldCypress80.jpg" -> "bald_cypress_80_bark.jpg"
        #           "NorthernRedOak60.jpg" -> "northern_red_oak_60_bark.jpg"
        texture_stem = Path(texture_file).stem
        file_ext = Path(texture_file).suffix

        # Convert to snake_case (handles numbers correctly)
        standardized_name = camel_to_snake(texture_stem)
        dst_file = dst_textures / f"{standardized_name}_bark{file_ext}"

        if src_file.exists():
            if resize_textures:
                # Resize to power-of-2 for Unreal virtual texture support (slow)
                if copy_and_resize_texture(src_file, dst_file):
                    stats["textures_copied"] += 1
                else:
                    shutil.copy2(src_file, dst_file)
                    stats["textures_copied"] += 1
            else:
                # Just copy without resizing (fast)
                shutil.copy2(src_file, dst_file)
                stats["textures_copied"] += 1
        else:
            logger.warning("Bark texture not found: %s", src_file)
            stats["textures_missing"] += 1

    # Generate PVE config files with null placeholders for each species
    dst_pve_configs = assets_dir / "pve_configs"

    for _, row in df.iterrows():
        common_name = row["Common Name"]
        standardized_name = standardize_species_name(common_name)

        config_file = dst_pve_configs / f"{standardized_name}_pve.json"

        # Only create if it doesn't exist (preserve user customizations)
        if not config_file.exists():
            create_null_placeholder_config(config_file, standardized_name, common_name)
            stats["pve_configs_created"] += 1

    logger.info(
        "Assets copied: %d presets, %d twigs, %d textures, %d PVE configs",
        stats["presets_copied"],
        stats["twigs_copied"],
        stats["textures_copied"],
        stats["pve_configs_created"],
    )
    if (
        stats["presets_missing"] > 0
        or stats["twigs_missing"] > 0
        or stats["textures_missing"] > 0
    ):
        logger.warning(
            "Missing items: %d presets, %d twigs, %d textures",
            stats["presets_missing"],
            stats["twigs_missing"],
            stats["textures_missing"],
        )
        return 1

    logger.info("All assets prepared successfully.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
