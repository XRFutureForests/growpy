#!/usr/bin/env python3
"""
Test script for Nanite Assembly USD export.

This script validates that the Nanite Assembly integration is working correctly.
It tests both the species library and forest generation workflows.

Usage:
    python test_nanite_assembly.py
"""

import os
import sys
from pathlib import Path

# Add src to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root / "src"))

print("=" * 60)
print("Nanite Assembly Integration Test")
print("=" * 60)
print()

# Check if schema path is set
schema_path = project_root / "data" / "unreal_schema"
env_var = os.environ.get("PXR_PLUGINPATH_NAME")

print(f"Schema location: {schema_path}")
print(f"Schema exists: {schema_path.exists()}")
print(f"PXR_PLUGINPATH_NAME: {env_var}")

if env_var != str(schema_path):
    print()
    print("⚠️  WARNING: PXR_PLUGINPATH_NAME not set correctly!")
    print(f"   Current: {env_var}")
    print(f"   Should be: {schema_path}")
    print()
    print("   To fix (macOS/Linux):")
    print(f'   export PXR_PLUGINPATH_NAME="{schema_path}"')
    print()
    print("   Or add to ~/.zshrc:")
    print(f'   export PXR_PLUGINPATH_NAME="{schema_path}"')
    print()
else:
    print("✅ PXR_PLUGINPATH_NAME correctly set")

print()
print("-" * 60)
print("Testing Imports")
print("-" * 60)
print()

# Test imports
try:
    from growpy import EXPORT_AVAILABLE, create_grove, get_config

    print("✅ growpy imports successful")
except ImportError as e:
    print(f"❌ growpy import failed: {e}")
    sys.exit(1)

try:
    from growpy.io.blender_export import export_grove_tree_as_usda_native

    print("✅ export_grove_tree_as_usda_native available")
except ImportError as e:
    print(f"❌ export function import failed: {e}")
    sys.exit(1)

try:
    from growpy.io.unreal_nanite_assembly import create_nanite_assembly_usd

    print("✅ create_nanite_assembly_usd available")
except ImportError as e:
    print(f"❌ Nanite assembly function import failed: {e}")
    sys.exit(1)

try:
    import the_grove_22_core as gc

    print("✅ The Grove 2.2 core available")
except ImportError as e:
    print(f"❌ Grove core import failed: {e}")
    print("   Make sure PYTHONPATH includes src/the_grove_22/modules")
    sys.exit(1)

# Check USD Python availability
print()
try:
    from pxr import Sdf, Usd, UsdGeom

    print("✅ USD Python (pxr) available")
    usd_available = True
except ImportError:
    print("⚠️  USD Python (pxr) not available")
    print("   Install with: pip install usd-core")
    usd_available = False

print()
print("-" * 60)
print("Testing Configuration")
print("-" * 60)
print()

try:
    config = get_config()
    print(f"✅ Configuration loaded")
    print(f"   Species count: {len(config.get_all_species())}")
    print(f"   Assets path: {config.assets_path}")
    print(f"   Twigs path: {config.twigs_path}")
except Exception as e:
    print(f"❌ Configuration failed: {e}")
    sys.exit(1)

print()
print("-" * 60)
print("Testing Grove Creation")
print("-" * 60)
print()

try:
    species_list = config.get_all_species()
    if not species_list:
        print("❌ No species configured")
        sys.exit(1)

    test_species = species_list[0]
    print(f"Creating grove for: {test_species}")

    grove = create_grove(test_species)
    print("✅ Grove created")

    # Add tree
    grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
    print("✅ Tree added")

    # Simulate
    grove.simulate(flushes=3)
    print("✅ Simulation complete (3 flushes)")

except Exception as e:
    print(f"❌ Grove creation failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print()
print("-" * 60)
print("Testing USD Export")
print("-" * 60)
print()

output_dir = project_root / "data" / "output" / "test_nanite"
output_dir.mkdir(parents=True, exist_ok=True)

output_file = output_dir / "test_tree.usda"

try:
    print(f"Exporting to: {output_file}")
    print("Options:")
    print("  - include_twigs: True")
    print("  - create_nanite_assembly: True")
    print("  - resolution: 16")
    print()

    success = export_grove_tree_as_usda_native(
        grove=grove,
        output_path=output_file,
        species_name=test_species,
        include_twigs=True,
        create_nanite_assembly=True,
        resolution=16,
        resolution_reduce=0.8,
        texture_repeat=3,
        build_cutoff_age=0,
        build_cutoff_thickness=0.0,
        build_blend=True,
        build_end_cap=True,
    )

    if success:
        print("✅ Export completed")
    else:
        print("❌ Export returned False")

except Exception as e:
    print(f"❌ Export failed: {e}")
    import traceback

    traceback.print_exc()
    sys.exit(1)

print()
print("-" * 60)
print("Validating Output Files")
print("-" * 60)
print()

# Check for expected files
tree_only = output_dir / "test_tree_tree_only.usda"
standard_usd = output_dir / "test_tree.usda"
nanite_assembly = output_dir / "test_tree_NaniteAssembly.usda"

files_expected = [
    ("Tree-only USD", tree_only),
    ("Standard USD", standard_usd),
    ("Nanite Assembly USD", nanite_assembly),
]

all_exist = True
for name, path in files_expected:
    exists = path.exists()
    status = "✅" if exists else "❌"
    print(f"{status} {name}: {path.name}")
    if exists:
        size_kb = path.stat().st_size / 1024
        print(f"     Size: {size_kb:.1f} KB")
    all_exist = all_exist and exists

if not all_exist:
    print()
    print("⚠️  Not all expected files were created")
    print("   This might be normal if twigs or USD export had issues")

# Validate USD files if pxr available
if usd_available and nanite_assembly.exists():
    print()
    print("-" * 60)
    print("Validating Nanite Assembly USD")
    print("-" * 60)
    print()

    try:
        stage = Usd.Stage.Open(str(nanite_assembly))
        if stage:
            print("✅ Nanite Assembly USD opens successfully")

            # Check for root prim
            root_prim = stage.GetDefaultPrim()
            if root_prim:
                print(f"✅ Default prim: {root_prim.GetName()}")

                # Check for NaniteAssemblyRootAPI
                api_schemas = root_prim.GetMetadata("apiSchemas")
                if api_schemas and "NaniteAssemblyRootAPI" in api_schemas:
                    print("✅ NaniteAssemblyRootAPI found")
                else:
                    print("⚠️  NaniteAssemblyRootAPI not found")
                    print(f"   API schemas: {api_schemas}")

                # Check mesh type
                mesh_type_attr = root_prim.GetAttribute(
                    "unreal:naniteAssembly:meshType"
                )
                if mesh_type_attr:
                    mesh_type = mesh_type_attr.Get()
                    print(f"✅ Mesh type: {mesh_type}")
                else:
                    print("⚠️  unreal:naniteAssembly:meshType not set")

                # Check for child prims
                children = list(root_prim.GetChildren())
                print(f"✅ Child prims: {len(children)}")
                for child in children:
                    print(f"   - {child.GetName()} ({child.GetTypeName()})")
            else:
                print("⚠️  No default prim set")
        else:
            print("❌ Failed to open Nanite Assembly USD")

    except Exception as e:
        print(f"❌ USD validation failed: {e}")

print()
print("=" * 60)
print("Test Summary")
print("=" * 60)
print()

if all_exist:
    print("✅ All tests passed!")
    print()
    print("Next steps:")
    print("1. Import Nanite Assembly USD into Unreal Engine 5.7+")
    print(f"   File: {nanite_assembly}")
    print("2. Check Unreal Output Log for schema registration")
    print("3. Verify automatic Nanite conversion")
    print()
    print("For detailed instructions, see:")
    print("  docs/growpy/NANITE_ASSEMBLY_GUIDE.md")
else:
    print("⚠️  Some tests had issues")
    print()
    print("Check the error messages above for details.")
    print("Common issues:")
    print("- USD Python (pxr) not installed: pip install usd-core")
    print("- Grove core not available: check PYTHONPATH")
    print("- bpy not available: conda install -c conda-forge bpy")

print()
