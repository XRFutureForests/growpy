#!/usr/bin/env python3
"""Generate species library - export template trees for each configured species.

This script exports trees in multiple formats (FBX, USD) with optional twig instances.
Uses Grove's native USD export for preserving all attributes, and includes twig
placement as PointInstancer prims.

Usage:
    python generate_species_library.py --formats fbx usda --include-twigs
"""

from pathlib import Path

from tqdm import tqdm

try:
    import the_grove_22_core as gc
except ImportError:
    gc = None

from growpy import EXPORT_AVAILABLE, GrowPyConfig, create_grove, get_config


def place_twigs_on_species_library(
    tree_usd_files: list, twigs_dir: Path, output_dir: Path
) -> None:
    """Place twigs on exported species library USD files.

    Args:
        tree_usd_files: List of tree USD file paths
        twigs_dir: Directory containing twig files
        output_dir: Output directory for tree+twig assemblies
    """
    import bpy

    from growpy.io.twig_placement import export_twig_placements_to_usd

    twigs_output = output_dir / "with_twigs"
    twigs_output.mkdir(parents=True, exist_ok=True)

    for tree_file in tree_usd_files:
        try:
            species_name = tree_file.stem

            # Look for twig directory matching species
            twig_candidates = list(twigs_dir.glob(f"*{species_name}*Twig"))
            if not twig_candidates:
                # Try without species name
                twig_candidates = list(twigs_dir.glob("*Twig"))

            if not twig_candidates:
                print(f"  No twig found for {species_name}, skipping")
                continue

            twig_dir = twig_candidates[0]
            print(f"  {species_name}: using {twig_dir.name}")

            # Find twig USD files
            twig_files = list(twig_dir.glob("*.usda")) + list(twig_dir.glob("*.usd"))
            if not twig_files:
                print(f"    No USD twigs found")
                continue

            # Load tree to extract placement data
            bpy.ops.wm.read_factory_settings(use_empty=True)
            bpy.ops.wm.usd_import(filepath=str(tree_file))

            tree_obj = None
            for obj in bpy.context.scene.objects:
                if obj.type == "MESH":
                    tree_obj = obj
                    break

            if not tree_obj:
                print(f"    No mesh found")
                continue

            # Map twig types to USD files
            twig_usd_map = {}
            for twig_file in twig_files:
                name_lower = twig_file.stem.lower()
                if "end" in name_lower or "long" in name_lower:
                    twig_usd_map["twig_long"] = twig_file
                elif "side" in name_lower or "short" in name_lower:
                    twig_usd_map["twig_short"] = twig_file
                else:
                    # Use generic twig for all types
                    twig_usd_map["twig_long"] = twig_file
                    twig_usd_map["twig_short"] = twig_file
                    break

            if not twig_usd_map:
                print(f"    Could not map twig types")
                continue

            # Export assembly with twigs
            output_file = twigs_output / f"{species_name}_with_twigs.usda"
            if export_twig_placements_to_usd(
                tree_file, twig_usd_map, output_file, tree_obj
            ):
                print(f"    Created: {output_file.name}")

        except Exception as e:
            print(f"  Failed for {tree_file.name}: {e}")
            continue


def export_all_species(
    config: GrowPyConfig,
    output_dir: Path,
    growth_flushes: list = [10],
    variants_per_species: int = 1,
    formats: list = ["usda"],
    include_twigs: bool = False,
    resolution: int = 24,
    create_nanite_assembly: bool = True,
) -> None:
    """Export all configured species as template trees in multiple formats.

    Args:
        config: GrowPy configuration with species settings
        output_dir: Directory to save export files
        growth_flushes: List of growth flush counts to export (e.g., [10, 25, 50, 75])
        variants_per_species: Number of variants to generate per species per flush count
        formats: List of export formats ('fbx', 'usd', 'usda')
        include_twigs: Whether to include twig instances (USD only)
        resolution: Branch resolution (4-32, higher = more detailed)
        create_nanite_assembly: Create Nanite Assembly USD for Unreal Engine (default: True)
    """
    if not EXPORT_AVAILABLE and "fbx" in formats:
        print("FBX export not available - bpy module required")
        formats = [f for f in formats if f in ["usd", "usda"]]
        if not formats:
            print("No valid export formats available")
            return

    output_dir.mkdir(parents=True, exist_ok=True)
    species_list = config.get_all_species()

    if not species_list:
        print("No species found in configuration")
        return

    # Create format-specific directories
    fbx_dir = output_dir / "FBX" if "fbx" in formats else None
    usd_dir = output_dir / "USD" if any(f in formats for f in ["usd", "usda"]) else None

    if fbx_dir:
        fbx_dir.mkdir(parents=True, exist_ok=True)
    if usd_dir:
        usd_dir.mkdir(parents=True, exist_ok=True)

    exported_count = 0
    failed_count = 0
    export_results = {"fbx": [], "usd": [], "failed": []}

    total_combinations = len(species_list) * len(growth_flushes) * variants_per_species

    print(f"\nExporting {len(species_list)} species")
    print(f"Formats: {', '.join(formats)}")
    print(f"Resolution: {resolution}")
    print(f"Include twigs: {include_twigs}")
    print(f"Growth flushes: {growth_flushes}")
    print(f"Variants per species: {variants_per_species}")
    print(f"Total trees to export: {total_combinations}\n")

    for species in tqdm(species_list, desc="Exporting species"):
        # Clean species name for filename
        species_clean = (
            "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
            .strip()
            .replace(" ", "_")
        )
        if not species_clean:
            species_clean = f"species_{exported_count}"

        for flush_count in growth_flushes:
            for variant_num in range(1, variants_per_species + 1):
                try:
                    # Create grove for this species
                    grove = create_grove(species)

                    # Add single tree at origin
                    grove.add_new_tree(
                        gc.Vector(0, 0, 0),  # Origin
                        gc.Vector(0, 0, 1),  # Up direction
                        0,  # No delay
                    )

                    # Simulate realistic growth
                    grove.simulate(flushes=flush_count)

                    # Construct filename with flush count and variant number
                    filename_base = f"{species_clean}_f{flush_count:02d}_var{variant_num}"

                    format_success = False

                    # Export USD formats (with optional twigs)
                    if usd_dir:
                        from growpy.io.blender_export import (
                            export_grove_tree_as_usda_native,
                            get_twig_usd_map_for_species,
                        )

                        usd_ext = "usda" if "usda" in formats else "usd"
                        usd_path = usd_dir / f"{filename_base}.{usd_ext}"

                        # Get twig USD paths if including twigs
                        twig_usd_map = None
                        if include_twigs:
                            twig_usd_map = get_twig_usd_map_for_species(species, config, prefer_skeletal=False)

                        # Export using native USD export with twigs
                        if export_grove_tree_as_usda_native(
                            grove=grove,
                            output_path=usd_path,
                            species_name=species,
                            twig_usd_paths=twig_usd_map,
                            include_twigs=include_twigs and twig_usd_map is not None,
                            use_point_instancer=True,
                            convert_to_ue=True,
                            create_nanite_assembly=create_nanite_assembly,
                            resolution=resolution,
                            resolution_reduce=0.8,
                            texture_repeat=3,
                            build_cutoff_age=0,
                            build_cutoff_thickness=0.0,
                            build_blend=True,
                            build_end_cap=True,
                        ):
                            format_success = True
                            export_results["usd"].append(usd_path)

                    # Export FBX format
                    if fbx_dir and EXPORT_AVAILABLE:
                        from growpy.io.blender_export import _export_fbx_internal

                        fbx_path = fbx_dir / f"{filename_base}.fbx"

                        if _export_fbx_internal(
                            grove=grove,
                            output_path=fbx_path,
                            species_name=species,
                            include_skeleton=True,
                            include_twig_attributes=True,
                            config=config,
                        ):
                            format_success = True
                            export_results["fbx"].append(fbx_path)

                    if format_success:
                        exported_count += 1
                    else:
                        failed_count += 1
                        export_results["failed"].append(f"{species} (f{flush_count}_var{variant_num})")

                except Exception as e:
                    print(f"\nFailed to export {species} f{flush_count}_var{variant_num}: {e}")
                    failed_count += 1
                    export_results["failed"].append(f"{species} (f{flush_count}_var{variant_num})")
                    continue

    # Print summary
    print(f"\n{'='*60}")
    print("Export Complete")
    print(f"{'='*60}")
    print(f"Successful: {exported_count}")
    print(f"Failed: {failed_count}")

    if export_results["usd"]:
        print(f"\nUSD files: {len(export_results['usd'])}")
        print(f"  Location: {usd_dir}")

    if export_results["fbx"]:
        print(f"\nFBX files: {len(export_results['fbx'])}")
        print(f"  Location: {fbx_dir}")

    if export_results["failed"]:
        print(f"\nFailed species ({len(export_results['failed'])}):")
        for species in export_results["failed"]:
            print(f"  - {species}")

    print()


def main():
    """Main export function."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate species library - export template trees for all configured species",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Export all species as USDA with default settings
    python generate_species_library.py

    # Export 2 variants of each species for multiple flush counts
    python generate_species_library.py --flushes 10 25 50 75 --variants 2

    # Export as both FBX and USDA with twigs
    python generate_species_library.py --formats fbx usda --include-twigs

    # Export high quality with custom growth
    python generate_species_library.py --resolution 32 --flushes 15 20 25

    # Export to custom directory
    python generate_species_library.py --output-dir data/output/species --formats fbx usda

    # Export with twigs as point instances (USD only)
    python generate_species_library.py --formats usda --include-twigs --variants 3
        """,
    )

    parser.add_argument(
        "--flushes",
        type=int,
        nargs="+",
        default=[10],
        help="Growth flush counts to simulate (default: 10). Can specify multiple: --flushes 10 25 50 75",
    )
    parser.add_argument(
        "--variants",
        type=int,
        default=1,
        help="Number of variants to generate per species per flush count (default: 1)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output/species_library"),
        help="Directory to save species library (default: data/output/species_library)",
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["fbx", "usd", "usda"],
        default=["usda"],
        help="Export formats (default: usda). Can specify multiple: --formats fbx usda",
    )
    parser.add_argument(
        "--include-twigs",
        action="store_true",
        help="Include twig instances in USD exports (uses PointInstancer for memory efficiency)",
    )
    parser.add_argument(
        "--resolution",
        type=int,
        default=24,
        choices=range(4, 33),
        metavar="4-32",
        help="Branch resolution - vertices around circumference (default: 24, higher=more detail)",
    )
    parser.add_argument(
        "--create-nanite-assembly",
        action="store_true",
        default=True,
        help="Create Nanite Assembly USD files for Unreal Engine 5.7+ (default: True)",
    )
    parser.add_argument(
        "--no-nanite-assembly",
        dest="create_nanite_assembly",
        action="store_false",
        help="Skip Nanite Assembly USD creation",
    )

    args = parser.parse_args()

    print(f"\n{'='*60}")
    print("Grove Species Library Generator")
    print(f"{'='*60}")

    try:
        config = get_config()
        export_all_species(
            config=config,
            output_dir=args.output_dir,
            growth_flushes=args.flushes,
            variants_per_species=args.variants,
            formats=args.formats,
            include_twigs=args.include_twigs,
            resolution=args.resolution,
            create_nanite_assembly=args.create_nanite_assembly,
        )
    except Exception as e:
        print(f"\n✗ Export failed: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
