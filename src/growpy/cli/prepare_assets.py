#!/usr/bin/env python3
"""
Prepare Grove 2.2 assets for GrowPy.

Copies species presets, textures, and twig files from The Grove 2.2 installation.

Quick Start:
    python prepare_assets.py

Common Flags:
    --grove-dir PATH    Source directory (default: src/the_grove_22)
    --assets-dir PATH   Target directory (default: data/assets)

Full Documentation:
    See docs/guides/cli-reference.md for complete flag reference and examples

Usage:
    python prepare_assets.py [options]
"""
import argparse
import shutil
import sys
from pathlib import Path


def main():
    """Simple asset preparation - just copy three folders."""
    parser = argparse.ArgumentParser(
        description="Copy assets from The Grove 2.2 to GrowPy assets directory",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Use default paths (src/the_grove_22 -> data/assets)
    python prepare_assets.py

    # Specify custom paths
    python prepare_assets.py --grove-dir /path/to/grove --assets-dir /path/to/assets
        """,
    )

    # Default paths
    script_dir = Path(__file__).parent.parent.parent.parent
    default_grove = script_dir / "src" / "the_grove_22"
    default_assets = script_dir / "data" / "assets"

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

    args = parser.parse_args()

    print("📦 GrowPy Asset Preparation")
    print("=" * 30)

    if not args.grove_dir.exists():
        print(f"❌ Grove directory not found: {args.grove_dir}")
        return 1

    print(f"📂 Source: {args.grove_dir}")
    print(f"📂 Target: {args.assets_dir}")

    # Create target directory
    args.assets_dir.mkdir(parents=True, exist_ok=True)

    # Copy the three main folders
    folders_to_copy = ["presets", "textures", "twigs"]

    for folder in folders_to_copy:
        src_folder = args.grove_dir / folder
        dst_folder = args.assets_dir / folder

        if src_folder.exists():
            print(f"\n📁 Copying {folder}...")
            if dst_folder.exists():
                shutil.rmtree(dst_folder)
            shutil.copytree(src_folder, dst_folder)
            print(f"✅ Copied {folder}")
        else:
            print(f"⚠️ {folder} not found in Grove directory")

    print(f"\n🎉 Asset preparation complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
