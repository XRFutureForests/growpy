"""Quick test of skeletal Nanite Assembly export with twig lookup fix."""

import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

import the_grove_22_core as gc

from growpy import get_config
from growpy.io.unreal_nanite_assembly import export_tree_as_nanite_assembly


def test_skeletal_assembly_with_twigs():
    """Test full skeletal Nanite Assembly export with Western Red Cedar."""

    print("=" * 60)
    print("Testing Skeletal Nanite Assembly with Twig Lookup Fix")
    print("=" * 60)

    # Species to test
    species_name = "Cupressaceae - Western redcedar"
    output_dir = Path("data/output/skeletal_assembly_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    print(f"\nSpecies: {species_name}")
    print(f"Output: {output_dir}")
    print()

    # Get config
    config = get_config()
    print("✓ Config loaded")

    # Create grove with species preset
    print("\n--- Growing Tree ---")
    grove = gc.Grove()
    grove.clear_trees()

    # Load species preset
    preset_path = config.get_preset_path(species_name)
    print(f"  Loading preset: {preset_path}")

    with open(preset_path, "r") as f:
        preset_json = f.read()
    properties = gc.io.properties_from_json_string(preset_json)
    grove.set_properties(properties)
    print(f"  Loaded species properties: {species_name}")

    # Add tree
    position = gc.Vector(0, 0, 0)
    direction = gc.Vector(0, 0, 1)
    grove.add_new_tree(position, direction, 0)
    print("  Added tree at origin")

    # Simulate growth
    num_cycles = 4
    for i in range(num_cycles):
        grove.simulate(flushes=1)
        print(f"  Cycle {i+1}/{num_cycles}")

    print(f"  Growth complete: {num_cycles} cycles")

    # Export as skeletal Nanite Assembly with twigs
    print("\n--- Exporting Skeletal Nanite Assembly ---")

    output_file = (
        output_dir
        / f"{species_name.replace(' ', '_').replace('-', '_')}_skeletal_assembly.usda"
    )

    success = export_tree_as_nanite_assembly(
        grove=grove,
        output_path=output_file,
        species_name=species_name,
        include_twigs=True,
        use_skeletal_mesh=True,
        resolution=32,
        resolution_reduce=0.8,
    )

    if success:
        print(f"\n✓ SUCCESS: Exported {output_file.name}")
        print(f"  File size: {output_file.stat().st_size / 1024:.1f} KB")

        # Check if twigs were included
        content = output_file.read_text()
        if "TwigPrototypes" in content:
            print("  ✓ Twig prototypes found in assembly")
        if "PointInstancer" in content:
            print("  ✓ Point instancer found in assembly")
        if "NaniteAssemblyRootAPI" in content:
            print("  ✓ Nanite Assembly Root API applied")
        if "skeletalMesh" in content:
            print("  ✓ Mesh type set to skeletalMesh")

        print("\n" + "=" * 60)
        print("TEST PASSED: Skeletal Assembly Created Successfully!")
        print("=" * 60)
        return True
    else:
        print("\n✗ FAILED: Export failed")
        print("=" * 60)
        return False


if __name__ == "__main__":
    success = test_skeletal_assembly_with_twigs()
    sys.exit(0 if success else 1)
    success = test_skeletal_assembly_with_twigs()
    sys.exit(0 if success else 1)
