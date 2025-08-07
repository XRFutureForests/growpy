#!/usr/bin/env python3
"""
Test script to verify USD coordinate transformation functionality.
"""

import sys
from pathlib import Path

# Add the src path to import our twig module
sys.path.append(str(Path(__file__).parent / "src" / "growpy"))

from pxr import Gf, Usd, UsdGeom
from twig import (
    create_y_to_z_transform_matrix,
    transform_points_y_to_z,
    transform_y_up_to_z_up,
)


def test_coordinate_transform():
    """Test the Y-up to Z-up coordinate transformation."""
    print("🧪 Testing coordinate transformation...")

    # Test points
    test_points = [
        (0, 1, 0),  # Y-up becomes Z-up: (0, 0, 1)
        (1, 0, 0),  # X stays X: (1, 0, 0)
        (0, 0, 1),  # Z becomes -Y: (0, -1, 0)
        (1, 2, 3),  # General case: (1, -3, 2)
    ]

    expected_results = [
        (0, 0, 1),
        (1, 0, 0),
        (0, -1, 0),
        (1, -3, 2),
    ]

    for i, (point, expected) in enumerate(zip(test_points, expected_results)):
        result = transform_y_up_to_z_up(point)
        print(f"  Test {i+1}: {point} -> {result} (expected: {expected})")
        assert result == expected, f"Transform failed for {point}"

    print("✅ All coordinate transformation tests passed!")


def test_matrix_creation():
    """Test the transformation matrix creation."""
    print("🧪 Testing transformation matrix...")

    try:
        matrix = create_y_to_z_transform_matrix()
        print(f"✅ Transformation matrix created successfully: {type(matrix)}")

        # Test matrix application on a simple point
        point = Gf.Vec3f(0, 1, 0)  # Y-up
        transformed = matrix.Transform(point)
        print(
            f"  Matrix transform: (0,1,0) -> ({transformed[0]:.3f}, {transformed[1]:.3f}, {transformed[2]:.3f})"
        )

        # Should be approximately (0, 0, 1)
        expected = (0, 0, 1)
        tolerance = 1e-6
        for i, (actual, exp) in enumerate(zip(transformed, expected)):
            assert (
                abs(actual - exp) < tolerance
            ), f"Matrix transform failed at index {i}: {actual} vs {exp}"

        print("✅ Matrix transformation test passed!")

    except Exception as e:
        print(f"❌ Matrix test failed: {e}")
        raise


def test_usd_file_access():
    """Test accessing a real USD file."""
    print("🧪 Testing USD file access...")

    # Try to find a test USD file
    test_file = (
        Path(__file__).parent
        / "data"
        / "output"
        / "mini_tree_inventory_32632"
        / "SilverFir_LOD3_Low_004.usda"
    )

    if not test_file.exists():
        print(f"⚠️  Test file not found: {test_file}")
        print("   Skipping USD file access test")
        return

    try:
        stage = Usd.Stage.Open(str(test_file))
        if not stage:
            print(f"❌ Could not open USD stage from: {test_file}")
            return

        print(f"✅ Successfully opened USD stage")

        # Check metadata
        up_axis = stage.GetMetadata("upAxis")
        print(f"  upAxis: {up_axis}")

        # Try to get the tree mesh
        tree_prim = stage.GetPrimAtPath("/Tree/Tree")
        if tree_prim:
            print(f"✅ Found tree prim: {tree_prim.GetPath()}")

            # Try to access mesh attributes
            mesh = UsdGeom.Mesh(tree_prim)
            points_attr = mesh.GetPointsAttr()
            if points_attr:
                points = points_attr.Get()
                print(f"  Points count: {len(points)}")
                print(f"  First point: {points[0] if points else 'None'}")

        else:
            print("⚠️  Tree prim not found at /Tree/Tree")

        print("✅ USD file access test passed!")

    except Exception as e:
        print(f"❌ USD file access test failed: {e}")
        raise


if __name__ == "__main__":
    print("🔧 Testing USD coordinate transformation system...")
    print("=" * 60)

    test_coordinate_transform()
    print()

    test_matrix_creation()
    print()

    test_usd_file_access()
    print()

    print("🎉 All tests completed successfully!")
    print("💡 The coordinate transformation system is ready to use.")
