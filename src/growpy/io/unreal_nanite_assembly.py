"""Unreal Engine Nanite Assembly USD export.

This module creates USD files following Unreal Engine 5.7+ Nanite Assembly schema.
It wraps Grove's native USD export with proper Unreal API schemas for optimal import.

Based on:
- https://www.youtube.com/watch?v=-ZGWblVF8Qk
- https://www.artstation.com/blogs/liamwedge/mpygZ/nanite-assemblies-in-unreal-engine-57-from-dcc-to-ue-import
"""

from pathlib import Path
from typing import Any, Dict, Optional


def create_nanite_assembly_usd(
    tree_usd_path: Path,
    output_path: Path,
    species_name: str,
    twig_usd_paths: Optional[Dict[str, Path]] = None,
    use_skeletal_mesh: bool = False,
    skeleton_path: Optional[Path] = None,
    tree_fbx_path: Optional[Path] = None,
    twig_fbx_paths: Optional[Dict[str, Path]] = None,
) -> bool:
    """Create a Nanite Assembly USD file for Unreal Engine import.

    This creates a USD Assembly following Unreal's schema with proper API schemas:
    - NaniteAssemblyRootAPI on the root Xform
    - NaniteAssemblyExternalRefAPI on child meshes (references USD or FBX)
    - PointInstancer for twig instances

    When FBX paths are provided, creates a skeletal mesh assembly that references
    FBX files instead of USD files for better animation support in Unreal.

    Args:
        tree_usd_path: Path to base tree USD file (from Grove export)
        output_path: Output path for Nanite Assembly USDA
        species_name: Tree species name
        twig_usd_paths: Optional dict mapping twig types to USD paths
        use_skeletal_mesh: Whether to use skeletal mesh type
        skeleton_path: Path to skeleton USD (if using skeletal mesh)
        tree_fbx_path: Optional path to tree FBX file (skeletal mesh)
        twig_fbx_paths: Optional dict mapping twig types to FBX paths

    Returns:
        bool: Success status
    """
    try:
        from pxr import Gf, Sdf, Usd, UsdGeom

        # Create new stage
        stage = Usd.Stage.CreateNew(str(output_path))

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

        # Reference the tree mesh (FBX for skeletal, USD for static)
        if use_skeletal_mesh and tree_fbx_path and tree_fbx_path.exists():
            tree_prim.GetReferences().AddReference(str(tree_fbx_path.resolve()))
            tree_ref_name = tree_fbx_path.name
        else:
            tree_prim.GetReferences().AddReference(str(tree_usd_path.resolve()))
            tree_ref_name = tree_usd_path.name

        print(f"  ✓ Created Nanite Assembly root: {assembly_name}")
        print(f"    Mesh type: {mesh_type}")
        print(f"    Tree reference: {tree_ref_name}")

        # Add twigs if provided
        if twig_usd_paths:
            print(f"  Adding twigs as PointInstancer...")

            # Extract twig placements from tree USD
            from .twig_placement import extract_twig_placements_from_usd

            placements = extract_twig_placements_from_usd(tree_usd_path)

            if placements and any(placements.values()):
                # Create prototypes group
                prototypes_group = stage.DefinePrim(
                    f"/{assembly_name}/TwigPrototypes", "Scope"
                )

                # Map twig types to prototype indices
                twig_type_to_proto_idx = {}
                prototype_paths = []

                for idx, (twig_type, twig_path) in enumerate(
                    sorted(twig_usd_paths.items())
                ):
                    # Use FBX path if available (for skeletal mesh), otherwise USD
                    if (
                        use_skeletal_mesh
                        and twig_fbx_paths
                        and twig_type in twig_fbx_paths
                    ):
                        twig_ref_path = twig_fbx_paths[twig_type]
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

                    # Reference twig mesh (FBX or USD)
                    proto_prim.GetReferences().AddReference(
                        str(twig_ref_path.resolve())
                    )

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
                                convert_blender_normal_to_ue,
                                convert_blender_to_ue_coords,
                                normal_to_rotation_matrix,
                                rotation_matrix_to_quaternion,
                            )

                            pos = placement["position"]
                            normal = placement["normal"]

                            # Convert to Unreal Engine coordinates
                            ue_pos = convert_blender_to_ue_coords(pos)
                            ue_normal = convert_blender_normal_to_ue(normal)

                            # Create rotation matrix from UE normal
                            rot_matrix = normal_to_rotation_matrix(ue_normal)

                            # Convert to quaternion
                            quat = rotation_matrix_to_quaternion(rot_matrix)

                            # Add to arrays
                            all_positions.append(
                                Gf.Vec3f(ue_pos[0], ue_pos[1], ue_pos[2])
                            )
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

                    print(
                        f"    ✓ Added {len(all_positions)} twig instances ({len(prototype_paths)} types)"
                    )

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
