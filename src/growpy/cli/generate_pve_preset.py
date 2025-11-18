"""
CLI tool to generate PVE (Procedural Vegetation Editor) preset JSON files.

Creates JSON files compatible with Unreal Engine's PVE Preset Loader node,
matching the Quixel Megaplants format.
"""

import bpy

if hasattr(bpy.utils, "expose_bundled_modules"):
    bpy.utils.expose_bundled_modules()

import argparse
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(
        description="Generate PVE preset JSON files for Unreal Engine",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate single PVE preset
  python src/growpy/cli/generate_pve_preset.py "European Beech" --output beech_preset.json
  
  # Generate multiple variations
  python src/growpy/cli/generate_pve_preset.py "European Beech" --variations 3 --output-dir presets/
  
  # High quality with more growth cycles
  python src/growpy/cli/generate_pve_preset.py "Scots Pine" --cycles 15 --resolution 32
        """,
    )

    parser.add_argument(
        "species",
        help="Species name (e.g., 'European Beech', 'Scots Pine')",
    )

    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output JSON file path (for single preset)",
    )

    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output/pve_presets"),
        help="Output directory (for multiple variations, default: data/output/pve_presets)",
    )

    parser.add_argument(
        "--variations",
        "-n",
        type=int,
        default=1,
        help="Number of variations to generate (default: 1)",
    )

    parser.add_argument(
        "--cycles",
        "-c",
        type=int,
        default=12,
        help="Number of growth cycles/flushes (default: 12)",
    )

    parser.add_argument(
        "--resolution",
        "-r",
        type=int,
        default=24,
        help="Branch resolution (default: 24)",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("PVE Preset JSON Generator")
    print("=" * 60)
    print(f"Species: {args.species}")
    print(f"Variations: {args.variations}")
    print(f"Growth cycles: {args.cycles}")
    print(f"Resolution: {args.resolution}")
    print()

    try:
        from growpy.io.pve_preset_json import (
            generate_pve_preset_for_species,
            generate_pve_preset_json,
        )

        if args.variations == 1 and args.output:
            # Single preset to specific file
            import the_grove_22_core as gc

            from growpy import create_grove

            print(f"Creating grove for '{args.species}'...")
            grove = create_grove(args.species)
            grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

            print(f"Simulating {args.cycles} growth cycles...")
            grove.simulate(flushes=args.cycles)

            print(f"Generating PVE preset JSON...")
            generate_pve_preset_json(
                grove=grove,
                species_name=args.species.replace(" ", "_"),
                output_path=args.output,
            )

            print()
            print("=" * 60)
            print("SUCCESS!")
            print("=" * 60)
            print(f"PVE preset JSON: {args.output}")

        else:
            # Multiple variations to directory
            print(f"Generating {args.variations} variations...")
            generated = generate_pve_preset_for_species(
                species_name=args.species,
                output_dir=args.output_dir,
                num_variations=args.variations,
                growth_cycles=args.cycles,
                resolution=args.resolution,
            )

            print()
            print("=" * 60)
            print("SUCCESS!")
            print("=" * 60)
            print(f"Generated {len(generated)} PVE preset JSON files:")
            for json_path in generated:
                print(f"  - {json_path}")

    except ImportError as e:
        print(f"ERROR: Missing dependencies - {e}")
        print("Make sure you're running in the conda environment:")
        print("  conda activate the-grove")
        return 1
    except Exception as e:
        print(f"ERROR: {e}")
        import traceback

        traceback.print_exc()
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
    exit(main())
