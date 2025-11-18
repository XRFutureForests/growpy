"""Texture processing utilities for GrowPy.

Includes bump-to-normal map conversion and texture manipulation.
Based on https://github.com/MircoWerner/BumpToNormalMap
"""

from pathlib import Path
from typing import Optional

import numpy as np
from PIL import Image


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
            output_path = bump_path.parent / f"{bump_path.stem}_normal{bump_path.suffix}"

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
    normal_path = texture_path.parent / f"{texture_path.stem}_normal{texture_path.suffix}"
    if normal_path.exists():
        return normal_path

    # Convert bump to normal
    return bump_to_normal(texture_path, normal_path, strength, invert)
