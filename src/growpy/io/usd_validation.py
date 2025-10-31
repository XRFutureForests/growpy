"""USD skeletal structure validation utilities.

This module provides validation functions for USD files with skeletal meshes,
ensuring they have proper structure for use in Unreal Engine Nanite Assemblies.
"""

from pathlib import Path
from typing import Dict, Optional

# Try to use Blender's bundled USD first (recommended for bpy environments)
try:
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
    from pxr import Usd, UsdGeom, UsdSkel

    USD_AVAILABLE = True
except ImportError:
    # Fall back to system-installed USD if bpy not available
    try:
        from pxr import Usd, UsdGeom, UsdSkel

        USD_AVAILABLE = True
    except ImportError:
        USD_AVAILABLE = False


def validate_skeletal_structure(usd_path: Path, verbose: bool = False) -> dict:
    """Validate that USD file has correct skeletal structure.

    Checks for:
    - SkelRoot at /tree
    - Skeleton at /tree/TreeSkel
    - Hierarchical joint names (root/joint_1/joint_2, etc.)
    - Twig mount bones (root/joint_X/twig_Y)
    - Multi-joint skinning (elementSize=2)
    - Bind and rest transforms matching joint count

    Args:
        usd_path: Path to USD file to validate
        verbose: If True, print detailed validation information

    Returns:
        dict with validation results:
        {
            "valid": bool,              # Overall validation status
            "errors": list[str],        # List of error messages
            "warnings": list[str],      # List of warning messages
            "info": {                   # Detailed information
                "total_joints": int,
                "hierarchical_joints": int,
                "twig_bones": int,
                "skinning_element_size": int,
            }
        }

    Example:
        >>> results = validate_skeletal_structure(Path("tree_skel.usda"))
        >>> if results["valid"]:
        ...     print(f"Valid skeleton with {results['info']['total_joints']} joints")
        >>> else:
        ...     print(f"Validation errors: {results['errors']}")
    """
    if not USD_AVAILABLE:
        return {
            "valid": False,
            "errors": ["USD Python module not available"],
            "warnings": [],
            "info": {},
        }

    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "info": {},
    }

    try:
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            results["valid"] = False
            results["errors"].append(f"Could not open USD file: {usd_path}")
            return results

        # Check for SkelRoot
        skel_root_prim = stage.GetPrimAtPath("/tree")
        if not skel_root_prim or not skel_root_prim.IsA(UsdSkel.Root):
            results["valid"] = False
            results["errors"].append("No SkelRoot found at /tree")
            return results

        # Check for Skeleton
        skel_prim = stage.GetPrimAtPath("/tree/TreeSkel")
        if not skel_prim or not skel_prim.IsA(UsdSkel.Skeleton):
            results["valid"] = False
            results["errors"].append("No Skeleton found at /tree/TreeSkel")
            return results

        skeleton = UsdSkel.Skeleton(skel_prim)

        # Get joint names
        joints_attr = skeleton.GetJointsAttr()
        if not joints_attr:
            results["valid"] = False
            results["errors"].append("No joints attribute on skeleton")
            return results

        joint_names = joints_attr.Get()
        results["info"]["total_joints"] = len(joint_names)

        # Check for hierarchical joint naming
        hierarchical_joints = [j for j in joint_names if "/" in str(j)]
        results["info"]["hierarchical_joints"] = len(hierarchical_joints)

        if len(hierarchical_joints) == 0:
            results["warnings"].append(
                "No hierarchical joint names found (expected format: root/joint_1/joint_2)"
            )

        # Check for twig mount bones
        twig_bones = [j for j in joint_names if "twig" in str(j).lower()]
        results["info"]["twig_bones"] = len(twig_bones)

        if verbose and len(twig_bones) > 0:
            print(f"  Found {len(twig_bones)} twig mount bone(s):")
            for twig_bone in twig_bones[:5]:  # Show first 5
                print(f"    - {twig_bone}")

        # Check for mesh with skinning
        mesh_prim = stage.GetPrimAtPath("/tree/TreeMesh")
        if mesh_prim and mesh_prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(mesh_prim)

            # Check for skinning primvars
            primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)
            joint_indices_primvar = primvars_api.GetPrimvar("skel:jointIndices")
            joint_weights_primvar = primvars_api.GetPrimvar("skel:jointWeights")

            if joint_indices_primvar and joint_indices_primvar.HasValue():
                element_size = joint_indices_primvar.GetElementSize()
                results["info"]["skinning_element_size"] = element_size

                if element_size != 2:
                    results["warnings"].append(
                        f"Expected elementSize=2 for multi-joint skinning, got {element_size}"
                    )
            else:
                results["warnings"].append("No skel:jointIndices primvar found on mesh")
        else:
            results["warnings"].append("No mesh found at /tree/TreeMesh")

        # Check bind and rest transforms
        bind_transforms_attr = skeleton.GetBindTransformsAttr()
        rest_transforms_attr = skeleton.GetRestTransformsAttr()

        if bind_transforms_attr and rest_transforms_attr:
            bind_transforms = bind_transforms_attr.Get()
            rest_transforms = rest_transforms_attr.Get()

            if len(bind_transforms) != len(joint_names):
                results["errors"].append(
                    f"Bind transforms count ({len(bind_transforms)}) doesn't match joints count ({len(joint_names)})"
                )
                results["valid"] = False

            if len(rest_transforms) != len(joint_names):
                results["errors"].append(
                    f"Rest transforms count ({len(rest_transforms)}) doesn't match joints count ({len(joint_names)})"
                )
                results["valid"] = False
        else:
            results["errors"].append("Missing bind or rest transforms")
            results["valid"] = False

    except Exception as e:
        results["valid"] = False
        results["errors"].append(f"Validation failed: {e}")

    return results


def validate_twig_skeletal_structure(usd_path: Path, verbose: bool = False) -> dict:
    """Validate that twig USD file has correct skeletal structure.

    Checks for:
    - SkelRoot at /Twig
    - Skeleton at /Twig/TwigSkel
    - Root joint
    - Skinning data

    Args:
        usd_path: Path to twig USD file to validate
        verbose: If True, print detailed validation information

    Returns:
        dict with validation results similar to validate_skeletal_structure
    """
    if not USD_AVAILABLE:
        return {
            "valid": False,
            "errors": ["USD Python module not available"],
            "warnings": [],
            "info": {},
        }

    results = {
        "valid": True,
        "errors": [],
        "warnings": [],
        "info": {},
    }

    try:
        stage = Usd.Stage.Open(str(usd_path))
        if not stage:
            results["valid"] = False
            results["errors"].append(f"Could not open USD file: {usd_path}")
            return results

        # Check for SkelRoot (CamelCase naming convention)
        skel_root_prim = stage.GetPrimAtPath("/Twig")
        if not skel_root_prim or not skel_root_prim.IsA(UsdSkel.Root):
            results["valid"] = False
            results["errors"].append("No SkelRoot found at /Twig")
            return results

        # Check for Skeleton
        skel_prim = stage.GetPrimAtPath("/Twig/TwigSkel")
        if not skel_prim or not skel_prim.IsA(UsdSkel.Skeleton):
            results["valid"] = False
            results["errors"].append("No Skeleton found at /Twig/TwigSkel")
            return results

        skeleton = UsdSkel.Skeleton(skel_prim)

        # Get joint names
        joints_attr = skeleton.GetJointsAttr()
        if not joints_attr:
            results["valid"] = False
            results["errors"].append("No joints attribute on skeleton")
            return results

        joint_names = joints_attr.Get()
        results["info"]["total_joints"] = len(joint_names)

        # Check for mesh with skinning (CamelCase naming convention)
        mesh_prim = stage.GetPrimAtPath("/Twig/Mesh")
        if mesh_prim and mesh_prim.IsA(UsdGeom.Mesh):
            mesh = UsdGeom.Mesh(mesh_prim)

            # Check for skinning primvars
            primvars_api = UsdGeom.PrimvarsAPI(mesh_prim)
            joint_indices_primvar = primvars_api.GetPrimvar("skel:jointIndices")

            if joint_indices_primvar and joint_indices_primvar.HasValue():
                element_size = joint_indices_primvar.GetElementSize()
                results["info"]["skinning_element_size"] = element_size
            else:
                results["warnings"].append("No skel:jointIndices primvar found on mesh")
        else:
            results["errors"].append("No mesh found at /Twig/Mesh")
            results["valid"] = False

        # Check bind and rest transforms
        bind_transforms_attr = skeleton.GetBindTransformsAttr()
        rest_transforms_attr = skeleton.GetRestTransformsAttr()

        if bind_transforms_attr and rest_transforms_attr:
            bind_transforms = bind_transforms_attr.Get()
            rest_transforms = rest_transforms_attr.Get()

            if len(bind_transforms) != len(joint_names):
                results["errors"].append(
                    f"Bind transforms count ({len(bind_transforms)}) doesn't match joints count ({len(joint_names)})"
                )
                results["valid"] = False

            if len(rest_transforms) != len(joint_names):
                results["errors"].append(
                    f"Rest transforms count ({len(rest_transforms)}) doesn't match joints count ({len(joint_names)})"
                )
                results["valid"] = False
        else:
            results["errors"].append("Missing bind or rest transforms")
            results["valid"] = False

    except Exception as e:
        results["valid"] = False
        results["errors"].append(f"Validation failed: {e}")

    return results


def print_validation_results(results: dict, file_name: str = "") -> None:
    """Print validation results in a readable format.

    Args:
        results: Validation results dict from validate_skeletal_structure
        file_name: Optional file name to include in output
    """
    prefix = f"{file_name}: " if file_name else ""

    print(f"\n{prefix}Validation Results:")
    print(f"  Valid: {results['valid']}")

    if results["info"]:
        print(f"  Total joints: {results['info'].get('total_joints', 0)}")
        print(f"  Hierarchical joints: {results['info'].get('hierarchical_joints', 0)}")
        print(f"  Twig mount bones: {results['info'].get('twig_bones', 0)}")
        print(
            f"  Skinning element size: {results['info'].get('skinning_element_size', 'N/A')}"
        )

    if results["errors"]:
        print(f"\n  Errors:")
        for error in results["errors"]:
            print(f"    - {error}")

    if results["warnings"]:
        print(f"\n  Warnings:")
        for warning in results["warnings"]:
            print(f"    - {warning}")
