#!/usr/bin/env python3
"""Copy Grove assets (presets, twigs, textures) for species in CSV.

Step 1 of the pipeline. Defaults from growpy.toml [assets]. See docs/cli-reference.md.
"""
import argparse

# Direct imports using importlib to avoid circular import through growpy package __init__.py
# These modules only depend on numpy/PIL, not the heavy sklearn/bpy imports
import importlib.util
import logging
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def _import_module_directly(module_name: str, file_path: Path):
    """Import a module directly from file path, bypassing package __init__.py."""
    spec = importlib.util.spec_from_file_location(module_name, file_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Get the src directory
_src_dir = Path(__file__).parent.parent.parent

# Import texture_utils directly (only needs numpy, PIL)
_texture_utils = _import_module_directly(
    "texture_utils", _src_dir / "growpy" / "io" / "texture_utils.py"
)
ensure_power_of_2_textures = _texture_utils.ensure_power_of_2_textures
copy_and_resize_texture = _texture_utils.copy_and_resize_texture
process_twig_textures = _texture_utils.process_twig_textures

# Import pve_species_overrides directly (only needs json, pathlib)
_pve_overrides = _import_module_directly(
    "pve_species_overrides", _src_dir / "growpy" / "config" / "pve_species_overrides.py"
)
create_null_placeholder_config = _pve_overrides.create_null_placeholder_config

# Import config core directly (only needs tomllib, pathlib)
_config_core = _import_module_directly(
    "config_core", _src_dir / "growpy" / "config" / "core.py"
)
get_config = _config_core.get_config

# Import log module directly
_log_module = _import_module_directly("log", _src_dir / "growpy" / "utils" / "log.py")
setup_logging = _log_module.setup_logging


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
    """
    # Insert underscore before uppercase letters
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    # Insert underscore before uppercase letters followed by lowercase
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    # Insert underscore before numbers (after letters)
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
    # Replace spaces and special characters with underscores
    name = re.sub(r"[^\w\s-]", "", common_name.lower())
    name = re.sub(r"[-\s]+", "_", name)
    return name.strip("_")


def load_species_csv(
    csv_path: Path, script_dir: Path, use_gbif: bool = True
) -> pd.DataFrame:
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
        script_dir: Path to project root for loading asset lookup table
        use_gbif: Whether to use GBIF for unmatched species (default: True)

    Returns:
        DataFrame with species data in asset lookup format

    Raises:
        FileNotFoundError: If CSV doesn't exist
        ValueError: If CSV is invalid or species not found in lookup
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Species CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    # Check if this is a forest placement CSV (has "species" column)
    if "species" in df.columns and "Common Name" not in df.columns:
        # Extract unique species names
        unique_species = df["species"].dropna().unique().tolist()

        # Load the asset lookup table
        asset_lookup_path = (
            script_dir / "src" / "growpy" / "config" / "tree_asset_lookup.csv"
        )
        if not asset_lookup_path.exists():
            raise FileNotFoundError(
                f"Asset lookup table not found: {asset_lookup_path}\n"
                f"Need this to map species names to assets."
            )

        lookup_df = pd.read_csv(asset_lookup_path)

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
            # Fallback: local matching only
            for species in unique_species:
                # Try matching Common Name
                match = lookup_df[
                    lookup_df["Common Name"].str.lower() == species.lower()
                ]

                # Try matching Scientific Name
                if match.empty and "Scientific Name" in lookup_df.columns:
                    match = lookup_df[
                        lookup_df["Scientific Name"].str.lower() == species.lower()
                    ]

                # Try matching aliases if no direct match
                if match.empty and "Aliases" in lookup_df.columns:
                    for idx, row in lookup_df.iterrows():
                        aliases = str(row.get("Aliases", "")).lower()
                        if species.lower() in [a.strip() for a in aliases.split(",")]:
                            match = lookup_df.iloc[[idx]]
                            break

                if not match.empty:
                    filtered_rows.append(match)
                else:
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

    # Default paths
    script_dir = Path(__file__).parent.parent.parent.parent
    default_assets = script_dir / "data" / "assets"

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

    args = parser.parse_args()

    # Resolve config: TOML defaults + CLI overrides
    config = get_config()
    config.resolve(args)
    setup_logging(verbose=config.verbose)

    # Resolve grove_dir
    grove_dir = config.grove_dir
    if args.grove_dir is not None:
        grove_dir = args.grove_dir
    elif not grove_dir.is_absolute():
        grove_dir = script_dir / grove_dir

    # Resolve CSV path
    csv_path = config.csv_file
    if args.csv is not None:
        csv_path = args.csv
    elif not csv_path.is_absolute():
        csv_path = script_dir / csv_path

    resize_textures = config.resize_textures

    # Validate paths
    if not grove_dir.exists():
        return 1

    # Override CSV if --all flag is set
    if args.all:
        csv_path = script_dir / "src" / "growpy" / "config" / "tree_asset_lookup.csv"

    if not csv_path.exists():
        return 1

    # Load species CSV
    try:
        df = load_species_csv(csv_path, script_dir)
    except Exception as e:
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
        if pd.isna(preset_file) or not preset_file.strip():
            continue

        src_file = src_presets / preset_file

        # Standardize preset name: "Fagaceae - Beech.seed.json" -> "european_beech.seed.json"
        standardized_name = standardize_species_name(common_name)
        dst_file = dst_presets / f"{standardized_name}.seed.json"

        if src_file.exists():
            shutil.copy2(src_file, dst_file)
            stats["presets_copied"] += 1
        else:
            stats["presets_missing"] += 1

    # Copy twigs (with CamelCase -> snake_case conversion)
    src_twigs = grove_dir / "twigs"
    dst_twigs = assets_dir / "twigs"

    for _, row in df.iterrows():
        twig_name = row["Twig"]
        if pd.isna(twig_name) or twig_name in ["—", ""]:
            continue

        twig_name_original = str(twig_name).strip()

        # Check if this is CamelCase (from Grove) or snake_case (already standardized)
        # If it contains uppercase letters, it's likely CamelCase from Grove
        if any(c.isupper() for c in twig_name_original):
            # CamelCase - look for direct match in Grove source
            src_twig_dir = src_twigs / twig_name_original
            twig_name_snake = camel_to_snake(twig_name_original)
        else:
            # Already snake_case - try to find matching CamelCase directory
            twig_name_snake = twig_name_original
            found_dirs = []
            for src_dir in src_twigs.iterdir():
                if src_dir.is_dir():
                    converted = camel_to_snake(src_dir.name)
                    if converted == twig_name_snake:
                        found_dirs.append(src_dir)
            src_twig_dir = (
                found_dirs[0] if found_dirs else src_twigs / twig_name_original
            )

        if src_twig_dir.exists():
            original_name = src_twig_dir.name
            dst_twig_dir = dst_twigs / twig_name_snake

            # Copy with new name
            if dst_twig_dir.exists():
                shutil.rmtree(dst_twig_dir)
            shutil.copytree(src_twig_dir, dst_twig_dir)

            # Optional: Resize twig textures to power-of-2 for Unreal virtual texture support
            # This is slow for large textures, so skip by default
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

            # Log texture validation result
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

    # Print summary

    if (
        stats["presets_missing"] > 0
        or stats["twigs_missing"] > 0
        or stats["textures_missing"] > 0
    ):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
