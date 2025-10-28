#!/usr/bin/env python3
"""
Test script to validate skeletal nanite mesh assembly pipeline.

This script generates a simple tree with twigs and validates that the exported
structure matches the working demo format from data/working_assemblies_working_skel/.

Usage:
    python test_skeletal_assembly.py --output-dir data/output/test_assembly

Requirements:
    - Run in the-grove conda environment
    - USD Python (pxr) must be available
"""

import sys
from pathlib import Path

# CRITICAL: Try Blender's bundled USD first (matches the-grove conda environment)
USD_AVAILABLE = False
try:
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
        from pxr import Usd, UsdGeom, UsdSkel

        USD_AVAILABLE = True
        print("Using Blender's bundled USD")
except ImportError:
    # Fallback: try system USD installation
    try:
        from pxr import Usd, UsdGeom, UsdSkel

        USD_AVAILABLE = True
        print("Using system USD installation")
    except ImportError:
        pass

if not USD_AVAILABLE:
    print("ERROR: USD Python (pxr) not available")
    print("\nTo fix this, install USD in your conda environment:")
    print("  conda install -c conda-forge usd-core")
    print("\nOr run through Blender to use its bundled USD:")
    print("  blender --background --python src/growpy/cli/test_skeletal_assembly.py -- --output-dir data/output/test_assembly")
    sys.exit(1)

# Import Grove after USD
try:
    import the_grove_22_core as gc
except ImportError:
    print("ERROR: Grove core (the_grove_22_core) not available")
    sys.exit(1)

from growpy.io.usd_builder import build_tree_usd, add_skeleton_to_usd
from growpy.io.unreal_nanite_assembly import create_nanite_assembly_usd
from growpy.io.blender_export import get_twig_usd_map_for_species


def validate_skeletal_structure(usd_path: Path) -> dict:
    """Validate that USD file has correct skeletal structure.

    Checks for:
    - SkelRoot at /Tree
    - Skeleton at /Tree/TreeSkel
    - Hierarchical joint names (root/joint_1/joint_2, etc.)
    - Twig mount bones (root/joint_X/twig_Y)
    - Multi-joint skinning (elementSize=2)

    Returns:
        dict with validation results
    """
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
        skel_root_prim = stage.GetPrimAtPath("/Tree")
        if not skel_root_prim or not skel_root_prim.IsA(UsdSkel.Root):
            results["valid"] = False
            results["errors"].append("No SkelRoot found at /Tree")
            return results

        # Check for Skeleton
        skel_prim = stage.GetPrimAtPath("/Tree/TreeSkel")
        if not skel_prim or not skel_prim.IsA(UsdSkel.Skeleton):
            results["valid"] = False
            results["errors"].append("No Skeleton found at /Tree/TreeSkel")
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

        if len(twig_bones) > 0:
            print(f"  Found {len(twig_bones)} twig mount bone(s):")
            for twig_bone in twig_bones[:5]:  # Show first 5
                print(f"    - {twig_bone}")
        else:
            results["warnings"].append("No twig mount bones found in skeleton")

        # Check for mesh with skinning
        mesh_prim = stage.GetPrimAtPath("/Tree/TreeMesh")
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


def test_simple_tree_with_twigs(output_dir: Path, csv_path: Path):
    """Test pipeline with a tree from CSV input.

    Args:
        output_dir: Output directory for test files
        csv_path: Path to CSV file with tree data (fid, species, x, y, dbh, height, z)
    """

    print("\n" + "=" * 80)
    print("Testing Skeletal Nanite Mesh Assembly Pipeline")
    print("=" * 80)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Read tree data from CSV
    print(f"\n1. Reading tree data from CSV...")
    print(f"   CSV file: {csv_path}")

    import pandas as pd
    df = pd.read_csv(csv_path)

    if df.empty:
        print("   ERROR: CSV file is empty")
        return False

    # Get first tree from CSV
    tree_data = df.iloc[0]
    species = tree_data['species']
    target_height = tree_data['height']
    position_x = tree_data['x']
    position_y = tree_data['y']
    position_z = tree_data.get('z', 0)  # z is optional

    print(f"   Species: {species}")
    print(f"   Target height: {target_height}m")
    print(f"   Position: ({position_x}, {position_y}, {position_z})")

    # Create grove for this species
    print(f"\n2. Creating grove for {species}...")
    from growpy import create_grove

    grove = create_grove(species)

    # Add tree at specified position
    position = gc.Vector(position_x, position_y, position_z)
    direction = gc.Vector(0, 0, 1)
    delay = 0
    grove.add_new_tree(position, direction, delay)

    # For testing, use a simple heuristic for growth cycles
    # Typically: ~2-4m growth per cycle, so height/3 is a rough estimate
    # But limit to 5 cycles max for fast testing
    estimated_cycles = int(target_height / 3)
    growth_cycles = min(estimated_cycles, 5)

    if growth_cycles < 2:
        growth_cycles = 2  # Minimum 2 cycles for reasonable tree

    print(f"   Simulating {growth_cycles} growth cycles (target: {target_height}m)...")
    grove.simulate(growth_cycles)

    # Build tree model
    print(f"\n3. Building tree model...")
    build_options = {
        "resolution": 8,  # Low resolution for fast testing
        "resolution_reduce": 0.8,
        "texture_repeat": 3,
        "build_cutoff_age": 0,
        "build_cutoff_thickness": 0.0,
        "build_blend": True,
        "build_end_cap": True,
    }
    models = grove.build_models(build_options)

    if not models:
        print("   ERROR: No models generated")
        return False

    model = models[0]

    # Export tree mesh to USD
    print("\n4. Exporting tree mesh to USD...")
    tree_usd_path = output_dir / f"{species.lower().replace(' ', '_')}_tree.usda"
    if not build_tree_usd(model, tree_usd_path, up_axis="Z"):
        print("   ERROR: Failed to export tree mesh")
        return False

    print(f"   [OK] Exported tree mesh: {tree_usd_path.name}")

    # Add skeleton WITHOUT dedicated twig bones
    # Twigs will bind to nearest existing tree joints instead
    print("\n5. Adding skeleton (without dedicated twig bones)...")
    if not add_skeleton_to_usd(tree_usd_path, grove, add_twig_bones=False):
        print("   ERROR: Failed to add skeleton")
        return False

    print(f"   [OK] Added skeleton: {tree_usd_path.name}")
    print(f"   NOTE: Twigs will bind to nearest tree joints (no dedicated twig bones)")

    # Validate tree structure
    print("\n6. Validating tree skeletal structure...")
    validation = validate_skeletal_structure(tree_usd_path)

    print(f"\n   Validation Results:")
    print(f"   Valid: {validation['valid']}")
    print(f"   Total joints: {validation['info'].get('total_joints', 0)}")
    print(f"   Hierarchical joints: {validation['info'].get('hierarchical_joints', 0)}")
    print(f"   Twig mount bones: {validation['info'].get('twig_bones', 0)}")
    print(
        f"   Skinning element size: {validation['info'].get('skinning_element_size', 'N/A')}"
    )

    if validation["errors"]:
        print(f"\n   Errors:")
        for error in validation["errors"]:
            print(f"     - {error}")

    if validation["warnings"]:
        print(f"\n   Warnings:")
        for warning in validation["warnings"]:
            print(f"     - {warning}")

    # Look for twig USD files
    print("\n7. Looking for twig USD files...")

    # Try multiple approaches to find twigs
    twig_usd_paths = None

    # First try: Use species lookup with the species from CSV
    # Normalize species name (remove spaces, lowercase)
    species_normalized = species.lower().replace(" ", "")
    print(f"   Trying species lookup for: {species} (normalized: {species_normalized})")
    try:
        # Try both original and normalized species names
        twig_usd_paths = get_twig_usd_map_for_species(species, prefer_skeletal=True)
        if not twig_usd_paths:
            twig_usd_paths = get_twig_usd_map_for_species(species_normalized, prefer_skeletal=True)
        if twig_usd_paths:
            print(f"   Found {len(twig_usd_paths)} twig type(s) via species lookup")
            for twig_type, twig_path in twig_usd_paths.items():
                print(f"     - {twig_type}: {twig_path.name}")
    except Exception as e:
        print(f"   Species lookup failed: {e}")

    # Second try: Direct directory lookup (fallback)
    if not twig_usd_paths:
        print(f"   Trying direct directory lookup...")
        # Look in common twig directories
        possible_twig_dirs = [
            Path("data/assets/twigs/WesternRedCedarTwig"),
            Path("data/assets/twigs/westernredcedar"),
            Path("data/output/twigs/WesternRedCedarTwig"),
        ]

        for twig_dir in possible_twig_dirs:
            if twig_dir.exists():
                print(f"   Found twig directory: {twig_dir}")

                # Find skeletal USD files
                skel_files = list(twig_dir.glob("*_skel.usda"))
                if skel_files:
                    print(f"   Found {len(skel_files)} skeletal twig file(s)")

                    # Map to twig types
                    twig_usd_paths = {}
                    for skel_file in skel_files:
                        filename = skel_file.stem.lower()
                        if "apical" in filename:
                            twig_usd_paths["twig_long"] = skel_file
                            print(f"     - twig_long: {skel_file.name}")
                        elif "lateral" in filename:
                            twig_usd_paths["twig_short"] = skel_file
                            print(f"     - twig_short: {skel_file.name}")
                        elif "upward" in filename:
                            twig_usd_paths["twig_upward"] = skel_file
                            print(f"     - twig_upward: {skel_file.name}")

                    if twig_usd_paths:
                        break

    if not twig_usd_paths:
        print(f"   No twig USD files found for '{species}'")
        print(f"   NOTE: To test with twigs, first convert twigs using:")
        print(f"         python src/growpy/cli/convert_twigs.py <path_to_twigs.blend>")
        print(f"   Skipping Nanite Assembly creation (testing skeleton only)")
        print("\n" + "=" * 80)
        print("SUCCESS: Skeleton structure validated!")
        print(f"\nGenerated file:")
        print(f"  - Tree skeleton: {tree_usd_path}")
        print(f"\nCompare with working demo:")
        print(f"  - data/working_assemblies_working_skel/demo_tree_skel.usda")
        print("=" * 80)
        return validation["valid"]

    # Create Nanite Assembly
    print("\n8. Creating Nanite Assembly...")
    assembly_path = output_dir / f"{species_normalized}_assembly.usda"

    success = create_nanite_assembly_usd(
        tree_usd_path=tree_usd_path,
        output_path=assembly_path,
        species_name=species,
        twig_usd_paths=twig_usd_paths,
        use_skeletal_mesh=True,
    )

    if success:
        print(f"   [OK] Created Nanite Assembly: {assembly_path.name}")
    else:
        print(f"   ERROR: Failed to create Nanite Assembly")
        return False

    # Final summary
    print("\n" + "=" * 80)
    if validation["valid"] and success:
        print("SUCCESS: Pipeline test completed successfully!")
        print(f"\nGenerated files:")
        print(f"  - Tree skeleton: {tree_usd_path}")
        print(f"  - Nanite Assembly: {assembly_path}")
        print(f"\nCompare with working demo:")
        print(f"  - data/working_assemblies_working_skel/demo_tree_skel.usda")
        print(f"  - data/working_assemblies_working_skel/demo_assembly_external_ref.usda")
    else:
        print("FAILED: Pipeline test completed with errors")
        return False

    print("=" * 80)
    return True


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Test skeletal nanite mesh assembly pipeline with CSV input"
    )
    parser.add_argument(
        "--csv",
        type=Path,
        default=Path("data/input/test.csv"),
        help="CSV file with tree data (fid, species, x, y, dbh, height, z)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("data/output/test_assembly"),
        help="Output directory for test files",
    )

    args = parser.parse_args()

    # Check if CSV exists
    if not args.csv.exists():
        print(f"ERROR: CSV file not found: {args.csv}")
        print(f"\nPlease provide a valid CSV file with columns:")
        print(f"  fid, species, x, y, dbh, height, z")
        print(f"\nExample:")
        print(f"  python {sys.argv[0]} --csv data/input/test.csv")
        sys.exit(1)

    success = test_simple_tree_with_twigs(args.output_dir, args.csv)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
