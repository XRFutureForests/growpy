"""
Test PVE preset generation with new foliage and hierarchy features.

Run this to verify the implementation works correctly.
"""

import sys
from pathlib import Path

# Add project to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root / "src"))


def test_pve_generation():
    """Test PVE generation with a simple tree."""
    print("=" * 60)
    print("Testing PVE Preset Generation with Foliage")
    print("=" * 60)
    print()

    try:
        import the_grove_22_core as gc

        from growpy import create_grove
        from growpy.io.pve_grove_mapper import generate_pve_from_grove

        # Create simple oak tree
        print("1. Creating European Oak grove...")
        species_name = "european_oak"
        grove = create_grove("European Oak")
        grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

        print("2. Simulating growth (5 cycles)...")
        grove.simulate(flushes=5)

        print("3. Generating PVE preset with foliage...")
        output_path = project_root / "data" / "output" / "test_pve_with_foliage.json"

        pve_data = generate_pve_from_grove(
            grove=grove,
            output_path=output_path,
            species_name=species_name,
            tree_index=0,
            verbose=True,
            use_default_growth_params=True,  # Use Hazel defaults
            twig_density=1.0,  # Full foliage
        )

        print()
        print("4. Checking generated data...")

        # Check foliage data
        instancer_name = pve_data["primitives"]["attributes"]["instancer_name"]["value"]
        total_twigs = sum(len(names) for names in instancer_name)
        print(f"   - Total twig instances: {total_twigs}")

        # Check hierarchy
        parents = pve_data["primitives"]["attributes"]["parents"]["value"]
        children = pve_data["primitives"]["attributes"]["children"]["value"]
        num_branches = len(parents)
        print(f"   - Number of branches: {num_branches}")
        print(f"   - Root branches: {sum(1 for p in parents if p == [-1])}")

        # Check growth params
        phyllotaxy = pve_data["globalAttributes"]["phyllotaxyLeaf"]["value"]
        print(f"   - phyllotaxyLeaf populated: {len(phyllotaxy)} values")

        print()
        print("=" * 60)
        print("SUCCESS! PVE preset generated with:")
        print(f"  - {total_twigs} twig instances")
        print(f"  - {num_branches} branches with hierarchy")
        print(f"  - Growth parameters from Hazel defaults")
        print(f"  - Output: {output_path}")
        print("=" * 60)

        return True

    except Exception as e:
        print()
        print("=" * 60)
        print(f"ERROR: {e}")
        print("=" * 60)
        import traceback

        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = test_pve_generation()
    sys.exit(0 if success else 1)
