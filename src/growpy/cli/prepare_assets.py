#!/usr/bin/env python3
"""
Prepare Grove 2.2 assets for GrowPy.

CSV-driven asset preparation: only copies assets for species listed in input CSV
- Species presets (.seed.json files)
- Twig directories (converted from CamelCase to snake_case)
- Bark texture files

Supports two CSV formats:
  1. Forest placement CSV (x, y, species, height) - auto-extracts unique species
  2. Asset lookup CSV (Common Name, Preset, Twig, Bark Texture) - direct asset reference

Quick Start:
    python src/growpy/cli/prepare_assets.py

Common Flags:
    --grove-dir PATH    Source directory (default: src/the_grove_22)
    --assets-dir PATH   Target directory (default: data/assets)
    --csv PATH          Species CSV (default: data/input/test.csv)
    --all               Copy ALL 57 Grove assets (ignores --csv)

Full Documentation:
    See docs/guides/cli-reference.md for complete flag reference and examples

Usage:
    python prepare_assets.py [options]
"""
import argparse
import re
import shutil
import sys
from pathlib import Path

import pandas as pd


def camel_to_snake(name: str) -> str:
    """Convert CamelCase to snake_case.

    Args:
        name: CamelCase string

    Returns:
        snake_case string
    """
    # Insert underscore before uppercase letters
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    # Insert underscore before uppercase letters followed by lowercase
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.lower()


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


def load_species_csv(csv_path: Path, script_dir: Path) -> pd.DataFrame:
    """Load and validate species CSV.

    Handles two CSV formats:
    1. Forest placement CSV (columns: species, x, y, height) - extracts unique species
    2. Asset lookup CSV (columns: Common Name, Preset, Twig, Bark Texture) - direct use

    Args:
        csv_path: Path to species CSV file
        script_dir: Path to project root for loading asset lookup table

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
        print(f"[INFO] Detected forest placement CSV, extracting unique species...")

        # Extract unique species names
        unique_species = df["species"].dropna().unique().tolist()
        print(
            f"[INFO] Found {len(unique_species)} unique species: {', '.join(unique_species)}"
        )

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

        # Filter lookup table by species names (match Common Name or Aliases)
        filtered_rows = []
        for species in unique_species:
            # Try matching Common Name
            match = lookup_df[lookup_df["Common Name"].str.lower() == species.lower()]

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
                print(f"[WARN] Species '{species}' not found in asset lookup table")

        if not filtered_rows:
            raise ValueError(
                f"None of the species in {csv_path.name} were found in asset lookup table.\n"
                f"Species: {unique_species}"
            )

        df = pd.concat(filtered_rows, ignore_index=True)
        print(f"[INFO] Matched {len(df)} species entries in asset lookup table")

    # Validate we have required columns (either from direct CSV or after lookup)
    required_cols = ["Common Name", "Preset", "Twig", "Bark Texture"]
    missing = [col for col in required_cols if col not in df.columns]
    if missing:
        raise ValueError(f"CSV missing required columns: {missing}")

    return df


def main():
    """CSV-driven asset preparation - only copy assets for species in CSV."""
    parser = argparse.ArgumentParser(
        description="Copy assets from The Grove 2.2 to GrowPy assets directory (CSV-driven)",
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
    default_grove = script_dir / "src" / "the_grove_22"
    default_assets = script_dir / "data" / "assets"
    default_csv = script_dir / "data" / "input" / "test.csv"

    parser.add_argument(
        "--grove-dir",
        type=Path,
        default=default_grove,
        help=f"Path to The Grove 2.2 directory (default: {default_grove})",
    )
    parser.add_argument(
        "--assets-dir",
        type=Path,
        default=default_assets,
        help=f"Path to assets output directory (default: {default_assets})",
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=default_csv,
        help=f"Path to species CSV (default: {default_csv})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Copy ALL available Grove assets (uses comprehensive lookup table, ignores --csv)",
    )

    args = parser.parse_args()

    print("📦 GrowPy Asset Preparation (CSV-driven)")
    print("=" * 40)

    # Validate paths
    if not args.grove_dir.exists():
        print(f"[FAIL] Grove directory not found: {args.grove_dir}")
        return 1

    # Override CSV if --all flag is set
    if args.all:
        args.csv = script_dir / "src" / "growpy" / "config" / "tree_asset_lookup.csv"
        print(f"[INFO] --all flag set: copying ALL available Grove assets (57 species)")

    if not args.csv.exists():
        print(f"[FAIL] Species CSV not found: {args.csv}")
        return 1

    print(f"📂 Source: {args.grove_dir}")
    print(f"📂 Target: {args.assets_dir}")
    print(f"📄 Species CSV: {args.csv}")

    # Load species CSV
    try:
        df = load_species_csv(args.csv, script_dir)
        print(f"\n[CSV] Loaded {len(df)} species from CSV")
    except Exception as e:
        print(f"[FAIL] Error loading CSV: {e}")
        return 1

    # Create target directories
    args.assets_dir.mkdir(parents=True, exist_ok=True)
    (args.assets_dir / "presets").mkdir(exist_ok=True)
    (args.assets_dir / "textures").mkdir(exist_ok=True)
    (args.assets_dir / "twigs").mkdir(exist_ok=True)

    # Track statistics
    stats = {
        "presets_copied": 0,
        "presets_missing": 0,
        "twigs_copied": 0,
        "twigs_missing": 0,
        "textures_copied": 0,
        "textures_missing": 0,
    }

    # Copy presets with standardized naming
    print(f"\n[PRESETS] Copying and standardizing species presets...")
    src_presets = args.grove_dir / "presets"
    dst_presets = args.assets_dir / "presets"

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
            print(f"  ✓ {preset_file} -> {dst_file.name}")
        else:
            stats["presets_missing"] += 1
            print(f"  ✗ {preset_file} (not found)")

    # Copy twigs (with CamelCase -> snake_case conversion)
    print(f"\n[TWIGS] Copying and standardizing twig directories...")
    src_twigs = args.grove_dir / "twigs"
    dst_twigs = args.assets_dir / "twigs"

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

            stats["twigs_copied"] += 1
            print(f"  ✓ {original_name} -> {twig_name_snake}")
        else:
            stats["twigs_missing"] += 1
            print(f"  ✗ {twig_name_original} (not found)")

    # Copy bark textures with standardized naming
    print(f"\n[TEXTURES] Copying and standardizing bark textures...")
    src_textures = args.grove_dir / "textures"
    dst_textures = args.assets_dir / "textures"

    for _, row in df.iterrows():
        texture_file = row["Bark Texture"]
        common_name = row["Common Name"]
        if pd.isna(texture_file) or not texture_file.strip():
            continue

        src_file = src_textures / texture_file

        # Standardize texture name: "Beech60.jpg" -> "european_beech_bark.jpg"
        standardized_name = standardize_species_name(common_name)
        file_ext = Path(texture_file).suffix
        dst_file = dst_textures / f"{standardized_name}_bark{file_ext}"

        if src_file.exists():
            shutil.copy2(src_file, dst_file)
            stats["textures_copied"] += 1
            print(f"  ✓ {texture_file} -> {dst_file.name}")
        else:
            stats["textures_missing"] += 1
            print(f"  ✗ {texture_file} (not found)")

    # Print summary
    print(f"\n{'='*40}")
    print(f"[SUMMARY]")
    print(
        f"  Presets:  {stats['presets_copied']} copied, {stats['presets_missing']} missing"
    )
    print(
        f"  Twigs:    {stats['twigs_copied']} copied, {stats['twigs_missing']} missing"
    )
    print(
        f"  Textures: {stats['textures_copied']} copied, {stats['textures_missing']} missing"
    )
    print(f"\n[DONE] Asset preparation complete!")

    if (
        stats["presets_missing"] > 0
        or stats["twigs_missing"] > 0
        or stats["textures_missing"] > 0
    ):
        print(f"[WARN] Some assets were not found - check CSV entries")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
