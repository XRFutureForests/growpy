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

from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel


def _extract_twig_placements_from_usd_inline(usd_path: Path) -> Dict[str, List[Dict]]:
    """Extract twig placements from USD primvars - simplified inline version."""
    placements = {}
    try:
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            return placements

        for prim in stage.Traverse():
            if prim.IsA(UsdGeom.Mesh):
                mesh = UsdGeom.Mesh(prim)
                primvars_api = UsdGeom.PrimvarsAPI(mesh)

                # Check for twig primvars
                for twig_type in ["twig_long", "twig_short", "twig_upward", "twig_dead"]:
                    pos_primvar = primvars_api.GetPrimvar(f"{twig_type}_position")
                    normal_primvar = primvars_api.GetPrimvar(f"{twig_type}_normal")
                    scale_primvar = primvars_api.GetPrimvar(f"{twig_type}_scale")

                    if pos_primvar and normal_primvar:
                        positions = pos_primvar.Get()
                        normals = normal_primvar.Get()
                        scales = scale_primvar.Get() if scale_primvar else [1.0] * len(positions)

                        if positions and normals:
                            placements[twig_type] = []
                            for i in range(len(positions)):
                                placements[twig_type].append({
                                    "position": tuple(positions[i]),
                                    "normal": tuple(normals[i]),
                                    "scale": scales[i] if i < len(scales) else 1.0,
                                })
    except Exception as e:
        print(f"Warning: Failed to extract twig placements: {e}")

    return placements


def create_assembly(
    tree_usd_path: Path,
    output_path: Path,
    species_name: str,
    twig_usd_paths: Optional[Dict[str, Path]] = None,
    use_skeletal_mesh: bool = False,
    skeleton_source_usd: Optional[Path] = None,
    twig_placement_source_usd: Optional[Path] = None,
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

        # Reference the tree mesh
        # CRITICAL: Always explicitly reference the /tree prim path for consistency
        # This ensures Unreal properly understands the skeleton structure
        tree_prim.GetReferences().AddReference(
            f"./{tree_usd_path.name}",
            "/tree",  # Explicit prim path (matches demo structure)
        )

        if use_skeletal_mesh:
            # For skeletal: Set skeleton relationship to embedded skeleton
            # /tree is now a SkelRoot with /tree/tree_skel skeleton
            print(f"  Adding skeletal tree with embedded skeleton...")

            # CRITICAL FIX: Override skel:* relationships with empty targets
            # USD references are compositional - we must explicitly override
            # the tree's internal skeleton bindings to prevent double-transformation
            # The Nanite Assembly's skeleton relationship is the ONLY binding that should apply

            # Create empty skel:skeleton relationship (overrides referenced tree's binding)
            tree_skel_rel = tree_prim.CreateRelationship("skel:skeleton", custom=False)
            tree_skel_rel.ClearTargets(
                removeSpec=True
            )  # removeSpec=True to block composition

            # Create empty skel:animationSource relationship (overrides referenced tree's binding)
            tree_anim_rel = tree_prim.CreateRelationship(
                "skel:animationSource", custom=False
            )
            tree_anim_rel.ClearTargets(
                removeSpec=True
            )  # removeSpec=True to block composition

            print(
                f"    [FIX] Overrode skel:* relationships with empty targets (prevents double-binding)"
            )

            # Now set the Nanite Assembly skeleton relationship (the ONLY binding)
            skeleton_rel = root_prim.CreateRelationship(
                "unreal:naniteAssembly:skeleton",
                custom=False,
            )
            skeleton_rel.AddTarget(f"/{assembly_name}/TreeMesh/TreeSkel")

            print(f"    [OK] Skeletal tree embedded via TreeMesh (mesh + skeleton)")
            print(f"    Skeleton relationship: /{assembly_name}/TreeMesh/TreeSkel")
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
            placement_source = (
                twig_placement_source_usd
                if twig_placement_source_usd
                else tree_usd_path
            )
            if twig_placement_source_usd:
                print(
                    f"    Extracting placements from: {twig_placement_source_usd.name}"
                )
            placements = _extract_twig_placements_from_usd_inline(placement_source)

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

                # Map twig types to prototype indices
                twig_type_to_proto_idx = {}
                prototype_paths = []

                for idx, (twig_type, twig_path) in enumerate(
                    sorted(remapped_twig_paths.items())
                ):
                    # VIDEO REQUIREMENT: Skeletal assemblies MUST use skeletal twigs
                    # Each twig must have its own root bone for wind/animation
                    twig_ref_path = twig_path

                    # Validate skeletal twigs for skeletal assemblies
                    if use_skeletal_mesh:
                        is_skeletal_twig = "_skeletal" in twig_ref_path.stem
                        if not is_skeletal_twig:
                            print(
                                f"    WARNING: Using static twig '{twig_ref_path.name}' in skeletal assembly!"
                            )
                            print(
                                f"      Skeletal assemblies require skeletal twigs (_skeletal.usda)"
                            )
                            print(
                                f"      This may cause Unreal import to fail or twigs not to animate"
                            )

                    if not twig_ref_path.exists():
                        print(f"    Warning: Twig mesh not found: {twig_ref_path}")
                        continue

                    # Copy twig file to output directory for relative references
                    # This ensures the assembly can find its twigs using ./filename.usda
                    import shutil

                    output_twig_path = output_path.parent / twig_ref_path.name
                    if not output_twig_path.exists():
                        shutil.copy2(twig_ref_path, output_twig_path)
                        print(f"      Copied twig to output: {output_twig_path.name}")

                    # Also copy any referenced texture files (if they exist alongside the twig)
                    twig_dir = twig_ref_path.parent
                    for texture_ext in [".png", ".jpg", ".jpeg", ".exr"]:
                        for texture_file in twig_dir.glob(f"*{texture_ext}"):
                            output_texture = output_path.parent / texture_file.name
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
                        skel_root_prim.GetReferences().AddReference(
                            f"./{twig_ref_path.name}", "/twig"
                        )

                        print(
                            f"      Prototype {proto_name}: {twig_ref_path.stem} (skeletal, Xform+SkelRoot wrapper)"
                        )
                    else:
                        # Static twigs: simpler structure
                        proto_prim = stage.DefinePrim(
                            f"/{assembly_name}/TwigPrototypes/{proto_name}"
                        )
                        proto_prim.GetReferences().AddReference(
                            f"./{twig_ref_path.name}"
                        )
                        proto_prim.SetInstanceable(True)

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
                            from growpy.core.twig import (
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

                    if use_skeletal_mesh:
                        # Apply NaniteAssemblySkelBindingAPI and set bindJoints for skeletal assembly
                        #
                        # CRITICAL: bindJoints controls INSTANCE PLACEMENT (not vertex deformation)
                        # - Tree skeleton twig mount bones (e.g., "root/joint_1/twig_0") move instances
                        # - Each twig's internal skeleton (e.g., "root") deforms its own mesh vertices
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

                        # Extract skeleton joints from tree USD (positions and paths)
                        skeleton_joints = _extract_skeleton_joints_from_usd(
                            tree_usd_path
                        )

                        # Build bindJoints array - each twig instance binds to nearest tree joint
                        # These control INSTANCE transforms, not vertex deformation
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
                                # Get twig position
                                twig_pos = placement.get("position", (0, 0, 0))

                                # Find nearest tree skeleton joint
                                if skeleton_joints:
                                    nearest_joint, distance = _find_nearest_joint(
                                        Gf.Vec3f(twig_pos[0], twig_pos[1], twig_pos[2]),
                                        skeleton_joints,
                                    )
                                    bind_joints.append(nearest_joint)
                                    bind_weights.append(1.0)
                                else:
                                    # Fallback to root if no skeleton joints found
                                    bind_joints.append("joint_0")
                                    bind_weights.append(1.0)

                        # Create bindJoints primvar with uniform variability and interpolation
                        bind_joints_attr = instancer_prim.CreateAttribute(
                            "primvars:unreal:naniteAssembly:bindJoints",
                            Sdf.ValueTypeNames.TokenArray,
                            False,  # custom (not built-in)
                            Sdf.VariabilityUniform,  # uniform variability
                        )
                        bind_joints_attr.Set(bind_joints)

                        # Set interpolation and elementSize metadata
                        bind_joints_attr.SetMetadata("interpolation", "uniform")
                        bind_joints_attr.SetMetadata("elementSize", 1)

                        # Create bindJointWeights primvar with uniform variability and interpolation
                        bind_weights_attr = instancer_prim.CreateAttribute(
                            "primvars:unreal:naniteAssembly:bindJointWeights",
                            Sdf.ValueTypeNames.FloatArray,
                            False,  # custom (not built-in)
                            Sdf.VariabilityUniform,  # uniform variability
                        )
                        bind_weights_attr.Set(bind_weights)

                        # Set interpolation and elementSize metadata
                        bind_weights_attr.SetMetadata("interpolation", "uniform")
                        bind_weights_attr.SetMetadata("elementSize", 1)

                        print(
                            f"    [OK] Bound {len(bind_joints)} twig instances to tree skeleton joints"
                        )
                        print(
                            f"    [OK] bindJoints controls instance placement (not vertex deformation)"
                        )
                    else:
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

        # Validate the assembly structure (based on video requirements)
        if use_skeletal_mesh:
            print(f"\n  Validating skeletal assembly...")
            validation_result = validate_assembly(output_path)
            if not validation_result["valid"]:
                print(f"  [WARN] Assembly validation found issues - may fail in Unreal")
                for error in validation_result["errors"]:
                    print(f"    ERROR: {error}")
            else:
                print(f"  [OK] Assembly validation passed")

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

        # Export tree using direct Grove API geometry (no coordinate transformation)
        from .tree_export import build_tree_mesh

        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_tree_path = output_path.parent / f"{output_path.stem}_tree.usda"

        # Build USD directly from Grove API data
        if not build_tree_mesh(model, temp_tree_path, up_axis="Z", triangulated=False):
            print(f"  Error: Failed to build tree USD")
            return False

        print(f"  [OK] Exported base tree: {temp_tree_path.name}")

        # Auto-lookup twigs if include_twigs=True and none provided
        if include_twigs and twig_usd_paths is None:
            try:
                from .tree_export import get_twig_usd_map_for_species

                print(f"  Looking up twigs for species: {species_name}")
                twig_usd_paths = get_twig_usd_map_for_species(
                    species_name, prefer_skeletal=use_skeletal_mesh
                )
                if twig_usd_paths:
                    print(f"  Found {len(twig_usd_paths)} twig type(s)")
                else:
                    print(f"  Warning: No twig USD files found for '{species_name}'")
            except Exception as e:
                print(f"  Warning: Failed to lookup twigs: {e}")
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
                        print(f"  Warning: Failed to copy {twig_path.name}: {e}")

            if copied_count > 0:
                print(f"  Copied {copied_count} twig USD file(s) to output directory")

        # Create Assembly USD
        success = create_assembly(
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
        # The mesh will be referenced externally via tree_mesh
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


def _extract_twig_joint_mapping_from_usd(tree_usd_path: Path) -> Dict[str, str]:
    """Extract twig joint mapping from tree USD metadata.

    The skeleton building process stores a mapping of twig placement indices
    to dedicated twig mount bone names in the USD stage metadata.

    Args:
        tree_usd_path: Path to tree USD with skeleton

    Returns:
        Dict mapping twig keys (e.g., "twig_long_0") to joint paths (e.g., "root/joint_1/twig_0")
    """
    try:
        from pxr import Usd

        stage = Usd.Stage.Open(str(tree_usd_path))
        if not stage:
            return {}

        # Extract twig joint mapping from customLayerData
        custom_data = stage.GetMetadata("customLayerData")
        if custom_data and isinstance(custom_data, dict):
            twig_joint_names = custom_data.get("twig_joint_names", {})
            if twig_joint_names:
                return twig_joint_names

        return {}

    except Exception as e:
        print(f"      Warning: Could not extract twig joint mapping: {e}")
        return {}


def _extract_skeleton_joints_from_usd(tree_usd_path: Path) -> Dict[str, Gf.Vec3d]:
    """Extract skeleton joint names and positions from tree USD file.

    Args:
        tree_usd_path: Path to tree USD with skeleton

    Returns:
        Dict mapping joint names to their world positions
    """
    try:
        from pxr import Usd, UsdSkel

        stage = Usd.Stage.Open(str(tree_usd_path))
        joints_map = {}

        # Find skeleton prims
        for prim in stage.Traverse():
            if prim.IsA(UsdSkel.Skeleton):
                skeleton = UsdSkel.Skeleton(prim)

                # Get joint names and bind transforms
                joints_attr = skeleton.GetJointsAttr()
                bind_transforms_attr = skeleton.GetBindTransformsAttr()

                if joints_attr and bind_transforms_attr:
                    joint_names = joints_attr.Get()
                    bind_transforms = bind_transforms_attr.Get()

                    # Extract position from each transform matrix
                    for i, (joint_name, transform) in enumerate(
                        zip(joint_names, bind_transforms)
                    ):
                        # Get translation component from matrix
                        position = transform.ExtractTranslation()
                        joints_map[str(joint_name)] = position

        return joints_map

    except Exception as e:
        print(f"      Warning: Could not extract skeleton joints: {e}")
        return {}


def _find_nearest_joint(
    position: Gf.Vec3f, joints: Dict[str, Gf.Vec3d]
) -> Tuple[str, float]:
    """Find the nearest skeleton joint to a given position.

    Args:
        position: Twig position as Vec3f
        joints: Dict of joint_name -> joint_position

    Returns:
        Tuple of (nearest_joint_name, distance)
    """
    if not joints:
        return ("Root", float("inf"))

    # Convert position to Vec3d for calculation
    pos_d = Gf.Vec3d(position[0], position[1], position[2])

    min_distance = float("inf")
    nearest_joint = "Root"

    for joint_name, joint_pos in joints.items():
        distance = (joint_pos - pos_d).GetLength()
        if distance < min_distance:
            min_distance = distance
            nearest_joint = joint_name

    return (nearest_joint, min_distance)
