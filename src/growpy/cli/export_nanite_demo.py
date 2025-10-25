"""Export simple Nanite Assembly demo files for Unreal Engine testing.

This script creates minimal tree and twig USD files without materials/textures,
following the working demo structure for skeletal Nanite assemblies.

Usage:
    python src/growpy/cli/export_nanite_demo.py

Output:
    data/output/nanite_demo/
    ├── demo_tree_simple.usda          # Tree mesh with skeleton (no materials)
    ├── demo_twig_simple.usda          # Twig mesh with skeleton (no materials)
    ├── demo_assembly_inline.usda       # Assembly with inline geometry
    └── demo_assembly_external.usda     # Assembly with external references
"""

import sys
from pathlib import Path

# Import bpy and expose bundled USD
try:
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel

    USD_AVAILABLE = True
except ImportError:
    try:
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel

        USD_AVAILABLE = True
    except ImportError:
        print("Error: USD Python module not available")
        print("Please run this script with Blender's Python or install USD")
        USD_AVAILABLE = False
        sys.exit(1)


def export_simple_tree_with_skeleton(output_path: Path) -> bool:
    """Export a simple tree mesh with skeleton, no materials.

    Creates a SkelRoot USD file following the working demo pattern:
    - SkelRoot "Tree"
      - Skeleton "TreeSkel" with joints
      - Mesh "Trunk" with skeletal binding

    Args:
        output_path: Where to save the USD file

    Returns:
        bool: Success status
    """
    try:

        # Create stage
        stage = Usd.Stage.CreateNew(str(output_path))
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        stage.SetMetadata("metersPerUnit", 1.0)
        stage.SetMetadata("defaultPrim", "Tree")

        # Create SkelRoot
        tree_path = Sdf.Path("/Tree")
        skel_root = UsdSkel.Root.Define(stage, tree_path)

        # Create Skeleton with 3 joints (root + 2 branches)
        skel_path = tree_path.AppendChild("TreeSkel")
        skeleton = UsdSkel.Skeleton.Define(stage, skel_path)

        joints = ["root", "joint_1", "joint_2"]
        skeleton.CreateJointsAttr(joints)

        # Define bind transforms (identity matrices at different heights)
        bind_transforms = [
            Gf.Matrix4d(1.0).SetTranslateOnly(Gf.Vec3d(0, 0, 0)),  # root at origin
            Gf.Matrix4d(1.0).SetTranslateOnly(Gf.Vec3d(0, 0, 1)),  # joint_1 at 1m
            Gf.Matrix4d(1.0).SetTranslateOnly(Gf.Vec3d(0, 0, 2)),  # joint_2 at 2m
        ]
        skeleton.CreateBindTransformsAttr(bind_transforms)
        skeleton.CreateRestTransformsAttr(bind_transforms)

        # Create Mesh with skeletal binding
        mesh_path = tree_path.AppendChild("Trunk")
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)

        # Apply SkelBindingAPI
        binding_api = UsdSkel.BindingAPI.Apply(mesh.GetPrim())
        binding_api.CreateSkeletonRel().SetTargets([skel_path])

        # Simple cylinder mesh (5 quads forming a trunk)
        # 3 sections, 4 vertices each = 12 vertices
        points = [
            Gf.Vec3f(-0.1, -0.1, 0),
            Gf.Vec3f(0.1, -0.1, 0),
            Gf.Vec3f(-0.1, 0.1, 0),
            Gf.Vec3f(0.1, 0.1, 0),
            Gf.Vec3f(-0.1, -0.1, 1),
            Gf.Vec3f(0.1, -0.1, 1),
            Gf.Vec3f(-0.1, 0.1, 1),
            Gf.Vec3f(0.1, 0.1, 1),
            Gf.Vec3f(-0.1, -0.1, 2),
            Gf.Vec3f(0.1, -0.1, 2),
            Gf.Vec3f(-0.1, 0.1, 2),
            Gf.Vec3f(0.1, 0.1, 2),
        ]

        face_vertex_counts = [4, 4, 4, 4, 4]
        face_vertex_indices = [
            0,
            1,
            3,
            2,  # Bottom quad
            1,
            4,
            5,
            3,  # Middle-bottom
            4,
            6,
            7,
            5,  # Middle-top
            6,
            8,
            9,
            7,  # Top-middle
            8,
            10,
            11,
            9,  # Top quad
        ]

        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
        mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)
        mesh.CreateDoubleSidedAttr(True)

        # Add normals (simple face-varying)
        normals = [Gf.Vec3f(0, 0, -1)] * 20  # 5 quads × 4 vertices
        mesh.CreateNormalsAttr(normals)
        mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)

        # Add part primvar
        primvars_api = UsdGeom.PrimvarsAPI(mesh)
        part_primvar = primvars_api.CreatePrimvar(
            "part", Sdf.ValueTypeNames.Token, UsdGeom.Tokens.uniform
        )
        part_primvar.Set("trunk")

        # Skeletal binding - bind vertices to joints
        # Bottom section (verts 0-7) → root and joint_1
        # Top section (verts 8-11) → joint_2
        joint_indices = [
            0,
            0,
            0,
            0,  # Bottom 4 verts → root
            0,
            0,
            0,
            0,  # Next 4 verts → root
            1,
            1,
            1,
            1,  # Middle 4 verts → joint_1
            1,
            1,
            1,
            1,  # Next 4 verts → joint_1
            2,
            2,
            2,
            2,  # Top 4 verts → joint_2
        ]
        joint_weights = [1.0] * 20

        joint_indices_primvar = primvars_api.CreatePrimvar(
            "skel:jointIndices",
            Sdf.ValueTypeNames.IntArray,
            UsdGeom.Tokens.vertex,
        )
        joint_indices_primvar.Set(joint_indices)
        joint_indices_primvar.SetElementSize(1)

        joint_weights_primvar = primvars_api.CreatePrimvar(
            "skel:jointWeights",
            Sdf.ValueTypeNames.FloatArray,
            UsdGeom.Tokens.vertex,
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(1)

        stage.Save()
        print(f"✓ Created simple tree: {output_path.name}")
        return True

    except Exception as e:
        print(f"Error creating simple tree: {e}")
        import traceback

        traceback.print_exc()
        return False


def export_simple_twig_with_skeleton(output_path: Path) -> bool:
    """Export a simple twig/leaf mesh with skeleton, no materials.

    Creates a SkelRoot USD file following the working demo pattern:
    - SkelRoot "Twig"
      - Skeleton "Skel" with single root joint
      - Mesh "Leaf" with skeletal binding

    Args:
        output_path: Where to save the USD file

    Returns:
        bool: Success status
    """
    try:

        # Create stage
        stage = Usd.Stage.CreateNew(str(output_path))
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        stage.SetMetadata("metersPerUnit", 1.0)
        stage.SetMetadata("defaultPrim", "Twig")

        # Create SkelRoot
        twig_path = Sdf.Path("/Twig")
        skel_root = UsdSkel.Root.Define(stage, twig_path)

        # Create Skeleton with single root joint
        skel_path = twig_path.AppendChild("Skel")
        skeleton = UsdSkel.Skeleton.Define(stage, skel_path)

        skeleton.CreateJointsAttr(["root"])

        # Identity matrix at origin
        identity = Gf.Matrix4d(1.0)
        skeleton.CreateBindTransformsAttr([identity])
        skeleton.CreateRestTransformsAttr([identity])

        # Create Mesh
        mesh_path = twig_path.AppendChild("Leaf")
        mesh = UsdGeom.Mesh.Define(stage, mesh_path)

        # Apply SkelBindingAPI
        binding_api = UsdSkel.BindingAPI.Apply(mesh.GetPrim())
        binding_api.CreateSkeletonRel().SetTargets([skel_path])

        # Simple quad mesh (leaf)
        points = [
            Gf.Vec3f(-0.1, -0.1, 0),
            Gf.Vec3f(0.1, -0.1, 0),
            Gf.Vec3f(0.1, 0.1, 0),
            Gf.Vec3f(-0.1, 0.1, 0),
        ]

        mesh.CreatePointsAttr(points)
        mesh.CreateFaceVertexCountsAttr([4])
        mesh.CreateFaceVertexIndicesAttr([0, 1, 2, 3])
        mesh.CreateDoubleSidedAttr(True)

        # Add normals
        normals = [Gf.Vec3f(0, 0, 1)] * 4
        mesh.CreateNormalsAttr(normals)
        mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)

        # Add part primvar
        primvars_api = UsdGeom.PrimvarsAPI(mesh)
        part_primvar = primvars_api.CreatePrimvar(
            "part", Sdf.ValueTypeNames.Token, UsdGeom.Tokens.uniform
        )
        part_primvar.Set("leaf")

        # Skeletal binding - all vertices to root joint
        joint_indices_primvar = primvars_api.CreatePrimvar(
            "skel:jointIndices",
            Sdf.ValueTypeNames.IntArray,
            UsdGeom.Tokens.vertex,
        )
        joint_indices_primvar.Set([0, 0, 0, 0])
        joint_indices_primvar.SetElementSize(1)

        joint_weights_primvar = primvars_api.CreatePrimvar(
            "skel:jointWeights",
            Sdf.ValueTypeNames.FloatArray,
            UsdGeom.Tokens.vertex,
        )
        joint_weights_primvar.Set([1.0, 1.0, 1.0, 1.0])
        joint_weights_primvar.SetElementSize(1)

        stage.Save()
        print(f"✓ Created simple twig: {output_path.name}")
        return True

    except Exception as e:
        print(f"Error creating simple twig: {e}")
        import traceback

        traceback.print_exc()
        return False


def create_inline_assembly(tree_path: Path, twig_path: Path, output_path: Path) -> bool:
    """Create Nanite Assembly with inline geometry (no external references).

    This matches the working demo_assembly_skel.usda structure.

    Args:
        tree_path: Path to tree USD (used to copy structure)
        twig_path: Path to twig USD (used to copy structure)
        output_path: Where to save assembly

    Returns:
        bool: Success status
    """
    try:

        # For inline assembly, we'll directly embed the geometry
        # This matches demo_assembly_skel.usda pattern

        stage = Usd.Stage.CreateNew(str(output_path))
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        stage.SetMetadata("metersPerUnit", 1.0)
        stage.SetMetadata("defaultPrim", "DemoAssembly")

        # Create root Xform with Nanite Assembly Root API
        root_path = Sdf.Path("/DemoAssembly")
        root = UsdGeom.Xform.Define(stage, root_path)

        # Apply API schemas
        api_schemas = root.GetPrim().GetMetadata("apiSchemas") or Sdf.TokenListOp()
        if not isinstance(api_schemas, Sdf.TokenListOp):
            api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["NaniteAssemblyRootAPI", "GeomModelAPI"]
        root.GetPrim().SetMetadata("apiSchemas", api_schemas)
        root.GetPrim().SetMetadata("kind", "assembly")

        # Set mesh type
        root.GetPrim().CreateAttribute(
            "unreal:naniteAssembly:meshType",
            Sdf.ValueTypeNames.Token,
            custom=False,
            variability=Sdf.VariabilityUniform,
        ).Set("skeletalMesh")

        # Set skeleton relationship
        root.GetPrim().CreateRelationship(
            "unreal:naniteAssembly:skeleton", custom=False
        ).SetTargets([Sdf.Path("/DemoAssembly/TreeMesh/TreeSkel")])

        # Embed tree geometry (copy from tree_path)
        tree_stage = Usd.Stage.Open(str(tree_path))
        tree_skel_root = tree_stage.GetPrimAtPath("/Tree")

        tree_dest_path = root_path.AppendChild("TreeMesh")
        UsdGeom.XformCommonAPI(stage.DefinePrim(tree_dest_path, "SkelRoot"))

        # Copy tree skeleton and mesh
        for prim in tree_skel_root.GetChildren():
            dest_prim_path = tree_dest_path.AppendChild(prim.GetName())
            stage.DefinePrim(dest_prim_path, prim.GetTypeName())
            dest_prim = stage.GetPrimAtPath(dest_prim_path)

            # Copy apiSchemas metadata if present
            api_schemas = prim.GetMetadata("apiSchemas")
            if api_schemas:
                dest_prim.SetMetadata("apiSchemas", api_schemas)

            # Copy all attributes and relationships (only explicitly authored ones)
            for attr in prim.GetAttributes():
                # Skip extent attribute (causes type mismatch errors)
                if attr.GetName() == "extent":
                    continue

                # Only copy explicitly authored attributes (skip defaults)
                if not attr.HasAuthoredValue():
                    continue

                value = attr.Get()
                if value is None:
                    continue

                # Get variability from source
                variability = attr.GetMetadata("variability")

                dest_attr = dest_prim.CreateAttribute(
                    attr.GetName(),
                    attr.GetTypeName(),
                    custom=False,  # Don't mark as custom
                    variability=variability if variability else Sdf.VariabilityVarying,
                )
                dest_attr.Set(value)

                # Copy metadata
                if attr.GetMetadata("interpolation"):
                    dest_attr.SetMetadata(
                        "interpolation", attr.GetMetadata("interpolation")
                    )
                if attr.GetMetadata("elementSize"):
                    dest_attr.SetMetadata(
                        "elementSize", attr.GetMetadata("elementSize")
                    )

            for rel in prim.GetRelationships():
                # Only copy explicitly authored relationships
                if not rel.IsAuthored():
                    continue

                dest_rel = dest_prim.CreateRelationship(rel.GetName(), custom=False)
                # Update skeleton relationship path
                targets = rel.GetTargets()
                new_targets = []
                for target in targets:
                    # Remap /Tree/ paths to /DemoAssembly/TreeMesh/
                    new_target = str(target).replace(
                        "/Tree/", "/DemoAssembly/TreeMesh/"
                    )
                    new_targets.append(Sdf.Path(new_target))
                dest_rel.SetTargets(new_targets)

        # Create twig prototypes scope
        prototypes_path = root_path.AppendChild("TwigPrototypes")
        UsdGeom.Scope.Define(stage, prototypes_path)

        # Create twig prototype Xform
        twig_xform_path = prototypes_path.AppendChild("twig")
        twig_xform = UsdGeom.Xform.Define(stage, twig_xform_path)
        twig_xform.GetPrim().SetInstanceable(True)

        # Embed twig SkelRoot
        twig_stage = Usd.Stage.Open(str(twig_path))
        twig_skel_root = twig_stage.GetPrimAtPath("/Twig")

        twig_skel_dest = twig_xform_path.AppendChild("TwigSkelRoot")
        stage.DefinePrim(twig_skel_dest, "SkelRoot")

        # Copy twig skeleton and mesh
        for prim in twig_skel_root.GetChildren():
            dest_prim_path = twig_skel_dest.AppendChild(prim.GetName())
            stage.DefinePrim(dest_prim_path, prim.GetTypeName())
            dest_prim = stage.GetPrimAtPath(dest_prim_path)

            # Copy apiSchemas metadata if present
            api_schemas = prim.GetMetadata("apiSchemas")
            if api_schemas:
                dest_prim.SetMetadata("apiSchemas", api_schemas)

            for attr in prim.GetAttributes():
                # Skip extent attribute
                if attr.GetName() == "extent":
                    continue

                # Only copy explicitly authored attributes (skip defaults)
                if not attr.HasAuthoredValue():
                    continue

                value = attr.Get()
                if value is None:
                    continue

                # Get variability from source
                variability = attr.GetMetadata("variability")

                dest_attr = dest_prim.CreateAttribute(
                    attr.GetName(),
                    attr.GetTypeName(),
                    custom=False,  # Don't mark as custom
                    variability=variability if variability else Sdf.VariabilityVarying,
                )
                dest_attr.Set(value)

                if attr.GetMetadata("interpolation"):
                    dest_attr.SetMetadata(
                        "interpolation", attr.GetMetadata("interpolation")
                    )
                if attr.GetMetadata("elementSize"):
                    dest_attr.SetMetadata(
                        "elementSize", attr.GetMetadata("elementSize")
                    )

            for rel in prim.GetRelationships():
                # Only copy explicitly authored relationships
                if not rel.IsAuthored():
                    continue

                dest_rel = dest_prim.CreateRelationship(rel.GetName(), custom=False)
                targets = rel.GetTargets()
                new_targets = []
                for target in targets:
                    new_target = str(target).replace(
                        "/Twig/", "/DemoAssembly/TwigPrototypes/twig/TwigSkelRoot/"
                    )
                    new_targets.append(Sdf.Path(new_target))
                dest_rel.SetTargets(new_targets)

        # Create PointInstancer
        instancer_path = root_path.AppendChild("TwigInstances")
        instancer = UsdGeom.PointInstancer.Define(stage, instancer_path)

        # Apply API schema
        instancer_api_schemas = Sdf.TokenListOp()
        instancer_api_schemas.prependedItems = ["NaniteAssemblySkelBindingAPI"]
        instancer.GetPrim().SetMetadata("apiSchemas", instancer_api_schemas)

        # Set instance data
        instancer.CreatePositionsAttr(
            [
                Gf.Vec3f(0.5, 0.5, 1.0),
                Gf.Vec3f(-0.5, 0.5, 1.5),
            ]
        )
        instancer.CreateOrientationsAttr(
            [
                Gf.Quath(1, 0, 0, 0),
                Gf.Quath(1, 0, 0, 0),
            ]
        )
        instancer.CreateScalesAttr(
            [
                Gf.Vec3f(1, 1, 1),
                Gf.Vec3f(1, 1, 1),
            ]
        )
        instancer.CreateProtoIndicesAttr([0, 0])
        instancer.CreatePrototypesRel().SetTargets([twig_xform_path])

        # Add bind joints primvar
        primvars_api = UsdGeom.PrimvarsAPI(instancer)
        bind_joints = primvars_api.CreatePrimvar(
            "unreal:naniteAssembly:bindJoints",
            Sdf.ValueTypeNames.TokenArray,
            UsdGeom.Tokens.uniform,
        )
        bind_joints.Set(["joint_1", "joint_2"])
        bind_joints.SetElementSize(1)

        bind_weights = primvars_api.CreatePrimvar(
            "unreal:naniteAssembly:bindJointWeights",
            Sdf.ValueTypeNames.FloatArray,
            UsdGeom.Tokens.uniform,
        )
        bind_weights.Set([1.0, 1.0])
        bind_weights.SetElementSize(1)

        stage.Save()
        print(f"✓ Created inline assembly: {output_path.name}")
        return True

    except Exception as e:
        print(f"Error creating inline assembly: {e}")
        import traceback

        traceback.print_exc()
        return False


def create_external_ref_assembly(
    tree_path: Path, twig_path: Path, output_path: Path
) -> bool:
    """Create Nanite Assembly with external references.

    This matches the demo_assembly_external_ref.usda structure.

    Args:
        tree_path: Path to tree USD to reference
        twig_path: Path to twig USD to reference
        output_path: Where to save assembly

    Returns:
        bool: Success status
    """
    try:

        stage = Usd.Stage.CreateNew(str(output_path))
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        stage.SetMetadata("metersPerUnit", 1.0)
        stage.SetMetadata("defaultPrim", "DemoAssemblyExternal")

        # Create root Xform
        root_path = Sdf.Path("/DemoAssemblyExternal")
        root = UsdGeom.Xform.Define(stage, root_path)

        # Apply API schemas
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["NaniteAssemblyRootAPI", "GeomModelAPI"]
        root.GetPrim().SetMetadata("apiSchemas", api_schemas)
        root.GetPrim().SetMetadata("kind", "assembly")

        # Set mesh type
        root.GetPrim().CreateAttribute(
            "unreal:naniteAssembly:meshType",
            Sdf.ValueTypeNames.Token,
            custom=False,
            variability=Sdf.VariabilityUniform,
        ).Set("skeletalMesh")

        # Set skeleton relationship
        root.GetPrim().CreateRelationship(
            "unreal:naniteAssembly:skeleton", custom=False
        ).SetTargets([Sdf.Path("/DemoAssemblyExternal/TreeMesh/TreeSkel")])

        # Reference tree
        tree_prim_path = root_path.AppendChild("TreeMesh")
        tree_prim = stage.DefinePrim(tree_prim_path, "SkelRoot")
        tree_prim.GetReferences().AddReference(f"./{tree_path.name}", "/Tree")

        # Create twig prototypes
        prototypes_path = root_path.AppendChild("TwigPrototypes")
        UsdGeom.Scope.Define(stage, prototypes_path)

        twig_xform_path = prototypes_path.AppendChild("twig")
        twig_xform = UsdGeom.Xform.Define(stage, twig_xform_path)
        twig_xform.GetPrim().SetInstanceable(True)

        # Reference twig
        twig_skel_path = twig_xform_path.AppendChild("TwigSkelRoot")
        twig_skel_prim = stage.DefinePrim(twig_skel_path, "SkelRoot")
        twig_skel_prim.GetReferences().AddReference(f"./{twig_path.name}", "/Twig")

        # Create PointInstancer
        instancer_path = root_path.AppendChild("TwigInstances")
        instancer = UsdGeom.PointInstancer.Define(stage, instancer_path)

        # Apply API schema
        instancer_api_schemas = Sdf.TokenListOp()
        instancer_api_schemas.prependedItems = ["NaniteAssemblySkelBindingAPI"]
        instancer.GetPrim().SetMetadata("apiSchemas", instancer_api_schemas)

        # Set instance data
        instancer.CreatePositionsAttr(
            [
                Gf.Vec3f(0.5, 0.5, 1.0),
                Gf.Vec3f(-0.5, 0.5, 1.5),
            ]
        )
        instancer.CreateOrientationsAttr(
            [
                Gf.Quath(1, 0, 0, 0),
                Gf.Quath(1, 0, 0, 0),
            ]
        )
        instancer.CreateScalesAttr(
            [
                Gf.Vec3f(1, 1, 1),
                Gf.Vec3f(1, 1, 1),
            ]
        )
        instancer.CreateProtoIndicesAttr([0, 0])
        instancer.CreatePrototypesRel().SetTargets([twig_xform_path])

        # Add bind joints primvar
        primvars_api = UsdGeom.PrimvarsAPI(instancer)
        bind_joints = primvars_api.CreatePrimvar(
            "unreal:naniteAssembly:bindJoints",
            Sdf.ValueTypeNames.TokenArray,
            UsdGeom.Tokens.uniform,
        )
        bind_joints.Set(["joint_1", "joint_2"])
        bind_joints.SetElementSize(1)

        bind_weights = primvars_api.CreatePrimvar(
            "unreal:naniteAssembly:bindJointWeights",
            Sdf.ValueTypeNames.FloatArray,
            UsdGeom.Tokens.uniform,
        )
        bind_weights.Set([1.0, 1.0])
        bind_weights.SetElementSize(1)

        stage.Save()
        print(f"✓ Created external ref assembly: {output_path.name}")
        return True

    except Exception as e:
        print(f"Error creating external ref assembly: {e}")
        import traceback

        traceback.print_exc()
        return False


def main():
    """Export all demo files."""
    print("=" * 60)
    print("Exporting Nanite Assembly Demo Files")
    print("=" * 60)

    # Setup output directory
    output_dir = Path("data/output/nanite_demo")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nOutput directory: {output_dir}\n")

    # Export simple tree with skeleton
    tree_path = output_dir / "demo_tree_simple.usda"
    if not export_simple_tree_with_skeleton(tree_path):
        print("Failed to export tree")
        return 1

    # Export simple twig with skeleton
    twig_path = output_dir / "demo_twig_simple.usda"
    if not export_simple_twig_with_skeleton(twig_path):
        print("Failed to export twig")
        return 1

    # Create inline assembly
    inline_path = output_dir / "demo_assembly_inline.usda"
    if not create_inline_assembly(tree_path, twig_path, inline_path):
        print("Failed to create inline assembly")
        return 1

    # Create external reference assembly
    external_path = output_dir / "demo_assembly_external.usda"
    if not create_external_ref_assembly(tree_path, twig_path, external_path):
        print("Failed to create external ref assembly")
        return 1

    print("\n" + "=" * 60)
    print("Export Complete!")
    print("=" * 60)
    print(f"\nGenerated files in: {output_dir}")
    print("\nImport in Unreal Engine 5.7+:")
    print(f"  1. {inline_path.name} - Inline geometry (self-contained)")
    print(f"  2. {external_path.name} - External references (modular)")
    print("\nBoth should work as skeletal Nanite assemblies with twigs!")

    return 0


if __name__ == "__main__":
    sys.exit(main())
