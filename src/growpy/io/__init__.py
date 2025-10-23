"""Import/Export functionality for GrowPy.

USD export with skeleton support, twig placement, and Nanite Assembly.

Key Functions:
    export_tree_as_usd()              Export single tree to USD
    batch_export_trees_for_unreal()   Export multiple trees for UE5
    create_nanite_assembly_usd()      Create Nanite Assembly USD
    build_tree_usd()                  Build USD directly from Grove API
    extract_twig_placements_from_mesh() Extract twig placements from mesh
    get_quality_preset()              Get quality settings

Quality Presets:
    ultra:       32 vertices, maximum detail
    high:        24 vertices, high detail
    medium:      16 vertices, balanced
    low:         12 vertices, reduced detail
    performance: 8 vertices, minimal detail

Example:
    from growpy.io import export_tree_as_usd, get_quality_preset
    from growpy import create_grove

    grove = create_grove("Quaking Aspen")
    grove.simulate(flushes=10)

    quality = get_quality_preset("high")
    export_tree_as_usd(grove, "tree.usda", **quality)

USD Builder Example (Direct API):
    from growpy.io import build_tree_usd
    from the_grove_22_core import grove_core as gc

    grove = gc.Grove()
    grove.add_new_tree(...)
    grove.simulate(flushes=10)
    model = grove.build_models()[0]

    build_tree_usd(model, "tree.usda", up_axis="Z")

Note:
    Blender export requires bpy module: conda install -c conda-forge bpy
    Check EXPORT_AVAILABLE flag before using export functions.
"""

from .export import get_quality_preset
from .nanite import add_nanite_attributes_to_usd, validate_mesh_for_nanite
from .unreal_metadata import (
    UnrealPCGMetadata,
    calculate_density_from_spacing,
    calculate_spacing_from_crown_radius,
    create_forest_metadata,
    create_metadata_from_growth_data,
    load_metadata,
)
from .usd_builder import add_materials_to_usd, add_skeleton_to_usd, build_tree_usd

# Blender-dependent exports
try:
    from .blender_export import (
        batch_export_tree_usd,
        batch_export_trees_for_unreal,
        create_nanite_assembly_usd,
        export_tree_as_usd,
        export_twigs_from_blend,
    )

    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    export_tree_as_usd = None
    batch_export_tree_usd = None
    batch_export_trees_for_unreal = None
    create_nanite_assembly_usd = None
    export_twigs_from_blend = None

# Twig functionality
try:
    from .twig_placement import (
        create_geometry_nodes_twig_instancer,
        export_twig_placements_to_usd,
        extract_twig_placements_from_mesh,
        get_face_center_and_normal,
        normal_to_rotation_matrix,
        place_twigs_in_blender,
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

# Nanite Assembly
try:
    from .unreal_nanite_assembly import validate_nanite_assembly

    NANITE_VALIDATION_AVAILABLE = True
except ImportError:
    NANITE_VALIDATION_AVAILABLE = False
    validate_nanite_assembly = None
__all__ = [
    "get_quality_preset",
    "build_tree_usd",
    "add_skeleton_to_usd",
    "add_materials_to_usd",
    "export_tree_as_usd",
    "batch_export_tree_usd",
    "batch_export_trees_for_unreal",
    "create_nanite_assembly_usd",
    "export_twigs_from_blend",
    "EXPORT_AVAILABLE",
    "extract_twig_placements_from_mesh",
    "place_twigs_in_blender",
    "export_twig_placements_to_usd",
    "create_geometry_nodes_twig_instancer",
    "get_face_center_and_normal",
    "normal_to_rotation_matrix",
    "TWIG_PLACEMENT_AVAILABLE",
    "add_nanite_attributes_to_usd",
    "validate_mesh_for_nanite",
    "UnrealPCGMetadata",
    "create_metadata_from_growth_data",
    "create_forest_metadata",
    "load_metadata",
    "calculate_spacing_from_crown_radius",
    "calculate_density_from_spacing",
    "validate_nanite_assembly",
    "NANITE_VALIDATION_AVAILABLE",
]
