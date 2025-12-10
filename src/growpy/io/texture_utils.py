"""Texture processing utilities for GrowPy.

Includes bump-to-normal map conversion, texture manipulation, and power-of-2
resolution scaling for Unreal Engine virtual texture compatibility.

Based on https://github.com/MircoWerner/BumpToNormalMap for normal conversion.

Virtual Texture Requirements (Unreal Engine):
    - Textures must have power-of-2 dimensions (e.g., 256, 512, 1024, 2048)
    - Both width and height must be powers of 2 (but can be different)
    - This is required for virtual texture streaming to work properly
    - See: https://dev.epicgames.com/community/learning/knowledge-base/jB8v/unreal-engine-usd-ue-format-support
"""

import math
import shutil
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
from PIL import Image


def next_power_of_2(value: int) -> int:
    """Return the next power of 2 >= value.

    Args:
        value: Input integer

    Returns:
        Smallest power of 2 that is >= value

    Examples:
        next_power_of_2(100) -> 128
        next_power_of_2(256) -> 256
        next_power_of_2(257) -> 512
    """
    if value <= 0:
        return 1
    # If already a power of 2, return as-is
    if value & (value - 1) == 0:
        return value
    # Find next power of 2
    return 1 << (value - 1).bit_length()


def is_power_of_2(value: int) -> bool:
    """Check if value is a power of 2.

    Args:
        value: Integer to check

    Returns:
        True if value is a power of 2
    """
    return value > 0 and (value & (value - 1)) == 0


def resize_to_power_of_2(
    image_path: Path,
    output_path: Optional[Path] = None,
    resample: int = Image.LANCZOS,
    upscale_only: bool = True,
) -> Optional[Path]:
    """Resize image to power-of-2 dimensions for Unreal virtual texture compatibility.

    CRITICAL: Unreal Engine virtual textures require power-of-2 dimensions.
    This function upscales images to the nearest power of 2 to avoid losing detail.

    Args:
        image_path: Path to input image
        output_path: Optional output path (defaults to overwriting input)
        resample: PIL resampling filter (default: LANCZOS for high quality)
        upscale_only: If True, only upscale to next power of 2 (never downscale)
                      If False, use nearest power of 2 (may downscale if closer)

    Returns:
        Path to resized image, or None if failed

    Examples:
        # 720x480 -> 1024x512 (upscale both dimensions)
        # 1024x1024 -> 1024x1024 (already power of 2, no change)
        # 2000x1500 -> 2048x2048 (upscale to next power of 2)
    """
    try:
        img = Image.open(image_path)
        original_width, original_height = img.size

        # Calculate target dimensions
        if upscale_only:
            new_width = next_power_of_2(original_width)
            new_height = next_power_of_2(original_height)
        else:
            # Find nearest power of 2 (may be smaller)
            new_width = next_power_of_2(original_width)
            new_height = next_power_of_2(original_height)
            # Check if previous power of 2 is closer
            prev_width = new_width // 2
            prev_height = new_height // 2
            if abs(original_width - prev_width) < abs(original_width - new_width):
                new_width = prev_width
            if abs(original_height - prev_height) < abs(original_height - new_height):
                new_height = prev_height

        # Skip if already correct size
        if new_width == original_width and new_height == original_height:
            return image_path

        # Resize image
        resized_img = img.resize((new_width, new_height), resample=resample)

        # Determine output path
        if output_path is None:
            output_path = image_path

        # Save with same format
        resized_img.save(output_path)

        return output_path

    except Exception as e:
        return None


def ensure_power_of_2_textures(
    texture_dir: Path,
    extensions: Optional[Tuple[str, ...]] = None,
    upscale_only: bool = True,
) -> int:
    """Ensure all textures in a directory have power-of-2 dimensions.

    Args:
        texture_dir: Directory containing textures
        extensions: File extensions to process (default: common image formats)
        upscale_only: If True, only upscale (never downscale)

    Returns:
        Number of textures resized
    """
    if extensions is None:
        extensions = (".png", ".jpg", ".jpeg", ".tiff", ".exr", ".bmp")

    resized_count = 0

    if not texture_dir.exists():
        return 0

    for ext in extensions:
        for texture_file in texture_dir.glob(f"*{ext}"):
            result = resize_to_power_of_2(texture_file, upscale_only=upscale_only)
            if result and result != texture_file:
                resized_count += 1
        # Also check uppercase extensions
        for texture_file in texture_dir.glob(f"*{ext.upper()}"):
            result = resize_to_power_of_2(texture_file, upscale_only=upscale_only)
            if result and result != texture_file:
                resized_count += 1

    return resized_count


def copy_and_resize_texture(
    src_path: Path,
    dst_path: Path,
    upscale_only: bool = True,
) -> Optional[Path]:
    """Copy a texture to destination and resize to power-of-2 if needed.

    Args:
        src_path: Source texture path
        dst_path: Destination texture path
        upscale_only: If True, only upscale (never downscale)

    Returns:
        Path to destination texture, or None if failed
    """
    try:
        img = Image.open(src_path)
        original_width, original_height = img.size

        # Calculate target dimensions
        if upscale_only:
            new_width = next_power_of_2(original_width)
            new_height = next_power_of_2(original_height)
        else:
            new_width = next_power_of_2(original_width)
            new_height = next_power_of_2(original_height)

        # Resize if needed
        if new_width != original_width or new_height != original_height:
            img = img.resize((new_width, new_height), resample=Image.LANCZOS)

        # Ensure destination directory exists
        dst_path.parent.mkdir(parents=True, exist_ok=True)

        # Save to destination
        img.save(dst_path)

        return dst_path

    except Exception as e:
        return None


def bump_to_normal(
    bump_path: Path,
    output_path: Optional[Path] = None,
    strength: float = 40.0,
    invert: bool = False,
) -> Optional[Path]:
    """Convert a bump/height map to a normal map.

    Args:
        bump_path: Path to input bump/height map image
        output_path: Optional output path (defaults to input_name_normal.ext)
        strength: Normal map strength multiplier (default: 40.0, higher = more pronounced details)
        invert: Invert the bump map before conversion (default: False)

    Returns:
        Path to generated normal map, or None if conversion failed
    """
    try:
        # Load bump map
        bump_img = Image.open(bump_path)

        # Convert to grayscale if needed
        if bump_img.mode != "L":
            bump_img = bump_img.convert("L")

        # Convert to numpy array (normalized to 0-1)
        bump_array = np.array(bump_img, dtype=np.float32) / 255.0

        # Invert if requested (white=low, black=high)
        if invert:
            bump_array = 1.0 - bump_array

        # Note: Don't apply strength to bump_array itself
        # Strength is applied through inv_strength in the normal calculation

        # Calculate gradients using Sobel kernels
        # Following https://github.com/MircoWerner/BumpToNormalMap implementation

        # Pad the array to handle edges (replicate border pixels)
        padded = np.pad(bump_array, 1, mode="edge")

        # Sobel X kernel (horizontal gradient)
        # [-1  0  1]
        # [-2  0  2]
        # [-1  0  1]
        grad_x = (
            -1.0 * padded[:-2, :-2]
            + 1.0 * padded[:-2, 2:]
            - 2.0 * padded[1:-1, :-2]
            + 2.0 * padded[1:-1, 2:]
            - 1.0 * padded[2:, :-2]
            + 1.0 * padded[2:, 2:]
        ) / 8.0

        # Sobel Y kernel (vertical gradient)
        # [-1 -2 -1]
        # [ 0  0  0]
        # [ 1  2  1]
        grad_y = (
            -1.0 * padded[:-2, :-2]
            - 2.0 * padded[:-2, 1:-1]
            - 1.0 * padded[:-2, 2:]
            + 1.0 * padded[2:, :-2]
            + 2.0 * padded[2:, 1:-1]
            + 1.0 * padded[2:, 2:]
        ) / 8.0

        # Create normal map following reference implementation
        # Reference uses: normalize(vec3(inv_strength, dy, dx))
        # But the channel mapping is: R=dx, G=dy, B=inv_strength
        # This creates proper normal maps where Z (blue) is dominant for flat surfaces
        inv_strength = 1.0 / strength
        normal_x = grad_x  # R channel = horizontal gradient (X)
        normal_y = grad_y  # G channel = vertical gradient (Y)
        normal_z = np.full_like(grad_x, inv_strength)  # B channel = Z (surface normal)

        # Normalize the vectors
        magnitude = np.sqrt(normal_x**2 + normal_y**2 + normal_z**2)
        normal_x /= magnitude
        normal_y /= magnitude
        normal_z /= magnitude

        # Convert to 0-255 range (map -1..1 to 0..255)
        # Following reference: colors = normals * 0.5 + 0.5
        normal_map = np.stack([normal_x, normal_y, normal_z], axis=-1)
        normal_map = (normal_map * 0.5 + 0.5) * 255.0
        normal_map = normal_map.astype(np.uint8)

        # Convert to image
        normal_img = Image.fromarray(normal_map, mode="RGB")

        # Determine output path
        if output_path is None:
            # Generate output path: input_name_normal.ext
            output_path = (
                bump_path.parent / f"{bump_path.stem}_normal{bump_path.suffix}"
            )

        # Save normal map
        normal_img.save(output_path)

        return output_path

    except Exception as e:
        # Silently fail - conversion is optional
        return None


def ensure_normal_map(
    texture_path: Path,
    is_bump: bool = False,
    strength: float = 40.0,
    invert: bool = False,
) -> Optional[Path]:
    """Ensure a normal map exists, converting from bump if needed.

    Args:
        texture_path: Path to texture (normal or bump)
        is_bump: Whether this is a bump map that needs conversion
        strength: Normal map strength if converting from bump (default: 40.0)
        invert: Invert bump map before conversion

    Returns:
        Path to normal map (either original or converted), or None
    """
    if not texture_path.exists():
        return None

    # If it's already a normal map, return as-is
    if not is_bump:
        return texture_path

    # Check if converted normal map already exists
    normal_path = (
        texture_path.parent / f"{texture_path.stem}_normal{texture_path.suffix}"
    )
    if normal_path.exists():
        return normal_path

    # Convert bump to normal
    return bump_to_normal(texture_path, normal_path, strength, invert)


def extract_alpha_from_diffuse(
    diffuse_path: Path, output_path: Path = None
) -> Optional[Path]:
    """Extract alpha channel from RGBA diffuse texture and save as grayscale.

    Creates a dedicated alpha texture from diffuse textures that have embedded
    alpha channels. This standardizes the alpha source for consistent geometry
    trimming across all twig types.

    Args:
        diffuse_path: Path to RGBA diffuse texture
        output_path: Output path for alpha texture (default: auto-generate)

    Returns:
        Path to extracted alpha texture, or None if no alpha channel
    """
    try:
        if not diffuse_path.exists():
            return None

        img = Image.open(diffuse_path)

        # Check if image has alpha channel
        if "A" not in img.getbands():
            return None

        # Extract alpha channel as grayscale
        alpha = img.getchannel("A")

        # Check if alpha is meaningful (not all opaque)
        extrema = alpha.getextrema()
        if extrema[0] == extrema[1] == 255:
            # All opaque, no meaningful alpha
            return None

        # Generate output path if not provided
        if output_path is None:
            # Use same naming convention as existing alpha textures
            stem = diffuse_path.stem
            # Remove _diffuse suffix if present, add _alpha
            if "_diffuse" in stem.lower():
                base = (
                    stem.lower()
                    .replace("_diffuse", "")
                    .replace("_top", "")
                    .replace("_bottom", "")
                )
            else:
                base = stem.lower()
            output_path = diffuse_path.parent / f"{base}_alpha.png"

        # Save as PNG for lossless alpha preservation
        alpha.save(output_path)
        return output_path

    except Exception:
        return None


def strip_alpha_from_diffuse(diffuse_path: Path) -> bool:
    """Remove alpha channel from diffuse texture, converting RGBA to RGB.

    This ensures diffuse textures don't have embedded alpha after we've
    extracted it to a dedicated alpha texture. Matches the pattern of
    existing Grove textures like BeechDiffuse.jpg which have no alpha.

    Args:
        diffuse_path: Path to diffuse texture (PNG with alpha)

    Returns:
        True if alpha was stripped, False otherwise
    """
    try:
        if not diffuse_path.exists():
            return False

        img = Image.open(diffuse_path)

        # Only process if image has alpha channel
        if "A" not in img.getbands():
            return False

        # Convert RGBA to RGB (removes alpha channel)
        rgb_img = img.convert("RGB")

        # Save back to same path (overwrite)
        rgb_img.save(diffuse_path)
        return True

    except Exception:
        return False


def _get_standardized_alpha_name(twig_dir: Path) -> str:
    """Get standardized alpha texture name based on twig directory name.

    Args:
        twig_dir: Path to twig directory (e.g., european_beech_twig)

    Returns:
        Standardized alpha filename (e.g., european_beech_twig_alpha.png)
    """
    twig_name = twig_dir.name.lower()
    if not twig_name.endswith("_twig"):
        twig_name = f"{twig_name}_twig"
    return f"{twig_name}_alpha.png"


def ensure_alpha_texture(twig_dir: Path) -> Optional[Path]:
    """Ensure a dedicated alpha texture exists for a twig directory.

    If a non-standardized alpha texture exists (e.g., BeechAlpha.jpg), converts
    it to standardized naming (e.g., european_beech_twig_alpha.png).

    If no dedicated alpha texture exists but diffuse textures have embedded
    alpha, extracts the alpha channel to create a dedicated texture.

    Also strips alpha channels from all diffuse textures to ensure they are
    pure RGB (matching the pattern of existing Grove textures like BeechDiffuse).

    Args:
        twig_dir: Path to twig directory containing textures

    Returns:
        Path to alpha texture (existing, renamed, or newly created), or None
    """
    textures_dir = twig_dir / "textures"
    if not textures_dir.exists():
        textures_dir = twig_dir

    standardized_name = _get_standardized_alpha_name(twig_dir)
    standardized_path = textures_dir / standardized_name

    # Collect all diffuse textures for later alpha stripping
    # Includes standardized names (diffuse, albedo, etc.) and Grove original patterns
    # (files with top/bottom variants without explicit diffuse keyword)
    diffuse_keywords = ["diffuse", "albedo", "color", "basecolor"]
    bump_keywords = ["bump", "height"]
    all_diffuse_files = []
    for tex_file in textures_dir.iterdir():
        if tex_file.is_file() and tex_file.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            name_lower = tex_file.stem.lower()
            # Exclude alpha, normal, and bump maps
            if any(
                k in name_lower
                for k in ["alpha", "opacity", "mask", "normal", "nrm", "bump"]
            ):
                continue
            # Match explicit diffuse keywords OR top/bottom variants (Grove pattern)
            if any(k in name_lower for k in diffuse_keywords) or any(
                k in name_lower for k in ["top", "bottom"]
            ):
                all_diffuse_files.append(tex_file)

    # Check if standardized alpha texture already exists
    if standardized_path.exists():
        # Still strip alpha from diffuse textures for consistency
        for diffuse_file in all_diffuse_files:
            strip_alpha_from_diffuse(diffuse_file)
        return standardized_path

    # Check if non-standardized alpha texture exists
    alpha_keywords = ["alpha", "opacity", "mask", "cutout"]
    existing_alpha = None
    for tex_file in textures_dir.iterdir():
        if tex_file.is_file() and tex_file.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            name_lower = tex_file.stem.lower()
            if any(k in name_lower for k in alpha_keywords):
                existing_alpha = tex_file
                break

    if existing_alpha:
        # Convert existing alpha to standardized format
        try:
            img = Image.open(existing_alpha)
            # Convert to grayscale if not already
            if img.mode != "L":
                img = img.convert("L")
            # Save as PNG with standardized name
            img.save(standardized_path)
            # Strip alpha from diffuse textures
            for diffuse_file in all_diffuse_files:
                strip_alpha_from_diffuse(diffuse_file)
            return standardized_path
        except Exception:
            return existing_alpha  # Fallback to original if conversion fails

    # No dedicated alpha - look for diffuse with embedded alpha
    diffuse_files_with_alpha = []
    for tex_file in all_diffuse_files:
        # Prefer "top" variants
        name_lower = tex_file.stem.lower()
        priority = 1 if "top" in name_lower else 0
        diffuse_files_with_alpha.append((priority, tex_file))

    if not diffuse_files_with_alpha:
        return None

    # Sort by priority and use best match
    diffuse_files_with_alpha.sort(key=lambda x: -x[0])
    diffuse_path = diffuse_files_with_alpha[0][1]

    # Extract alpha from diffuse with standardized name
    alpha_result = extract_alpha_from_diffuse(diffuse_path, standardized_path)

    # Strip alpha from ALL diffuse textures (both top and bottom variants)
    # Do this regardless of whether alpha extraction succeeded
    # (need to convert RGBA to RGB for all textures, even if alpha was all-opaque)
    for diffuse_file in all_diffuse_files:
        strip_alpha_from_diffuse(diffuse_file)

    return alpha_result


def ensure_normal_from_bump(twig_dir: Path) -> Optional[Path]:
    """Convert bump maps to normal maps for a twig directory.

    Searches for bump/height map textures and converts them to normal maps.
    The original bump map is preserved, and a new normal map is created.

    Args:
        twig_dir: Path to twig directory containing textures

    Returns:
        Path to generated normal map, or None if no bump map found
    """
    textures_dir = twig_dir / "textures"
    if not textures_dir.exists():
        textures_dir = twig_dir

    # Find bump maps
    bump_keywords = ["bump", "height", "displacement"]
    bump_file = None

    for tex_file in textures_dir.iterdir():
        if tex_file.is_file() and tex_file.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            name_lower = tex_file.stem.lower()
            if any(k in name_lower for k in bump_keywords):
                bump_file = tex_file
                break

    if not bump_file:
        return None

    # Check if normal map already exists (don't regenerate)
    # Look for existing normal maps
    for tex_file in textures_dir.iterdir():
        if tex_file.is_file() and tex_file.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            name_lower = tex_file.stem.lower()
            if any(k in name_lower for k in ["normal", "normals", "nrm"]):
                return tex_file  # Normal already exists

    # Generate standardized normal map name
    twig_name = twig_dir.name.lower()
    if not twig_name.endswith("_twig"):
        twig_name = f"{twig_name}_twig"
    normal_path = textures_dir / f"{twig_name}_normal.png"

    # Convert bump to normal
    return bump_to_normal(bump_file, normal_path)


def standardize_twig_textures(twig_dir: Path) -> dict:
    """Standardize naming and format of textures in a twig directory.

    Creates PNG copies with standardized naming pattern:
        {twig_name}_{texture_type}.png

    All standardized textures are converted to PNG format for consistency.
    Original textures are preserved (required for Blender blend files which
    reference them). Standardized versions are used for USD export and
    geometry processing (alpha trimming).

    Handles:
        - Diffuse (with top/bottom variants, including bark) - converted to PNG
        - Normal - converted to PNG
        - Bump - kept as-is, will be converted to normal
        - Alpha - skipped (will be handled by ensure_alpha_texture to guarantee PNG)
        - Other textures - kept as-is, not processed

    Args:
        twig_dir: Path to twig directory containing textures

    Returns:
        Dict with standardized texture paths:
            - 'diffuse': Path to primary diffuse texture (PNG)
            - 'diffuse_top': Path to top variant (PNG, if exists)
            - 'diffuse_bottom': Path to bottom variant (PNG, if exists)
            - 'diffuse_bark': Path to bark texture (PNG, if exists)
            - 'alpha': Always None (handled by ensure_alpha_texture)
            - 'normal': Path to normal texture (PNG, if exists)
            - 'copied_count': Number of files processed to standard PNG format
    """
    textures_dir = twig_dir / "textures"
    if not textures_dir.exists():
        textures_dir = twig_dir

    twig_name = twig_dir.name.lower()
    if not twig_name.endswith("_twig"):
        twig_name = f"{twig_name}_twig"

    results = {
        "diffuse": None,
        "diffuse_top": None,
        "diffuse_bottom": None,
        "diffuse_bark": None,
        "alpha": None,
        "normal": None,
        "copied_count": 0,
    }

    # Define texture type keywords and their standardized names
    # Keywords are used to identify texture type - matches on any keyword
    texture_patterns = {
        "diffuse": {
            # Matches: diffuse, albedo, color, basecolor, base, or Grove pattern (just top/bottom with no other keyword)
            "keywords": ["diffuse", "albedo", "color", "basecolor", "base", "top", "bottom"],
            "modifiers": {None: "_diffuse", "top": "_diffuse_top", "bottom": "_diffuse_bottom", "bark": "_diffuse_bark"},
        },
        "alpha": {
            "keywords": ["alpha", "opacity", "mask", "cutout"],
            "modifiers": {None: "_alpha"},
        },
        "normal": {
            "keywords": ["normal", "norm", "nrm"],
            "modifiers": {None: "_normal"},
        },
    }

    # Collect all texture files
    texture_files = []
    if textures_dir.exists():
        for tex_file in textures_dir.iterdir():
            if tex_file.is_file() and tex_file.suffix.lower() in [".png", ".jpg", ".jpeg"]:
                texture_files.append(tex_file)

    # Process each texture file
    for tex_file in texture_files:
        name_lower = tex_file.stem.lower()

        # Skip bump maps (will be handled separately)
        if any(k in name_lower for k in ["bump", "height"]):
            continue

        # Skip alpha maps (will be handled by ensure_alpha_texture to guarantee PNG format)
        if any(k in name_lower for k in ["alpha", "opacity", "mask", "cutout"]):
            continue

        # Determine texture type and modifier (top/bottom)
        texture_type = None
        modifier = None

        # Check for explicit texture type keywords first (normal maps)
        # Alpha is skipped above, so we don't check it here
        if any(k in name_lower for k in ["normal", "norm", "nrm"]):
            texture_type = "normal"
        else:
            # Everything else is diffuse (matches Grove convention: OakEuropeanTop, OakEuropeanBottom)
            # This includes leaf diffuse and bark diffuse (different mesh parts)
            texture_type = "diffuse"

            # Check for modifier (top/bottom/bark) for diffuse
            if any(k in name_lower for k in ["bark"]):
                modifier = "bark"
            elif any(k in name_lower for k in ["top", "upper", "face", "summer", "spring", "green"]):
                modifier = "top"
            elif any(k in name_lower for k in ["bottom", "lower", "back", "underside", "fall", "winter"]):
                modifier = "bottom"

        if not texture_type:
            continue

        # Generate standardized name (always use PNG for standardized files)
        patterns = texture_patterns[texture_type]
        if modifier and texture_type in ["diffuse"]:
            suffix = patterns["modifiers"][modifier]
        else:
            suffix = patterns["modifiers"][None]

        # Standardized files always use PNG format for consistency
        new_name = f"{twig_name}{suffix}.png"
        new_path = textures_dir / new_name

        # Only process if different
        if new_path != tex_file:
            try:
                # Convert and save as PNG (standardizes format)
                img = Image.open(tex_file)

                # For diffuse: preserve alpha for now (will be extracted by ensure_alpha_texture)
                # For normal: ensure RGB format
                if texture_type == "normal":
                    # Normal maps should be RGB (discard any alpha)
                    if img.mode == "RGBA":
                        img = img.convert("RGB")
                    elif img.mode not in ["RGB", "L"]:
                        img = img.convert("RGB")
                # else: keep diffuse as-is (including RGBA if present)

                # Save as PNG
                img.save(new_path)
                results["copied_count"] += 1

                # Track result
                if texture_type == "diffuse":
                    if modifier == "top":
                        results["diffuse_top"] = new_path
                    elif modifier == "bottom":
                        results["diffuse_bottom"] = new_path
                    elif modifier == "bark":
                        results["diffuse_bark"] = new_path
                    else:
                        results["diffuse"] = new_path
                elif texture_type == "normal":
                    results["normal"] = new_path
            except Exception as e:
                # Log error for debugging
                import sys
                print(f"  Warning: Could not process {tex_file.name} to {new_name}: {e}", file=sys.stderr)

    return results


def validate_twig_textures(twig_dir: Path) -> Tuple[bool, str]:
    """Validate that all required textures exist for a twig directory.

    After alpha extraction and normal conversion, validates:
        1. At least one diffuse texture (standard, top, or bottom)
        2. Alpha texture exists (extracted or original)
        3. Normal texture exists (original or converted from bump)

    Args:
        twig_dir: Path to twig directory containing textures

    Returns:
        Tuple (is_valid: bool, message: str)
            - True if all required textures present
            - String describing validation result
    """
    textures_dir = twig_dir / "textures"
    if not textures_dir.exists():
        textures_dir = twig_dir

    # Check for diffuse textures
    diffuse_found = False
    alpha_found = False
    normal_found = False

    for tex_file in textures_dir.iterdir():
        if not tex_file.is_file() or tex_file.suffix.lower() not in [".png", ".jpg", ".jpeg"]:
            continue

        name_lower = tex_file.stem.lower()

        if any(k in name_lower for k in ["diffuse", "albedo", "color", "basecolor"]):
            # Verify it's RGB (no alpha channel)
            try:
                img = Image.open(tex_file)
                if img.mode == "RGBA" or "A" in img.getbands():
                    # Has embedded alpha - this is a problem
                    pass  # Will be caught if alpha stripping failed
                else:
                    diffuse_found = True
            except Exception:
                pass

        elif any(k in name_lower for k in ["alpha", "opacity", "mask", "cutout"]):
            # Verify it's grayscale
            try:
                img = Image.open(tex_file)
                if img.mode == "L" or len(img.getbands()) == 1:
                    alpha_found = True
            except Exception:
                pass

        elif any(k in name_lower for k in ["normal", "norm", "nrm"]):
            normal_found = True

    # Build result message
    missing = []
    if not diffuse_found:
        missing.append("diffuse (RGB)")
    if not alpha_found:
        missing.append("alpha (grayscale)")
    if not normal_found:
        missing.append("normal")

    if missing:
        msg = f"Missing textures in {twig_dir.name}: {', '.join(missing)}"
        return False, msg

    return True, f"All required textures found in {twig_dir.name}"


def process_twig_textures(twig_dir: Path) -> dict:
    """Process all textures for a twig directory during asset preparation.

    This is the main entry point for texture processing during prepare_assets.
    It handles:
        1. Standardize texture naming to consistent pattern
        2. Bump-to-normal map conversion
        3. Alpha extraction from diffuse textures (if no dedicated alpha)
        4. Alpha channel stripping from diffuse textures (RGBA -> RGB)
        5. Validate all required textures exist

    After processing, all twigs will have consistent texture sets:
        - Diffuse (RGB only, no embedded alpha)
        - Alpha (dedicated grayscale texture)
        - Normal (from existing normal map or converted from bump)

    Args:
        twig_dir: Path to twig directory containing textures

    Returns:
        Dict with processing results:
            - 'alpha_path': Path to alpha texture (or None)
            - 'normal_path': Path to normal texture (or None)
            - 'diffuse_paths': List of standardized diffuse texture paths
            - 'copied_count': Number of files copied to standard names
            - 'is_valid': Whether all required textures present
            - 'validation_message': Validation result message
    """
    results = {
        "alpha_path": None,
        "normal_path": None,
        "diffuse_paths": [],
        "copied_count": 0,
        "is_valid": False,
        "validation_message": "",
    }

    # Step 0: Standardize texture naming
    standardize_results = standardize_twig_textures(twig_dir)
    results["copied_count"] = standardize_results["copied_count"]

    # Step 1: Convert bump maps to normal maps
    normal_path = ensure_normal_from_bump(twig_dir)
    if normal_path:
        results["normal_path"] = normal_path

    # Step 2: Ensure alpha texture exists (also strips alpha from diffuse)
    alpha_path = ensure_alpha_texture(twig_dir)
    if alpha_path:
        results["alpha_path"] = alpha_path

    # Step 3: Collect all standardized diffuse paths
    textures_dir = twig_dir / "textures"
    if not textures_dir.exists():
        textures_dir = twig_dir

    for tex_file in textures_dir.iterdir():
        if tex_file.is_file() and tex_file.suffix.lower() in [".png", ".jpg", ".jpeg"]:
            name_lower = tex_file.stem.lower()
            if any(k in name_lower for k in ["diffuse"]):
                results["diffuse_paths"].append(tex_file)

    # Step 4: Validate all required textures
    is_valid, validation_msg = validate_twig_textures(twig_dir)
    results["is_valid"] = is_valid
    results["validation_message"] = validation_msg

    return results
