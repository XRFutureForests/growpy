"""Generate metadata for Unreal Engine PCG (Procedural Content Generation) workflows.

This module creates JSON metadata files that provide parameters for:
- PCG Surface Sampler spacing
- Instance scale variations
- Rotation constraints
- Foliage density recommendations
- Material setup hints

The metadata is derived from growth models and forest simulation data.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from dataclasses import dataclass, asdict


@dataclass
class UnrealPCGMetadata:
    """Metadata for Unreal Engine PCG foliage placement.

    Attributes:
        species_name: Name of tree species
        min_spacing: Minimum distance between instances (UE units, cm)
        max_spacing: Maximum distance between instances (UE units, cm)
        scale_min: Minimum uniform scale factor
        scale_max: Maximum uniform scale factor
        rotation_random: Enable random yaw rotation
        ground_slope_min: Minimum ground slope angle (degrees)
        ground_slope_max: Maximum ground slope angle (degrees)
        density_per_1000: Recommended density per 1000 square units
        cull_distance_min: Minimum cull distance (0 = no culling)
        cull_distance_max: Maximum cull distance for LOD
        align_to_normal: Align instances to surface normal
        preserve_area: Nanite Preserve Area setting (prevents thinning)
        wpo_disable_distance: World Position Offset disable distance
        height_range: Typical height range [min, max] in meters
        crown_radius_range: Typical crown radius range [min, max] in meters
        growth_rate: Growth rate category (slow/medium/fast)
        twig_files: List of twig mesh files used by this species
        variation_count: Number of mesh variations available
        nanite_enabled: Whether Nanite should be enabled
        nanite_fallback_percent: Fallback triangle percentage for non-Nanite
        mesh_validation: Mesh statistics and Nanite validation results
        foliage_type: Recommended Foliage Type settings
    """

    species_name: str
    min_spacing: float
    max_spacing: float
    scale_min: float = 0.8
    scale_max: float = 1.2
    rotation_random: bool = True
    ground_slope_min: float = 0.0
    ground_slope_max: float = 45.0
    density_per_1000: int = 50
    cull_distance_min: float = 0.0
    cull_distance_max: float = 20000.0
    align_to_normal: bool = True
    preserve_area: bool = True
    wpo_disable_distance: float = 5000.0
    height_range: Tuple[float, float] = (10.0, 30.0)
    crown_radius_range: Tuple[float, float] = (3.0, 8.0)
    growth_rate: str = "medium"
    twig_files: List[str] = None
    variation_count: int = 3
    nanite_enabled: bool = True
    nanite_fallback_percent: int = 100
    mesh_validation: Optional[Dict[str, Any]] = None
    foliage_type: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        """Initialize default values."""
        if self.twig_files is None:
            self.twig_files = []

        if self.foliage_type is None:
            self.foliage_type = {
                "density": self.density_per_1000 / 1000.0,
                "radius": (self.min_spacing + self.max_spacing) / 2,
                "align_to_normal": self.align_to_normal,
                "random_yaw": self.rotation_random,
                "ground_slope_angle": {
                    "min": self.ground_slope_min,
                    "max": self.ground_slope_max
                },
                "scale": {
                    "min": self.scale_min,
                    "max": self.scale_max
                },
                "cull_distance": {
                    "min": self.cull_distance_min,
                    "max": self.cull_distance_max
                }
            }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON export."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Convert to JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, output_path: Path) -> None:
        """Save metadata to JSON file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(self.to_json())


def calculate_spacing_from_crown_radius(
    crown_radius_min: float,
    crown_radius_max: float,
    overlap_factor: float = 0.7
) -> Tuple[float, float]:
    """Calculate min/max spacing from crown radius.

    Args:
        crown_radius_min: Minimum crown radius in meters
        crown_radius_max: Maximum crown radius in meters
        overlap_factor: Amount of crown overlap (0.7 = 30% overlap typical)

    Returns:
        Tuple of (min_spacing, max_spacing) in UE units (cm)
    """
    # Convert meters to cm (Unreal units)
    # Add overlap factor (trees naturally overlap crowns)
    min_spacing = (crown_radius_min * 2 * overlap_factor) * 100
    max_spacing = (crown_radius_max * 2 * overlap_factor) * 100

    return (min_spacing, max_spacing)


def calculate_density_from_spacing(
    min_spacing: float,
    max_spacing: float
) -> int:
    """Calculate density per 1000 square units from spacing.

    Args:
        min_spacing: Minimum spacing in UE units (cm)
        max_spacing: Maximum spacing in UE units (cm)

    Returns:
        Density per 1000 square units
    """
    avg_spacing = (min_spacing + max_spacing) / 2
    area_per_tree = avg_spacing * avg_spacing
    trees_per_1000 = int(1000 * 1000 / area_per_tree)
    return max(1, trees_per_1000)


def create_metadata_from_growth_data(
    species_name: str,
    height_range: Tuple[float, float],
    crown_radius_range: Tuple[float, float],
    growth_rate: str = "medium",
    twig_files: Optional[List[str]] = None,
    variation_count: int = 3
) -> UnrealPCGMetadata:
    """Create PCG metadata from growth model data.

    Args:
        species_name: Name of tree species
        height_range: (min_height, max_height) in meters
        crown_radius_range: (min_radius, max_radius) in meters
        growth_rate: Growth rate category (slow/medium/fast)
        twig_files: List of twig file names
        variation_count: Number of mesh variations

    Returns:
        UnrealPCGMetadata instance
    """
    # Calculate spacing from crown size
    min_spacing, max_spacing = calculate_spacing_from_crown_radius(
        crown_radius_range[0],
        crown_radius_range[1]
    )

    # Calculate density
    density = calculate_density_from_spacing(min_spacing, max_spacing)

    # Growth rate affects scale variation
    scale_variations = {
        "slow": (0.9, 1.1),   # Less variation, more uniform
        "medium": (0.8, 1.2), # Standard variation
        "fast": (0.7, 1.3)    # More variation, wider range
    }
    scale_min, scale_max = scale_variations.get(growth_rate, (0.8, 1.2))

    # WPO disable distance based on tree size
    avg_height = (height_range[0] + height_range[1]) / 2
    wpo_distance = avg_height * 100 * 20  # 20x tree height in cm

    return UnrealPCGMetadata(
        species_name=species_name,
        min_spacing=min_spacing,
        max_spacing=max_spacing,
        scale_min=scale_min,
        scale_max=scale_max,
        density_per_1000=density,
        height_range=height_range,
        crown_radius_range=crown_radius_range,
        growth_rate=growth_rate,
        twig_files=twig_files or [],
        variation_count=variation_count,
        wpo_disable_distance=wpo_distance
    )


def create_forest_metadata(
    tree_metadata_list: List[UnrealPCGMetadata],
    output_dir: Path
) -> Path:
    """Create combined forest metadata file.

    Args:
        tree_metadata_list: List of tree species metadata
        output_dir: Output directory for metadata file

    Returns:
        Path to created metadata file
    """
    forest_data = {
        "format_version": "1.0",
        "generator": "GrowPy",
        "description": "PCG metadata for Unreal Engine forest generation",
        "species_count": len(tree_metadata_list),
        "species": [meta.to_dict() for meta in tree_metadata_list],
        "pcg_setup_guide": {
            "surface_sampler": {
                "points_per_square_meter": "Use species density_per_1000",
                "point_extents": "Set to species max_spacing / 2"
            },
            "static_mesh_spawner": {
                "meshes": "Load all species variations",
                "selection": "Random weighted by density",
                "scale": "Use species scale_min/scale_max",
                "rotation": "Random yaw if rotation_random = true"
            },
            "nanite_settings": {
                "preserve_area": "Enable on all foliage meshes",
                "wpo_disable_distance": "Use species wpo_disable_distance"
            }
        }
    }

    output_path = output_dir / "forest_metadata.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dumps(forest_data, f, indent=2)

    return output_path


def load_metadata(metadata_path: Path) -> UnrealPCGMetadata:
    """Load PCG metadata from JSON file.

    Args:
        metadata_path: Path to JSON metadata file

    Returns:
        UnrealPCGMetadata instance
    """
    with open(metadata_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Convert tuples back from lists
    if 'height_range' in data and isinstance(data['height_range'], list):
        data['height_range'] = tuple(data['height_range'])
    if 'crown_radius_range' in data and isinstance(data['crown_radius_range'], list):
        data['crown_radius_range'] = tuple(data['crown_radius_range'])

    return UnrealPCGMetadata(**data)
