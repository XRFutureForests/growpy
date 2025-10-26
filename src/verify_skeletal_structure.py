#!/usr/bin/env python3
"""Verify skeletal USD structure matches working assembly example."""

from pathlib import Path

# Expose Blender's bundled USD module
try:
    import bpy
    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
except ImportError:
    pass

from pxr import Usd, UsdSkel, UsdGeom, Sdf


def verify_twig_structure(usd_path: Path) -> dict:
    """Verify skeletal twig USD structure.

    Expected structure from working example:
        /Twig (SkelRoot)
            /Skel (Skeleton)
                joints = ["root"]
                bindTransforms, restTransforms
            /Mesh (Mesh with SkelBindingAPI)
                skel:skeleton → /Twig/Skel
                primvars:skel:jointIndices
                primvars:skel:jointWeights
    """
    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "structure": {},
    }

    try:
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            results["valid"] = False
            results["errors"].append(f"Failed to open USD: {usd_path}")
            return results

        # Check /Twig SkelRoot
        twig_prim = stage.GetPrimAtPath("/Twig")
        if not twig_prim or not twig_prim.IsA(UsdSkel.Root):
            results["valid"] = False
            results["errors"].append("/Twig prim is not a SkelRoot")
        else:
            results["structure"]["root"] = "✓ /Twig (SkelRoot)"

        # Check /Twig/Skel Skeleton
        skel_prim = stage.GetPrimAtPath("/Twig/Skel")
        if not skel_prim or not skel_prim.IsA(UsdSkel.Skeleton):
            results["valid"] = False
            results["errors"].append("/Twig/Skel is not a Skeleton")
        else:
            skel = UsdSkel.Skeleton(skel_prim)
            joints = skel.GetJointsAttr().Get()
            bind_transforms = skel.GetBindTransformsAttr().Get()
            rest_transforms = skel.GetRestTransformsAttr().Get()

            results["structure"]["skeleton"] = f"✓ /Twig/Skel (Skeleton with {len(joints)} joints)"
            results["structure"]["joints"] = joints

            if len(joints) != 1 or joints[0] != "root":
                results["warnings"].append(f"Expected single 'root' joint, got: {joints}")

        # Check /Twig/Mesh
        mesh_prim = stage.GetPrimAtPath("/Twig/Mesh")
        if not mesh_prim or not mesh_prim.IsA(UsdGeom.Mesh):
            results["valid"] = False
            results["errors"].append("/Twig/Mesh is not a Mesh")
        else:
            mesh = UsdGeom.Mesh(mesh_prim)

            # Check SkelBindingAPI
            has_binding = mesh_prim.HasAPI("SkelBindingAPI")
            if not has_binding:
                results["valid"] = False
                results["errors"].append("/Twig/Mesh missing SkelBindingAPI")

            # Check skeleton relationship
            skel_rel = mesh_prim.GetRelationship("skel:skeleton")
            if skel_rel:
                targets = skel_rel.GetTargets()
                if targets and targets[0] == Sdf.Path("/Twig/Skel"):
                    results["structure"]["mesh_skeleton_binding"] = "✓ Mesh bound to /Twig/Skel"
                else:
                    results["errors"].append(f"Skeleton binding incorrect: {targets}")
            else:
                results["errors"].append("Missing skel:skeleton relationship")

            # Check skinning data
            primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)
            joint_indices_pv = primvars_api.GetPrimvar("skel:jointIndices")
            joint_weights_pv = primvars_api.GetPrimvar("skel:jointWeights")

            if joint_indices_pv and joint_weights_pv:
                joint_indices = joint_indices_pv.Get()
                joint_weights = joint_weights_pv.Get()
                num_verts = len(mesh.GetPointsAttr().Get())

                results["structure"]["skinning"] = (
                    f"✓ Skinning data: {len(joint_indices)} joint indices, "
                    f"{len(joint_weights)} weights for {num_verts} vertices"
                )

                if len(joint_indices) != num_verts:
                    results["warnings"].append(
                        f"Joint indices count ({len(joint_indices)}) != vertex count ({num_verts})"
                    )
            else:
                results["errors"].append("Missing skinning primvars (skel:jointIndices or skel:jointWeights)")

        # Check defaultPrim
        default_prim = stage.GetDefaultPrim()
        if default_prim and default_prim.GetPath() == Sdf.Path("/Twig"):
            results["structure"]["default_prim"] = "✓ defaultPrim set to /Twig"
        else:
            results["warnings"].append("defaultPrim not set to /Twig")

        # Check no leftover /root prim from Blender
        root_prim = stage.GetPrimAtPath("/root")
        if root_prim and root_prim.IsValid():
            results["errors"].append("Found leftover /root prim from Blender export (should be removed)")
        else:
            results["structure"]["no_root_artifact"] = "✓ No /root artifact"

    except Exception as e:
        results["valid"] = False
        results["errors"].append(f"Exception during verification: {e}")

    return results


def print_verification_results(results: dict, usd_path: Path):
    """Print verification results."""
    print(f"\n{'='*60}")
    print(f"Skeletal Twig Structure Verification: {usd_path.name}")
    print(f"{'='*60}")

    if results["valid"]:
        print("✓ VALID - Structure matches working example")
    else:
        print("✗ INVALID - Structure does not match")

    print(f"\nStructure:")
    for key, value in results["structure"].items():
        print(f"  {value}")

    if results["warnings"]:
        print(f"\nWarnings:")
        for warning in results["warnings"]:
            print(f"  ⚠ {warning}")

    if results["errors"]:
        print(f"\nErrors:")
        for error in results["errors"]:
            print(f"  ✗ {error}")

    print(f"\n{'='*60}\n")


if __name__ == "__main__":
    import sys

    # Verify working example
    working_example = Path("data/working_assemblies/demo_twig_skel.usda")
    if working_example.exists():
        print("Verifying WORKING EXAMPLE structure:")
        results = verify_twig_structure(working_example)
        print_verification_results(results, working_example)

    # Verify any provided paths
    for path_str in sys.argv[1:]:
        usd_path = Path(path_str)
        if usd_path.exists():
            results = verify_twig_structure(usd_path)
            print_verification_results(results, usd_path)
        else:
            print(f"File not found: {usd_path}")
