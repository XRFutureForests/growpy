#!/usr/bin/env python3
"""Export clean skeletal meshes matching demo structure.

This script generates clean USD files without materials/textures for testing
and demonstration purposes. The output matches the structure of the working
demo files exactly.

Usage:
    python export_clean_demo.py

Output:
    data/output/clean_demo/
        - tree_clean.usda - Tree with skeleton, no materials
        - twig_clean.usda - Twig with skeleton, no materials
        - assembly_clean.usda - Nanite assembly referencing the above
"""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

# Import USD builder
from growpy.io.unreal_nanite_assembly import create_nanite_assembly_usd


def create_clean_tree(output_dir: Path) -> Path:
    """Create a simple tree mesh with skeleton (no materials).

    This creates a tree matching the demo structure by copying and adapting
    the export_nanite_demo.py approach.
    """
    print("Creating clean tree mesh...")

    # Import here to avoid issues
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

    tree_path = output_dir / "tree_clean.usda"
    stage = Usd.Stage.CreateNew(str(tree_path))

    # Set metadata
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1.0)
    stage.SetMetadata("defaultPrim", "Tree")

    # Create SkelRoot
    skel_root = UsdSkel.Root.Define(stage, "/Tree")

    # Create skeleton with 3 joints for tree trunk
    skel = UsdSkel.Skeleton.Define(stage, "/Tree/TreeSkel")

    joint_tokens = ["root", "joint_1", "joint_2"]

    # Bind transforms (world space)
    bind_transforms = [
        Gf.Matrix4d(1.0).SetTranslateOnly(Gf.Vec3d(0, 0, 0)),
        Gf.Matrix4d(1.0).SetTranslateOnly(Gf.Vec3d(0, 0, 1)),
        Gf.Matrix4d(1.0).SetTranslateOnly(Gf.Vec3d(0, 0, 2)),
    ]

    # Rest transforms (local space)
    rest_transforms = [
        Gf.Matrix4d(1.0).SetTranslateOnly(Gf.Vec3d(0, 0, 0)),
        Gf.Matrix4d(1.0).SetTranslateOnly(Gf.Vec3d(0, 0, 1)),
        Gf.Matrix4d(1.0).SetTranslateOnly(Gf.Vec3d(0, 0, 1)),
    ]

    skel.CreateJointsAttr(joint_tokens)
    skel.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_transforms))
    skel.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_transforms))

    # Create mesh (simple trunk - box extruded in Z)
    mesh = UsdGeom.Mesh.Define(stage, "/Tree/Trunk")

    # Manually add SkelBindingAPI to apiSchemas
    mesh_prim = mesh.GetPrim()
    api_schemas = Sdf.TokenListOp()
    api_schemas.prependedItems = ["SkelBindingAPI"]
    mesh_prim.SetMetadata("apiSchemas", api_schemas)

    # Simple box trunk (3 segments for 3 joints)
    points = [
        # Bottom segment (joint 0)
        Gf.Vec3f(-0.1, -0.1, 0),
        Gf.Vec3f(0.1, -0.1, 0),
        Gf.Vec3f(-0.1, 0.1, 0),
        Gf.Vec3f(0.1, 0.1, 0),
        # Middle segment (joint 1)
        Gf.Vec3f(-0.1, -0.1, 1),
        Gf.Vec3f(0.1, -0.1, 1),
        Gf.Vec3f(-0.1, 0.1, 1),
        Gf.Vec3f(0.1, 0.1, 1),
        # Top segment (joint 2)
        Gf.Vec3f(-0.1, -0.1, 2),
        Gf.Vec3f(0.1, -0.1, 2),
        Gf.Vec3f(-0.1, 0.1, 2),
        Gf.Vec3f(0.1, 0.1, 2),
    ]

    mesh.CreatePointsAttr(points)
    mesh.CreateFaceVertexCountsAttr([4, 4, 4, 4, 4])
    mesh.CreateFaceVertexIndicesAttr(
        [0, 1, 3, 2, 1, 4, 5, 3, 4, 6, 7, 5, 6, 8, 9, 7, 8, 10, 11, 9]
    )
    mesh.CreateDoubleSidedAttr(True)

    # Add normals
    normals = [Gf.Vec3f(0, 0, -1)] * 20
    normals_attr = mesh.CreateNormalsAttr()
    normals_attr.Set(normals)
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)

    # Add part primvar
    primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)
    part_primvar = primvars_api.CreatePrimvar(
        "part",
        Sdf.ValueTypeNames.Token,
        UsdGeom.Tokens.uniform,
    )
    part_primvar.Set("trunk")

    # Create skeleton relationship
    skel_rel = mesh_prim.CreateRelationship("skel:skeleton", custom=False)
    skel_rel.SetTargets(["/Tree/TreeSkel"])

    # Add skinning - each segment bound to corresponding joint
    joint_indices = [
        0,
        0,
        0,
        0,  # Bottom 4 verts -> joint 0
        0,
        0,
        0,
        0,  # Middle bottom 4 -> joint 0
        1,
        1,
        1,
        1,  # Middle top 4 -> joint 1
        1,
        1,
        1,
        1,  # Top bottom 4 -> joint 1
        2,
        2,
        2,
        2,  # Top 4 verts -> joint 2
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
    print(f"  ✓ Created: {tree_path.name}")
    return tree_path


def create_clean_twig(output_dir: Path) -> Path:
    """Create a simple twig mesh with skeleton (no materials)."""
    print("Creating clean twig mesh...")

    # Create simple twig manually (plane with 4 vertices)
    from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

    twig_path = output_dir / "twig_clean.usda"
    stage = Usd.Stage.CreateNew(str(twig_path))

    # Set metadata
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    stage.SetMetadata("metersPerUnit", 1.0)
    stage.SetMetadata("defaultPrim", "Twig")

    # Create SkelRoot
    skel_root = UsdSkel.Root.Define(stage, "/Twig")

    # Create skeleton
    skel = UsdSkel.Skeleton.Define(stage, "/Twig/TwigSkel")
    skel.CreateJointsAttr(["root"])

    bind_transform = Gf.Matrix4d(1.0)
    bind_transform.SetTranslateOnly(Gf.Vec3d(0, 0, 0))
    skel.CreateBindTransformsAttr(Vt.Matrix4dArray([bind_transform]))
    skel.CreateRestTransformsAttr(Vt.Matrix4dArray([bind_transform]))

    # Create mesh (simple quad)
    mesh = UsdGeom.Mesh.Define(stage, "/Twig/TwigMesh")

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
    normals_attr = mesh.CreateNormalsAttr()
    normals_attr.Set(normals)
    mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)

    # Add part primvar
    primvars_api = UsdGeom.PrimvarsAPI(mesh.GetPrim())
    part_primvar = primvars_api.CreatePrimvar(
        "part",
        Sdf.ValueTypeNames.Token,
        UsdGeom.Tokens.uniform,
    )
    part_primvar.Set("leaf")

    # Bind mesh to skeleton using clean export style
    mesh_prim = mesh.GetPrim()

    # Manually add SkelBindingAPI to apiSchemas
    api_schemas = Sdf.TokenListOp()
    api_schemas.prependedItems = ["SkelBindingAPI"]
    mesh_prim.SetMetadata("apiSchemas", api_schemas)

    # Create skeleton relationship
    skel_rel = mesh_prim.CreateRelationship("skel:skeleton", custom=False)
    skel_rel.SetTargets(["/Twig/TwigSkel"])

    # Add skinning
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
    print(f"  ✓ Created: {twig_path.name}")
    return twig_path


def create_clean_assembly(tree_path: Path, twig_path: Path, output_dir: Path) -> Path:
    """Create Nanite assembly referencing clean meshes."""
    print("Creating clean Nanite assembly...")

    assembly_path = output_dir / "assembly_clean.usda"

    success = create_nanite_assembly_usd(
        tree_usd_path=tree_path,
        output_path=assembly_path,
        species_name="CleanDemo",
        twig_usd_paths={"twig": twig_path},
        use_skeletal_mesh=True,
    )

    if success:
        print(f"  ✓ Created: {assembly_path.name}")
        return assembly_path
    else:
        print("ERROR: Failed to create assembly")
        return None


def main():
    print("=" * 60)
    print("Exporting Clean Demo Files (No Materials/Textures)")
    print("=" * 60)
    print()

    # Create output directory
    output_dir = Path("data/output/clean_demo")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create components
    tree_path = create_clean_tree(output_dir)
    if not tree_path:
        return 1

    twig_path = create_clean_twig(output_dir)
    if not twig_path:
        return 1

    assembly_path = create_clean_assembly(tree_path, twig_path, output_dir)
    if not assembly_path:
        return 1

    print()
    print("=" * 60)
    print("Clean Demo Export Complete!")
    print("=" * 60)
    print()
    print(f"Output directory: {output_dir}")
    print()
    print("Files created:")
    print(f"  - {tree_path.name} - Tree with skeleton (no materials)")
    print(f"  - {twig_path.name} - Twig with skeleton (no materials)")
    print(f"  - {assembly_path.name} - Nanite assembly")
    print()
    print("These files match the demo structure exactly and can be")
    print("compared with the working demo files in data/test_files/")

    return 0


if __name__ == "__main__":
    sys.exit(main())
