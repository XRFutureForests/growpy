"""Validate Nanite Assembly USD files for Unreal Engine compatibility.

This script validates USD files to ensure they follow the Unreal Engine 5.7+
Nanite Assembly schema correctly.

Usage:
    python validate_nanite_assembly.py <usd_file>
    python validate_nanite_assembly.py <directory>  # validates all .usda files
"""

import sys
from pathlib import Path

from growpy.io.unreal_nanite_assembly import validate_nanite_assembly


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_nanite_assembly.py <usd_file_or_directory>")
        print("\nValidates USD files for Unreal Engine Nanite Assembly compatibility")
        sys.exit(1)

    target_path = Path(sys.argv[1])

    if not target_path.exists():
        print(f"Error: Path not found: {target_path}")
        sys.exit(1)

    # Collect USD files to validate
    usd_files = []
    if target_path.is_file():
        if target_path.suffix.lower() in [".usd", ".usda", ".usdc"]:
            usd_files.append(target_path)
        else:
            print(f"Error: Not a USD file: {target_path}")
            sys.exit(1)
    else:
        # Find all USD files in directory
        usd_files.extend(target_path.glob("**/*.usda"))
        usd_files.extend(target_path.glob("**/*.usd"))
        usd_files.extend(target_path.glob("**/*.usdc"))

    if not usd_files:
        print(f"No USD files found in: {target_path}")
        sys.exit(1)

    print(f"\nValidating {len(usd_files)} USD file(s)...\n")

    # Validate each file
    all_valid = True
    results = []

    for usd_file in sorted(usd_files):
        result = validate_nanite_assembly(usd_file)
        results.append((usd_file, result))

        if not result["valid"]:
            all_valid = False

    # Summary
    print("\n" + "=" * 80)
    print("VALIDATION SUMMARY")
    print("=" * 80)

    valid_count = sum(1 for _, r in results if r["valid"])
    print(f"\nTotal: {len(results)} file(s)")
    print(f"Valid: {valid_count}")
    print(f"Invalid: {len(results) - valid_count}")

    # Group by mesh type
    static_count = sum(1 for _, r in results if r["mesh_type"] == "staticMesh")
    skeletal_count = sum(1 for _, r in results if r["mesh_type"] == "skeletalMesh")

    if static_count > 0:
        print(f"\nStatic Mesh Assemblies: {static_count}")
    if skeletal_count > 0:
        print(f"Skeletal Mesh Assemblies: {skeletal_count}")

    # List files with errors
    error_files = [(f, r) for f, r in results if not r["valid"]]
    if error_files:
        print("\nFiles with errors:")
        for usd_file, result in error_files:
            print(f"  - {usd_file.name}")
            for error in result["errors"]:
                print(f"      {error}")

    print()

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
