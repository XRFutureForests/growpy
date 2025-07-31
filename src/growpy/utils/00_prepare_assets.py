#!/usr/bin/env python3
"""
Simple Grove asset preparation for GrowPy.

This script copies assets from The Grove 2.2 installation to GrowPy assets folder:
- Species presets (.json files)
- Texture files
- Twig .blend files and textures
"""
import shutil
import sys
from pathlib import Path


def main():
    """Simple asset preparation - just copy three folders."""
    print("📦 GrowPy Asset Preparation")
    print("=" * 30)

    # Fixed paths
    grove_dir = Path(__file__).parent.parent.parent.parent / "src" / "the_grove_22"
    assets_dir = Path(__file__).parent.parent.parent.parent / "data" / "assets"

    if not grove_dir.exists():
        print(f"❌ Grove directory not found: {grove_dir}")
        return 1

    print(f"📂 Source: {grove_dir}")
    print(f"📂 Target: {assets_dir}")

    # Create target directory
    assets_dir.mkdir(parents=True, exist_ok=True)

    # Copy the three main folders
    folders_to_copy = ["presets", "textures", "twigs"]

    for folder in folders_to_copy:
        src_folder = grove_dir / folder
        dst_folder = assets_dir / folder

        if src_folder.exists():
            print(f"\n📁 Copying {folder}...")
            if dst_folder.exists():
                shutil.rmtree(dst_folder)
            shutil.copytree(src_folder, dst_folder)
            print(f"✅ Copied {folder}")
        else:
            print(f"⚠️ {folder} not found in Grove directory")

    print(f"\n🎉 Asset preparation complete!")


if __name__ == "__main__":
    sys.exit(main())
