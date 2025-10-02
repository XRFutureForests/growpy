"""Import/Export functionality for GrowPy."""

try:
    from .blender_export import (
        export_tree_as_usd,
        export_twigs_from_blend,
        batch_export_tree_usd,
        batch_export_trees_for_unreal,
        create_nanite_assembly_usd,
        get_quality_preset,
    )
    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    export_tree_as_usd = None
    export_twigs_from_blend = None
    batch_export_tree_usd = None
    batch_export_trees_for_unreal = None
    create_nanite_assembly_usd = None
    get_quality_preset = None

try:
    from .twig_placement import (
        extract_twig_placements_from_mesh,
        place_twigs_in_blender,
        export_twig_placements_to_usd,
        create_geometry_nodes_twig_instancer,
        get_face_center_and_normal,
        normal_to_rotation_matrix
    )
    TWIG_PLACEMENT_AVAILABLE = True
except ImportError:
    TWIG_PLACEMENT_AVAILABLE = False
    extract_twig_placements_from_mesh = None
    place_twigs_in_blender = None
    export_twig_placements_to_usd = None
    create_geometry_nodes_twig_instancer = None
    get_face_center_and_normal = None
    normal_to_rotation_matrix = None

# Unreal metadata (always available, no bpy dependency)
from .unreal_metadata import (
    UnrealPCGMetadata,
    create_metadata_from_growth_data,
    create_forest_metadata,
    load_metadata,
    calculate_spacing_from_crown_radius,
    calculate_density_from_spacing,
)

__all__ = [
    "export_tree_as_usd",
    "export_twigs_from_blend",
    "batch_export_tree_usd",
    "batch_export_trees_for_unreal",
    "create_nanite_assembly_usd",
    "get_quality_preset",
    "EXPORT_AVAILABLE",
    "extract_twig_placements_from_mesh",
    "place_twigs_in_blender",
    "export_twig_placements_to_usd",
    "create_geometry_nodes_twig_instancer",
    "get_face_center_and_normal",
    "normal_to_rotation_matrix",
    "TWIG_PLACEMENT_AVAILABLE",
    "UnrealPCGMetadata",
    "create_metadata_from_growth_data",
    "create_forest_metadata",
    "load_metadata",
    "calculate_spacing_from_crown_radius",
    "calculate_density_from_spacing",
]