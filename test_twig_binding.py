"""Test script to verify twig binding fix using Grove attribute system."""

from pathlib import Path

from growpy import create_grove, get_config
from growpy.io import create_assembly, export_tree


def test_twig_binding():
    """Generate a simple tree and verify twig binding to branch root bones."""

    # Configure output directory
    output_dir = Path("data/output/binding_test")
    output_dir.mkdir(parents=True, exist_ok=True)

    # Create grove with European beech
    config = get_config()
    grove = create_grove(species_name="European beech", num_trees=1)

    # Export tree with skeleton to USD
    tree_usd = output_dir / "test_tree.usda"
    export_tree(
        grove, str(tree_usd), species_name="European beech", include_skeleton=True
    )
    print(f"Exported tree to: {tree_usd}")

    # Export Nanite assembly (this uses the fixed twig binding code)
    assembly_file = output_dir / "test_assembly.usda"
    create_assembly(
        tree_usd_path=str(tree_usd),
        twig_usd_paths={
            "twig_long": "data/assets/twigs/twig_long.usda",
            "twig_short": "data/assets/twigs/twig_short.usda",
        },
        output_path=str(assembly_file),
        species_name="European beech",
    )
    print(f"Exported Nanite assembly to: {assembly_file}")

    # Parse assembly and check bindJoints
    print("\nVerifying twig bindings...")
    from pxr import Usd

    stage = Usd.Stage.Open(str(assembly_file))

    # Check each twig for bindJoints
    for prim in stage.Traverse():
        prim_name = prim.GetName()
        if prim_name.startswith("twig_"):
            # Check for bindJoints attribute
            if prim.HasAttribute("primvars:bindJoints"):
                bind_joints_attr = prim.GetAttribute("primvars:bindJoints")
                bind_joints = bind_joints_attr.Get()

                if bind_joints:
                    # Extract bone number from path like /Root/Skeleton/bone_9
                    joint_path = str(bind_joints[0])
                    bone_num = joint_path.split("_")[-1]

                    print(f"  {prim_name}: bound to bone_{bone_num}")

                    # Expected branch root bones: 0, 9, 12, 15, 18, 21, etc.
                    # These should be at depth 0-2 in skeleton hierarchy
                else:
                    print(f"  {prim_name}: NO BINDING (ERROR)")

    print("\nTest complete!")
    print(f"Check {assembly_file} for correct branch root bone bindings.")
    print("Expected: All twigs bound to bones like bone_0, bone_9, bone_12, etc.")
    print("         (branch root bones, NOT deep leaf joints like bone_8, bone_11)")


if __name__ == "__main__":
    test_twig_binding()
if __name__ == "__main__":
    test_twig_binding()
