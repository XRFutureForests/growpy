#!/usr/bin/env python3
"""
Convert Grove twig .blend files to USD with textures.

This is a pure Blender-to-format conversion that produces static mesh assets
in Unreal Engine in USD format. No Grove functions are required -
only Blender Python API (bpy).

Key Features:
    - Material/texture mapping optimized for USD
    - Textures copied to output directory with relative path references
    - Coordinate system: Z-up (Blender right-handed to Unreal left-handed)
    - Standardized naming convention for twig types
    - Static mesh only (skeletal twig variants deprecated)

Quick Start:
    # Single-step conversion with automatic skeleton addition
    python ./src/growpy/cli/convert_twigs.py data/assets/twigs

    # Both static and skeletal variants exported in one pass
    # Skeletons added using Blender's bundled USD (bpy.utils.expose_bundled_modules)

Common Flags:
    --formats {usd,usda}  Export formats (default: usda)

Output per twig:
    - standard_name.usda          # Static mesh USD (no skeleton)
    - standard_name_skel.usda     # Skeletal mesh USD (skeleton added in step 2)
    - textures/*                  # All textures copied to output directory
    - twig_manifest.json          # Metadata about exported twigs

Twig Type Mapping:
    apical/long/end/terminal -> twig_long attribute (terminal twigs)
    lateral/short/side -> twig_short attribute (side branches)
    upward/up -> twig_upward attribute (upward-facing twigs)
    dead/fall/winter -> twig_dead attribute (dead/bare twigs)

Coordinate Systems:
    - Both Blender and Unreal use Z-up coordinate systems
    - Blender: Z-up, right-handed (X-right, Y-forward, Z-up)
    - Unreal: Z-up, left-handed (X-forward, Y-right, Z-up)
    - USD preserves Z-up, handedness handled on Unreal import

Note:
    Tree skeletons (for main trees) remain supported for animation and wind effects.
    Only twig skeletons have been deprecated as they are not needed for static foliage.

Full Documentation:
    See docs/guides/cli-reference.md for complete flag reference and examples

Usage:
    python convert_twigs.py <path> [options]
"""

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from tqdm import tqdm

# Standardized twig type mapping
TWIG_NAME_MAPPINGS = {
    # Apical/Terminal/End twigs (twig_long attribute)
    "apical": ["apical", "end", "long", "terminal", "tip"],
    # Lateral/Side twigs (twig_short attribute)
    "lateral": ["lateral", "side", "short", "laterall"],  # note: typo in some files
    # Upward-facing twigs (twig_upward attribute)
    "upward": ["upward", "up"],
    # Dead/Fall/Winter twigs (twig_dead attribute)
    "dead": ["dead", "fall", "winter", "bare"],
    # Summer/Spring variants
    "summer": ["summer", "spring", "green"],
}

# Texture type classifications with extended keywords
TEXTURE_CLASSIFICATIONS = {
    "diffuse": ["diffuse", "albedo", "color", "basecolor", "base", "diff", "col"],
    "alpha": ["alpha", "opacity", "mask", "transparent", "cutout"],
    "normal": ["normal", "norm", "nrm", "bump", "height"],
    "translucent": ["translucent", "translucency", "transmission", "sss", "subsurface"],
    "roughness": ["roughness", "rough", "gloss", "glossiness"],
    "metallic": ["metallic", "metal", "metalness"],
    "ao": ["ao", "ambient", "occlusion", "ambientocclusion"],
    "emissive": ["emissive", "emission", "glow"],
}

# Special texture patterns (top/bottom for leaves)
TEXTURE_MODIFIERS = {
    "top": ["top", "upper", "face"],
    "bottom": ["bottom", "lower", "back", "underside"],
}


def standardize_twig_name(original_name: str, species_name: str) -> Tuple[str, Dict]:
    """
    Convert varied twig naming to standardized format.

    Returns:
        (standardized_name, metadata_dict)

    Examples:
        "BeechApicalTwig" -> ("beech_apical", {"type": "apical", "species": "beech"})
        "ScotsPineVariationCLateralTwig" -> ("scots_pine_lateral_var_c", {...})
        "OakEuropeanLongTwig" -> ("european_oak_apical", {"type": "apical"})
    """
    name_lower = original_name.lower()

    # Extract metadata
    metadata = {
        "original_name": original_name,
        "species": species_name,
        "type": "generic",  # Default
        "variation": None,
        "season": None,
        "is_standardized": True,
    }

    # Detect twig type
    for standard_type, keywords in TWIG_NAME_MAPPINGS.items():
        if any(kw in name_lower for kw in keywords):
            metadata["type"] = standard_type
            break

    # Detect variation (A, B, C, Var, Variation)
    for letter in ["a", "b", "c", "d", "e"]:
        if f"var{letter}" in name_lower or f"variation{letter}" in name_lower:
            metadata["variation"] = letter
            break
        # Single letter patterns like "TwigA", "TwigB"
        if name_lower.endswith(f"twig{letter}") or name_lower.endswith(f"{letter}twig"):
            metadata["variation"] = letter
            break

    # Detect season
    for season_type, keywords in TWIG_NAME_MAPPINGS.items():
        if season_type in ["summer", "dead"] and any(
            kw in name_lower for kw in keywords
        ):
            metadata["season"] = season_type

    # Build standardized name
    parts = []

    # Species name (clean)
    species_clean = species_name.lower().replace(" ", "_")
    parts.append(species_clean)

    # Twig type
    if metadata["type"] != "generic":
        parts.append(metadata["type"])

    # Variation
    if metadata["variation"]:
        parts.append(f"var_{metadata['variation']}")

    # Season modifier
    if metadata["season"] and metadata["season"] != metadata["type"]:
        parts.append(metadata["season"])

    standardized = "_".join(parts)

    return standardized, metadata


def classify_texture_type(texture_path: Path, material_name: str = "") -> str:
    """
    Classify texture type from filename with context awareness.

    Handles:
    - Standard PBR naming (diffuse, normal, etc.)
    - Top/bottom variants for leaves
    - Compound names with duplicates
    """
    name_lower = texture_path.stem.lower()

    # Check for modifiers first (top/bottom)
    modifier = None
    for mod_type, keywords in TEXTURE_MODIFIERS.items():
        if any(kw in name_lower for kw in keywords):
            modifier = mod_type
            break

    # Classify base type
    base_type = "diffuse"  # Default
    for tex_type, keywords in TEXTURE_CLASSIFICATIONS.items():
        if any(kw in name_lower for kw in keywords):
            base_type = tex_type
            break

    # Combine with modifier if present
    if modifier and base_type == "diffuse":
        return f"diffuse_{modifier}"

    return base_type


def find_textures_for_material(
    blend_dir: Path, material_name: str, search_parent: bool = True
) -> Dict[str, Path]:
    """
    Find all available textures for a material with intelligent matching.

    Returns:
        Dict mapping texture type to file path
        e.g., {'diffuse': Path(...), 'alpha': Path(...), 'normal': Path(...)}
    """
    texture_extensions = [".png", ".jpg", ".jpeg", ".tiff", ".exr", ".bmp"]
    texture_map = {}

    # Search locations
    search_dirs = [blend_dir / "textures", blend_dir]
    if search_parent:
        search_dirs.extend([blend_dir.parent / "textures", blend_dir.parent])

    # Find all textures
    available_textures = []
    for search_dir in search_dirs:
        if not search_dir.exists():
            continue
        for ext in texture_extensions:
            available_textures.extend(search_dir.glob(f"*{ext}"))
            available_textures.extend(search_dir.glob(f"*{ext.upper()}"))

    # Remove duplicates and HDR placeholders
    available_textures = list(set(available_textures))
    available_textures = [
        t
        for t in available_textures
        if not t.stem.startswith("color_") or not t.suffix == ".hdr"
    ]

    if not available_textures:
        return texture_map

    # Match textures to material
    material_lower = material_name.lower()
    material_words = set(material_lower.replace("_", " ").split())

    for texture in available_textures:
        tex_name_lower = texture.stem.lower()
        tex_type = classify_texture_type(texture, material_name)

        # Scoring system for texture matching
        match_score = 0

        # Direct name match
        if material_lower in tex_name_lower or tex_name_lower in material_lower:
            match_score += 10

        # Word overlap
        tex_words = set(tex_name_lower.replace("_", " ").split())
        overlap = len(material_words & tex_words)
        match_score += overlap * 3

        # Species name in texture
        species_words = {"beech", "oak", "pine", "maple", "birch", "alder"}
        if any(word in tex_name_lower for word in material_words & species_words):
            match_score += 5

        # If few textures, be permissive
        if len(available_textures) <= 5:
            match_score += 2

        # Accept if reasonable match
        if match_score > 0:
            # Keep best match for each type
            if tex_type not in texture_map:
                texture_map[tex_type] = (texture, match_score)
            elif match_score > texture_map[tex_type][1]:
                texture_map[tex_type] = (texture, match_score)

    # Extract paths from (path, score) tuples
    texture_map = {k: v[0] for k, v in texture_map.items()}

    return texture_map


def get_processor_script_path() -> Path:
    """Get path to the Blender processor script module.

    Returns:
        Path to blender_twig_processor.py module
    """
    # Get path relative to this file
    current_dir = Path(__file__).parent
    processor_path = current_dir.parent / "io" / "blender_twig_processor.py"

    if not processor_path.exists():
        raise FileNotFoundError(
            f"Blender processor script not found at {processor_path}"
        )

    return processor_path


def process_twig_directory(
    twig_dir: Path,
    formats: List[str] = ["usda"],
    clean_export: bool = False,
) -> Dict[str, List[Path]]:
    """Process all twig blend files in a directory.

    Args:
        twig_dir: Directory containing .blend twig files
        formats: Export formats to create
        clean_export: If True, creates minimal USD without default attributes (demo mode)
    """

    blend_files = list(twig_dir.rglob("*.blend"))

    if not blend_files:
        print(f"No .blend files found in {twig_dir}")
        return {}

    print(f"\nFound {len(blend_files)} .blend file(s)")
    print(f"Export formats: {', '.join(formats)}")
    print(f"Using: Python + bpy module (with bundled USD)")
    print(f"Python executable: {sys.executable}")
    print(f"{'='*60}\n")

    # Get path to the Blender processor module
    processor_script = get_processor_script_path()

    results = {}

    for blend_file in tqdm(blend_files, desc="Converting twigs"):
        try:
            # Determine species name from directory
            species_name = blend_file.parent.name.replace("Twig", "").replace("_", " ")
            output_dir = blend_file.parent

            # Run processor script with conda Python (has bpy pip package + bundled USD)
            cmd = [
                sys.executable,
                str(processor_script),
                str(blend_file),
                str(output_dir),
                ",".join(formats),
                species_name,
                "--clean-export" if clean_export else "--no-clean-export",
            ]

            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=300  # 5 minute timeout
            )

            # Show output
            if result.stdout:
                print(result.stdout)

            if result.returncode == 0:
                # Find exported files
                for fmt in formats:
                    exported = list(output_dir.glob(f"*.{fmt}"))
                    if species_name not in results:
                        results[species_name] = []
                    results[species_name].extend(exported)

            else:
                print(f"\n[ERROR] Processing {blend_file.name}")
                if result.stderr:
                    print(result.stderr[-1000:])  # Last 1000 chars

        except subprocess.TimeoutExpired:
            print(f"\n[ERROR] Timeout processing {blend_file.name} (>5 minutes)")
        except Exception as e:
            print(f"\n[ERROR] Exception processing {blend_file.name}: {e}")

    return results


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert Grove twig files with robust texture handling and standardized naming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Convert all twigs to USD
    python convert_twigs.py data/assets/twigs --formats usda
    
    # Convert with both USD formats
    python convert_twigs.py data/assets/twigs --formats usd usda
    
    # Convert specific species
    python convert_twigs.py data/assets/twigs/Betulaceae_Downy_birch --formats usda

Output per twig:
    - standard_name.usda                   # Static mesh USD (no skeleton)
    - standard_name_skel.usda              # Skeletal mesh USD (root joint at pivot)
        """,
    )
    parser.add_argument(
        "path", type=Path, help="Path to twig directory or single .blend file"
    )
    parser.add_argument(
        "--formats",
        nargs="+",
        choices=["usd", "usda"],
        default=["usda"],
        help="Export formats (default: usda)",
    )
    parser.add_argument(
        "--clean-export",
        action="store_true",
        default=False,
        help="Create minimal USD without materials/textures (demo mode, matches demo structure)",
    )

    args = parser.parse_args()

    if not args.path.exists():
        print(f"Error: Path not found: {args.path}")
        return 1

    if args.path.is_file() and args.path.suffix == ".blend":
        # Single file
        print(f"Processing single file: {args.path.name}")
        results = process_twig_directory(
            args.path.parent, args.formats, args.clean_export
        )
    elif args.path.is_dir():
        # Directory
        results = process_twig_directory(args.path, args.formats, args.clean_export)
    else:
        print(f"Error: Invalid path (must be .blend file or directory)")
        return 1

    # Summary
    print(f"\n{'='*60}")
    print("Conversion Complete")
    print(f"{'='*60}")

    total_files = sum(len(files) for files in results.values())
    print(f"\nTotal exported: {total_files} files")
    print(f"Species processed: {len(results)}")

    # Check for any files that might need manual skeleton addition
    skel_files = []
    for species, files in results.items():
        skel_files.extend([f for f in files if "_skel" in f.stem])

    if skel_files:
        print(f"\nSkeletal variants: {len(skel_files)} files")
        print(
            "  (Skeletons added automatically during export via Blender's bundled USD)"
        )
        print(
            f"  If any failed, run: python src/growpy/cli/add_twig_skeletons.py {args.path}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())
