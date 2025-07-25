#!/usr/bin/env python3
"""
Prepare Grove assets for GrowPy package use.

This utility copies all required assets from The Grove 2.2 installation to the
GrowPy assets folder, making the package self-contained and independent of the
Grove installation directory.

The script copies:
- Species presets (.seed.json files)
- Texture files (various formats)
- Twig .blend files and their textures

Usage:
    python src/growpy/utils/prepare_assets.py
    python src/growpy/utils/prepare_assets.py --grove_dir src/the_grove_22 --assets_dir data/assets
    python src/growpy/utils/prepare_assets.py --verbose --dry-run

Requirements:
    - Access to The Grove 2.2 installation directory
    - Write permissions to the assets directory
"""

import argparse
import logging
import shutil
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional, Set

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class AssetPreparer:
    """Copies Grove assets to GrowPy assets directory."""

    # File extensions to copy for each asset type
    PRESET_EXTENSIONS = {".json"}
    TEXTURE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tga", ".exr", ".hdr"}
    TWIG_EXTENSIONS = {".blend", ".jpg", ".jpeg", ".png", ".tga"}

    def __init__(self, grove_dir: Path, assets_dir: Path, dry_run: bool = False):
        """
        Initialize the asset preparer.

        Args:
            grove_dir: Path to The Grove 2.2 installation directory
            assets_dir: Path to GrowPy assets directory
            dry_run: If True, only show what would be copied without actually copying
        """
        self.grove_dir = Path(grove_dir)
        self.assets_dir = Path(assets_dir)
        self.dry_run = dry_run

        # Validate source directory
        if not self.grove_dir.exists():
            raise FileNotFoundError(f"Grove directory not found: {self.grove_dir}")

        # Create assets directory structure if it doesn't exist
        if not self.dry_run:
            self.assets_dir.mkdir(parents=True, exist_ok=True)
            (self.assets_dir / "presets").mkdir(exist_ok=True)
            (self.assets_dir / "textures").mkdir(exist_ok=True)
            (self.assets_dir / "twigs").mkdir(exist_ok=True)

        # Track statistics
        self.stats = {
            "presets_copied": 0,
            "textures_copied": 0,
            "twigs_copied": 0,
            "twig_textures_copied": 0,
            "total_size": 0,
            "errors": [],
        }

    def get_file_size_mb(self, file_path: Path) -> float:
        """Get file size in megabytes."""
        try:
            return file_path.stat().st_size / (1024 * 1024)
        except (OSError, FileNotFoundError):
            return 0.0

    def copy_file_safely(self, src: Path, dst: Path) -> bool:
        """
        Copy a file safely with error handling.

        Args:
            src: Source file path
            dst: Destination file path

        Returns:
            True if successful, False otherwise
        """
        try:
            if self.dry_run:
                logger.info(f"[DRY RUN] Would copy: {src.name} -> {dst}")
                return True

            # Create destination directory if needed
            dst.parent.mkdir(parents=True, exist_ok=True)

            # Copy file and preserve metadata
            shutil.copy2(src, dst)

            # Track file size
            size_mb = self.get_file_size_mb(src)
            self.stats["total_size"] += size_mb

            logger.debug(f"Copied: {src.name} ({size_mb:.2f} MB)")
            return True

        except (OSError, shutil.Error) as e:
            error_msg = f"Failed to copy {src.name}: {e}"
            logger.error(error_msg)
            self.stats["errors"].append(error_msg)
            return False

    def copy_presets(self) -> int:
        """
        Copy species preset files from Grove to assets directory.

        Returns:
            Number of presets copied
        """
        logger.info("Copying species presets...")
        presets_src = self.grove_dir / "presets"
        presets_dst = self.assets_dir / "presets"

        if not presets_src.exists():
            logger.warning(f"Presets directory not found: {presets_src}")
            return 0

        copied_count = 0
        preset_files = [
            f
            for f in presets_src.iterdir()
            if f.is_file() and f.suffix.lower() in self.PRESET_EXTENSIONS
        ]

        logger.info(f"Found {len(preset_files)} preset files to copy")

        for preset_file in preset_files:
            dst_file = presets_dst / preset_file.name
            if self.copy_file_safely(preset_file, dst_file):
                copied_count += 1

        self.stats["presets_copied"] = copied_count
        logger.info(f"Copied {copied_count} species presets")
        return copied_count

    def copy_textures(self) -> int:
        """
        Copy texture files from Grove to assets directory.

        Returns:
            Number of textures copied
        """
        logger.info("Copying texture files...")
        textures_src = self.grove_dir / "textures"
        textures_dst = self.assets_dir / "textures"

        if not textures_src.exists():
            logger.warning(f"Textures directory not found: {textures_src}")
            return 0

        copied_count = 0
        texture_files = [
            f
            for f in textures_src.iterdir()
            if f.is_file() and f.suffix.lower() in self.TEXTURE_EXTENSIONS
        ]

        logger.info(f"Found {len(texture_files)} texture files to copy")

        for texture_file in texture_files:
            dst_file = textures_dst / texture_file.name
            if self.copy_file_safely(texture_file, dst_file):
                copied_count += 1

        self.stats["textures_copied"] = copied_count
        logger.info(f"Copied {copied_count} texture files")
        return copied_count

    def copy_twig_directory(self, twig_dir: Path, dst_twig_dir: Path) -> int:
        """
        Copy a single twig directory with all its contents.

        Args:
            twig_dir: Source twig directory
            dst_twig_dir: Destination twig directory

        Returns:
            Number of files copied
        """
        copied_count = 0

        for item in twig_dir.rglob("*"):
            if item.is_file() and item.suffix.lower() in self.TWIG_EXTENSIONS:
                # Calculate relative path from twig directory
                rel_path = item.relative_to(twig_dir)
                dst_file = dst_twig_dir / rel_path

                if self.copy_file_safely(item, dst_file):
                    copied_count += 1

        return copied_count

    def copy_twigs(self) -> Dict[str, int]:
        """
        Copy twig directories from Grove to assets directory.

        Returns:
            Dictionary with 'blend_files' and 'textures' counts
        """
        logger.info("Copying twig files...")
        twigs_src = self.grove_dir / "twigs"
        twigs_dst = self.assets_dir / "twigs"

        if not twigs_src.exists():
            logger.warning(f"Twigs directory not found: {twigs_src}")
            return {"blend_files": 0, "textures": 0}

        # Find all twig directories (containing .blend files)
        twig_dirs = []
        for item in twigs_src.iterdir():
            if item.is_dir():
                # Check if directory contains .blend files
                blend_files = list(item.glob("*.blend"))
                if blend_files:
                    twig_dirs.append(item)

        logger.info(f"Found {len(twig_dirs)} twig directories to copy")

        total_blend_files = 0
        total_textures = 0

        for twig_dir in twig_dirs:
            logger.info(f"Copying twig directory: {twig_dir.name}")
            dst_twig_dir = twigs_dst / twig_dir.name

            # Count files by type before copying
            blend_files = list(twig_dir.rglob("*.blend"))
            texture_files = [
                f
                for f in twig_dir.rglob("*")
                if f.is_file() and f.suffix.lower() in {".jpg", ".jpeg", ".png", ".tga"}
            ]

            copied_count = self.copy_twig_directory(twig_dir, dst_twig_dir)

            # Track statistics
            total_blend_files += len(blend_files)
            total_textures += len(texture_files)

            logger.debug(
                f"  Copied {len(blend_files)} .blend files and {len(texture_files)} textures"
            )

        self.stats["twigs_copied"] = total_blend_files
        self.stats["twig_textures_copied"] = total_textures

        logger.info(
            f"Copied {total_blend_files} twig .blend files and {total_textures} twig textures"
        )
        return {"blend_files": total_blend_files, "textures": total_textures}

    def create_asset_manifest(self) -> None:
        """Create a manifest file describing the copied assets."""
        manifest = {
            "asset_preparation": {
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
                "grove_source": str(self.grove_dir),
                "assets_destination": str(self.assets_dir),
                "dry_run": self.dry_run,
            },
            "statistics": {
                "presets_copied": self.stats["presets_copied"],
                "textures_copied": self.stats["textures_copied"],
                "twigs_copied": self.stats["twigs_copied"],
                "twig_textures_copied": self.stats["twig_textures_copied"],
                "total_size_mb": round(self.stats["total_size"], 2),
                "errors_count": len(self.stats["errors"]),
            },
            "errors": self.stats["errors"] if self.stats["errors"] else None,
        }

        if not self.dry_run:
            import json

            manifest_path = self.assets_dir / "asset_manifest.json"
            with open(manifest_path, "w") as f:
                json.dump(manifest, f, indent=2)
            logger.info(f"Created asset manifest: {manifest_path}")
        else:
            logger.info("[DRY RUN] Would create asset manifest")

    def prepare_all_assets(self) -> bool:
        """
        Prepare all Grove assets for GrowPy use.

        Returns:
            True if all operations successful, False if any errors occurred
        """
        logger.info("Starting Grove asset preparation for GrowPy")
        logger.info("=" * 50)

        if self.dry_run:
            logger.info("DRY RUN MODE - No files will be copied")

        logger.info(f"Source (Grove): {self.grove_dir}")
        logger.info(f"Destination (Assets): {self.assets_dir}")

        start_time = time.time()

        try:
            # Copy each asset type
            self.copy_presets()
            self.copy_textures()
            self.copy_twigs()

            # Create manifest
            self.create_asset_manifest()

            # Summary
            total_time = time.time() - start_time
            total_files = (
                self.stats["presets_copied"]
                + self.stats["textures_copied"]
                + self.stats["twigs_copied"]
                + self.stats["twig_textures_copied"]
            )

            logger.info("=" * 50)
            logger.info("Asset preparation completed!")
            logger.info(f"Total files processed: {total_files}")
            logger.info(f"Total size: {self.stats['total_size']:.2f} MB")
            logger.info(f"Time taken: {total_time:.2f} seconds")

            if self.stats["errors"]:
                logger.warning(f"Completed with {len(self.stats['errors'])} errors")
                return False
            else:
                logger.info("All assets prepared successfully!")
                return True

        except Exception as e:
            logger.error(f"Asset preparation failed: {e}")
            return False


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description="Prepare Grove assets for GrowPy package use",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Prepare assets with default paths
    python src/growpy/utils/prepare_assets.py
    
    # Prepare assets with custom paths
    python src/growpy/utils/prepare_assets.py --grove_dir src/the_grove_22 --assets_dir data/assets
    
    # Dry run to see what would be copied
    python src/growpy/utils/prepare_assets.py --dry-run --verbose
    
    # Verbose output
    python src/growpy/utils/prepare_assets.py --verbose
        """,
    )

    # Get script directory for default paths
    script_dir = Path(__file__).parent.parent.parent.parent  # Go up to project root

    parser.add_argument(
        "--grove_dir",
        type=Path,
        default=script_dir / "src" / "the_grove_22",
        help="Directory containing Grove 2.2 installation (default: src/the_grove_22)",
    )
    parser.add_argument(
        "--assets_dir",
        type=Path,
        default=script_dir / "data" / "assets",
        help="Directory to copy assets to (default: data/assets)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be copied without actually copying files",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    logger.info("Grove Asset Preparation Utility")
    logger.info("=" * 40)

    # Validate Grove directory
    if not args.grove_dir.exists():
        logger.error(f"Grove directory not found: {args.grove_dir}")
        logger.error("Please ensure The Grove 2.2 is installed and accessible")
        sys.exit(1)

    # Check for required Grove subdirectories
    required_dirs = ["presets", "textures", "twigs"]
    missing_dirs = [d for d in required_dirs if not (args.grove_dir / d).exists()]

    if missing_dirs:
        logger.error(f"Missing required Grove directories: {missing_dirs}")
        logger.error("Please check your Grove installation")
        sys.exit(1)

    # Initialize and run asset preparer
    try:
        preparer = AssetPreparer(args.grove_dir, args.assets_dir, args.dry_run)
        success = preparer.prepare_all_assets()

        if success:
            logger.info("Asset preparation completed successfully!")
            if not args.dry_run:
                logger.info(f"Assets are ready in: {args.assets_dir}")
        else:
            logger.error("Asset preparation completed with errors")
            sys.exit(1)

    except Exception as e:
        logger.error(f"Asset preparation failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
