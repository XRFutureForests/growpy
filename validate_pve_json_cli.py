#!/usr/bin/env python
"""
Validate PVE JSON files from command line.

Usage:
    python validate_pve_json_cli.py <json_file> [<json_file2> ...]
"""

import sys
from pathlib import Path

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from growpy.io.validate_pve_json import print_validation_report


def main():
    if len(sys.argv) < 2:
        print("Usage: python validate_pve_json_cli.py <json_file> [<json_file2> ...]")
        print("\nExample:")
        print(
            "  python validate_pve_json_cli.py data/output/forest_quick/european_beech/tree_0003/european_beech_tree_0003.json"
        )
        sys.exit(1)

    json_files = [Path(arg) for arg in sys.argv[1:]]

    # Check all files exist
    missing = [f for f in json_files if not f.exists()]
    if missing:
        print("Error: File(s) not found:")
        for f in missing:
            print(f"  - {f}")
        sys.exit(1)

    all_valid = True
    for json_file in json_files:
        valid = print_validation_report(json_file)
        if not valid:
            all_valid = False

    sys.exit(0 if all_valid else 1)


if __name__ == "__main__":
    main()
