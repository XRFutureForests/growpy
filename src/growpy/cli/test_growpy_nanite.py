#!/usr/bin/env python3
"""Test GrowPy Nanite Assembly generation with updated structure.

This script verifies that GrowPy can generate Nanite assemblies matching
the working demo structure.
"""

import sys
from pathlib import Path

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))

from growpy.io.unreal_nanite_assembly import create_nanite_assembly_usd


def test_growpy_nanite_assembly():
    """Test creating a Nanite assembly using the simple demo files."""

    print("=" * 60)
    print("Testing GrowPy Nanite Assembly Generation")
    print("=" * 60)
    print()

    # Use the simple demo files as input
    demo_dir = Path("data/output/nanite_demo")
    tree_usd = demo_dir / "demo_tree_simple.usda"
    twig_usd = demo_dir / "demo_twig_simple.usda"

    # Output to same directory for comparison
    output_path = demo_dir / "test_assembly_growpy.usda"

    # Check inputs exist
    if not tree_usd.exists():
        print(f"Error: Tree USD not found: {tree_usd}")
        return False

    if not twig_usd.exists():
        print(f"Error: Twig USD not found: {twig_usd}")
        return False

    print(f"Input tree: {tree_usd}")
    print(f"Input twig: {twig_usd}")
    print(f"Output: {output_path}")
    print()

    # Create assembly
    success = create_nanite_assembly_usd(
        tree_usd_path=tree_usd,
        output_path=output_path,
        species_name="TestTree",
        twig_usd_paths={"twig": twig_usd},
        use_skeletal_mesh=True,
    )

    if success:
        print()
        print("=" * 60)
        print("SUCCESS: Assembly generated!")
        print("=" * 60)
        print()
        print("Compare the generated file to demo_assembly_external.usda")
        print("They should have matching structure:")
        print('  - kind="assembly" on root')
        print("  - No NaniteAssemblyExternalRefAPI on tree or prototypes")
        print("  - NaniteAssemblySkelBindingAPI on PointInstancer")
        print("  - Proper primvars with elementSize metadata")
        return True
    else:
        print()
        print("=" * 60)
        print("FAILED: Assembly generation failed")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = test_growpy_nanite_assembly()
    sys.exit(0 if success else 1)
