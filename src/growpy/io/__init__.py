"""Import/Export functionality for GrowPy.

Organized into three sub-packages by output target:
    io.usd/       Universal USD export (tree mesh, assembly, twig, texture, preview)
    io.unreal/    Unreal Engine output (import scripts, remote exec, PVE, wind JSON)
    io.helios/    Helios++ output (OBJ/MTL, mesh simplification, scene XML)

Key Functions:
    build_tree_mesh()       Build USD mesh from Grove model
    create_assembly()       Create assembly USD for Unreal
    validate_assembly()     Validate assembly structure

Note:
    Some functions require bpy: conda install -c conda-forge bpy
    Check TREE_EXPORT_AVAILABLE flag before using.
"""

# Tree export (requires bpy and USD)
try:
    from .usd.tree_export import (
        build_tree_mesh,
        bundle_twigs_for_species,
        get_twig_usd_map_for_species,
    )

    TREE_EXPORT_AVAILABLE = True
except ImportError:
    TREE_EXPORT_AVAILABLE = False
    build_tree_mesh = None
    bundle_twigs_for_species = None
    get_twig_usd_map_for_species = None

# Assembly creation and validation (requires USD)
try:
    from .usd.assembly_export import create_assembly, validate_assembly

    ASSEMBLY_AVAILABLE = True
except ImportError:
    ASSEMBLY_AVAILABLE = False
    create_assembly = None
    validate_assembly = None

# OBJ/MTL export for Helios++ (requires USD)
try:
    from .helios.obj_export import convert_tree_to_obj, export_forest_obj

    OBJ_EXPORT_AVAILABLE = True
except ImportError:
    OBJ_EXPORT_AVAILABLE = False
    convert_tree_to_obj = None
    export_forest_obj = None

# Helios++ scene XML generation
try:
    from .helios.helios_scene import generate_helios_scene

    HELIOS_SCENE_AVAILABLE = True
except ImportError:
    HELIOS_SCENE_AVAILABLE = False
    generate_helios_scene = None

__all__ = [
    # Tree export
    "build_tree_mesh",
    "bundle_twigs_for_species",
    "get_twig_usd_map_for_species",
    "TREE_EXPORT_AVAILABLE",
    # Assembly
    "create_assembly",
    "validate_assembly",
    "ASSEMBLY_AVAILABLE",
    # Helios OBJ/MTL
    "convert_tree_to_obj",
    "export_forest_obj",
    "OBJ_EXPORT_AVAILABLE",
    # Helios scene XML
    "generate_helios_scene",
    "HELIOS_SCENE_AVAILABLE",
]
