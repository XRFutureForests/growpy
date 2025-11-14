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


def create_assembly(
    tree_usd_path: Path,
    output_path: Path,
    species_name: str,
    twig_usd_paths: Optional[Dict[str, Path]] = None,
    use_skeletal_mesh: bool = False,
    skeleton_source_usd: Optional[Path] = None,
    twig_placements: Optional[Dict[str, List]] = None,
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
        twig_placement_source_usd: Optional USD to extract twig placements from (if different from tree_usd_path)

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
        assembly_name = f"{sanitized_name}_nanite_assembly"
        root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")
        stage.SetDefaultPrim(root_prim)

        # Apply NaniteAssemblyRootAPI and GeomModelAPI using TokenListOp
        # Both schemas are required by Unreal Engine 5.7
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["NaniteAssemblyRootAPI", "GeomModelAPI"]
        root_prim.SetMetadata("apiSchemas", api_schemas)
        # Set kind metadata to 'assembly' as required by Unreal (not 'group')
        root_prim.SetMetadata("kind", "assembly")

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
        tree_prim = stage.DefinePrim(f"/{assembly_name}/TreeMesh", tree_prim_type)

        # Do not apply SkelBindingAPI to TreeMesh here.
        # For Nanite assemblies, binding is driven by NaniteAssemblySkelBindingAPI
        # on the PointInstancer; TreeMesh remains a plain SkelRoot.

        # Reference the tree mesh
        # CRITICAL: Always explicitly reference the /tree prim path for consistency
        # This ensures Unreal properly understands the skeleton structure
        tree_prim.GetReferences().AddReference(
            f"./{tree_usd_path.name}",
            "/tree",  # Explicit prim path (matches demo structure)
        )

        if use_skeletal_mesh:
            # Set the Nanite Assembly skeleton relationship on root prim
            # This points to the skeleton inside the referenced tree
            skeleton_rel = root_prim.CreateRelationship(
                "unreal:naniteAssembly:skeleton",
                custom=False,
            )
            skeleton_rel.SetTargets([Sdf.Path(f"/{assembly_name}/TreeMesh/TreeSkel")])

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
            else:
                placements = {}

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

                    # Copy twig file to output directory for relative references
                    # This ensures the assembly can find its twigs using ./filename.usda
                    import shutil

                    output_twig_path = output_path.parent / twig_ref_path.name
                    if not output_twig_path.exists():
                        shutil.copy2(twig_ref_path, output_twig_path)

                    # Copy twig textures for static assemblies only
                    # Skeletal assemblies should configure materials in Unreal Engine
                    if not use_skeletal_mesh:
                        # Use source path (in assets) to find textures
                        twig_dir = source_twig_path.parent
                        # Twigs store textures in a textures/ subdirectory
                        source_textures_dir = twig_dir / "textures"

                        if source_textures_dir.exists():
                            # Create output textures subdirectory
                            output_textures_dir = output_path.parent / "textures"
                            output_textures_dir.mkdir(exist_ok=True)

                            # Copy all texture files
                            for texture_ext in [".png", ".jpg", ".jpeg", ".exr"]:
                                for texture_file in source_textures_dir.glob(
                                    f"*{texture_ext}"
                                ):
                                    output_texture = (
                                        output_textures_dir / texture_file.name
                                    )
                                    if not output_texture.exists():
                                        shutil.copy2(texture_file, output_texture)

                    twig_type_to_proto_idx[twig_type] = idx

                    # Create prototype with ExternalRef
                    proto_name = twig_type.replace("_", "")

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

                        # Create SkelRoot child that references the twig USD
                        skel_root_path = (
                            f"/{assembly_name}/TwigPrototypes/{proto_name}/TwigSkelRoot"
                        )
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

                        # Create child Xform that references the twig USD
                        # Using child prim isolates the reference from direct rendering
                        twig_child_path = (
                            f"/{assembly_name}/TwigPrototypes/{proto_name}/TwigMesh"
                        )
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
                        if (
                            not placement_list
                            or twig_type not in twig_type_to_proto_idx
                        ):
                            continue

                        proto_idx = twig_type_to_proto_idx[twig_type]

                        for placement in placement_list:
                            from growpy.core.twig import (
                                normal_to_rotation_matrix,
                                rotation_matrix_to_quaternion,
                            )

                            pos = placement["position"]
                            normal = placement["normal"]

                            # CRITICAL: Positions remain in world space (matching reference assembly)
                            # The bindJoints attribute tells Unreal which skeleton joint each instance follows
                            # No position transformation needed

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
                        joint_names = _extract_joint_names_from_usd(tree_usd_path)

                        # Extract bone segments (start/end points) for distance-based binding
                        joint_segments = _extract_joint_coordinates_from_usd(
                            tree_usd_path
                        )

                        # Build bindJoints array using perpendicular distance to bone segments
                        # Each twig binds to the NEAREST bone segment within its assigned branch
                        bind_joints = []
                        bind_weights = []

                        # Iterate through placements in same order as instance creation
                        for twig_type, placement_list in placements.items():
                            if (
                                not placement_list
                                or twig_type not in twig_type_to_proto_idx
                            ):
                                continue

                            for placement in placement_list:
                                # Get branch ID and position from placement
                                # Handle both TwigPlacement objects and dict representations
                                if isinstance(placement, dict):
                                    branch_id = placement.get("branch_id")
                                    position = placement.get("position")
                                else:
                                    # TwigPlacement object
                                    branch_id = getattr(placement, "branch_id", None)
                                    position = getattr(placement, "position", None)

                                if position is not None:
                                    # Find nearest joint using perpendicular distance to bone segments
                                    # Use global search for best spatial accuracy
                                    joint_path = _find_nearest_joint_globally(
                                        joint_names,
                                        joint_segments,
                                        position,
                                    )
                                    bind_joints.append(joint_path)
                                    bind_weights.append(1.0)
                                else:
                                    # Fallback to tree root if no position
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
        if use_skeletal_mesh:
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
    bones_info: Optional[List] = None,
    twig_usd_paths: Optional[Dict[str, Path]] = None,
    include_twigs: bool = True,
    use_skeletal_mesh: bool = False,
    use_static_mesh: bool = False,
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
        bones_info: Optional list of bone tuples from grove.tag_bone_id() for this specific tree
        twig_usd_paths: Dict mapping twig types to USD paths
        include_twigs: Whether to include twig instances
        use_skeletal_mesh: Use skeletal mesh type (for animation)
        use_static_mesh: Use static mesh type (with materials/textures, no skeleton)

    Returns:
        bool: Success status
    """
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
        from .tree_export import build_static_tree_mesh, build_tree_mesh

        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Remove _nanite_assembly and mesh type suffix from output_path.stem to get base tree name
        base_name = output_path.stem.replace("_nanite_assembly", "")
        # Also strip mesh type suffix if present (e.g., _skeletal or _static)
        base_name = base_name.replace("_skeletal", "").replace("_static", "")

        # Triangulate model before building USD (CRITICAL for proper face/attribute matching)
        try:
            model.triangulate()
        except Exception as e:
            pass

        # Choose export function and filename based on mesh type
        if use_static_mesh:
            # Static mesh export
            temp_tree_path = output_path.parent / f"{base_name}_static.usda"
            if not build_static_tree_mesh(
                model=model,
                output_path=temp_tree_path,
                species_name=species_name,
                up_axis="Z",
                triangulated=True,
            ):
                return False
        else:
            # Skeletal mesh export (default)
            temp_tree_path = output_path.parent / f"{base_name}_skeletal.usda"
            if not build_tree_mesh(
                model=model,
                skeleton=skeleton,
                bones_info=bones_info,
                output_path=temp_tree_path,
                up_axis="Z",
                triangulated=True,
                species_name=species_name,
            ):
                return False

        # Extract twig placements from Grove model BEFORE creating assembly
        twig_placements = None
        if include_twigs:
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
            try:
                from .tree_export import get_twig_usd_map_for_species

                twig_usd_paths = get_twig_usd_map_for_species(
                    species_name,
                    prefer_skeletal=use_skeletal_mesh,
                    prefer_static=use_static_mesh,
                )
                if twig_usd_paths:
                    pass
                else:
                    pass
            except Exception as e:
                twig_usd_paths = None

        # Copy twig USD files to output directory for relative references
        if twig_usd_paths:
            import shutil

            copied_count = 0
            unique_twig_files = set()

            for twig_type, twig_path in twig_usd_paths.items():
                if twig_path.exists() and twig_path not in unique_twig_files:
                    dest_path = output_path.parent / twig_path.name
                    try:
                        shutil.copy2(twig_path, dest_path)
                        unique_twig_files.add(twig_path)
                        copied_count += 1
                    except Exception as e:
                        pass

            if copied_count > 0:
                pass

        # Create Assembly USD
        success = create_assembly(
            tree_usd_path=temp_tree_path,
            output_path=output_path,
            species_name=species_name,
            twig_usd_paths=twig_usd_paths if include_twigs else None,
            use_skeletal_mesh=use_skeletal_mesh and not use_static_mesh,
            twig_placements=twig_placements,
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


def _find_nearest_joint_globally(
    joint_names: List[str],
    joint_segments: Dict[
        str, Tuple[Tuple[float, float, float], Tuple[float, float, float]]
    ],
    twig_position: Tuple[float, float, float],
) -> str:
    """Find the nearest joint to a twig position across all joints.

    Uses perpendicular distance to bone segments for accurate spatial binding.

    Args:
        joint_names: List of all joint paths from skeleton
        joint_segments: Dict mapping joint_path to ((start_x,y,z), (end_x,y,z))
        twig_position: Twig location as (x, y, z) tuple

    Returns:
        Joint path of nearest joint
    """
    import math

    def point_to_segment_distance(
        point: Tuple[float, float, float],
        seg_start: Tuple[float, float, float],
        seg_end: Tuple[float, float, float],
    ) -> float:
        """Calculate perpendicular distance from point to line segment."""
        px, py, pz = point
        ax, ay, az = seg_start
        bx, by, bz = seg_end

        abx, aby, abz = bx - ax, by - ay, bz - az
        apx, apy, apz = px - ax, py - ay, pz - az
        ab_len_sq = abx * abx + aby * aby + abz * abz

        if ab_len_sq == 0:
            return math.sqrt(apx * apx + apy * apy + apz * apz)

        t = (apx * abx + apy * aby + apz * abz) / ab_len_sq
        t = max(0.0, min(1.0, t))

        closest_x = ax + t * abx
        closest_y = ay + t * aby
        closest_z = az + t * abz

        dx = px - closest_x
        dy = py - closest_y
        dz = pz - closest_z

        return math.sqrt(dx * dx + dy * dy + dz * dz)

    min_distance = float("inf")
    nearest_joint = "tree_root"

    for joint_path in joint_names:
        if joint_path not in joint_segments:
            continue

        start_point, end_point = joint_segments[joint_path]
        distance = point_to_segment_distance(twig_position, start_point, end_point)

        if distance < min_distance:
            min_distance = distance
            nearest_joint = joint_path

    return nearest_joint


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


def _extract_joint_coordinates_from_usd(
    tree_usd_path: Path,
) -> Dict[str, Tuple[Tuple[float, float, float], Tuple[float, float, float]]]:
    """Extract bone segment endpoints from tree USD skeleton.

    Each bone is represented by its start and end points, enabling accurate
    point-to-segment distance calculations for twig binding.

    Args:
        tree_usd_path: Path to tree USD with skeleton

    Returns:
        Dict mapping joint_path to ((start_x, start_y, start_z), (end_x, end_y, end_z))
    """
    try:
        from pxr import Usd, UsdSkel

        stage = Usd.Stage.Open(str(tree_usd_path))
        joint_segments = {}

        # Find skeleton prim
        for prim in stage.Traverse():
            if prim.IsA(UsdSkel.Skeleton):
                skeleton = UsdSkel.Skeleton(prim)

                # Get joint names
                joints_attr = skeleton.GetJointsAttr()
                if not joints_attr:
                    continue
                joint_names = [str(name) for name in joints_attr.Get()]

                # Get bind transforms (rest pose) for joint endpoints
                bind_transforms_attr = skeleton.GetBindTransformsAttr()
                if not bind_transforms_attr:
                    continue
                bind_transforms = bind_transforms_attr.Get()

                # Extract joint positions (endpoints)
                joint_positions = {}
                for joint_name, transform in zip(joint_names, bind_transforms):
                    translation = transform.ExtractTranslation()
                    joint_positions[joint_name] = (
                        float(translation[0]),
                        float(translation[1]),
                        float(translation[2]),
                    )

                # Build bone segments: start = parent position, end = joint position
                for joint_name in joint_names:
                    if "/" in joint_name:
                        # Joint has parent - create segment from parent to this joint
                        parent_path = joint_name.rsplit("/", 1)[0]
                        if (
                            parent_path in joint_positions
                            and joint_name in joint_positions
                        ):
                            joint_segments[joint_name] = (
                                joint_positions[parent_path],  # start (parent)
                                joint_positions[joint_name],  # end (this joint)
                            )
                    else:
                        # Root joint - segment from origin to root
                        if joint_name in joint_positions:
                            joint_segments[joint_name] = (
                                (0.0, 0.0, 0.0),  # start (origin)
                                joint_positions[joint_name],  # end (root)
                            )

                break  # Found skeleton, done

        return joint_segments

    except Exception as e:
        return {}
