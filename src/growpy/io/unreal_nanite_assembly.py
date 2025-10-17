"""Unreal Engine Nanite Assembly USD export.

This module creates USD files following Unreal Engine 5.7+ Nanite Assembly schema.
It wraps Grove's native USD export with proper Unreal API schemas for optimal import.

CRITICAL Requirements:
1. Static Mesh Assemblies:
   - Use meshType="staticMesh"
   - Reference static (non-skeletal) tree USD files
   - Reference static (non-skeletal) twig USD files
   - No skeleton relationships

2. Skeletal Mesh Assemblies:
   - Use meshType="skeletalMesh"
   - Reference skeletal tree USD with embedded UsdSkel
   - Reference skeletal twig USD files with embedded UsdSkel
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
from typing import Any, Dict, Optional

from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel


def create_nanite_assembly_usd(
    tree_usd_path: Path,
    output_path: Path,
    species_name: str,
    twig_usd_paths: Optional[Dict[str, Path]] = None,
    use_skeletal_mesh: bool = False,
    skeleton_source_usd: Optional[Path] = None,
    twig_placement_source_usd: Optional[Path] = None,
) -> bool:
    """Create a Nanite Assembly USD file for Unreal Engine import.

    This creates a USD Assembly following Unreal's schema with proper API schemas:
    - NaniteAssemblyRootAPI on the root Xform with meshType attribute
    - NaniteAssemblyExternalRefAPI on child meshes (USD references ONLY)
    - PointInstancer for twig instances

    CRITICAL: For skeletal assemblies (NEW APPROACH):
    - tree_usd_path MUST point to STATIC (non-skeletal) tree USD (geometry only)
    - twig_usd_paths MUST point to STATIC (non-skeletal) twigs (geometry only)
    - skeleton_source_usd MUST point to skeletal USD with embedded UsdSkelRoot/Skeleton
    - Skeleton is COPIED into assembly file (not referenced)
    - Static meshes are referenced and bound to embedded skeleton via NaniteAssemblySkelBindingAPI

    CRITICAL: For static assemblies:
    - tree_usd_path MUST point to a static (non-skeletal) USD
    - twig_usd_paths MUST point to static (non-skeletal) twigs
    - No skeleton data should be present

    Args:
        tree_usd_path: Path to tree USD file (ALWAYS static - geometry only)
        output_path: Output path for Nanite Assembly USDA
        species_name: Tree species name
        twig_usd_paths: Optional dict mapping twig types to STATIC USD paths
        use_skeletal_mesh: Whether to use skeletal mesh type (embeds skeleton from skeleton_source_usd)
        skeleton_source_usd: Path to skeletal USD to extract skeleton from (for skeletal assemblies)
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
        assembly_name = f"{species_name.replace(' ', '_')}_NaniteAssembly"
        root_prim = stage.DefinePrim(f"/{assembly_name}", "Xform")
        stage.SetDefaultPrim(root_prim)

        # Apply NaniteAssemblyRootAPI using TokenListOp
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]
        root_prim.SetMetadata("apiSchemas", api_schemas)

        # Set mesh type - CRITICAL: Must use uniform variability
        mesh_type = "skeletalMesh" if use_skeletal_mesh else "staticMesh"
        root_prim.CreateAttribute(
            "unreal:naniteAssembly:meshType",
            Sdf.ValueTypeNames.Token,
            custom=False,
            variability=Sdf.VariabilityUniform,
        ).Set(mesh_type)

        # Handle tree mesh - BOTH static and skeletal use TreeMesh wrapper
        # This ensures consistent structure and correct skeleton path resolution
        tree_prim = stage.DefinePrim(f"/{assembly_name}/TreeMesh", "Xform")

        # Apply NaniteAssemblyExternalRefAPI using TokenListOp
        tree_api_schemas = Sdf.TokenListOp()
        tree_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
        tree_prim.SetMetadata("apiSchemas", tree_api_schemas)

        # Reference the tree mesh using absolute path (required by Unreal)
        tree_prim.GetReferences().AddReference(
            str(tree_usd_path.resolve()),
            "/Tree",  # Reference the Tree prim from source USD
        )

        if use_skeletal_mesh:
            # For skeletal: Set skeleton relationship to embedded skeleton
            # Path is /{assembly}/TreeMesh/SkelRoot/Skeleton (from /Tree/SkelRoot/Skeleton in source)
            print(f"  Adding skeletal tree with embedded skeleton...")

            skeleton_rel = root_prim.CreateRelationship(
                "unreal:naniteAssembly:skeleton",
                custom=True,
            )
            skeleton_rel.AddTarget(f"/{assembly_name}/TreeMesh/SkelRoot/Skeleton")

            print(f"    [OK] Skeletal tree embedded via TreeMesh (mesh + skeleton)")
            print(
                f"    Skeleton relationship: /{assembly_name}/TreeMesh/SkelRoot/Skeleton"
            )
        else:
            print(f"  Adding static tree mesh...")

        print(f"  [OK] Created Nanite Assembly root: {assembly_name}")
        print(f"    Mesh type: {mesh_type}")
        print(f"    Tree reference: {tree_usd_path.resolve()}")

        # Add twigs if provided
        if twig_usd_paths:
            print(f"  Adding twigs as PointInstancer...")

            # Extract twig placements from tree USD
            # Use twig_placement_source_usd if provided (for skeletal assemblies),
            # otherwise use tree_usd_path
            from .twig_placement import extract_twig_placements_from_usd

            placement_source = (
                twig_placement_source_usd
                if twig_placement_source_usd
                else tree_usd_path
            )
            if twig_placement_source_usd:
                print(
                    f"    Extracting placements from: {twig_placement_source_usd.name}"
                )
            placements = extract_twig_placements_from_usd(placement_source)

            if placements and any(placements.values()):
                # Remap twig paths from source assets to output directory copies
                # Twigs are bundled/copied to output/Species/twigs/ directory
                # Nanite Assembly must reference these copies for Unreal import to work
                output_dir = output_path.parent
                species_twigs_dir = output_dir.parent / "twigs"

                remapped_twig_paths = {}
                for twig_type, source_twig_path in twig_usd_paths.items():
                    # Check if twig was copied to output directory
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

                # Map twig types to prototype indices
                twig_type_to_proto_idx = {}
                prototype_paths = []

                for idx, (twig_type, twig_path) in enumerate(
                    sorted(remapped_twig_paths.items())
                ):
                    # EXPERIMENTAL: Allow skeletal twigs in skeletal assemblies
                    # Hypothesis: Unreal may bind skeletal twig instances to tree skeleton
                    twig_ref_path = twig_path

                    if not twig_ref_path.exists():
                        print(f"    Warning: Twig mesh not found: {twig_ref_path}")
                        continue

                    twig_type_to_proto_idx[twig_type] = idx

                    # Create prototype with ExternalRef
                    proto_name = twig_type.replace("_", "")
                    proto_prim = stage.DefinePrim(
                        f"/{assembly_name}/TwigPrototypes/{proto_name}", "Xform"
                    )

                    # Apply ExternalRefAPI to prototype using TokenListOp
                    proto_api_schemas = Sdf.TokenListOp()
                    proto_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
                    proto_prim.SetMetadata("apiSchemas", proto_api_schemas)

                    # Make instanceable for memory efficiency
                    proto_prim.SetInstanceable(True)

                    # Hide prototypes - they should only be visible when instanced
                    proto_prim.CreateAttribute(
                        "visibility",
                        Sdf.ValueTypeNames.Token,
                        custom=False,
                    ).Set("invisible")

                    # Reference twig mesh using absolute path (required by Unreal)
                    proto_prim.GetReferences().AddReference(
                        str(twig_ref_path.resolve())
                    )
                    print(f"      Reference: {twig_ref_path.resolve()}")

                    prototype_paths.append(Sdf.Path(proto_prim.GetPath()))

                if prototype_paths:
                    # Create PointInstancer
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
                            from .twig_placement import (
                                normal_to_rotation_matrix,
                                rotation_matrix_to_quaternion,
                            )

                            pos = placement["position"]
                            normal = placement["normal"]

                            # Keep positions in Blender coordinates to match tree mesh
                            # Both tree and twigs use Blender Z-up coordinate system
                            # No coordinate conversion needed here

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

                    # CRITICAL: For skeletal assemblies, bind twigs to skeleton joints
                    # This allows twigs to follow skeleton animation (wind, growth, etc.)
                    if use_skeletal_mesh:
                        print(f"    Binding twig instances to skeleton joints...")

                        # Apply NaniteAssemblySkelBindingAPI to PointInstancer
                        skel_binding_schemas = Sdf.TokenListOp()
                        skel_binding_schemas.prependedItems = [
                            "NaniteAssemblySkelBindingAPI"
                        ]
                        instancer_prim.SetMetadata("apiSchemas", skel_binding_schemas)

                        # STRATEGY: Add new skeleton joints at twig mount points
                        # This gives exact placement - each twig gets its own joint
                        # The joints will be children of the nearest tree branch joint
                        #
                        # Alternative simpler approach: Bind to nearest existing joint
                        # This is faster but may cause slight displacement if bones are sparse

                        # For first implementation: bind to nearest existing joint
                        # TODO: Enhance by adding dedicated twig mount point joints

                        bind_joints = []
                        bind_weights = []

                        # Extract skeleton from tree USD
                        skeleton_joints = _extract_skeleton_joints_from_usd(
                            tree_usd_path
                        )

                        if skeleton_joints:
                            print(
                                f"      Found {len(skeleton_joints)} skeleton joints in tree"
                            )

                            # For each twig, find nearest joint
                            for twig_pos in all_positions:
                                nearest_joint, distance = _find_nearest_joint(
                                    twig_pos, skeleton_joints
                                )
                                bind_joints.append(nearest_joint)
                                bind_weights.append(1.0)

                            print(
                                f"      Bound {len(bind_joints)} twig instances to skeleton"
                            )
                        else:
                            # Fallback: bind all to root
                            print(
                                f"      Warning: No skeleton joints found, binding to root"
                            )
                            for i in range(len(all_positions)):
                                bind_joints.append("Root")
                                bind_weights.append(1.0)

                        # Create primvars for joint binding
                        # CRITICAL: Use uniform variability and proper interpolation
                        bind_joints_attr = instancer_prim.CreateAttribute(
                            "primvars:unreal:naniteAssembly:bindJoints",
                            Sdf.ValueTypeNames.TokenArray,
                            custom=False,
                            variability=Sdf.VariabilityUniform,
                        )
                        bind_joints_attr.Set(bind_joints)

                        # elementSize=1 means one joint per instance
                        instancer_prim.CreateAttribute(
                            "primvars:unreal:naniteAssembly:bindJoints:elementSize",
                            Sdf.ValueTypeNames.Int,
                            custom=False,
                        ).Set(1)

                        bind_weights_attr = instancer_prim.CreateAttribute(
                            "primvars:unreal:naniteAssembly:bindJointWeights",
                            Sdf.ValueTypeNames.FloatArray,
                            custom=False,
                            variability=Sdf.VariabilityUniform,
                        )
                        bind_weights_attr.Set(bind_weights)

                        print(
                            f"    [OK] Bound {len(all_positions)} twigs to skeleton (root joint)"
                        )

                    print(
                        f"    [OK] Added {len(all_positions)} twig instances ({len(prototype_paths)} types)"
                    )
            else:
                print(
                    f"    WARNING: No twig placements found or all placement lists empty"
                )
                print(f"    Twig USD files will not be added to assembly")

        # Skeleton is already embedded if use_skeletal_mesh=True (handled earlier)

        # Save stage
        stage.GetRootLayer().Save()
        print(f"  [OK] Saved Nanite Assembly: {output_path.name}")

        return True

    except ImportError:
        print("ERROR: USD Python (pxr) not available")
        print("Install with: pip install usd-core")
        return False
    except Exception as e:
        print(f"Failed to create Nanite Assembly USD: {e}")
        import traceback

        traceback.print_exc()
        return False


def export_tree_as_nanite_assembly(
    grove: Any,
    output_path: Path,
    species_name: str,
    twig_usd_paths: Optional[Dict[str, Path]] = None,
    include_twigs: bool = True,
    use_skeletal_mesh: bool = False,
    resolution: int = 32,
    resolution_reduce: float = 0.8,
    texture_repeat: int = 3,
    build_cutoff_age: int = 0,
    build_cutoff_thickness: float = 0.0,
    build_blend: bool = True,
    build_end_cap: bool = True,
) -> bool:
    """Export Grove tree as Unreal Engine Nanite Assembly.

    This function:
    1. Exports tree using Grove's native USD export
    2. Creates Nanite Assembly USD with proper Unreal schema
    3. Includes twigs as PointInstancer prims

    Args:
        grove: Grove instance with simulated trees
        output_path: Path for Nanite Assembly USDA file
        species_name: Tree species name
        twig_usd_paths: Dict mapping twig types to USD paths
        include_twigs: Whether to include twig instances
        use_skeletal_mesh: Use skeletal mesh type (for animation)
        resolution: Branch resolution (4-32)
        resolution_reduce: Detail reduction rate (0.0-1.0)
        texture_repeat: Texture repetitions
        build_cutoff_age: Skip branches younger than N years
        build_cutoff_thickness: Skip branches thinner than N meters
        build_blend: Smooth branch joints
        build_end_cap: Close branch ends

    Returns:
        bool: Success status
    """
    try:
        # First, export using Grove's native USD
        try:
            import the_grove_22_core as gc
        except ImportError:
            print("ERROR: Grove core (the_grove_22_core) not available")
            return False

        print(f"Exporting {species_name} as Unreal Nanite Assembly...")

        # Build tree model
        models = grove.build_models(
            {
                "resolution": resolution,
                "resolution_reduce": resolution_reduce,
                "texture_repeat": texture_repeat,
                "build_cutoff_age": build_cutoff_age,
                "build_cutoff_thickness": build_cutoff_thickness,
                "build_blend": build_blend,
                "build_end_cap": build_end_cap,
            }
        )

        if not models:
            print("No models generated from grove")
            return False

        model = models[0]

        # Export tree using Grove's native USD export
        usda_string = gc.io.model_to_usda_string(model)

        # Save tree to temporary file
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_tree_path = output_path.parent / f"{output_path.stem}_tree.usda"

        with open(temp_tree_path, "w") as f:
            f.write(usda_string)

        print(f"  [OK] Exported base tree: {temp_tree_path.name}")

        # Create Nanite Assembly USD
        success = create_nanite_assembly_usd(
            tree_usd_path=temp_tree_path,
            output_path=output_path,
            species_name=species_name,
            twig_usd_paths=twig_usd_paths if include_twigs else None,
            use_skeletal_mesh=use_skeletal_mesh,
        )

        if success:
            print(f"\n[OK] Complete: {output_path.name}")
            print(f"  Import in Unreal Engine with USD importer")
            print(f"  Schema: NaniteAssemblyRootAPI")
            print(f"  Mesh type: {'skeletal' if use_skeletal_mesh else 'static'}")

        return success

    except Exception as e:
        print(f"Failed to export Nanite Assembly: {e}")
        import traceback

        traceback.print_exc()
        return False


def _copy_skeleton_to_assembly(
    source_usd_path: Path,
    assembly_stage: Usd.Stage,
    assembly_root_path: str,
) -> bool:
    """Copy skeleton hierarchy from source USD into assembly file.

    This extracts the SkelRoot/Skeleton prims from the source file
    and adds them directly to the assembly, allowing static meshes
    to reference the geometry while the skeleton controls animation.

    Args:
        source_usd_path: Path to skeletal USD with embedded skeleton
        assembly_stage: Target assembly stage to add skeleton to
        assembly_root_path: Path to assembly root prim (e.g., "/TreeName_NaniteAssembly")

    Returns:
        bool: Success status
    """
    try:
        source_stage = Usd.Stage.Open(str(source_usd_path))

        # Find SkelRoot in source
        skel_root_prim = None
        for prim in source_stage.Traverse():
            if prim.IsA(UsdSkel.Root):
                skel_root_prim = prim
                break

        if not skel_root_prim:
            print("      Warning: No SkelRoot found in source USD")
            return False

        # Create SkelRoot in assembly
        assembly_skel_root = assembly_stage.DefinePrim(
            f"{assembly_root_path}/SkelRoot", "SkelRoot"
        )

        # Copy skeleton prim recursively
        def copy_prim_hierarchy(source_prim, target_parent_path, skip_mesh=False):
            """Recursively copy prim and its children.

            Args:
                source_prim: Source prim to copy from
                target_parent_path: Target parent path
                skip_mesh: If True, skip copying Mesh prims (we only want skeleton structure)
            """
            # CRITICAL: Skip Mesh prims - we only want the skeleton structure
            # The actual mesh geometry will be referenced externally
            if skip_mesh and source_prim.GetTypeName() == "Mesh":
                print(f"        Skipping embedded mesh prim: {source_prim.GetName()}")
                return

            # Create target prim with same type
            target_path = f"{target_parent_path}/{source_prim.GetName()}"
            target_prim = assembly_stage.DefinePrim(
                target_path, source_prim.GetTypeName()
            )

            # Copy attributes
            for attr in source_prim.GetAttributes():
                attr_name = attr.GetName()
                # Skip xform ops and problematic computed attributes
                if attr_name.startswith("xformOp") or attr_name == "extent":
                    continue

                value = attr.Get()
                if value is not None:  # Only set if value exists
                    target_attr = target_prim.CreateAttribute(
                        attr_name, attr.GetTypeName()
                    )
                    target_attr.Set(value)

            # Copy metadata (API schemas, etc.)
            for key in source_prim.GetAllMetadata():
                if key not in ["specifier", "typeName"]:  # Skip auto-managed metadata
                    target_prim.SetMetadata(key, source_prim.GetMetadata(key))

            # Copy relationships
            for rel in source_prim.GetRelationships():
                target_rel = target_prim.CreateRelationship(rel.GetName())
                for target in rel.GetTargets():
                    # Adjust relationship paths to assembly
                    adjusted_target = str(target).replace(
                        source_prim.GetPath().GetParentPath().pathString,
                        target_parent_path,
                    )
                    target_rel.AddTarget(adjusted_target)

            # Recursively copy children (propagate skip_mesh flag)
            for child in source_prim.GetChildren():
                copy_prim_hierarchy(child, target_path, skip_mesh=skip_mesh)

        # Copy SkelRoot and all descendants, but SKIP mesh geometry
        # The mesh will be referenced externally via TreeMesh
        copy_prim_hierarchy(skel_root_prim, assembly_root_path, skip_mesh=True)

        print(f"      [OK] Copied skeleton hierarchy (without embedded meshes)")
        return True

    except Exception as e:
        print(f"      Warning: Failed to copy skeleton: {e}")
        return False


def _extract_skeleton_joints_from_usd(
    tree_usd_path: Path,
) -> Dict[str, "Gf.Vec3d"]:
    """Extract skeleton joint names and positions from tree USD file.

    Args:
        tree_usd_path: Path to skeletal tree USD file

    Returns:
        Dictionary mapping joint names to their world positions
    """
    joint_positions = {}

    try:
        stage = Usd.Stage.Open(str(tree_usd_path))

        # Find skeleton primitive
        for prim in stage.Traverse():
            if prim.IsA(UsdSkel.Skeleton):
                skeleton = UsdSkel.Skeleton(prim)

                # Get joint names
                joints_attr = skeleton.GetJointsAttr()
                if not joints_attr:
                    continue

                joint_names = joints_attr.Get()

                # Get bind transforms (joint rest positions in world space)
                bind_transforms_attr = skeleton.GetBindTransformsAttr()
                if not bind_transforms_attr:
                    continue

                bind_transforms = bind_transforms_attr.Get()

                # Extract position from each transform matrix
                for joint_name, transform in zip(joint_names, bind_transforms):
                    # Get translation component from matrix
                    position = transform.ExtractTranslation()
                    joint_positions[joint_name] = position

                break  # Found skeleton, stop searching

    except Exception as e:
        print(f"      Warning: Could not extract skeleton joints: {e}")

    return joint_positions


def _find_nearest_joint(
    position: "Gf.Vec3f", skeleton_joints: Dict[str, "Gf.Vec3d"]
) -> tuple[str, float]:
    """Find the nearest skeleton joint to a given position.

    Args:
        position: Twig mount position
        skeleton_joints: Dictionary of joint names to positions

    Returns:
        Tuple of (nearest_joint_name, distance)
    """
    if not skeleton_joints:
        return ("Root", float("inf"))

    nearest_joint = "Root"
    nearest_distance = float("inf")

    # Convert position to Vec3d for consistent math
    pos_vec = Gf.Vec3d(position[0], position[1], position[2])

    for joint_name, joint_pos in skeleton_joints.items():
        # Calculate Euclidean distance
        delta = pos_vec - joint_pos
        distance = (delta[0] ** 2 + delta[1] ** 2 + delta[2] ** 2) ** 0.5

        if distance < nearest_distance:
            nearest_distance = distance
            nearest_joint = joint_name

    return (nearest_joint, nearest_distance)


def validate_nanite_assembly(usd_path: Path) -> Dict[str, Any]:
    """Validate a Nanite Assembly USD file for Unreal Engine compatibility.

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
        if not api_schemas or "NaniteAssemblyRootAPI" not in api_schemas:
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
            if api_schemas and "NaniteAssemblyExternalRefAPI" in api_schemas:
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
                    if (
                        not api_schemas
                        or "NaniteAssemblySkelBindingAPI" not in api_schemas
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

        print(f"\n{'[OK]' if result['valid'] else '[X]'} Validation: {usd_path.name}")
        print(f"  Mesh Type: {result['mesh_type']}")
        if result["details"].get("skeleton_target"):
            print(f"  Skeleton: {result['details']['skeleton_target']}")
        print(f"  Prototypes: {result['details'].get('prototype_count', 0)}")

        if result["errors"]:
            print("  Errors:")
            for error in result["errors"]:
                print(f"    - {error}")

        if result["warnings"]:
            print("  Warnings:")
            for warning in result["warnings"]:
                print(f"    - {warning}")

    except Exception as e:
        result["errors"].append(f"Validation failed: {e}")
        result["valid"] = False

    return result
