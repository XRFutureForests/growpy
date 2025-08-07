#!/usr/bin/env python3
"""
Test script for the new twig integration system.
This will test the twig placement on a single existing USD file.
"""

import sys
from pathlib import Path

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from growpy.config import GrowPyConfig


def add_twigs_to_usd_file_text_based(usd_file_path, species_name, config):
    """
    Add twig instances to a USD tree file using text-based manipulation.
    This approach works without USD Python bindings and supports multiple twig types.
    """
    try:
        # Get twig information for this species
        twig_name = config.get_twig_for_species(species_name)
        if not twig_name:
            print(f"  ⚠️  No twig available for species: {species_name}")
            return False

        # Get available twig files organized by type
        twig_files_by_type = config.get_twig_files_by_type(species_name)
        if not twig_files_by_type:
            print(f"  ⚠️  No twig USD files found for {species_name}")
            return False

        print(f"  🌿 Adding {twig_name} twigs to {usd_file_path.name}")
        print(f"      Available twig types: {list(twig_files_by_type.keys())}")

        # Read the USD file content
        with open(usd_file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Generate twig instances for different positions and types
        twig_instances = []

        # Define twig placement based on position (simulating Grove's TwigEnd, TwigSide, TwigUpward)
        twig_placements = [
            # End/apical twigs (top of tree)
            {
                "position": (0.1, 0.2, 3.5),
                "type": "end",
                "preferred_files": ["apical", "end", "main"],
            },
            {
                "position": (-0.2, 0.3, 3.2),
                "type": "end",
                "preferred_files": ["apical", "end", "main"],
            },
            # Side/lateral twigs (middle sections)
            {
                "position": (0.8, 0.5, 2.0),
                "type": "side",
                "preferred_files": ["lateral", "side", "main"],
            },
            {
                "position": (-0.6, 0.7, 1.8),
                "type": "side",
                "preferred_files": ["lateral", "side", "main"],
            },
            {
                "position": (0.4, -0.8, 2.3),
                "type": "side",
                "preferred_files": ["lateral", "side", "main"],
            },
        ]

        # Process each twig placement
        for placement in twig_placements:
            # Find the best twig file for this placement
            twig_file = None
            twig_reference_name = None

            for preferred_type in placement["preferred_files"]:
                if (
                    preferred_type in twig_files_by_type
                    and twig_files_by_type[preferred_type]
                ):
                    twig_file = twig_files_by_type[preferred_type][
                        0
                    ]  # Use first file of this type
                    # Extract the reference name from the file
                    file_stem = twig_file.stem
                    if "_" in file_stem:
                        twig_reference_name = file_stem.split("_", 1)[1]
                    else:
                        twig_reference_name = file_stem
                    break

            if not twig_file:
                # Fallback to any available twig
                all_files = []
                for files in twig_files_by_type.values():
                    all_files.extend(files)
                if all_files:
                    twig_file = all_files[0]
                    file_stem = twig_file.stem
                    if "_" in file_stem:
                        twig_reference_name = file_stem.split("_", 1)[1]
                    else:
                        twig_reference_name = file_stem

            if twig_file and twig_reference_name:
                # Calculate relative path to twig file
                try:
                    twig_relative_path = twig_file.relative_to(usd_file_path.parent)
                except ValueError:
                    twig_relative_path = twig_file

                twig_instances.append(
                    {
                        "position": placement["position"],
                        "orientation": (
                            1.0,
                            0.0,
                            0.0,
                            0.0,
                        ),  # Identity quaternion for now
                        "file_path": twig_relative_path,
                        "reference_name": twig_reference_name,
                        "type": placement["type"],
                    }
                )

        if not twig_instances:
            print(f"  ⚠️  No twig instances could be created for {species_name}")
            return False

        # Group instances by twig file
        instances_by_file = {}
        for instance in twig_instances:
            file_key = str(instance["file_path"])
            if file_key not in instances_by_file:
                instances_by_file[file_key] = {
                    "file_path": instance["file_path"],
                    "reference_name": instance["reference_name"],
                    "instances": [],
                }
            instances_by_file[file_key]["instances"].append(instance)

        # Generate USD content
        twig_content = []
        twig_content.append("")

        for i, (file_key, file_info) in enumerate(instances_by_file.items()):
            prototype_name = f"TwigPrototype_{i}"
            instancer_name = f"TwigInstances_{i}"

            # Add prototype reference
            twig_content.append(f'    def "{prototype_name}" (')
            twig_content.append(
                f'        references = @{file_info["file_path"]}@</root/{file_info["reference_name"]}>'
            )
            twig_content.append("    )")
            twig_content.append("    {")
            twig_content.append("    }")
            twig_content.append("")

            # Add PointInstancer
            instances = file_info["instances"]
            twig_content.append(f'    def PointInstancer "{instancer_name}"')
            twig_content.append("    {")
            twig_content.append(f"        rel prototypes = </Tree/{prototype_name}>")
            twig_content.append(
                f'        int[] protoIndices = [{", ".join(["0"] * len(instances))}]'
            )
            twig_content.append(
                f'        int64[] ids = [{", ".join([str(j) for j in range(len(instances))])}]'
            )
            twig_content.append("")

            # Add positions
            positions_str = ", ".join(
                [
                    f"({inst['position'][0]:.4f}, {inst['position'][1]:.4f}, {inst['position'][2]:.4f})"
                    for inst in instances
                ]
            )
            twig_content.append(f"        point3f[] positions = [{positions_str}]")
            twig_content.append("")

            # Add orientations
            orientations_str = ", ".join(
                [
                    f"({inst['orientation'][0]:.6f}, {inst['orientation'][1]:.6f}, {inst['orientation'][2]:.6f}, {inst['orientation'][3]:.6f})"
                    for inst in instances
                ]
            )
            twig_content.append(f"        quath[] orientations = [{orientations_str}]")
            twig_content.append("")

            # Add uniform scale
            twig_content.append("        float3[] scales = [(1, 1, 1)]")
            twig_content.append("    }")
            twig_content.append("")

        # Join twig content
        twig_usd_text = "\n".join(twig_content)

        # Find insertion point (before the last closing brace)
        last_brace = content.rfind("}")
        if last_brace == -1:
            print("  ❌ Could not find closing brace in USD file")
            return False

        # Insert the twig content
        new_content = (
            content[:last_brace] + "\n" + twig_usd_text + "\n" + content[last_brace:]
        )

        # Create output filename with twigs
        output_file = str(usd_file_path).replace(".usda", "_with_twigs.usda")

        # Write the modified content
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(new_content)

        total_instances = sum(
            len(file_info["instances"]) for file_info in instances_by_file.values()
        )
        print(
            f"  ✅ Added {total_instances} {twig_name} twigs ({len(instances_by_file)} types)"
        )
        print(f"      Output: {Path(output_file).name}")
        return True

    except Exception as e:
        print(f"  ❌ Error adding twigs to {usd_file_path}: {e}")
        return False


def test_twig_integration():
    """Test the twig integration system."""
    print("🧪 Testing Twig Integration System")
    print("=" * 40)

    # Find an existing USD file to test with
    output_dir = Path("data/output/mini_tree_inventory_32632")
    if not output_dir.exists():
        print(f"❌ Output directory not found: {output_dir}")
        print("   Please run the forest generation script first.")
        return

    usd_files = list(output_dir.glob("*.usda"))
    if not usd_files:
        print(f"❌ No USD files found in: {output_dir}")
        print("   Please run the forest generation script first.")
        return

    # Use the first USD file for testing
    test_file = usd_files[0]
    print(f"📄 Testing with file: {test_file.name}")

    # Extract species name from filename
    # Expected format: SpeciesName_LOD_###.usda
    filename_parts = test_file.stem.split("_")
    if len(filename_parts) >= 2:
        species_clean = filename_parts[0]
        # Convert back to readable format
        species_mapping = {
            "SilverFir": "Silver fir",
            "EuropeanBeech": "European beech",
            "ScotsPine": "Scots pine",
            "EuropeanOak": "European oak",
            "PaperBirch": "Paper birch",
            "BlackAlder": "Black alder",
            "GreyPoplar": "Grey poplar",
            "Aspen": "Aspen",
        }
        species_name = species_mapping.get(species_clean, species_clean)
    else:
        species_name = "Silver fir"  # Default fallback

    print(f"🌳 Detected species: {species_name}")

    # Test the configuration
    config = GrowPyConfig()

    # Show available twig types for this species
    twig_files_by_type = config.get_twig_files_by_type(species_name)
    if twig_files_by_type:
        print(f"🌿 Available twig types for {species_name}:")
        for twig_type, files in twig_files_by_type.items():
            print(f"   • {twig_type}: {len(files)} files")
            for file in files[:2]:  # Show first 2 files
                print(f"     - {file.name}")
            if len(files) > 2:
                print(f"     - ... and {len(files) - 2} more")
    else:
        print(f"⚠️  No twig files found for {species_name}")
        return

    # Test the twig addition
    print(f"\n🔧 Adding twigs to {test_file.name}...")
    success = add_twigs_to_usd_file_text_based(test_file, species_name, config)

    if success:
        print(f"✅ Twig integration test completed successfully!")
        output_file = test_file.parent / f"{test_file.stem}_with_twigs.usda"
        print(f"📁 Output file: {output_file}")

        # Show file size comparison
        original_size = test_file.stat().st_size
        output_size = output_file.stat().st_size
        print(
            f"📊 File size: {original_size:,} → {output_size:,} bytes (+{output_size - original_size:,})"
        )

    else:
        print(f"❌ Twig integration test failed!")


if __name__ == "__main__":
    test_twig_integration()
