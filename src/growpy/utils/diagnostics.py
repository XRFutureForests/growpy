"""Diagnostic utilities for inspecting Grove model data.

Provides a complete geometry and attribute dump for debugging and exploring
Grove API output. Useful when integrating new tree species or investigating
export artefacts.
"""

import logging
from pathlib import Path
from typing import Any, List, Optional

logger = logging.getLogger(__name__)


def dump_grove_data(
    models: List[Any],
    skeletons: List[Any],
    bones_trees: List[List],
    root_models: Optional[List[Any]] = None,
    output_dir: Optional[Path] = None,
) -> Path:
    """Export all geometry and attribute data for each tree to text files.

    Writes one subdirectory per tree under output_dir with files covering:
    - tree_points.txt / tree_faces.txt / tree_uvs.txt
    - tree_points_flat.txt / tree_uvs_flat.txt / tree_directions_flat.txt
    - tree_face_attributes.txt / tree_point_attributes.txt
    - skeleton_data.txt / skeleton_bones.txt
    - roots_*.txt (if root_models provided)

    Args:
        models: List of tree model objects from grove.build_models()
        skeletons: List of skeleton objects from grove.build_skeletons()
        bones_trees: Per-tree bone lists from grove.tag_bone_id() (split by tree)
        root_models: Optional list of root model objects from grove.build_roots()
        output_dir: Directory to write files (default: data/output/grove_dump)

    Returns:
        Path to the output directory
    """
    if output_dir is None:
        output_dir = Path("data/output/grove_dump")

    for tree_idx, (model, skeleton, bones) in enumerate(
        zip(models, skeletons, bones_trees)
    ):
        tree_dir = output_dir / f"tree_{tree_idx}"
        tree_dir.mkdir(parents=True, exist_ok=True)

        _write_geometry(tree_dir, model)
        _write_face_attributes(tree_dir, model)
        _write_point_attributes(tree_dir, model)
        _write_skeleton(tree_dir, skeleton, bones)

        if root_models is not None and tree_idx < len(root_models):
            _write_root_data(tree_dir, root_models[tree_idx])

        logger.info(
            "Tree %d: %d pts, %d faces, %d skeleton bones -> %s",
            tree_idx,
            len(model.points),
            len(model.faces),
            len(bones),
            tree_dir,
        )

    return output_dir


def _write_geometry(tree_dir: Path, model: Any) -> None:
    with open(tree_dir / "tree_points.txt", "w") as f:
        f.write("# Point coordinates (x, y, z)\n")
        for i, p in enumerate(model.points):
            f.write(f"{i}: {p.x}, {p.y}, {p.z}\n")

    with open(tree_dir / "tree_faces.txt", "w") as f:
        f.write("# Face definitions (point indices)\n")
        for i, face in enumerate(model.faces):
            f.write(f"{i}: {face}\n")

    with open(tree_dir / "tree_uvs.txt", "w") as f:
        f.write("# UV coordinates (u, v)\n")
        for i, uv in enumerate(model.uvs):
            f.write(f"{i}: {uv}\n")

    with open(tree_dir / "tree_points_flat.txt", "w") as f:
        f.write("# Flat point array [x1,y1,z1,x2,y2,z2,...]\n")
        f.write(str(model.get_points_flat()))

    with open(tree_dir / "tree_uvs_flat.txt", "w") as f:
        f.write("# Flat UV array [u1,v1,u2,v2,...]\n")
        f.write(str(model.get_uvs_flat()))

    with open(tree_dir / "tree_directions_flat.txt", "w") as f:
        f.write("# Flat direction vectors\n")
        f.write(str(model.get_directions_flat()))


def _write_face_attributes(tree_dir: Path, model: Any) -> None:
    with open(tree_dir / "tree_face_attributes.txt", "w") as f:
        f.write("# Face Attributes\n\n")

        face_tree_id = getattr(model, "face_attribute_tree_id", None)
        if face_tree_id:
            f.write(f"## Tree ID\n{face_tree_id}\n\n")

        for attr, label in [
            ("face_attribute_branch_id", "Branch ID"),
            ("face_attribute_branch_id_parent", "Branch Parent ID"),
            ("face_attribute_twig_long", "Twig Long"),
            ("face_attribute_twig_short", "Twig Short"),
            ("face_attribute_twig_upward", "Twig Upward"),
            ("face_attribute_twig_dead", "Twig Dead"),
            ("face_attribute_dead", "Dead Faces"),
            ("face_attribute_end", "End Faces"),
            ("face_attribute_direction", "Face Direction"),
        ]:
            value = getattr(model, attr, None)
            if value is not None:
                f.write(f"## {label}\n{value}\n\n")


def _write_point_attributes(tree_dir: Path, model: Any) -> None:
    with open(tree_dir / "tree_point_attributes.txt", "w") as f:
        f.write("# Point Attributes\n\n")

        for attr, label in [
            ("point_attribute_age", "Age"),
            ("point_attribute_mass", "Mass"),
            ("point_attribute_thickness", "Thickness"),
            ("point_attribute_orientation", "Orientation"),
            ("point_attribute_pitch", "Pitch"),
            ("point_attribute_vigor", "Vigor"),
            ("point_attribute_shade", "Shade"),
            ("point_attribute_photosynthesis", "Photosynthesis"),
            ("point_attribute_bone_id", "Bone ID"),
            ("point_attribute_skeleton_joint_id", "Skeleton Joint ID"),
        ]:
            value = getattr(model, attr, None)
            if value is not None:
                f.write(f"## {label}\n{value}\n\n")


def _write_skeleton(tree_dir: Path, skeleton: Any, bones: List) -> None:
    with open(tree_dir / "skeleton_data.txt", "w") as f:
        f.write("# Skeleton Data\n\n")
        f.write("## Points\n")
        for i, p in enumerate(skeleton.points):
            f.write(f"{i}: {p}\n")
        f.write("\n## Poly Lines\n")
        for i, line in enumerate(skeleton.poly_lines):
            f.write(f"{i}: {line}\n")
        f.write(f"\n## Location\n{skeleton.location}\n\n")
        f.write(f"## Branch ID\n{skeleton.face_attribute_branch_id}\n\n")
        f.write(f"## Point Age\n{skeleton.point_attribute_age}\n\n")
        f.write(f"## Point Mass\n{skeleton.point_attribute_mass}\n\n")
        f.write(f"## Point Radius\n{skeleton.point_attribute_radius}\n")

    with open(tree_dir / "skeleton_bones.txt", "w") as f:
        f.write("# Skeleton Bones\n\n")
        f.write(
            "# Format: bone_id: (is_tree_root, parent_bone_id, start, end, "
            "radius, mass, is_branch_root, branch_id)\n\n"
        )
        f.write(f"# Total bones: {len(bones)}\n\n")
        for i, bone in enumerate(bones):
            f.write(f"{i}: {bone}\n")


def _write_root_data(tree_dir: Path, root_model: Any) -> None:
    with open(tree_dir / "roots_points.txt", "w") as f:
        f.write("# Root point coordinates (x, y, z)\n")
        for i, p in enumerate(root_model.points):
            f.write(f"{i}: {p.x}, {p.y}, {p.z}\n")

    with open(tree_dir / "roots_faces.txt", "w") as f:
        f.write("# Root face definitions (point indices)\n")
        for i, face in enumerate(root_model.faces):
            f.write(f"{i}: {face}\n")

    with open(tree_dir / "roots_face_attributes.txt", "w") as f:
        f.write("# Root Face Attributes\n\n")
        for attr, label in [
            ("face_attribute_branch_id", "Branch ID"),
            ("face_attribute_branch_id_parent", "Branch Parent ID"),
            ("face_attribute_dead", "Dead Faces"),
            ("face_attribute_end", "End Faces"),
            ("face_attribute_direction", "Face Direction"),
        ]:
            value = getattr(root_model, attr, None)
            if value is not None:
                f.write(f"## {label}\n{value}\n\n")

    with open(tree_dir / "roots_point_attributes.txt", "w") as f:
        f.write("# Root Point Attributes\n\n")
        for attr, label in [
            ("point_attribute_age", "Age"),
            ("point_attribute_mass", "Mass"),
            ("point_attribute_thickness", "Thickness"),
            ("point_attribute_bone_id", "Bone ID"),
        ]:
            value = getattr(root_model, attr, None)
            if value is not None:
                f.write(f"## {label}\n{value}\n\n")
