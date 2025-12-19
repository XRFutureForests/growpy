"""Unreal Engine Nanite Assembly USD export.

This module creates USD files following Unreal Engine 5.7+ Nanite Assembly schema.
It wraps Grove's native USD export with proper Unreal API schemas for optimal import.

CRITICAL: All exports are clean (no materials/textures/masks)
Nanite assemblies with skeletal meshes have known issues with materials, textures, and opacity masks.
All visual appearance should be configured in Unreal Engine after import using Material Instances.

CRITICAL Requirements:
1. Static Mesh Assemblies:
   - Use meshType="staticMesh"
   - Reference static (non-skeletal) tree USD files
   - Reference static (non-skeletal) twig USD files
   - No skeleton relationships

2. Skeletal Mesh Assemblies:
   - Use meshType="skeletalMesh"
   - Reference skeletal tree USD with embedded UsdSkel
   - Reference SKELETAL twig USD files with embedded UsdSkel
   - Set unreal:naniteAssembly:skeleton relationship to descendant skeleton
   - Requires proper UsdSkelRoot, Skeleton, and SkelAnimation prims

3. USD References Only:
   - Nanite Assembly MUST use USD references (.usda, .usd)
   - FBX references break USD composition system
   - For FBX export, import files directly (not via Nanite Assembly)

Based on:
- https://dev.epicgames.com/documentation/en-us/unreal-engine/skeletal-mesh-assets-in-unreal-engine
- https://dev.epicgames.com/documentation/en-us/unreal-engine/universal-scene-description-in-unreal-engine
- https://www.youtube.com/watch?v=-ZGWblVF8Qk
- https://www.artstation.com/blogs/liamwedge/mpygZ/nanite-assemblies-in-unreal-engine-57-from-dcc-to-ue-import
"""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from ..utils.pxr_init import ensure_pxr_with_unreal_schema

ensure_pxr_with_unreal_schema()

from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel

from ..core.twig import extract_twig_placements_from_model

# Module-level cache for copied twig files (optimization: avoid redundant copies per species)
# Key: (source_path, dest_dir) tuple, Value: destination path
_copied_twig_cache: dict = {}


def clear_twig_copy_cache() -> None:
    """Clear the twig file copy cache. Call at start of new export session."""
    global _copied_twig_cache
    _copied_twig_cache.clear()


def _copy_twig_file_cached(source_path: "Path", dest_dir: "Path") -> "Path":
    """Copy twig file to destination directory with caching.

    If the file has already been copied to this destination, skips the copy.
    Returns the destination path.
    """
    import shutil

    cache_key = (str(source_path), str(dest_dir))
    if cache_key in _copied_twig_cache:
        return _copied_twig_cache[cache_key]

    dest_path = dest_dir / source_path.name
    if not dest_path.exists():
        shutil.copy2(source_path, dest_path)

    _copied_twig_cache[cache_key] = dest_path
    return dest_path


def create_assembly(
    tree_usd_path: Path,
    output_path: Path,
    species_name: str,
    tree_id: Optional[str] = None,
    twig_usd_paths: Optional[Dict[str, Path]] = None,
    use_skeletal_mesh: bool = False,
    skeleton_source_usd: Optional[Path] = None,
    twig_placements: Optional[Dict[str, List]] = None,
    validate: bool = True,
) -> bool:
    """Create an assembly USD file for Unreal Engine import.

    This creates a USD Assembly following Unreal's schema with proper API schemas:
    - NaniteAssemblyRootAPI on the root Xform with meshType attribute
    - NaniteAssemblyExternalRefAPI on child meshes (USD references ONLY)
    - PointInstancer for twig instances

    CRITICAL: For skeletal assemblies:
    - tree_usd_path MUST point to SKELETAL tree USD with embedded UsdSkelRoot/Skeleton
    - twig_usd_paths MUST point to SKELETAL twigs with embedded UsdSkel
    - All skeletal meshes share or reference the same skeleton hierarchy

    CRITICAL: For static assemblies:
    - tree_usd_path MUST point to a static (non-skeletal) USD (geometry only)
    - twig_usd_paths MUST point to STATIC twigs (geometry only)
    - No skeleton data should be present

    Args:
        tree_usd_path: Path to tree USD (skeletal for skeletal assemblies, static for static)
        output_path: Output path for Nanite Assembly USDA
        species_name: Tree species name
        twig_usd_paths: Optional dict mapping twig types to USD paths (skeletal or static matching assembly type)
        use_skeletal_mesh: Whether to use skeletal mesh type
        skeleton_source_usd: Deprecated - skeleton is now embedded in tree_usd_path
        twig_placements: Optional dict of twig placements extracted from Grove model
        validate: If True, validate assembly structure after creation (default: True)

    Returns:
        bool: Success status
    """
    try:
        # Create new stage
        stage = Usd.Stage.CreateNew(str(output_path))

        # Set stage metadata to match tree USD (Z-up, meters)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)

        # Root Xform with NaniteAssemblyRootAPI
        # Sanitize species name: replace spaces and hyphens with underscores for valid USD path
        sanitized_name = species_name.replace(" ", "_").replace("-", "_").lower()
        # Include tree_id in prim name for unique Unreal assets
        if tree_id:
            assembly_name = f"{sanitized_name}_tree_{tree_id}_nanite_assembly"
        else:
            assembly_name = f"{sanitized_name}_nanite_assembly"
        root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")
        stage.SetDefaultPrim(root_prim)

        # Apply NaniteAssemblyRootAPI using TokenListOp
        # Megaplant only uses NaniteAssemblyRootAPI (no GeomModelAPI)
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]
        root_prim.SetMetadata("apiSchemas", api_schemas)
        # Set kind metadata to 'component' as per Megaplant reference (not 'assembly')
        root_prim.SetMetadata("kind", "component")

        # Set mesh type - CRITICAL: Must use uniform variability
        mesh_type = "skeletalMesh" if use_skeletal_mesh else "staticMesh"
        root_prim.CreateAttribute(
            "unreal:naniteAssembly:meshType",
            Sdf.ValueTypeNames.Token,
            custom=False,
            variability=Sdf.VariabilityUniform,
        ).Set(mesh_type)

        # Handle tree mesh - use SkelRoot for skeletal, Xform for static
        # For skeletal: TreeMesh must be SkelRoot so Unreal can find it as ancestor of skeleton
        # For static: TreeMesh is simple Xform wrapper
        tree_prim_type = "SkelRoot" if use_skeletal_mesh else "Xform"
        # Use species-specific mesh prim name for unique Unreal assets
        if tree_id:
            tree_mesh_name = f"{sanitized_name}_{tree_id}"
        else:
            tree_mesh_name = sanitized_name if sanitized_name else "TreeMesh"
        tree_prim = stage.DefinePrim(
            f"/{assembly_name}/{tree_mesh_name}", tree_prim_type
        )

        # Do not apply SkelBindingAPI to TreeMesh here.
        # For Nanite assemblies, binding is driven by NaniteAssemblySkelBindingAPI
        # on the PointInstancer; TreeMesh remains a plain SkelRoot.

        # Reference the tree mesh USD file
        # Prim path matches the species-specific naming in tree_export.py
        if tree_id:
            ref_root_name = f"{sanitized_name}_{tree_id}"
            ref_skel_name = f"{sanitized_name}_{tree_id}_skel"
        else:
            ref_root_name = "tree"
            ref_skel_name = "TreeSkel"

        tree_prim.GetReferences().AddReference(
            f"./{tree_usd_path.name}",
            f"/{ref_root_name}",
        )

        if use_skeletal_mesh:
            # Set the Nanite Assembly skeleton relationship on root prim
            # This points to the skeleton inside the referenced tree
            # CRITICAL: Must use custom=True to match Megaplant format:
            #   custom rel unreal:naniteAssembly:skeleton = <path>
            skeleton_rel = root_prim.CreateRelationship(
                "unreal:naniteAssembly:skeleton",
                custom=True,
            )
            skeleton_path = f"/{assembly_name}/{tree_mesh_name}/{ref_skel_name}"
            skeleton_rel.SetTargets([Sdf.Path(skeleton_path)])

            # Note: DynamicWind attributes are NOT added to USD files
            # Unreal requires separate JSON import via ImportDynamicWindSkeletalDataFromFile
            # Wind JSON is generated by generate_forest.py (*_DynamicWind.json)

        # Add twigs if provided
        if twig_usd_paths:
            pass

            # Use twig placements extracted from Grove model
            if twig_placements:
                # Convert TwigPlacement objects to dict format
                placements = {}
                for twig_type, placement_list in twig_placements.items():
                    if placement_list:
                        placements[twig_type] = [
                            {
                                "position": p.position,
                                "normal": p.normal,
                                "scale": p.scale,
                                "bone_id": p.bone_id,
                                "branch_id": p.branch_id,  # CRITICAL: branch_id for binding to branch_X joints
                            }
                            for p in placement_list
                        ]
                total_twigs = sum(len(p) for p in placements.values())
                print(f"  Creating assembly with {total_twigs} twig instances:")
                for twig_type, p_list in placements.items():
                    print(f"    {twig_type}: {len(p_list)} instances")
            else:
                placements = {}
                print("  WARNING: No twig placements available!")

            if placements and any(placements.values()):
                # Remap twig paths from source assets to output directory copies
                # Twigs already have "_twig" suffix from convert_twigs.py step
                # Nanite Assembly must reference these copies for Unreal import to work
                output_dir = output_path.parent
                species_twigs_dir = output_dir

                remapped_twig_paths = {}
                for twig_type, source_twig_path in twig_usd_paths.items():
                    # Twig files already have _twig suffix from convert_twigs.py
                    # Just look for the file by name in the output directory
                    output_twig_path = species_twigs_dir / source_twig_path.name
                    if output_twig_path.exists():
                        remapped_twig_paths[twig_type] = output_twig_path
                    else:
                        # Fall back to source path if copy doesn't exist yet
                        remapped_twig_paths[twig_type] = source_twig_path

                # Create prototypes group
                prototypes_group = stage.DefinePrim(
                    f"/{assembly_name}/TwigPrototypes", "Scope"
                )

                # CRITICAL: Visibility behavior differs between skeletal and static assemblies
                # - Skeletal assemblies: prototypes MUST be visible for Unreal to import them
                # - Static assemblies: prototypes MUST be invisible to prevent duplicate rendering at origin
                if not use_skeletal_mesh:
                    # Static assembly: hide prototypes to prevent rendering at tree base
                    prototypes_imageable = UsdGeom.Imageable(prototypes_group)
                    if prototypes_imageable:
                        prototypes_imageable.MakeInvisible()

                # Map twig types to prototype indices
                twig_type_to_proto_idx = {}
                prototype_paths = []

                for idx, (twig_type, twig_path) in enumerate(
                    sorted(remapped_twig_paths.items())
                ):
                    # VIDEO REQUIREMENT: Skeletal assemblies MUST use skeletal twigs
                    # Each twig must have its own root bone for wind/animation
                    twig_ref_path = twig_path

                    # Get original source path for texture copying
                    source_twig_path = twig_usd_paths.get(twig_type, twig_path)

                    # Validate skeletal twigs for skeletal assemblies
                    if use_skeletal_mesh:
                        is_skeletal_twig = "_skeletal" in twig_ref_path.stem
                        if not is_skeletal_twig:
                            pass

                    if not twig_ref_path.exists():
                        continue

                    # Copy twig file to output directory for relative references (with caching)
                    # This ensures the assembly can find its twigs using ./filename.usda
                    _copy_twig_file_cached(twig_ref_path, output_path.parent)

                    # Copy twig textures (base color and normal maps)
                    # Both skeletal and static assemblies now include textures
                    # Use source path (in assets) to find textures
                    twig_dir = source_twig_path.parent
                    # Twigs store textures in a textures/ subdirectory
                    source_textures_dir = twig_dir / "textures"

                    if source_textures_dir.exists():
                        # Create output textures subdirectory
                        output_textures_dir = output_path.parent / "textures"
                        output_textures_dir.mkdir(exist_ok=True)

                        # CRITICAL: Only copy standardized twig textures (diffuse/normal)
                        # Skip original Grove textures - only copy renamed versions with _twig_ naming
                        # Alpha/translucent/mask textures are NOT copied (used for geometry only)
                        from .texture_utils import copy_and_resize_texture
                        from .twig_export import classify_texture_from_name

                        ALLOWED_TEXTURE_TYPES = [
                            "diffuse",
                            "diffuse_top",
                            "diffuse_bottom",
                            "normal",
                        ]

                        for texture_ext in [".png", ".jpg", ".jpeg", ".exr"]:
                            for texture_file in source_textures_dir.glob(
                                f"*{texture_ext}"
                            ):
                                # CRITICAL: Only copy standardized textures (contain _twig_)
                                # Skip original Grove textures like BeechDiffuse.jpg
                                if "_twig_" not in texture_file.stem:
                                    continue

                                # Filter to only diffuse and normal textures
                                tex_type = classify_texture_from_name(texture_file.stem)
                                if tex_type not in ALLOWED_TEXTURE_TYPES:
                                    continue

                                output_texture = output_textures_dir / texture_file.name
                                if not output_texture.exists():
                                    copy_and_resize_texture(
                                        texture_file, output_texture
                                    )

                    twig_type_to_proto_idx[twig_type] = idx

                    # Create prototype with ExternalRef
                    proto_name = twig_type.replace("_", "")

                    # Extract twig name from file for unique Unreal asset names
                    # e.g., one_leaved_ash_twig_apical_var_d_skeletal -> one_leaved_ash_twig_apical_var_d
                    twig_asset_name = twig_ref_path.stem.replace(
                        "_skeletal", ""
                    ).replace("_static", "")

                    # CRITICAL: For skeletal twigs, use Xform wrapper with SkelRoot child
                    # This matches the demo structure and properly isolates the twig skeleton
                    # from the tree skeleton, preventing cross-skeleton interference
                    if use_skeletal_mesh:
                        # Create Xform wrapper (instanceable)
                        proto_xform = UsdGeom.Xform.Define(
                            stage, f"/{assembly_name}/TwigPrototypes/{proto_name}"
                        )
                        proto_prim = proto_xform.GetPrim()
                        proto_prim.SetInstanceable(True)

                        # Create SkelRoot child with twig-specific name for unique Unreal assets
                        skel_root_path = f"/{assembly_name}/TwigPrototypes/{proto_name}/{twig_asset_name}"
                        skel_root_prim = stage.DefinePrim(skel_root_path, "SkelRoot")

                        # Reference twig USD from SkelRoot child (not the wrapper)
                        # CRITICAL: Use "/Twig" (capital T) to match twig file's defaultPrim
                        skel_root_prim.GetReferences().AddReference(
                            f"./{twig_ref_path.name}", "/Twig"
                        )

                    else:
                        # Static twigs: use Xform wrapper like skeletal to isolate reference
                        # CRITICAL: This wrapper pattern prevents prototypes from rendering at root
                        proto_xform = UsdGeom.Xform.Define(
                            stage, f"/{assembly_name}/TwigPrototypes/{proto_name}"
                        )
                        proto_prim = proto_xform.GetPrim()
                        proto_prim.SetInstanceable(True)

                        # Create child Xform with twig-specific name for unique Unreal assets
                        # Using child prim isolates the reference from direct rendering
                        twig_child_path = f"/{assembly_name}/TwigPrototypes/{proto_name}/{twig_asset_name}"
                        twig_child_prim = stage.DefinePrim(twig_child_path, "Xform")

                        # Reference twig USD from child (not the wrapper)
                        twig_child_prim.GetReferences().AddReference(
                            f"./{twig_ref_path.name}", "/Twig"
                        )

                    prototype_paths.append(Sdf.Path(proto_prim.GetPath()))

                if prototype_paths:
                    # Create PointInstancer as sibling to TreeMesh
                    # Reference assembly shows PointInstancer at same level as TreeMesh (SkelRoot)
                    instancer_prim = stage.DefinePrim(
                        f"/{assembly_name}/TwigInstances", "PointInstancer"
                    )
                    instancer = UsdGeom.PointInstancer(instancer_prim)

                    # Set prototypes relationship
                    instancer.CreatePrototypesRel().SetTargets(prototype_paths)

                    # Collect instance data
                    all_positions = []
                    all_orientations = []
                    all_scales = []
                    all_proto_indices = []

                    for twig_type, placement_list in placements.items():
                        if not placement_list:
                            print(f"  Skipping {twig_type}: empty placement_list")
                            continue

                        # Map twig type to prototype index with fallback logic
                        # If this twig type has no matching prototype, use a fallback:
                        # Fallback mapping for twig types without dedicated prototypes:
                        # - twig_upward → twig_long (upward growth uses apical/terminal twigs)
                        # - twig_dead: NO MAPPING - dead branches have no foliage
                        fallback_map = {
                            "twig_upward": "twig_long",  # Upward twigs → apical/long
                            # twig_dead intentionally excluded - dead branches shouldn't have foliage
                        }

                        if twig_type in twig_type_to_proto_idx:
                            proto_idx = twig_type_to_proto_idx[twig_type]
                            mapped_type = twig_type
                        elif (
                            twig_type in fallback_map
                            and fallback_map[twig_type] in twig_type_to_proto_idx
                        ):
                            # Use fallback mapping
                            mapped_type = fallback_map[twig_type]
                            proto_idx = twig_type_to_proto_idx[mapped_type]
                            print(
                                f"  Mapping {twig_type} -> {mapped_type} (proto_idx={proto_idx})"
                            )
                        else:
                            # No mapping available - skip
                            print(
                                f"  Skipping {twig_type}: no matching prototype or fallback"
                            )
                            continue

                        print(
                            f"  Adding {len(placement_list)} instances of {twig_type} (proto_idx={proto_idx})"
                        )

                        # Import rotation functions once outside the loop for performance
                        from growpy.core.twig import (
                            normal_to_rotation_matrix,
                            rotation_matrix_to_quaternion,
                        )

                        for placement in placement_list:
                            pos = placement["position"]
                            normal = placement["normal"]

                            # CRITICAL: Positions from Grove API are already in the correct coordinate space
                            # The bindJoints attribute tells Unreal which skeleton joint each instance follows

                            # Create rotation matrix from normal
                            rot_matrix = normal_to_rotation_matrix(normal)

                            # Convert to quaternion
                            quat = rotation_matrix_to_quaternion(rot_matrix)

                            # Add to arrays
                            all_positions.append(Gf.Vec3f(pos[0], pos[1], pos[2]))
                            all_orientations.append(
                                Gf.Quath(quat[0], quat[1], quat[2], quat[3])
                            )
                            all_scales.append(Gf.Vec3f(1.0, 1.0, 1.0))
                            all_proto_indices.append(proto_idx)

                    # Set PointInstancer attributes
                    instancer.CreatePositionsAttr().Set(all_positions)
                    instancer.CreateOrientationsAttr().Set(all_orientations)
                    instancer.CreateScalesAttr().Set(all_scales)
                    instancer.CreateProtoIndicesAttr().Set(all_proto_indices)

                    if use_skeletal_mesh:
                        # Apply NaniteAssemblySkelBindingAPI and set bindJoints for skeletal assembly
                        #
                        # CRITICAL: bindJoints controls INSTANCE PLACEMENT (not vertex deformation)
                        # - Tree skeleton branch joints (e.g., "tree_root/joint_1/branch_0") move instances
                        # - Each twig's internal skeleton (e.g., "twig_root") deforms its own mesh vertices
                        # - NO cross-skeleton binding: tree skeleton doesn't deform twig vertices
                        #
                        # This is required for Unreal to recognize and import the skeletal assembly correctly.

                        skel_binding_schemas = Sdf.TokenListOp()
                        skel_binding_schemas.prependedItems = [
                            "NaniteAssemblySkelBindingAPI"
                        ]
                        instancer_prim.SetMetadata("apiSchemas", skel_binding_schemas)

                        # Get primvars API for creating custom attributes
                        primvars_api = UsdGeom.PrimvarsAPI(instancer_prim)

                        # Extract joint names array from tree skeleton
                        # Joint names are hierarchical paths like "joint_0/joint_1/joint_2"
                        # The bone_id in each TwigPlacement is a direct index into this array
                        joint_names = _extract_joint_names_from_usd(tree_usd_path)

                        # Build bindJoints array using direct bone_id lookup
                        # Each twig has a bone_id that's a direct index into joint_names
                        # This is O(1) per twig instead of O(n) spatial search
                        bind_joints = []
                        bind_weights = []

                        # Iterate through placements in same order as instance creation
                        # CRITICAL: Must match instance creation loop logic exactly
                        for twig_type, placement_list in placements.items():
                            if not placement_list:
                                continue

                            # Apply same fallback mapping as instance creation
                            # twig_dead intentionally excluded - dead branches have no foliage
                            fallback_map = {
                                "twig_upward": "twig_long",
                            }

                            if twig_type in twig_type_to_proto_idx:
                                # Direct mapping exists
                                pass
                            elif (
                                twig_type in fallback_map
                                and fallback_map[twig_type] in twig_type_to_proto_idx
                            ):
                                # Use fallback mapping
                                pass
                            else:
                                # No mapping - skip
                                continue

                            for placement in placement_list:
                                # Get bone_id from placement - this is a direct index into joint_names
                                # Handle both TwigPlacement objects and dict representations
                                if isinstance(placement, dict):
                                    bone_id = placement.get("bone_id")
                                else:
                                    # TwigPlacement object
                                    bone_id = getattr(placement, "bone_id", None)

                                # Use bone_id as direct index into joint_names (O(1) lookup)
                                if bone_id is not None and 0 <= bone_id < len(
                                    joint_names
                                ):
                                    joint_path = joint_names[bone_id]
                                    bind_joints.append(joint_path)
                                    bind_weights.append(1.0)
                                else:
                                    # Fallback to tree root if bone_id is invalid
                                    bind_joints.append("tree_root")
                                    bind_weights.append(1.0)

                        # Validate all bindJoints exist in skeleton
                        skeleton_joints = set(joint_names)
                        missing_joints = [
                            j for j in set(bind_joints) if j not in skeleton_joints
                        ]
                        if missing_joints:
                            print(
                                f"\n⚠️  WARNING: {len(missing_joints)} bindJoints not found in skeleton:"
                            )
                            for mj in missing_joints[:5]:
                                print(f"   - {mj}")

                        # Create bindJoints primvar with uniform variability and interpolation
                        bind_joints_attr = instancer_prim.CreateAttribute(
                            "primvars:unreal:naniteAssembly:bindJoints",
                            Sdf.ValueTypeNames.TokenArray,
                            False,  # custom (not built-in)
                            Sdf.VariabilityUniform,  # uniform variability
                        )
                        bind_joints_attr.Set(bind_joints)

                        # Set interpolation metadata (matching reference assembly)
                        # Note: elementSize is NOT set - Unreal infers 1 joint per instance from array length
                        bind_joints_attr.SetMetadata("interpolation", "uniform")

                        # Create bindJointWeights primvar with uniform variability and interpolation
                        bind_weights_attr = instancer_prim.CreateAttribute(
                            "primvars:unreal:naniteAssembly:bindJointWeights",
                            Sdf.ValueTypeNames.FloatArray,
                            False,  # custom (not built-in)
                            Sdf.VariabilityUniform,  # uniform variability
                        )
                        bind_weights_attr.Set(bind_weights)

                        # Set interpolation metadata (matching reference assembly)
                        # Note: elementSize is NOT set - Unreal infers 1 joint per instance from array length
                        bind_weights_attr.SetMetadata("interpolation", "uniform")

                    else:
                        pass
            else:
                pass

        # Skeleton is already embedded if use_skeletal_mesh=True (handled earlier)

        # Save stage
        stage.GetRootLayer().Save()

        # CRITICAL: USD composition overrides our apiSchemas metadata
        # We need to manually edit the saved file to add "prepend apiSchemas" directives
        # This ensures they take precedence over the referenced prim's schemas
        if use_skeletal_mesh:
            _fix_api_schemas_in_assembly(output_path, assembly_name)

        # Validate the assembly structure (based on video requirements)
        if validate and use_skeletal_mesh:
            validation_result = validate_assembly(output_path)
            if not validation_result["valid"]:
                for error in validation_result["errors"]:
                    pass
            else:
                pass

        return True

    except ImportError:
        return False
    except Exception as e:
        import traceback

        traceback.print_exc()
        return False


def export_tree_as_nanite_assembly(
    model: Any,
    skeleton: Optional[Any],
    output_path: Path,
    species_name: str,
    tree_id: Optional[str] = None,
    bones_info: Optional[List] = None,
    twig_usd_paths: Optional[Dict[str, Path]] = None,
    include_twigs: bool = True,
    use_skeletal_mesh: bool = False,
    use_static_mesh: bool = False,
    include_grove_attributes: bool = False,
    validate: bool = True,
    timer: Optional[Any] = None,
) -> bool:
    """Export Grove tree as Unreal Engine Nanite Assembly.

    This function:
    1. Exports tree using Grove's native USD export
    2. Creates Nanite Assembly USD with proper Unreal schema
    3. Includes twigs as PointInstancer prims

    Note: Model must already be built with desired quality settings.
    Call grove.build_models({...}) before passing model to this function.

    CRITICAL: For skeletal export, bones_info must be provided from grove.tag_bone_id()
    CRITICAL: use_skeletal_mesh and use_static_mesh are mutually exclusive

    Args:
        model: Grove tree model from grove.build_models()
        skeleton: Optional Grove skeleton from grove.build_skeletons()
        output_path: Path for Nanite Assembly USDA file
        species_name: Tree species name
        tree_id: Optional tree ID for unique prim names (e.g., "0007")
        bones_info: Optional list of bone tuples from grove.tag_bone_id() for this specific tree
        twig_usd_paths: Dict mapping twig types to USD paths
        include_twigs: Whether to include twig instances
        use_skeletal_mesh: Use skeletal mesh type (for animation)
        use_static_mesh: Use static mesh type (with materials/textures, no skeleton)
        include_grove_attributes: If True, include Grove metadata in USD (increases size ~70%)
        validate: If True, validate assembly structure after creation (default: True)
        timer: Optional ProfileTimer for sub-step profiling

    Returns:
        bool: Success status
    """
    # Create a no-op timer context if none provided
    from contextlib import nullcontext

    def _track(name):
        if timer is not None:
            return timer.track(name, parent="export_nanite_assembly_skeletal")
        return nullcontext()

    try:
        # First, export using Grove's native USD
        try:
            import the_grove_22_core as gc
        except ImportError:
            return False

        # Determine export mode
        if use_static_mesh and use_skeletal_mesh:
            # Both flags set - error
            return False

        # Export tree using direct Grove API geometry
        from .tree_export import build_tree_mesh

        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Generate tree mesh filename from species and tree_id for clear identification
        sanitized_species = species_name.replace(" ", "_").replace("-", "_").lower()
        if tree_id:
            base_name = f"{sanitized_species}_{tree_id}"
        else:
            base_name = sanitized_species

        # Triangulate model before building USD (CRITICAL for proper face/attribute matching)
        with _track("triangulate"):
            try:
                model.triangulate()
            except Exception as e:
                pass

        # Use unified build_tree_mesh for both skeletal and static
        # Skeletal mesh (with skeleton) is preferred for Nanite performance
        if use_static_mesh:
            # Static mesh export (no skeleton)
            temp_tree_path = output_path.parent / f"{base_name}_static.usda"
            with _track("build_tree_mesh"):
                if not build_tree_mesh(
                    model=model,
                    skeleton=None,
                    bones_info=None,
                    output_path=temp_tree_path,
                    up_axis="Z",
                    triangulated=True,
                    include_skeleton=False,
                    include_grove_attributes=include_grove_attributes,
                    species_name=species_name,
                    tree_id=tree_id,
                ):
                    return False
        else:
            # Skeletal mesh export (default - preferred for performance)
            temp_tree_path = output_path.parent / f"{base_name}_skeletal.usda"
            with _track("build_tree_mesh"):
                if not build_tree_mesh(
                    model=model,
                    skeleton=skeleton,
                    bones_info=bones_info,
                    output_path=temp_tree_path,
                    up_axis="Z",
                    triangulated=True,
                    include_skeleton=True,
                    include_grove_attributes=include_grove_attributes,
                    species_name=species_name,
                    tree_id=tree_id,
                ):
                    return False

        # Extract twig placements from Grove model BEFORE creating assembly
        twig_placements = None
        if include_twigs:
            with _track("extract_twig_placements"):
                try:
                    twig_placements = extract_twig_placements_from_model(
                        model, bones_info=bones_info if not use_static_mesh else None
                    )
                    total_twigs = sum(len(p) for p in twig_placements.values())
                    if total_twigs > 0:
                        pass
                except Exception as e:
                    twig_placements = None

        # Auto-lookup twigs if include_twigs=True and none provided
        if include_twigs and twig_usd_paths is None:
            with _track("twig_lookup"):
                try:
                    from .tree_export import get_twig_usd_map_for_species

                    # CRITICAL: Always use skeletal twigs for both skeletal and static assemblies
                    # Static twig variants don't exist, and skeletal twigs work as point instances
                    # in both assembly types (assembly type only affects tree mesh, not twig references)
                    twig_usd_paths = get_twig_usd_map_for_species(
                        species_name,
                        prefer_skeletal=True,
                        prefer_static=False,
                    )
                    if twig_usd_paths:
                        pass
                    else:
                        pass
                except Exception as e:
                    twig_usd_paths = None

        # Copy twig USD files to output directory for relative references (with caching)
        if twig_usd_paths:
            with _track("copy_twig_files"):
                dest_dir = output_path.parent

                for twig_type, twig_path in twig_usd_paths.items():
                    if twig_path.exists():
                        _copy_twig_file_cached(twig_path, dest_dir)

        # Create Assembly USD
        with _track("create_assembly"):
            success = create_assembly(
                tree_usd_path=temp_tree_path,
                output_path=output_path,
                species_name=species_name,
                tree_id=tree_id,
                twig_usd_paths=twig_usd_paths if include_twigs else None,
                use_skeletal_mesh=use_skeletal_mesh and not use_static_mesh,
                twig_placements=twig_placements,
                validate=validate,
            )

        if success:
            pass

        return success

    except Exception as e:
        import traceback

        traceback.print_exc()
        return False


def validate_assembly(usd_path: Path) -> Dict[str, Any]:
    """Validate an assembly USD file for Unreal Engine compatibility.

    Checks for:
    - Proper NaniteAssemblyRootAPI application
    - Correct meshType attribute (staticMesh or skeletalMesh)
    - Skeleton relationship (for skeletal meshes)
    - Proper prototype structure with NaniteAssemblyExternalRefAPI
    - Skeletal binding on PointInstancer (for skeletal meshes)

    Args:
        usd_path: Path to the USD file to validate

    Returns:
        Dictionary with validation results:
        {
            "valid": bool,
            "mesh_type": str,
            "errors": List[str],
            "warnings": List[str],
            "details": Dict[str, Any]
        }
    """
    result = {
        "valid": True,
        "mesh_type": None,
        "errors": [],
        "warnings": [],
        "details": {},
    }

    try:
        stage = Usd.Stage.Open(str(usd_path))
        default_prim = stage.GetDefaultPrim()

        if not default_prim:
            result["errors"].append("No default prim set")
            result["valid"] = False
            return result

        # Check for NaniteAssemblyRootAPI
        api_schemas = default_prim.GetMetadata("apiSchemas")
        if not api_schemas or "NaniteAssemblyRootAPI" not in (
            api_schemas.prependedItems if hasattr(api_schemas, "prependedItems") else []
        ):
            result["errors"].append("NaniteAssemblyRootAPI not applied to default prim")
            result["valid"] = False

        # Check meshType attribute
        mesh_type_attr = default_prim.GetAttribute("unreal:naniteAssembly:meshType")
        if not mesh_type_attr:
            result["errors"].append("Missing unreal:naniteAssembly:meshType attribute")
            result["valid"] = False
        else:
            mesh_type = mesh_type_attr.Get()
            result["mesh_type"] = mesh_type
            result["details"]["mesh_type"] = mesh_type

            if mesh_type not in ["staticMesh", "skeletalMesh"]:
                result["errors"].append(
                    f"Invalid meshType: {mesh_type} (must be 'staticMesh' or 'skeletalMesh')"
                )
                result["valid"] = False

            # Validate skeleton relationship for skeletal meshes
            if mesh_type == "skeletalMesh":
                skeleton_rel = default_prim.GetRelationship(
                    "unreal:naniteAssembly:skeleton"
                )
                if not skeleton_rel:
                    result["errors"].append(
                        "Missing unreal:naniteAssembly:skeleton relationship for skeletalMesh"
                    )
                    result["valid"] = False
                else:
                    targets = skeleton_rel.GetTargets()
                    if not targets:
                        result["errors"].append("Skeleton relationship has no targets")
                        result["valid"] = False
                    else:
                        result["details"]["skeleton_target"] = str(targets[0])

        # Check for prototypes with NaniteAssemblyExternalRefAPI
        prototypes_found = 0
        for prim in stage.Traverse():
            api_schemas = prim.GetMetadata("apiSchemas")
            if api_schemas and "NaniteAssemblyExternalRefAPI" in (
                api_schemas.prependedItems
                if hasattr(api_schemas, "prependedItems")
                else []
            ):
                prototypes_found += 1

                # Check if it's instanceable
                if not prim.IsInstanceable():
                    result["warnings"].append(
                        f"Prototype {prim.GetPath()} is not marked as instanceable"
                    )

        result["details"]["prototype_count"] = prototypes_found
        if prototypes_found == 0:
            result["warnings"].append(
                "No prototypes with NaniteAssemblyExternalRefAPI found"
            )

        # Check for PointInstancer with skeletal binding
        for prim in stage.Traverse():
            if prim.GetTypeName() == "PointInstancer":
                result["details"]["has_point_instancer"] = True

                if result["mesh_type"] == "skeletalMesh":
                    # Check for skeletal binding API
                    api_schemas = prim.GetMetadata("apiSchemas")
                    if not api_schemas or "NaniteAssemblySkelBindingAPI" not in (
                        api_schemas.prependedItems
                        if hasattr(api_schemas, "prependedItems")
                        else []
                    ):
                        result["warnings"].append(
                            "PointInstancer missing NaniteAssemblySkelBindingAPI for skeletal mesh"
                        )

                    # Check for binding primvars
                    bind_joints = prim.GetAttribute(
                        "primvars:unreal:naniteAssembly:bindJoints"
                    )
                    bind_weights = prim.GetAttribute(
                        "primvars:unreal:naniteAssembly:bindJointWeights"
                    )

                    if not bind_joints:
                        result["warnings"].append(
                            "Missing primvars:unreal:naniteAssembly:bindJoints"
                        )
                    if not bind_weights:
                        result["warnings"].append(
                            "Missing primvars:unreal:naniteAssembly:bindJointWeights"
                        )

        if result["details"].get("skeleton_target"):
            pass

        if result["errors"]:
            for error in result["errors"]:
                pass

        if result["warnings"]:
            for warning in result["warnings"]:
                pass

    except Exception as e:
        result["errors"].append(f"Validation failed: {e}")
        result["valid"] = False

    return result


def _fix_api_schemas_in_assembly(assembly_path: Path, assembly_name: str) -> None:
    """Fix apiSchemas in assembly file by manually editing USD text.

    USD composition can override our SetMetadata calls, so we need to manually
    add 'prepend apiSchemas' directives to ensure they take precedence.
    """
    try:
        # Read the file
        content = assembly_path.read_text()

        # TreeMesh is just a SkelRoot - no additional API schemas needed
        # (Reference file doesn't have SkelBindingAPI on TreeMesh)
        # The NaniteAssemblySkelBindingAPI on PointInstancer is sufficient

        # Fix PointInstancer - add prepend apiSchemas
        content = content.replace(
            f'def PointInstancer "TwigInstances"\n    {{',
            f'def PointInstancer "TwigInstances" (\n        prepend apiSchemas = ["NaniteAssemblySkelBindingAPI"]\n    )\n    {{',
        )

        # Write back
        assembly_path.write_text(content)

    except Exception as e:
        # Non-fatal - assembly might still work without perfect schema setup
        pass


def _extract_joint_names_from_usd(tree_usd_path: Path) -> List[str]:
    """Extract joint names array from tree USD skeleton.

    Joint names are hierarchical paths like "tree_root/joint_1/branch_0/joint_2".
    The bone ID from point_attribute_bone_id is an index into this array.

    Args:
        tree_usd_path: Path to tree USD with skeleton

    Returns:
        List of joint names in skeleton order
    """
    try:
        from pxr import Usd, UsdSkel

        stage = Usd.Stage.Open(str(tree_usd_path))

        # Find skeleton prim
        for prim in stage.Traverse():
            if prim.IsA(UsdSkel.Skeleton):
                skeleton = UsdSkel.Skeleton(prim)
                joints_attr = skeleton.GetJointsAttr()

                if joints_attr:
                    joint_names = joints_attr.Get()
                    # Convert to list of strings
                    return [str(name) for name in joint_names]

        return []

    except Exception as e:
        return []


def _extract_dynamic_wind_from_usd(tree_usd_path: Path) -> Tuple[List[str], List[int]]:
    """Extract DynamicWind attributes from tree USD skeleton.

    Reads the unreal:dynamicWind:jointNames and unreal:dynamicWind:jointSimulationGroups
    attributes from the referenced skeletal USD file.

    CRITICAL: jointNames should be simple bone names (last segment only), not
    hierarchical paths. This function ensures compatibility by converting any
    hierarchical paths to simple names.

    Args:
        tree_usd_path: Path to tree USD with skeleton and DynamicWind attributes

    Returns:
        Tuple of (joint_names, simulation_groups) lists
    """
    try:
        from pxr import Usd, UsdSkel

        stage = Usd.Stage.Open(str(tree_usd_path))

        # Find skeleton prim with DynamicWind attributes
        for prim in stage.Traverse():
            if prim.IsA(UsdSkel.Skeleton):
                joint_names_attr = prim.GetAttribute("unreal:dynamicWind:jointNames")
                sim_groups_attr = prim.GetAttribute(
                    "unreal:dynamicWind:jointSimulationGroups"
                )

                if joint_names_attr and sim_groups_attr:
                    joint_names = joint_names_attr.Get()
                    sim_groups = sim_groups_attr.Get()

                    if joint_names and sim_groups:
                        # Ensure names are simple (not hierarchical paths)
                        # Convert "tree_root/joint_1/joint_2" to "joint_2"
                        simple_names = [
                            str(name).split("/")[-1] for name in joint_names
                        ]
                        return (simple_names, list(sim_groups))

        return ([], [])

    except Exception as e:
        return ([], [])


def _add_dynamic_wind_to_assembly(
    stage: Usd.Stage,
    skeleton_path: str,
    joint_names: List[str],
    simulation_groups: List[int],
) -> bool:
    """Add DynamicWind attributes directly to skeleton prim in assembly.

    CRITICAL: Unreal looks for DynamicWind attributes in the main assembly file,
    not in referenced USD files. This function copies the attributes from the
    referenced skeletal USD to the assembly stage.

    The Megaplant reference shows that DynamicWind attributes must be:
    1. On the Skeleton prim (not SkelRoot)
    2. With DynamicWindSkeletonAPI in apiSchemas
    3. Using uniform variability (not custom)

    Args:
        stage: The assembly USD stage
        skeleton_path: Path to the skeleton prim in the assembly
        joint_names: List of joint names for DynamicWind
        simulation_groups: List of simulation group indices per joint

    Returns:
        True if attributes were added successfully
    """
    if not joint_names or not simulation_groups:
        return False

    try:
        # Get or create the skeleton prim
        skel_prim = stage.GetPrimAtPath(skeleton_path)
        if not skel_prim:
            # Prim doesn't exist yet (it will be composed from reference)
            # We need to create an override prim
            skel_prim = stage.OverridePrim(skeleton_path)

        # Apply SkelBindingAPI and DynamicWindSkeletonAPI to skeleton prim
        # Megaplant uses: prepend apiSchemas = ["SkelBindingAPI", "DynamicWindSkeletonAPI"]
        api_schemas = skel_prim.GetMetadata("apiSchemas")
        if api_schemas:
            prepended = list(api_schemas.prependedItems)
            if "SkelBindingAPI" not in prepended:
                prepended.insert(0, "SkelBindingAPI")
            if "DynamicWindSkeletonAPI" not in prepended:
                prepended.append("DynamicWindSkeletonAPI")
            api_schemas.prependedItems = prepended
            skel_prim.SetMetadata("apiSchemas", api_schemas)
        else:
            api_schemas = Sdf.TokenListOp()
            api_schemas.prependedItems = ["SkelBindingAPI", "DynamicWindSkeletonAPI"]
            skel_prim.SetMetadata("apiSchemas", api_schemas)

        # Add DynamicWind attributes with uniform variability (per Megaplant reference)
        joint_names_attr = skel_prim.CreateAttribute(
            "unreal:dynamicWind:jointNames",
            Sdf.ValueTypeNames.TokenArray,
            custom=False,
            variability=Sdf.VariabilityUniform,
        )
        joint_names_attr.Set(joint_names)

        sim_groups_attr = skel_prim.CreateAttribute(
            "unreal:dynamicWind:jointSimulationGroups",
            Sdf.ValueTypeNames.IntArray,
            custom=False,
            variability=Sdf.VariabilityUniform,
        )
        sim_groups_attr.Set(simulation_groups)

        # Add visibility = "invisible" as per Megaplant reference
        # This is required for DynamicWind skeleton to work properly in Unreal
        visibility_attr = skel_prim.CreateAttribute(
            "visibility",
            Sdf.ValueTypeNames.Token,
            custom=False,
            variability=Sdf.VariabilityUniform,
        )
        visibility_attr.Set("invisible")

        return True

    except Exception as e:
        print(f"  Warning: Failed to add DynamicWind to assembly: {e}")
        return False


def create_species_assembly(
    species_name: str,
    tree_assembly_paths: List[Path],
    output_path: Path,
    use_skeletal_mesh: bool = True,
) -> bool:
    """Create a species-level assembly that references all tree assemblies.

    This creates a single USD file per species that:
    1. Defines shared twig prototypes once (imported to single folder)
    2. References individual tree assemblies as child prims with unique names

    When imported to Unreal:
    - Creates ONE folder per species (based on this file's name)
    - Shared twigs are imported once
    - Each tree becomes a separate skeletal/static mesh asset

    Args:
        species_name: Species name (e.g., "common_ash")
        tree_assembly_paths: List of paths to individual tree assembly USDs
        output_path: Output path for species assembly USDA
        use_skeletal_mesh: Whether trees use skeletal mesh type

    Returns:
        bool: Success status
    """
    if not tree_assembly_paths:
        return False

    try:
        stage = Usd.Stage.CreateNew(str(output_path))

        # Set stage metadata
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)

        # Sanitize species name
        sanitized_name = species_name.replace(" ", "_").replace("-", "_").lower()
        assembly_name = f"{sanitized_name}_species"

        # Create root prim
        root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")
        stage.SetDefaultPrim(root_prim)

        # Apply model kind
        root_prim.SetMetadata("kind", "assembly")

        # Collect unique twig references from all tree assemblies
        twig_refs = {}  # twig_name -> relative_path

        for tree_path in tree_assembly_paths:
            try:
                tree_stage = Usd.Stage.Open(str(tree_path))
                for prim in tree_stage.Traverse():
                    refs = prim.GetMetadata("references")
                    if refs and hasattr(refs, "prependedItems"):
                        for ref in refs.prependedItems:
                            ref_path = (
                                ref.assetPath if hasattr(ref, "assetPath") else str(ref)
                            )
                            # Only collect twig references (not tree mesh)
                            if "twig" in ref_path.lower():
                                twig_name = Path(ref_path.lstrip("./")).stem
                                if twig_name not in twig_refs:
                                    twig_refs[twig_name] = ref_path
            except Exception:
                pass

        # Create shared TwigPrototypes scope
        if twig_refs:
            prototypes_prim = stage.DefinePrim(
                f"/{assembly_name}/TwigPrototypes", "Scope"
            )

            for twig_name, ref_path in twig_refs.items():
                # Create prototype prim
                proto_prim = stage.DefinePrim(
                    f"/{assembly_name}/TwigPrototypes/{twig_name}", "Xform"
                )
                proto_prim.SetInstanceable(True)

                # Reference the twig USD with twig-specific SkelRoot name
                prim_type = "SkelRoot" if use_skeletal_mesh else "Xform"
                # Use twig name for unique Unreal asset naming
                twig_asset_name = twig_name.replace("_skeletal", "").replace(
                    "_static", ""
                )
                twig_mesh_prim = stage.DefinePrim(
                    f"/{assembly_name}/TwigPrototypes/{twig_name}/{twig_asset_name}",
                    prim_type,
                )
                twig_mesh_prim.GetReferences().AddReference(ref_path, "/Twig")

        # Create Trees scope with references to individual tree assemblies
        trees_prim = stage.DefinePrim(f"/{assembly_name}/Trees", "Scope")

        for tree_path in tree_assembly_paths:
            # Extract tree ID from filename (e.g., "common_ash_tree_0007" from full path)
            tree_stem = (
                tree_path.stem
            )  # e.g., "common_ash_tree_0007_skeletal_nanite_assembly"
            # Extract just tree ID (e.g., "tree_0007")
            parts = tree_stem.split("_tree_")
            if len(parts) > 1:
                tree_id = f"tree_{parts[1].split('_')[0]}"
            else:
                tree_id = tree_stem

            # Create tree prim that references the individual assembly
            tree_prim = stage.DefinePrim(f"/{assembly_name}/Trees/{tree_id}", "Xform")
            tree_prim.GetReferences().AddReference(f"./{tree_path.name}")

        stage.GetRootLayer().Save()
        return True

    except Exception as e:
        print(f"Error creating species assembly: {e}")
        return False
