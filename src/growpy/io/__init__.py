"""Import/Export functionality for GrowPy."""

try:
    from .blender_export import (
        export_tree_as_fbx,
        export_tree_as_usd,
        export_twigs_from_blend,
        batch_export_tree_fbx,
        batch_export_tree_usd,
        batch_export_trees_for_unreal,
        create_nanite_assembly_usd,
    )
    EXPORT_AVAILABLE = True
except ImportError:
    EXPORT_AVAILABLE = False
    export_tree_as_fbx = None
    export_tree_as_usd = None
    export_twigs_from_blend = None
    batch_export_tree_fbx = None
    batch_export_tree_usd = None
    batch_export_trees_for_unreal = None
    create_nanite_assembly_usd = None

__all__ = [
    "export_tree_as_fbx",
    "export_tree_as_usd",
    "export_twigs_from_blend",
    "batch_export_tree_fbx",
    "batch_export_tree_usd",
    "batch_export_trees_for_unreal",
    "create_nanite_assembly_usd",
    "EXPORT_AVAILABLE",
]