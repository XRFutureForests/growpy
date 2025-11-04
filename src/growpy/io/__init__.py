"""Import/Export functionality for GrowPy.

USD export with skeleton support, twig placement, and assembly creation.

Key Functions:
    export_tree()           Export tree with skeleton to USD
    build_tree_mesh()       Build USD mesh from Grove model
    create_assembly()       Create assembly USD for Unreal
    validate_assembly()     Validate assembly structure

Example:
    from growpy.io import export_tree
    from growpy.config import get_quality_preset

    quality = get_quality_preset("high")
    export_tree(grove, "tree.usda", **quality)

Note:
    Some functions require bpy: conda install -c conda-forge bpy
    Check TREE_EXPORT_AVAILABLE flag before using.
"""

from growpy.config import get_quality_preset

# Tree export (requires bpy and USD)
try:
    from .tree_export import (
        build_tree_mesh,
        bundle_twigs_for_species,
        export_tree,
        get_twig_usd_map_for_species,
    )

    TREE_EXPORT_AVAILABLE = True
except ImportError:
    TREE_EXPORT_AVAILABLE = False
    export_tree = None
    build_tree_mesh = None
    bundle_twigs_for_species = None
    get_twig_usd_map_for_species = None

# Twig export (requires bpy)
try:
    from .twig_export import export_twigs_from_blend

    TWIG_EXPORT_AVAILABLE = True
except ImportError:
    TWIG_EXPORT_AVAILABLE = False
    export_twigs_from_blend = None

# Assembly creation and validation (requires USD)
try:
    from .assembly_export import create_assembly, validate_assembly

    ASSEMBLY_AVAILABLE = True
except ImportError:
    ASSEMBLY_AVAILABLE = False
    create_assembly = None
    validate_assembly = None
__all__ = [
    # Config
    "get_quality_preset",
    # Tree export
    "export_tree",
    "build_tree_mesh",
    "bundle_twigs_for_species",
    "get_twig_usd_map_for_species",
    "TREE_EXPORT_AVAILABLE",
    # Twig export
    "export_twigs_from_blend",
    "TWIG_EXPORT_AVAILABLE",
    # Assembly
    "create_assembly",
    "validate_assembly",
    "ASSEMBLY_AVAILABLE",
]
