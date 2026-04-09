"""Extract Grove tree data from Blender scene.

Reads The Grove 2.3 compressed JSON state from Blender collections and
rebuilds Grove objects for export. Handles both legacy byte format and
modern base64 string format (Blender 4.2+).
"""

import base64
import gzip
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

import bpy

logger = logging.getLogger(__name__)

try:
    import the_grove_23_core as gc
except ImportError:
    gc = None  # type: ignore[assignment]


UNREAL_MAX_BONE_INDEX = 32767
GROVE_SKELETON_DEFAULTS: Dict[str, Any] = {
    "length": 2.0,
    "reduce": 0.4,
    "bias": 0.5,
    "connected": True,
}


@dataclass
class GroveExtractionResult:
    """Result of extracting and rebuilding a Grove from Blender."""

    grove: Any
    trees: List[Any] = field(default_factory=list)
    skeletons: List[Any] = field(default_factory=list)
    bones_info_per_tree: List[List[Tuple]] = field(default_factory=list)
    twig_blend_paths: List[str] = field(default_factory=list)
    bark_texture_path: Optional[str] = None
    species_name: str = ""
    collection_name: str = ""


@dataclass
class ExportPreflightResult:
    """Preflight validation result for export readiness."""

    ok: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    infos: List[str] = field(default_factory=list)


def find_grove_collections() -> List[bpy.types.Collection]:
    """Find all Blender collections that contain Grove tree data."""
    grove_collections = []
    for collection in bpy.data.collections:
        has_grove_data = "grove" in collection
        has_grove_props = (
            hasattr(collection, "GROVE23_Properties")
            and getattr(collection.GROVE23_Properties, "unique_id", "") != ""
        )
        if has_grove_data or has_grove_props:
            grove_collections.append(collection)
    return grove_collections


def get_active_grove_collection() -> Optional[bpy.types.Collection]:
    """Get the active Grove collection from current view layer context."""
    active = bpy.context.collection
    if active and ("grove" in active or _has_valid_grove_unique_id(active)):
        return active

    collections = find_grove_collections()
    if collections:
        return collections[0]
    return None


def _has_grove_property_group(collection: bpy.types.Collection) -> bool:
    return hasattr(collection, "GROVE23_Properties")


def _has_valid_grove_unique_id(collection: bpy.types.Collection) -> bool:
    if not _has_grove_property_group(collection):
        return False
    unique_id = getattr(collection.GROVE23_Properties, "unique_id", "")
    return bool(unique_id)


def _has_built_tree_objects(collection: bpy.types.Collection) -> bool:
    for obj in collection.objects:
        if hasattr(obj, "get") and obj.get("grove_tree_id") is not None:
            return True
    return False


def _has_built_skeleton(collection: bpy.types.Collection) -> bool:
    for obj in collection.objects:
        if hasattr(obj, "get") and obj.get("grove_skeleton"):
            return True
    return False


def preflight_export(
    collection: bpy.types.Collection,
    require_skeletal: bool,
    strict_requirements: bool = True,
) -> ExportPreflightResult:
    """Validate whether a collection is ready for export.

    Strict mode enforces Grove-side prerequisites so export complements Grove
    workflow instead of duplicating it.
    """
    errors: List[str] = []
    warnings: List[str] = []
    infos: List[str] = []

    if gc is None:
        errors.append(
            "The Grove core module is not available. Enable The Grove addon first."
        )

    if collection is None:
        errors.append("No active collection selected.")
        return ExportPreflightResult(
            ok=False, errors=errors, warnings=warnings, infos=infos
        )

    if "grove" not in collection:
        errors.append(
            "Collection does not contain serialized Grove data. Select a Grove collection."
        )

    if not _has_grove_property_group(collection):
        errors.append(
            "Collection is missing GROVE23_Properties. Convert/import it in The Grove first."
        )
    elif not _has_valid_grove_unique_id(collection):
        errors.append(
            "Collection has no Grove unique_id. Use The Grove convert/import flow first."
        )

    if strict_requirements:
        if not _has_built_tree_objects(collection):
            errors.append(
                "No built Grove tree meshes found. Run The Grove Build tool first."
            )

        if require_skeletal:
            if not _has_built_skeleton(collection):
                warnings.append(
                    "No Grove skeleton object detected. Export can still generate USD skeleton from Grove core data."
                )
    else:
        warnings.append(
            "Strict Grove preflight is disabled. Export may proceed with incomplete Grove build state."
        )

    infos.append(
        "Export uses Grove core skeleton tagging (tag_bone_id) for USD; it does not create a Blender armature. Defaults match Grove Build Skeleton: length=2.0, reduce=0.4, bias=0.5, connected=True."
    )

    return ExportPreflightResult(
        ok=len(errors) == 0,
        errors=errors,
        warnings=warnings,
        infos=infos,
    )


def load_grove_from_collection(collection: bpy.types.Collection) -> Any:
    """Load and deserialize a Grove object from a Blender collection.

    Handles both legacy byte format (pre-4.2) and modern base64 string format.
    """
    if gc is None:
        raise RuntimeError(
            "the_grove_23_core not available. "
            "Ensure The Grove 2.3 Blender addon is installed and enabled."
        )

    data = collection["grove"]

    if isinstance(data, bytes):
        compressed = data
    elif isinstance(data, str):
        compressed = base64.b64decode(data.encode("utf-8"))
    else:
        raise ValueError(f"Unexpected grove data type: {type(data)}")

    json_string = gzip.decompress(compressed).decode("utf-8")
    grove = gc.io.grove_from_json_string(json_string)
    return grove


def get_species_name_from_collection(collection: bpy.types.Collection) -> str:
    """Extract species name from Grove collection objects."""
    for obj in collection.objects:
        if hasattr(obj, "get") and obj.get("grove_preset"):
            preset = obj["grove_preset"]
            name = preset.replace(".seed.json", "").replace("_", " ").title()
            return name
    return collection.name


def get_grove_twigs_folder() -> Optional[str]:
    """Return the Twigs Folder path from The Grove 2.3 addon preferences."""
    grove_addon_name = "the_grove_23_in_blender"
    addons = bpy.context.preferences.addons
    if grove_addon_name not in addons:
        return None
    prefs = addons[grove_addon_name].preferences
    twigs_path = getattr(prefs, "twigs_path", "")
    if twigs_path:
        return bpy.path.abspath(twigs_path)
    return None


def get_grove_textures_folder() -> Optional[str]:
    """Return the Textures Folder path from The Grove 2.3 addon preferences."""
    grove_addon_name = "the_grove_23_in_blender"
    addons = bpy.context.preferences.addons
    if grove_addon_name not in addons:
        return None
    prefs = addons[grove_addon_name].preferences
    textures_path = getattr(prefs, "textures_path", "")
    if textures_path:
        return bpy.path.abspath(textures_path)
    return None


def find_bark_texture_path(
    collection: Optional[bpy.types.Collection] = None,
) -> Optional[str]:
    """Find bark texture file path for the Grove collection.

    Checks two sources in order:
    1. The collection's GROVE23_Properties.texture_bark (set by user in Build)
    2. Blender materials on the first mesh object in the collection
    """
    import os

    # 1. Check collection property
    if collection is not None and hasattr(collection, "GROVE23_Properties"):
        grove_props = collection.GROVE23_Properties
        texture_bark = getattr(grove_props, "texture_bark", "")
        if texture_bark:
            resolved = bpy.path.abspath(texture_bark)
            if os.path.isfile(resolved):
                return resolved
            # texture_bark might be just a filename - search textures folder
            textures_folder = get_grove_textures_folder()
            if textures_folder:
                candidate = os.path.join(textures_folder, os.path.basename(texture_bark))
                if os.path.isfile(candidate):
                    return candidate

    # 2. Check Blender materials on mesh objects in the collection
    if collection is not None:
        for obj in collection.objects:
            if obj.type != "MESH" or not obj.data.materials:
                continue
            for mat in obj.data.materials:
                if mat is None or not mat.use_nodes:
                    continue
                for node in mat.node_tree.nodes:
                    if node.type != "TEX_IMAGE" or node.image is None:
                        continue
                    filepath = bpy.path.abspath(node.image.filepath)
                    if os.path.isfile(filepath):
                        return filepath

    return None


def find_twig_blend_paths(
    grove: Any,
    collection: Optional[bpy.types.Collection] = None,
) -> List[str]:
    """Find .blend twig file paths referenced by the Grove collection.

    Checks three sources in order:
    1. The collection's GROVE23_Properties.twig_menu (full path set by user)
    2. The grove core object's properties (attribute scan)
    3. The Grove addon's Twigs Folder preference (fallback search)
    """
    paths: List[str] = []

    # 1. Read twig_menu from collection properties (most reliable)
    if collection is not None and hasattr(collection, "GROVE23_Properties"):
        grove_props = collection.GROVE23_Properties
        twig_menu = getattr(grove_props, "twig_menu", "")
        if twig_menu and twig_menu.endswith(".blend"):
            resolved = bpy.path.abspath(twig_menu)
            if resolved not in paths:
                paths.append(resolved)

    # 2. Scan grove core properties for .blend references
    if hasattr(grove, "properties"):
        props = grove.properties
        for attr_name in dir(props):
            if "twig" not in attr_name.lower():
                continue
            val = getattr(props, attr_name, None)
            if isinstance(val, str) and val.endswith(".blend"):
                resolved = bpy.path.abspath(val)
                if resolved not in paths:
                    paths.append(resolved)

    # 3. If still empty, list all .blend files in the Grove Twigs Folder
    if not paths:
        twigs_folder = get_grove_twigs_folder()
        if twigs_folder:
            import os

            for root, _dirs, files in os.walk(twigs_folder):
                for f in files:
                    if f.endswith(".blend") and not f.startswith("."):
                        full = os.path.join(root, f)
                        if full not in paths:
                            paths.append(full)
            if paths:
                logger.info(
                    "Found %d twig .blend files in Grove Twigs Folder: %s",
                    len(paths),
                    twigs_folder,
                )

    return paths


def extract_grove(
    collection: bpy.types.Collection,
    skeleton_length: float = GROVE_SKELETON_DEFAULTS["length"],
    skeleton_reduce: float = GROVE_SKELETON_DEFAULTS["reduce"],
    skeleton_bias: float = GROVE_SKELETON_DEFAULTS["bias"],
    skeleton_connected: bool = GROVE_SKELETON_DEFAULTS["connected"],
) -> GroveExtractionResult:
    """Extract and rebuild a Grove from a Blender collection.

    Performs the critical build sequence:
    1. Load grove from compressed JSON
    2. grove.build_skeletons()
    3. grove.tag_bone_id(length, reduce^2, bias, connected)
    4. grove.build_models(build_options)

    Returns a GroveExtractionResult with all data needed for USD export.
    """
    grove = load_grove_from_collection(collection)
    species_name = get_species_name_from_collection(collection)

    # Build skeletons first (required before tag_bone_id)
    skeletons = grove.build_skeletons(skeleton_connected)

    # Tag bones for skeletal mesh export
    bones_info_all = grove.tag_bone_id(
        skeleton_length,
        skeleton_reduce**2,
        skeleton_bias,
        skeleton_connected,
    )

    # Build models with triangulation for USD export
    build_options = {
        "resolution": 24,
        "resolution_reduce": 0.8,
        "build_cutoff_age": 0,
        "build_cutoff_thickness": 0.01,
        "build_blend": True,
        "build_end_cap": True,
    }
    trees = grove.build_models(build_options)

    # Split bones_info per tree using is_tree_root flag
    bones_info_per_tree = _split_bones_by_tree(bones_info_all)

    # Find twig .blend paths (from collection properties, grove core, or addon prefs)
    twig_paths = find_twig_blend_paths(grove, collection)

    logger.info(
        "Extracted grove '%s': %d trees, %d skeletons, %d twig sources",
        collection.name,
        len(trees),
        len(skeletons),
        len(twig_paths),
    )

    return GroveExtractionResult(
        grove=grove,
        trees=trees,
        skeletons=skeletons,
        bones_info_per_tree=bones_info_per_tree,
        twig_blend_paths=twig_paths,
        bark_texture_path=find_bark_texture_path(collection),
        species_name=species_name,
        collection_name=collection.name,
    )


def _split_bones_by_tree(bones_info: List[Tuple]) -> List[List[Tuple]]:
    """Split a flat bones_info list into per-tree lists using is_tree_root flag."""
    if not bones_info:
        return []

    per_tree: List[List[Tuple]] = []
    current_tree: List[Tuple] = []

    for bone in bones_info:
        is_tree_root = bone[0]
        if is_tree_root and current_tree:
            per_tree.append(current_tree)
            current_tree = []
        current_tree.append(bone)

    if current_tree:
        per_tree.append(current_tree)

    return per_tree
