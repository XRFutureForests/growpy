#!/usr/bin/env python3
"""
Simple text-based verification of UsdSkel hierarchy structure.

This script checks USD files using text parsing (no pxr dependency required).

Usage:
    python verify_skel_simple.py <path_to_skeletal.usda>
"""

import sys
import re
from pathlib import Path


def verify_skeleton_simple(usd_path: Path) -> dict:
    """Verify skeleton hierarchy by parsing USD text.
    
    Args:
        usd_path: Path to USD file to verify
        
    Returns:
        Dictionary with verification results
    """
    results = {
        "file": str(usd_path),
        "errors": [],
        "warnings": [],
        "info": {},
        "valid": False
    }
    
    if not usd_path.exists():
        results["errors"].append(f"File not found: {usd_path}")
        return results
    
    try:
        with open(usd_path, 'r') as f:
            content = f.read()
    except Exception as e:
        results["errors"].append(f"Failed to read file: {e}")
        return results
    
    # Check for Skeleton prim
    if 'def Skeleton' not in content:
        results["errors"].append("No Skeleton prim found")
        return results
    
    results["info"]["has_skeleton"] = True
    
    # Extract skeleton name
    skel_match = re.search(r'def Skeleton "([^"]+)"', content)
    if skel_match:
        results["info"]["skeleton_name"] = skel_match.group(1)
    
    # Check for joints attribute
    joints_match = re.search(r'uniform token\[\] joints = \[([^\]]+)\]', content)
    if not joints_match:
        results["errors"].append("Missing 'uniform token[] joints' attribute")
    else:
        joints_str = joints_match.group(1)
        joint_names = re.findall(r'"([^"]+)"', joints_str)
        results["info"]["joint_count"] = len(joint_names)
        results["info"]["joint_names_sample"] = joint_names[:5]  # First 5
        
        # Check naming convention
        if joint_names and not all(name.startswith("joint_") for name in joint_names):
            results["warnings"].append("Some joints don't follow 'joint_N' naming convention")
    
    # Check for bindTransforms
    if 'uniform matrix4d[] bindTransforms' not in content:
        results["errors"].append("Missing 'uniform matrix4d[] bindTransforms' attribute")
    else:
        results["info"]["has_bind_transforms"] = True
    
    # Check for restTransforms
    if 'uniform matrix4d[] restTransforms' not in content:
        results["errors"].append("Missing 'uniform matrix4d[] restTransforms' attribute")
    else:
        results["info"]["has_rest_transforms"] = True
    
    # CRITICAL: Check for jointIndices (topology array) - MUST be uniform
    joint_indices_match = re.search(r'uniform int\[\] jointIndices = \[([^\]]+)\]', content)
    if not joint_indices_match:
        results["errors"].append(
            "Missing 'uniform int[] jointIndices' topology attribute "
            "(defines parent-child hierarchy)"
        )
    else:
        indices_str = joint_indices_match.group(1)
        indices = [int(x.strip()) for x in indices_str.split(',') if x.strip().lstrip('-').isdigit()]
        results["info"]["topology_array_length"] = len(indices)
        results["info"]["topology_sample"] = indices[:10]  # First 10
        
        # Verify topology
        if results["info"].get("joint_count"):
            if len(indices) != results["info"]["joint_count"]:
                results["errors"].append(
                    f"Topology array length ({len(indices)}) doesn't match "
                    f"joint count ({results['info']['joint_count']})"
                )
        
        # Check root joint
        if indices[0] != -1:
            results["errors"].append(
                f"First joint should have parent -1 (root), got {indices[0]}"
            )
        
        # Check for valid parent indices
        for i, parent_idx in enumerate(indices):
            if parent_idx >= i and parent_idx != -1:
                results["errors"].append(
                    f"Joint {i} has invalid parent index {parent_idx} "
                    f"(must be < {i} or -1)"
                )
                break  # Only report first error
    
    # Check for deprecated jointParents naming
    if re.search(r'int\[\] jointParents', content):
        results["errors"].append(
            "Found deprecated 'jointParents' attribute - MUST be 'jointIndices'"
        )
    
    # Check for SkelRoot
    if 'def SkelRoot' not in content:
        results["warnings"].append("No SkelRoot prim found")
    else:
        results["info"]["has_skel_root"] = True
    
    # Check for mesh with skeletal binding
    if 'primvars:skel:jointIndices' in content:
        results["info"]["has_vertex_binding"] = True
        
        # Extract vertex binding sample
        vertex_indices_match = re.search(
            r'primvars:skel:jointIndices = \[([^\]]+)\]',
            content
        )
        if vertex_indices_match:
            vertex_indices_str = vertex_indices_match.group(1)
            vertex_indices = [
                int(x.strip()) for x in vertex_indices_str.split(',')[:20]
                if x.strip().lstrip('-').isdigit()
            ]
            if vertex_indices:
                results["info"]["vertex_joint_range"] = (
                    min(vertex_indices),
                    max(vertex_indices)
                )
    else:
        results["warnings"].append("No vertex skinning data found (primvars:skel:jointIndices)")
    
    # Check for proper skeleton relationship
    if 'rel skel:skeleton' in content or 'unreal:naniteAssembly:skeleton' in content:
        results["info"]["has_skeleton_relationship"] = True
    else:
        results["warnings"].append("No skeleton relationship found on mesh")
    
    # Overall validation
    results["valid"] = len(results["errors"]) == 0
    
    return results


def print_results(results: dict):
    """Print verification results."""
    print("\n" + "="*70)
    print("Skeleton Hierarchy Verification (Text-Based)")
    print("="*70)
    print(f"\nFile: {results['file']}")
    print(f"Status: {'✓ VALID' if results['valid'] else '✗ INVALID'}")
    
    if results["info"]:
        print("\n--- Information ---")
        for key, value in results["info"].items():
            if isinstance(value, list) and len(value) > 5:
                print(f"  {key}: {value[:5]} ... ({len(value)} total)")
            else:
                print(f"  {key}: {value}")
    
    if results["warnings"]:
        print("\n--- Warnings ---")
        for warning in results["warnings"]:
            print(f"  ⚠  {warning}")
    
    if results["errors"]:
        print("\n--- Errors ---")
        for error in results["errors"]:
            print(f"  ✗  {error}")
    
    print("\n" + "="*70)
    
    if results["valid"]:
        print("✓ Skeleton structure is valid and ready for Unreal Engine!")
        print("\nNext steps:")
        print("  1. Import the skeletal Nanite Assembly USD into Unreal Engine 5.7+")
        print("  2. Check that bone hierarchy shows proper parent-child connections")
        print("  3. Test skeletal deformation (rotate parent bone → children should move)")
        print("  4. Verify stem bones affect mesh sections properly")
    else:
        print("✗ Skeleton has issues that need to be fixed before importing to Unreal.")
    print()


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\nExample:")
        print("  python verify_skel_simple.py data/output/joint_indices_fix_test/Western_redcedar/Western_redcedar_tree_0000_tree_only_skeletal.usda")
        sys.exit(1)
    
    usd_path = Path(sys.argv[1])
    results = verify_skeleton_simple(usd_path)
    print_results(results)
    
    sys.exit(0 if results["valid"] else 1)


if __name__ == "__main__":
    main()
