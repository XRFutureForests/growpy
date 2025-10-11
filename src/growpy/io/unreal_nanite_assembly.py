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
    skeleton_path: Optional[Path] = None,
    twig_placement_source_usd: Optional[Path] = None,
) -> bool:
    """Create a Nanite Assembly USD file for Unreal Engine import.

    This creates a USD Assembly following Unreal's schema with proper API schemas:
    - NaniteAssemblyRootAPI on the root Xform with meshType attribute
    - NaniteAssemblyExternalRefAPI on child meshes (USD references ONLY)
    - PointInstancer for twig instances

    CRITICAL: For skeletal assemblies:
    - tree_usd_path MUST point to a skeletal USD with embedded UsdSkelRoot/Skeleton
    - twig_usd_paths MUST point to skeletal twigs with embedded skeletons
    - All USD files must have proper UsdSkel hierarchy for Unreal recognition

    CRITICAL: For static assemblies:
    - tree_usd_path MUST point to a static (non-skeletal) USD
    - twig_usd_paths MUST point to static (non-skeletal) twigs
    - No skeleton data should be present

    Args:
        tree_usd_path: Path to tree USD file (skeletal or static based on use_skeletal_mesh)
        output_path: Output path for Nanite Assembly USDA
        species_name: Tree species name
        twig_usd_paths: Optional dict mapping twig types to USD paths (matching mesh type)
        use_skeletal_mesh: Whether to use skeletal mesh type (requires skeletal USD inputs)
        skeleton_path: Path to skeleton USD (deprecated - skeleton should be in tree_usd_path)
        twig_placement_source_usd: Optional USD to extract twig placements from (if different from tree_usd_path)
                                    Used when tree_usd_path is skeletal but placements are in static tree

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

        # Set mesh type
        mesh_type = "skeletalMesh" if use_skeletal_mesh else "staticMesh"
        root_prim.CreateAttribute(
            "unreal:naniteAssembly:meshType", Sdf.ValueTypeNames.Token, custom=False
        ).Set(mesh_type)

        # If skeletal mesh, set skeleton reference
        if use_skeletal_mesh and skeleton_path:
            skeleton_rel = root_prim.CreateRelationship(
                "unreal:naniteAssembly:skeleton"
            )
            # Skeleton must be a descendant prim
            skeleton_rel.AddTarget(f"/{assembly_name}/Skeleton")

        # Tree mesh as ExternalRef
        tree_prim = stage.DefinePrim(f"/{assembly_name}/TreeMesh", "Xform")

        # Apply NaniteAssemblyExternalRefAPI using TokenListOp
        tree_api_schemas = Sdf.TokenListOp()
        tree_api_schemas.prependedItems = ["NaniteAssemblyExternalRefAPI"]
        tree_prim.SetMetadata("apiSchemas", tree_api_schemas)

        # Reference the tree mesh using absolute path (required by Unreal)
        tree_prim.GetReferences().AddReference(str(tree_usd_path.resolve()))

        print(f"  ✓ Created Nanite Assembly root: {assembly_name}")
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
                    # CRITICAL: For skeletal assemblies, ALWAYS use STATIC twig meshes
                    # Reason: Skeleton binding happens at PointInstancer level via NaniteAssemblySkelBindingAPI
                    #         Individual twigs must be simple geometry without their own skeleton
                    #         The tree skeleton controls all twig instances through joint binding
                    #
                    # Skeletal twig USD files (which contain embedded SkelRoot/Skeleton/Mesh with weights)
                    # are NOT suitable for Nanite Assembly - they conflict with PointInstancer binding
                    if use_skeletal_mesh and "_skeletal" in str(twig_path):
                        # Replace skeletal twig with static version
                        static_twig_path = Path(str(twig_path).replace("_skeletal", ""))
                        if static_twig_path.exists():
                            twig_ref_path = static_twig_path
                            print(
                                f"    Using static twig for skeletal assembly: {static_twig_path.name}"
                            )
                        else:
                            print(
                                f"    Warning: Static twig not found: {static_twig_path}"
                            )
                            twig_ref_path = twig_path
                    else:
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
                        "visibility", Sdf.ValueTypeNames.Token
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
                        # elementSize=1 means one joint per instance
                        instancer_prim.CreateAttribute(
                            "primvars:unreal:naniteAssembly:bindJoints",
                            Sdf.ValueTypeNames.TokenArray,
                            custom=False,
                            variability=Sdf.VariabilityUniform,
                        ).Set(bind_joints)

                        instancer_prim.CreateAttribute(
                            "primvars:unreal:naniteAssembly:bindJoints:elementSize",
                            Sdf.ValueTypeNames.Int,
                            custom=False,
                        ).Set(
                            1
                        )  # One joint per instance

                        instancer_prim.CreateAttribute(
                            "primvars:unreal:naniteAssembly:bindJointWeights",
                            Sdf.ValueTypeNames.FloatArray,
                            custom=False,
                            variability=Sdf.VariabilityUniform,
                        ).Set(bind_weights)

                        print(
                            f"    ✓ Bound {len(all_positions)} twigs to skeleton (root joint)"
                        )

                    print(
                        f"    ✓ Added {len(all_positions)} twig instances ({len(prototype_paths)} types)"
                    )
            else:
                print(
                    f"    WARNING: No twig placements found or all placement lists empty"
                )
                print(f"    Twig USD files will not be added to assembly")

        # Add skeleton if provided
        if use_skeletal_mesh and skeleton_path and skeleton_path.exists():
            skel_prim = stage.DefinePrim(f"/{assembly_name}/Skeleton", "Xform")
            skel_prim.GetReferences().AddReference(str(skeleton_path.resolve()))
            print(f"    ✓ Added skeleton reference: {skeleton_path.name}")

        # Save stage
        stage.GetRootLayer().Save()
        print(f"  ✓ Saved Nanite Assembly: {output_path.name}")

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

        print(f"  ✓ Exported base tree: {temp_tree_path.name}")

        # Create Nanite Assembly USD
        success = create_nanite_assembly_usd(
            tree_usd_path=temp_tree_path,
            output_path=output_path,
            species_name=species_name,
            twig_usd_paths=twig_usd_paths if include_twigs else None,
            use_skeletal_mesh=use_skeletal_mesh,
        )

        if success:
            print(f"\n✓ Complete: {output_path.name}")
            print(f"  Import in Unreal Engine with USD importer")
            print(f"  Schema: NaniteAssemblyRootAPI")
            print(f"  Mesh type: {'skeletal' if use_skeletal_mesh else 'static'}")

        return success

    except Exception as e:
        print(f"Failed to export Nanite Assembly: {e}")
        import traceback

        traceback.print_exc()
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
