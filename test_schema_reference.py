#!/usr/bin/env python3
"""Test script to verify Unreal schema reference in Nanite Assembly USD files."""

from pathlib import Path

from pxr import Sdf, Usd, UsdGeom


def test_schema_reference():
    """Create a minimal Nanite Assembly to test schema reference."""
    output_path = Path("data/output/test_nanite_assembly.usda")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Create new stage
    stage = Usd.Stage.CreateNew(str(output_path))

    # Reference Unreal schema
    schema_path = Path("data/unreal_schema/generatedSchema.usda")
    if schema_path.exists():
        stage.GetRootLayer().subLayerPaths.append(str(schema_path.resolve()))
        print(f"✓ Added schema reference: {schema_path}")
    else:
        print(f"✗ Schema not found: {schema_path}")
        return False

    # Set stage metadata
    UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
    UsdGeom.SetStageMetersPerUnit(stage, 1.0)

    # Create root prim with NaniteAssemblyRootAPI
    root_prim = stage.DefinePrim("/TestAssembly", "Xform")
    stage.SetDefaultPrim(root_prim)

    # Apply API schema
    api_schemas = Sdf.TokenListOp()
    api_schemas.prependedItems = ["NaniteAssemblyRootAPI"]
    root_prim.SetMetadata("apiSchemas", api_schemas)

    # Set mesh type
    root_prim.CreateAttribute(
        "unreal:naniteAssembly:meshType", Sdf.ValueTypeNames.Token, custom=False
    ).Set("staticMesh")

    # Save stage
    stage.GetRootLayer().Save()

    print(f"\n✓ Created test file: {output_path}")
    print("\nFile contents preview:")
    print("-" * 60)
    with open(output_path, "r") as f:
        lines = f.readlines()
        for i, line in enumerate(lines[:20], 1):  # Show first 20 lines
            print(f"{i:3d}: {line}", end="")
    print("-" * 60)

    # Verify subLayers is in the file
    with open(output_path, "r") as f:
        content = f.read()
        if "subLayers" in content and "generatedSchema.usda" in content:
            print("\n✓ Schema reference found in USD file!")
            return True
        else:
            print("\n✗ Schema reference NOT found in USD file!")
            return False


if __name__ == "__main__":
    try:
        success = test_schema_reference()
        exit(0 if success else 1)
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback

        traceback.print_exc()
        exit(1)
        traceback.print_exc()
        exit(1)
