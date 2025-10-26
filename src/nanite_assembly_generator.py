#!/usr/bin/env python3
"""
Nanite Assembly Generator - Clean rebuild from Grove output data.

This script generates a complete Nanite skeletal assembly for Unreal Engine from:
1. Grove geometry dump (tree mesh + attributes)
2. Grove skeleton bones data
3. Twig blend files (extracted to USD)

The assembly follows the Unreal Nanite skeletal mesh workflow with:
- Skeletal tree mesh with bone hierarchy
- Twig prototypes as instanceable references
- PointInstancer for twig placement with skeletal binding

Usage:
    conda activate the-grove
    python src/nanite_assembly_generator.py

Requirements:
    - Blender's bundled USD (accessed via bpy.utils.expose_bundled_modules())
    - Grove output data in data/output/grove_geometry_dump/
    - Twig blend files in data/assets/twigs/WesternRedCedarTwig/
"""

import ast
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Try to import bpy - if available, we can use bundled USD
try:
    import bpy

    if hasattr(bpy.utils, "expose_bundled_modules"):
        bpy.utils.expose_bundled_modules()
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

        USD_AVAILABLE = True
        print("Using Blender's bundled USD library")
    else:
        print("Warning: bpy.utils.expose_bundled_modules() not available")
        USD_AVAILABLE = False
except ImportError:
    # Fallback to system USD if bpy not available
    try:
        from pxr import Gf, Sdf, Usd, UsdGeom, UsdSkel, Vt

        USD_AVAILABLE = True
        print("Using system USD library")
    except ImportError:
        print("Error: USD library not available")
        USD_AVAILABLE = False
        sys.exit(1)


class GroveDataLoader:
    """Loads and parses Grove geometry dump files."""

    def __init__(self, dump_dir: Path):
        self.dump_dir = dump_dir

    def load_points(self) -> List[Tuple[float, float, float]]:
        """Load point coordinates from points.txt."""
        points = []
        with open(self.dump_dir / "points.txt") as f:
            for line in f:
                if line.startswith("#") or ":" not in line:
                    continue
                # Parse: "idx: x, y, z"
                _, coords = line.split(":", 1)
                x, y, z = map(float, coords.strip().split(","))
                points.append((x, y, z))
        return points

    def load_faces(self) -> List[List[int]]:
        """Load face indices from faces.txt."""
        faces = []
        with open(self.dump_dir / "faces.txt") as f:
            for line in f:
                if line.startswith("#") or ":" not in line:
                    continue
                # Parse: "idx: [i1, i2, i3, ...]"
                _, indices = line.split(":", 1)
                face = ast.literal_eval(indices.strip())
                faces.append(face)
        return faces

    def load_uvs(self) -> List[Tuple[float, float]]:
        """Load UV coordinates from uvs.txt."""
        uvs = []
        with open(self.dump_dir / "uvs.txt") as f:
            for line in f:
                if line.startswith("#") or ":" not in line:
                    continue
                # Parse: "idx: (u, v)"
                _, coords = line.split(":", 1)
                uv = ast.literal_eval(coords.strip())
                uvs.append(uv)
        return uvs

    def load_skeleton_bones(self) -> List[Tuple]:
        """Load Grove bone data from skeleton_bones.txt.

        Grove's tag_bone_id() returns 8 fields per bone:
        - Field 0: bool (unknown flag)
        - Field 1: bone_id (int)
        - Field 2: head position (x, y, z) tuple
        - Field 3: tail position (x, y, z) tuple
        - Field 4: radius (float)
        - Field 5: unknown float (possibly length or mass)
        - Field 6: bool (possibly connected flag)
        - Field 7: parent_bone_id (int)

        Returns:
            List of 8-field tuples from Grove
        """
        bones = []
        with open(self.dump_dir / "skeleton_bones.txt") as f:
            reading_bones = False
            for line in f:
                line = line.strip()
                if not line or line.startswith("#"):
                    # Check if we've reached the bone data section
                    if "Format: bone_index:" in line:
                        reading_bones = True
                    continue
                if not reading_bones:
                    continue

                # Parse: "idx: (8-field tuple)"
                if ":" in line:
                    _, bone_data = line.split(":", 1)
                    bone = ast.literal_eval(bone_data.strip())
                    bones.append(bone)
        return bones

    def load_face_twig_attributes(self) -> Dict[str, List[int]]:
        """Load twig placement attributes from face_attributes.txt."""
        twig_attrs = {
            "twig_long": [],
            "twig_short": [],
            "twig_upward": [],
            "twig_dead": [],
        }

        with open(self.dump_dir / "face_attributes.txt") as f:
            current_section = None
            for line in f:
                line = line.strip()
                if line.startswith("## Twig Long"):
                    current_section = "twig_long"
                elif line.startswith("## Twig Short"):
                    current_section = "twig_short"
                elif line.startswith("## Twig Upward"):
                    current_section = "twig_upward"
                elif line.startswith("## Twig Dead"):
                    current_section = "twig_dead"
                elif line.startswith("##"):
                    current_section = None
                elif current_section and line and not line.startswith("#"):
                    # Parse the list
                    try:
                        values = ast.literal_eval(line)
                        twig_attrs[current_section] = values
                        current_section = None  # Move past this section
                    except:
                        continue

        return twig_attrs


class SkeletonBuilder:
    """Builds USD skeleton from Grove bone data."""

    def __init__(self, bones: List[Tuple], points: List[Tuple]):
        self.bones = bones
        self.points = points

    def build_skeleton(
        self, stage: Usd.Stage, skel_path: Sdf.Path
    ) -> Tuple[List[str], List[Gf.Matrix4d], List[Gf.Matrix4d], Dict[int, int]]:
        """Build skeleton hierarchy from Grove bones.

        Args:
            stage: USD stage
            skel_path: Path for skeleton prim

        Returns:
            Tuple of (joint_names, bind_transforms, rest_transforms, bone_to_joint_map)
        """
        # Create skeleton prim
        skel = UsdSkel.Skeleton.Define(stage, skel_path)

        # Root joint at origin
        joints = ["Root"]
        joint_parents = [-1]
        bind_transforms = [Gf.Matrix4d().SetIdentity()]
        rest_transforms = [Gf.Matrix4d().SetIdentity()]

        # Map bone indices to joint indices
        bone_to_joint = {-1: 0}

        # Track joint positions for calculating relative transforms
        world_positions = {0: Gf.Vec3d(0, 0, 0)}
        joint_path_names = {0: "Root"}

        # Process each bone
        # Grove tag_bone_id format (8 fields):
        # [0]: bool flag, [1]: bone_id, [2]: head (x,y,z), [3]: tail (x,y,z),
        # [4]: radius, [5]: float, [6]: bool, [7]: parent_bone_id
        for i, bone in enumerate(self.bones):
            bone_id = bone[1]
            head_pos_tuple = bone[2]
            tail_pos_tuple = bone[3]
            parent_bone_id = bone[7]

            # Convert to Gf.Vec3d
            world_start = Gf.Vec3d(
                head_pos_tuple[0], head_pos_tuple[1], head_pos_tuple[2]
            )
            world_end = Gf.Vec3d(
                tail_pos_tuple[0], tail_pos_tuple[1], tail_pos_tuple[2]
            )

            # Find parent joint
            parent_joint_idx = bone_to_joint.get(parent_bone_id, 0)
            joint_parents.append(parent_joint_idx)

            # Create hierarchical joint name
            parent_path = joint_path_names.get(parent_joint_idx, "Root")
            joint_name = f"{parent_path}/bone_{bone_id}"
            joint_idx = len(joints)
            joints.append(joint_name)
            bone_to_joint[bone_id] = joint_idx
            joint_path_names[joint_idx] = joint_name

            # Calculate position relative to parent
            parent_pos = world_positions.get(parent_joint_idx, Gf.Vec3d(0, 0, 0))
            relative_pos = world_start - parent_pos

            # Calculate bone direction and rotation
            bone_vector = world_end - world_start
            bone_length = bone_vector.GetLength()

            if bone_length > 0.0001:
                bone_dir = bone_vector / bone_length
                default_dir = Gf.Vec3d(0, 0, 1)  # Z-up

                rotation = Gf.Rotation()
                rotation.SetRotateInto(default_dir, bone_dir)
                rotation_matrix = Gf.Matrix3d(rotation.GetQuat())

                transform = Gf.Matrix4d().SetIdentity()
                transform.SetRotate(rotation_matrix)
                transform.SetTranslateOnly(relative_pos)

                bind_transforms.append(transform)
                rest_transforms.append(transform)
            else:
                # Zero-length bone
                transform = Gf.Matrix4d().SetIdentity()
                transform.SetTranslateOnly(relative_pos)
                bind_transforms.append(transform)
                rest_transforms.append(transform)

            # Store position for child bones
            world_positions[joint_idx] = world_start

        # Set skeleton attributes
        skel.CreateJointsAttr(Vt.TokenArray(joints))
        skel.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_transforms))
        skel.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_transforms))

        return joints, bind_transforms, rest_transforms, bone_to_joint


class TwigExtractor:
    """Extracts twigs from blend files using Blender."""

    def __init__(self, twig_dir: Path, output_dir: Path):
        self.twig_dir = twig_dir
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def extract_twigs(self, species_name: str = "WesternRedCedar") -> List[Path]:
        """Extract twigs from blend files to USD.

        Args:
            species_name: Species name for twig files

        Returns:
            List of exported USD file paths
        """
        # First, check if twigs already exist in the twig directory
        existing_twigs = list(self.twig_dir.glob("*_skel.usda"))
        if existing_twigs:
            print(
                f"  Found {len(existing_twigs)} existing twig file(s), using those..."
            )
            for twig_file in existing_twigs:
                print(f"    - {twig_file.name}")
            return existing_twigs

        # If no existing twigs, try to extract from blend files
        blend_files = list(self.twig_dir.glob("*.blend"))
        if not blend_files:
            print(f"  Warning: No blend files found in {self.twig_dir}")
            return []

        print(f"  Extracting {len(blend_files)} twig(s) from blend files...")

        exported_files = []

        for blend_file in blend_files:
            print(f"    Processing: {blend_file.name}")

            # Check if blender is available
            blender_path = shutil.which("blender")
            if not blender_path:
                print(f"    Warning: Blender not found in PATH, skipping extraction")
                break

            # Use Blender to process twig file
            result = subprocess.run(
                [
                    blender_path,
                    "--background",
                    str(blend_file),
                    "--python",
                    str(
                        Path(__file__).parent.parent
                        / "src/growpy/io/blender_twig_processor.py"
                    ),
                    "--",
                    str(blend_file),
                    str(self.output_dir),
                    "usda",
                    species_name,
                    "--clean-export",
                ],
                capture_output=True,
                text=True,
            )

            if result.returncode == 0:
                # Find exported files
                stem = blend_file.stem.lower()
                for file in self.output_dir.glob(f"*{stem}*.usda"):
                    if "_skel" in file.name:
                        exported_files.append(file)
                        print(f"      -> Exported: {file.name}")
            else:
                print(f"      -> Error: {result.stderr[:200]}")

        return exported_files


class NaniteAssemblyBuilder:
    """Builds Nanite skeletal assembly USD."""

    def __init__(
        self,
        output_path: Path,
        tree_name: str = "WesternRedCedar",
    ):
        self.output_path = output_path
        self.tree_name = tree_name
        self.stage = None

    def create_assembly(
        self,
        points: List[Tuple],
        faces: List[List[int]],
        uvs: List[Tuple],
        joints: List[str],
        bind_transforms: List[Gf.Matrix4d],
        rest_transforms: List[Gf.Matrix4d],
        twig_files: List[Path],
        twig_attrs: Dict,
    ):
        """Create complete Nanite assembly with tree mesh and twigs."""

        # Create USD stage
        self.stage = Usd.Stage.CreateNew(str(self.output_path))
        UsdGeom.SetStageUpAxis(self.stage, UsdGeom.Tokens.z)
        self.stage.SetMetadata("metersPerUnit", 1.0)

        # Create assembly root
        assembly_path = Sdf.Path(f"/{self.tree_name}Assembly")
        assembly = UsdGeom.Xform.Define(self.stage, assembly_path)
        assembly_prim = assembly.GetPrim()

        # Add Nanite assembly API
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["NaniteAssemblyRootAPI", "GeomModelAPI"]
        assembly_prim.SetMetadata("apiSchemas", api_schemas)
        assembly_prim.SetMetadata("kind", "assembly")

        # Set mesh type
        assembly_prim.CreateAttribute(
            "unreal:naniteAssembly:meshType", Sdf.ValueTypeNames.Token
        ).Set("skeletalMesh")

        # Create SkelRoot for tree
        skel_root_path = assembly_path.AppendChild("TreeMesh")
        skel_root = UsdSkel.Root.Define(self.stage, skel_root_path)

        # Create skeleton
        skel_path = skel_root_path.AppendChild("TreeSkel")
        skel = UsdSkel.Skeleton.Define(self.stage, skel_path)
        skel.CreateJointsAttr(Vt.TokenArray(joints))
        skel.CreateBindTransformsAttr(Vt.Matrix4dArray(bind_transforms))
        skel.CreateRestTransformsAttr(Vt.Matrix4dArray(rest_transforms))

        # Link assembly to skeleton
        assembly_prim.CreateRelationship("unreal:naniteAssembly:skeleton").SetTargets(
            [skel_path]
        )

        # Create tree trunk mesh
        trunk_path = skel_root_path.AppendChild("Trunk")
        trunk_mesh = UsdGeom.Mesh.Define(self.stage, trunk_path)

        # Convert faces to USD format (face vertex counts and indices)
        face_vertex_counts = [len(face) for face in faces]
        face_vertex_indices = [idx for face in faces for idx in face]

        # Set mesh geometry
        trunk_mesh.CreatePointsAttr([Gf.Vec3f(p[0], p[1], p[2]) for p in points])
        trunk_mesh.CreateFaceVertexCountsAttr(face_vertex_counts)
        trunk_mesh.CreateFaceVertexIndicesAttr(face_vertex_indices)

        # Set normals (calculate simple normals)
        normals = self._calculate_normals(points, faces)
        trunk_mesh.CreateNormalsAttr(normals)
        trunk_mesh.SetNormalsInterpolation(UsdGeom.Tokens.faceVarying)

        # Set UVs
        if uvs:
            uv_primvar = UsdGeom.PrimvarsAPI(trunk_mesh).CreatePrimvar(
                "st", Sdf.ValueTypeNames.TexCoord2fArray
            )
            uv_primvar.Set([Gf.Vec2f(uv[0], uv[1]) for uv in uvs])
            uv_primvar.SetInterpolation(UsdGeom.Tokens.faceVarying)

        # Set part attribute
        part_primvar = UsdGeom.PrimvarsAPI(trunk_mesh).CreatePrimvar(
            "part", Sdf.ValueTypeNames.Token
        )
        part_primvar.Set("trunk")

        # Enable double-sided rendering
        trunk_mesh.CreateDoubleSidedAttr(True)

        # Bind mesh to skeleton
        trunk_prim = trunk_mesh.GetPrim()
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["SkelBindingAPI"]
        trunk_prim.SetMetadata("apiSchemas", api_schemas)

        skel_rel = trunk_prim.CreateRelationship("skel:skeleton")
        skel_rel.SetTargets([skel_path])

        # Simple skinning: bind all vertices to root joint
        num_points = len(points)
        joint_indices = [0] * num_points
        joint_weights = [1.0] * num_points

        primvars_api = UsdGeom.PrimvarsAPI(trunk_prim)

        joint_indices_primvar = primvars_api.CreatePrimvar(
            "skel:jointIndices",
            Sdf.ValueTypeNames.IntArray,
            UsdGeom.Tokens.vertex,
        )
        joint_indices_primvar.Set(joint_indices)
        joint_indices_primvar.SetElementSize(1)

        joint_weights_primvar = primvars_api.CreatePrimvar(
            "skel:jointWeights",
            Sdf.ValueTypeNames.FloatArray,
            UsdGeom.Tokens.vertex,
        )
        joint_weights_primvar.Set(joint_weights)
        joint_weights_primvar.SetElementSize(1)

        print(f"  Created tree mesh with {len(points)} vertices, {len(faces)} faces")

        # Create twig prototypes
        if twig_files:
            self._create_twig_prototypes(assembly_path, twig_files)

            # Create twig instances
            self._create_twig_instances(
                assembly_path, points, faces, twig_attrs, joints
            )

        # Set default prim
        self.stage.SetDefaultPrim(assembly_prim)

        # Save
        self.stage.Save()
        print(f"\nSaved Nanite assembly: {self.output_path}")

    def _calculate_normals(
        self, points: List[Tuple], faces: List[List[int]]
    ) -> List[Gf.Vec3f]:
        """Calculate face-varying normals."""
        normals = []
        for face in faces:
            if len(face) < 3:
                # Degenerate face, use up vector
                for _ in face:
                    normals.append(Gf.Vec3f(0, 0, 1))
                continue

            # Calculate face normal from first three vertices
            p0 = Gf.Vec3f(points[face[0]][0], points[face[0]][1], points[face[0]][2])
            p1 = Gf.Vec3f(points[face[1]][0], points[face[1]][1], points[face[1]][2])
            p2 = Gf.Vec3f(points[face[2]][0], points[face[2]][1], points[face[2]][2])

            v1 = p1 - p0
            v2 = p2 - p0
            normal = Gf.Cross(v1, v2)

            length = normal.GetLength()
            if length > 0.0001:
                normal = normal / length
            else:
                normal = Gf.Vec3f(0, 0, 1)

            # Use same normal for all vertices in face
            for _ in face:
                normals.append(normal)

        return normals

    def _create_twig_prototypes(self, assembly_path: Sdf.Path, twig_files: List[Path]):
        """Create twig prototype references."""
        prototypes_path = assembly_path.AppendChild("TwigPrototypes")
        prototypes_scope = UsdGeom.Scope.Define(self.stage, prototypes_path)

        print(f"\n  Creating twig prototypes...")

        for i, twig_file in enumerate(twig_files):
            # Create prototype xform
            proto_name = twig_file.stem.replace("_skel", "")
            proto_path = prototypes_path.AppendChild(proto_name)
            proto_xform = UsdGeom.Xform.Define(self.stage, proto_path)
            proto_prim = proto_xform.GetPrim()

            # Make instanceable
            proto_prim.SetInstanceable(True)

            # Add reference to twig USD
            proto_prim.GetReferences().AddReference(str(twig_file))

            print(f"    Prototype {i}: {proto_name} -> {twig_file.name}")

    def _create_twig_instances(
        self,
        assembly_path: Sdf.Path,
        points: List[Tuple],
        faces: List[List[int]],
        twig_attrs: Dict,
        joints: List[str],
    ):
        """Create twig instances using PointInstancer."""

        # Find twig placement faces
        twig_faces = []
        for face_idx, is_twig in enumerate(twig_attrs.get("twig_long", [])):
            if is_twig:
                twig_faces.append(("long", face_idx))
        for face_idx, is_twig in enumerate(twig_attrs.get("twig_short", [])):
            if is_twig:
                twig_faces.append(("short", face_idx))

        if not twig_faces:
            print("  No twig placement faces found")
            return

        print(f"\n  Creating {len(twig_faces)} twig instance(s)...")

        # Create point instancer
        instancer_path = assembly_path.AppendChild("TwigInstances")
        instancer = UsdGeom.PointInstancer.Define(self.stage, instancer_path)
        instancer_prim = instancer.GetPrim()

        # Add Nanite skeletal binding API
        api_schemas = Sdf.TokenListOp()
        api_schemas.prependedItems = ["NaniteAssemblySkelBindingAPI"]
        instancer_prim.SetMetadata("apiSchemas", api_schemas)

        # Calculate twig positions and orientations
        positions = []
        orientations = []
        proto_indices = []
        bind_joints = []
        bind_weights = []

        for twig_type, face_idx in twig_faces:
            if face_idx >= len(faces):
                continue

            face = faces[face_idx]
            if len(face) < 3:
                continue

            # Calculate face center
            face_center = Gf.Vec3f(0, 0, 0)
            for idx in face:
                if idx < len(points):
                    p = points[idx]
                    face_center += Gf.Vec3f(p[0], p[1], p[2])
            face_center /= len(face)

            positions.append(face_center)
            orientations.append(Gf.Quath(1, 0, 0, 0))  # Identity quaternion
            proto_indices.append(0 if twig_type == "long" else 1)

            # Bind to root joint (simplified)
            bind_joints.append("Root")
            bind_weights.append(1.0)

        # Set instancer attributes
        instancer.CreatePositionsAttr(positions)
        instancer.CreateOrientationsAttr(orientations)
        instancer.CreateProtoIndicesAttr(proto_indices)
        instancer.CreateScalesAttr([Gf.Vec3f(1, 1, 1)] * len(positions))

        # Set prototype relationships
        prototypes_path = assembly_path.AppendChild("TwigPrototypes")
        prototype_paths = []
        for child in self.stage.GetPrimAtPath(prototypes_path).GetChildren():
            prototype_paths.append(child.GetPath())

        instancer.CreatePrototypesRel().SetTargets(prototype_paths[:2])

        # Set skeletal binding
        primvars_api = UsdGeom.PrimvarsAPI(instancer_prim)

        bind_joints_primvar = primvars_api.CreatePrimvar(
            "unreal:naniteAssembly:bindJoints",
            Sdf.ValueTypeNames.TokenArray,
        )
        bind_joints_primvar.Set(bind_joints)
        bind_joints_primvar.SetElementSize(1)

        bind_weights_primvar = primvars_api.CreatePrimvar(
            "unreal:naniteAssembly:bindJointWeights",
            Sdf.ValueTypeNames.FloatArray,
        )
        bind_weights_primvar.Set(bind_weights)
        bind_weights_primvar.SetElementSize(1)

        print(f"    Placed {len(positions)} twig(s)")


def main():
    """Main execution."""
    print("=" * 80)
    print("Nanite Assembly Generator - Clean Rebuild")
    print("=" * 80)

    # Configuration
    grove_dump_dir = Path("data/output/grove_geometry_dump")
    twig_blend_dir = Path("data/assets/twigs/WesternRedCedarTwig")
    twig_output_dir = Path("data/output/clean_demo/twigs")
    assembly_output = Path("data/output/clean_demo/western_red_cedar_assembly.usda")

    # Create output directory
    assembly_output.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Load Grove data
    print("\n[1/4] Loading Grove geometry dump...")
    loader = GroveDataLoader(grove_dump_dir)

    points = loader.load_points()
    faces = loader.load_faces()
    uvs = loader.load_uvs()
    bones = loader.load_skeleton_bones()
    twig_attrs = loader.load_face_twig_attributes()

    print(f"  Loaded: {len(points)} points, {len(faces)} faces")
    print(f"  Loaded: {len(bones)} bones")
    print(f"  Loaded: {sum(twig_attrs.values(), [])} twig placement faces")

    # Step 2: Build skeleton
    print("\n[2/4] Building skeleton from Grove bones...")
    skel_builder = SkeletonBuilder(bones, points)

    # Create temporary stage for skeleton building
    temp_stage = Usd.Stage.CreateInMemory()
    skel_path = Sdf.Path("/TempSkel")

    joints, bind_transforms, rest_transforms, bone_to_joint = (
        skel_builder.build_skeleton(temp_stage, skel_path)
    )

    print(f"  Built skeleton: {len(joints)} joints")

    # Step 3: Extract twigs
    print("\n[3/4] Extracting twigs from blend files...")
    twig_extractor = TwigExtractor(twig_blend_dir, twig_output_dir)
    twig_files = twig_extractor.extract_twigs("WesternRedCedar")

    if not twig_files:
        print("  Warning: No twigs extracted, continuing with tree only")

    # Step 4: Build Nanite assembly
    print("\n[4/4] Building Nanite assembly...")
    assembly_builder = NaniteAssemblyBuilder(
        assembly_output, tree_name="WesternRedCedar"
    )

    assembly_builder.create_assembly(
        points,
        faces,
        uvs,
        joints,
        bind_transforms,
        rest_transforms,
        twig_files,
        twig_attrs,
    )

    print("\n" + "=" * 80)
    print("Assembly generation complete!")
    print(f"Output: {assembly_output}")
    print("=" * 80)


if __name__ == "__main__":
    main()
