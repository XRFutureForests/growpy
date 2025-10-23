# %% IMPORTS
import re
from pathlib import Path

import numpy as np

# %% CONFIGURATION
dump_dir = Path("data/output/grove_geometry_dump")

# %% HELPER FUNCTIONS


def parse_vector_list(text):
    """Parse a list of vectors from text."""
    vectors = []
    for line in text.split("\n"):
        if line.startswith("#") or not line.strip():
            continue
        # Format: "0: x, y, z" or "(x, y, z)"
        if ":" in line:
            coords_str = line.split(":", 1)[1].strip()
        else:
            coords_str = line.strip()

        # Remove parentheses if present
        coords_str = coords_str.strip("()")

        # Split by comma and convert to floats
        try:
            coords = [float(x.strip()) for x in coords_str.split(",")]
            if len(coords) == 3:
                vectors.append(coords)
        except ValueError:
            continue

    return np.array(vectors)


def parse_flat_array(text):
    """Parse a flat array of numbers from text."""
    # Remove brackets and split by comma
    text = text.strip("[]")
    numbers = [float(x.strip()) for x in text.split(",") if x.strip()]
    return np.array(numbers)


def parse_int_list(text):
    """Parse a list of integers from text."""
    text = text.strip("[]")
    numbers = [int(x.strip()) for x in text.split(",") if x.strip()]
    return np.array(numbers)


def parse_bool_list(text):
    """Parse a list of boolean values from text."""
    text = text.strip("[]")
    values = []
    for x in text.split(","):
        x = x.strip()
        if x:
            if x == "True":
                values.append(True)
            elif x == "False":
                values.append(False)
            else:
                values.append(int(x))  # Fallback to int if not True/False
    return np.array(values)


def parse_face_list(text):
    """Parse a list of boolean values from text."""
    text = text.strip("[]")
    values = []
    for x in text.split(","):
        x = x.strip()
        if x:
            if x == "True":
                values.append(True)
            elif x == "False":
                values.append(False)
            else:
                values.append(int(x))  # Fallback to int if not True/False
    return np.array(values)


def parse_face_list(text):
    """Parse face indices from text file."""
    faces = []
    for line in text.split("\n"):
        if line.startswith("#") or not line.strip():
            continue
        # Format: "0: [idx1, idx2, idx3, ...]"
        if ":" in line:
            face_str = line.split(":", 1)[1].strip()
            face_str = face_str.strip("[]")
            indices = [int(x.strip()) for x in face_str.split(",") if x.strip()]
            faces.append(indices)
    return faces


# %% LOAD GROVE API DATA


def load_grove_data():
    """Load data extracted directly from Grove API."""
    data = {}

    # Load points
    with open(dump_dir / "points.txt", "r") as f:
        text = f.read()
        data["points"] = parse_vector_list(text)

    # Load points_flat
    with open(dump_dir / "points_flat.txt", "r") as f:
        text = f.read()
        text = text.split("\n", 1)[1]  # Skip header
        data["points_flat"] = parse_flat_array(text)

    # Load faces
    with open(dump_dir / "faces.txt", "r") as f:
        text = f.read()
        data["faces"] = parse_face_list(text)

    # Load UVs
    with open(dump_dir / "uvs.txt", "r") as f:
        text = f.read()
        # Parse UVs with the same method as vectors (2D coordinates)
        uvs = []
        for line in text.split("\n"):
            if line.startswith("#") or not line.strip():
                continue
            if ":" in line:
                coords_str = line.split(":", 1)[1].strip()
            else:
                coords_str = line.strip()

            coords_str = coords_str.strip("()")
            try:
                coords = [float(x.strip()) for x in coords_str.split(",")]
                if len(coords) == 2:
                    uvs.append(coords)
            except ValueError:
                continue
        data["uvs"] = np.array(uvs)

    # Load uvs_flat
    with open(dump_dir / "uvs_flat.txt", "r") as f:
        text = f.read()
        text = text.split("\n", 1)[1]  # Skip header
        data["uvs_flat"] = parse_flat_array(text)

    # Load skeleton data
    with open(dump_dir / "skeleton.txt", "r") as f:
        text = f.read()

        # Parse skeleton points
        points_section = re.search(r"## Points\n(.*?)\n\n", text, re.DOTALL)
        if points_section:
            skeleton_points = parse_vector_list(points_section.group(1))
            data["skeleton_points"] = skeleton_points

        # Parse poly lines
        lines_section = re.search(r"## Poly Lines\n(.*?)\n\n", text, re.DOTALL)
        if lines_section:
            poly_lines = []
            for line in lines_section.group(1).split("\n"):
                if ":" in line and not line.startswith("#"):
                    indices_str = line.split(":", 1)[1].strip().strip("[]")
                    indices = [
                        int(x.strip()) for x in indices_str.split(",") if x.strip()
                    ]
                    poly_lines.append(indices)
            data["skeleton_poly_lines"] = poly_lines

        # Parse skeleton attributes
        branch_id_section = re.search(r"## Branch ID\n(.*?)\n\n", text, re.DOTALL)
        if branch_id_section:
            data["skeleton_branch_id"] = parse_int_list(branch_id_section.group(1))

        point_age_section = re.search(r"## Point Age\n(.*?)\n\n", text, re.DOTALL)
        if point_age_section:
            data["skeleton_point_age"] = parse_flat_array(point_age_section.group(1))

        point_mass_section = re.search(r"## Point Mass\n(.*?)\n\n", text, re.DOTALL)
        if point_mass_section:
            data["skeleton_point_mass"] = parse_flat_array(point_mass_section.group(1))

        point_radius_section = re.search(
            r"## Point Radius\n(.*?)(\n\n|$)", text, re.DOTALL
        )
        if point_radius_section:
            data["skeleton_point_radius"] = parse_flat_array(
                point_radius_section.group(1)
            )

    # Load skeleton bones (advanced)
    bones_file = dump_dir / "skeleton_bones.txt"
    if bones_file.exists():
        with open(bones_file, "r") as f:
            text = f.read()
            bones = []
            for line in text.split("\n"):
                if line.strip() and not line.startswith("#") and ":" in line:
                    bone_str = line.split(":", 1)[1].strip()
                    bones.append(bone_str)
            data["skeleton_bones"] = bones

    # Load face attributes
    face_attrs_file = dump_dir / "face_attributes.txt"
    if face_attrs_file.exists():
        with open(face_attrs_file, "r") as f:
            text = f.read()

            # Parse each attribute section
            twig_long_section = re.search(r"## Twig Long\n(.*?)\n\n", text, re.DOTALL)
            if twig_long_section:
                data["face_twig_long"] = parse_bool_list(twig_long_section.group(1))

            twig_short_section = re.search(r"## Twig Short\n(.*?)\n\n", text, re.DOTALL)
            if twig_short_section:
                data["face_twig_short"] = parse_bool_list(twig_short_section.group(1))

            twig_upward_section = re.search(
                r"## Twig Upward\n(.*?)\n\n", text, re.DOTALL
            )
            if twig_upward_section:
                data["face_twig_upward"] = parse_bool_list(twig_upward_section.group(1))

            twig_dead_section = re.search(r"## Twig Dead\n(.*?)\n\n", text, re.DOTALL)
            if twig_dead_section:
                data["face_twig_dead"] = parse_bool_list(twig_dead_section.group(1))

            dead_section = re.search(r"## Dead Faces\n(.*?)\n\n", text, re.DOTALL)
            if dead_section:
                data["face_dead"] = parse_bool_list(dead_section.group(1))

            end_section = re.search(r"## End Faces\n(.*?)\n\n", text, re.DOTALL)
            if end_section:
                data["face_end"] = parse_bool_list(end_section.group(1))

    # Load point attributes
    point_attrs_file = dump_dir / "point_attributes.txt"
    if point_attrs_file.exists():
        with open(point_attrs_file, "r") as f:
            text = f.read()

            age_section = re.search(r"## Age\n(.*?)\n\n", text, re.DOTALL)
            if age_section:
                data["point_age"] = parse_flat_array(age_section.group(1))

            mass_section = re.search(r"## Mass\n(.*?)\n\n", text, re.DOTALL)
            if mass_section:
                data["point_mass"] = parse_flat_array(mass_section.group(1))

            thickness_section = re.search(r"## Thickness\n(.*?)\n\n", text, re.DOTALL)
            if thickness_section:
                data["point_thickness"] = parse_flat_array(thickness_section.group(1))

            pitch_section = re.search(r"## Pitch\n(.*?)\n\n", text, re.DOTALL)
            if pitch_section:
                data["point_pitch"] = parse_flat_array(pitch_section.group(1))

            vigor_section = re.search(r"## Vigor\n(.*?)\n\n", text, re.DOTALL)
            if vigor_section:
                data["point_vigor"] = parse_flat_array(vigor_section.group(1))

            shade_section = re.search(r"## Shade\n(.*?)\n\n", text, re.DOTALL)
            if shade_section:
                data["point_shade"] = parse_flat_array(shade_section.group(1))

            photosynthesis_section = re.search(
                r"## Photosynthesis\n(.*?)(\n\n|$)", text, re.DOTALL
            )
            if photosynthesis_section:
                data["point_photosynthesis"] = parse_flat_array(
                    photosynthesis_section.group(1)
                )

    return data


# USDA components loading removed - all data now accessed directly from Grove API


# %% ANALYSIS FUNCTIONS


def analyze_points(grove_data):
    """Analyze point coordinates from Grove API."""
    grove_points = grove_data["points"]

    print("\n=== POINTS ANALYSIS ===")
    print(f"Total points: {len(grove_points)}")

    print("\nCoordinate Statistics (Z-up):")
    print(
        f"  X range: [{grove_points[:, 0].min():.4f}, {grove_points[:, 0].max():.4f}]"
    )
    print(
        f"  Y range: [{grove_points[:, 1].min():.4f}, {grove_points[:, 1].max():.4f}]"
    )
    print(
        f"  Z range: [{grove_points[:, 2].min():.4f}, {grove_points[:, 2].max():.4f}]"
    )

    print("\nFirst 5 points:")
    for i in range(min(5, len(grove_points))):
        p = grove_points[i]
        print(f"  Point {i}: [{p[0]:7.4f}, {p[1]:7.4f}, {p[2]:7.4f}]")

    return {"point_count": len(grove_points)}


def analyze_faces(grove_data):
    """Analyze face topology from Grove API."""
    grove_faces = grove_data["faces"]

    print("\n=== FACE TOPOLOGY ANALYSIS ===")
    print(f"Total faces: {len(grove_faces)}")

    print(f"\nFirst 5 faces:")
    for i in range(min(5, len(grove_faces))):
        print(f"  Face {i}: {grove_faces[i]}")

    return {"face_count": len(grove_faces)}


def analyze_uvs(grove_data):
    """Analyze UV coordinates from Grove API."""
    grove_uvs = grove_data["uvs"]

    print("\n=== UV COORDINATES ANALYSIS ===")
    print(f"Total UV coordinates: {len(grove_uvs)}")

    print(f"\nFirst 5 UVs:")
    for i in range(min(5, len(grove_uvs))):
        print(f"  UV {i}: {grove_uvs[i]}")

    return {"uv_count": len(grove_uvs)}


def compare_skeleton(grove_data):
    """Compare skeleton geometry and attributes."""
    if "skeleton_points" not in grove_data:
        print("\n=== SKELETON DATA ===")
        print("No skeleton data found")
        return None

    skeleton_points = grove_data["skeleton_points"]
    poly_lines = grove_data.get("skeleton_poly_lines", [])
    branch_id = grove_data.get("skeleton_branch_id", np.array([]))
    point_age = grove_data.get("skeleton_point_age", np.array([]))
    point_mass = grove_data.get("skeleton_point_mass", np.array([]))
    point_radius = grove_data.get("skeleton_point_radius", np.array([]))

    print("\n=== SKELETON DATA ===")
    print(f"Skeleton points count: {len(skeleton_points)}")
    print(f"Poly lines (bone chains) count: {len(poly_lines)}")

    print("\nFirst 5 skeleton points:")
    for i in range(min(5, len(skeleton_points))):
        print(f"  Point {i}: {skeleton_points[i]}")

    print("\nFirst 5 poly lines (bone chains):")
    for i in range(min(5, len(poly_lines))):
        print(
            f"  Chain {i}: {poly_lines[i][:10]}{'...' if len(poly_lines[i]) > 10 else ''}"
        )

    print("\n=== SKELETON ATTRIBUTES ===")
    print(f"Branch IDs: {len(branch_id)} faces")
    if len(branch_id) > 0:
        print(f"  Unique branch IDs: {np.unique(branch_id)[:10]}...")

    print(f"\nPoint Ages: {len(point_age)} points")
    if len(point_age) > 0:
        print(f"  Age range: {point_age.min():.2f} to {point_age.max():.2f}")
        print(f"  First 10: {point_age[:10]}")

    print(f"\nPoint Mass: {len(point_mass)} points")
    if len(point_mass) > 0:
        print(f"  Mass range: {point_mass.min():.2f} to {point_mass.max():.2f}")
        print(f"  First 10: {point_mass[:10]}")

    print(f"\nPoint Radius: {len(point_radius)} points")
    if len(point_radius) > 0:
        print(f"  Radius range: {point_radius.min():.6f} to {point_radius.max():.6f}")
        print(f"  First 10: {point_radius[:10]}")

    # Analyze skeleton structure
    if len(poly_lines) > 0:
        print("\n=== SKELETON STRUCTURE ANALYSIS ===")
        total_bones = sum(max(0, len(chain) - 1) for chain in poly_lines)
        print(f"Total bone segments: {total_bones}")

        chain_lengths = [len(chain) for chain in poly_lines]
        print(
            f"Chain length range: {min(chain_lengths)} to {max(chain_lengths)} joints"
        )
        print(f"Average chain length: {np.mean(chain_lengths):.1f} joints")

        # Check if skeleton points match mesh points
        mesh_points = grove_data.get("points")
        if mesh_points is not None:
            print(f"\nMesh points: {len(mesh_points)}")
            print(f"Skeleton points: {len(skeleton_points)}")
            if len(skeleton_points) == len(mesh_points):
                print("  ✓ Skeleton point count matches mesh")
            else:
                print("  ℹ Skeleton is simplified (fewer points than mesh)")

    return {
        "skeleton_points": skeleton_points,
        "poly_lines": poly_lines,
        "branch_id": branch_id,
        "point_age": point_age,
        "point_mass": point_mass,
        "point_radius": point_radius,
    }


def analyze_skeleton_coordinates(grove_data):
    """Analyze raw skeleton data from Grove API."""
    grove_skel = grove_data.get("skeleton_points", np.array([]))

    if len(grove_skel) == 0:
        print("\n=== SKELETON ANALYSIS ===")
        print("⚠ No skeleton data available")
        return None

    print("\n=== SKELETON ANALYSIS ===")
    print(f"Skeleton points count: {len(grove_skel)}")

    # Show raw Grove API skeleton coordinates
    print("\nRaw skeleton points (Grove API output):")
    for i in range(min(5, len(grove_skel))):
        p = grove_skel[i]
        print(f"  Point {i}: [{p[0]:.4f}, {p[1]:.4f}, {p[2]:.4f}]")

    print(f"\nTree planting position: (1, 2, 0)")
    print(
        f"Skeleton root position: [{grove_skel[0][0]:.4f}, {grove_skel[0][1]:.4f}, {grove_skel[0][2]:.4f}]"
    )

    return {"point_count": len(grove_skel)}


def analyze_face_attributes(grove_data):
    """Analyze face attributes - twig placement, dead/end faces."""
    print("\n=== FACE ATTRIBUTES ANALYSIS ===")

    face_count = len(grove_data.get("faces", []))
    print(f"Total faces: {face_count}")

    # Twig placement attributes
    twig_long = grove_data.get("face_twig_long", np.array([]))
    twig_short = grove_data.get("face_twig_short", np.array([]))
    twig_upward = grove_data.get("face_twig_upward", np.array([]))
    twig_dead = grove_data.get("face_twig_dead", np.array([]))

    if len(twig_long) > 0:
        print(f"\nTwig Placement:")
        print(f"  Twig Long (lateral long twigs): {np.sum(twig_long)} faces")
        print(f"  Twig Short (lateral short twigs): {np.sum(twig_short)} faces")
        print(f"  Twig Upward (upward facing twigs): {np.sum(twig_upward)} faces")
        print(f"  Twig Dead (dead twig positions): {np.sum(twig_dead)} faces")

    # Face state attributes
    face_dead = grove_data.get("face_dead", np.array([]))
    face_end = grove_data.get("face_end", np.array([]))

    if len(face_dead) > 0:
        print(f"\nFace States:")
        print(f"  Dead faces (dead wood): {np.sum(face_dead)} faces")
        print(f"  End faces (branch tips): {np.sum(face_end)} faces")

    return {
        "twig_long": np.sum(twig_long) if len(twig_long) > 0 else 0,
        "twig_short": np.sum(twig_short) if len(twig_short) > 0 else 0,
        "twig_upward": np.sum(twig_upward) if len(twig_upward) > 0 else 0,
        "twig_dead": np.sum(twig_dead) if len(twig_dead) > 0 else 0,
        "dead_faces": np.sum(face_dead) if len(face_dead) > 0 else 0,
        "end_faces": np.sum(face_end) if len(face_end) > 0 else 0,
    }


def analyze_point_attributes(grove_data):
    """Analyze point attributes - age, mass, thickness, vigor, shade, etc."""
    print("\n=== POINT ATTRIBUTES ANALYSIS ===")

    point_count = len(grove_data.get("points", []))
    print(f"Total points: {point_count}")

    # Age and structure
    point_age = grove_data.get("point_age", np.array([]))
    point_mass = grove_data.get("point_mass", np.array([]))

    if len(point_age) > 0:
        print(f"\nAge and Structure:")
        print(f"  Age range: [{point_age.min():.2f}, {point_age.max():.2f}] flushes")
        print(f"  Age mean: {point_age.mean():.2f}")
        print(f"  Mass range: [{point_mass.min():.4f}, {point_mass.max():.4f}]")
        print(f"  Mass mean: {point_mass.mean():.4f}")

    # Physical properties
    point_thickness = grove_data.get("point_thickness", np.array([]))
    point_pitch = grove_data.get("point_pitch", np.array([]))

    if len(point_thickness) > 0:
        print(f"\nPhysical Properties:")
        print(
            f"  Thickness range: [{point_thickness.min():.4f}, {point_thickness.max():.4f}]"
        )
        print(f"  Thickness mean: {point_thickness.mean():.4f}")
        print(f"  Pitch range: [{point_pitch.min():.4f}, {point_pitch.max():.4f}]")
        print(f"  Pitch mean: {point_pitch.mean():.4f} (0=down, 0.5=horizontal, 1=up)")

    # Growth and lighting
    point_vigor = grove_data.get("point_vigor", np.array([]))
    point_shade = grove_data.get("point_shade", np.array([]))
    point_photosynthesis = grove_data.get("point_photosynthesis", np.array([]))

    if len(point_vigor) > 0:
        print(f"\nGrowth and Lighting:")
        print(f"  Vigor range: [{point_vigor.min():.4f}, {point_vigor.max():.4f}]")
        print(f"  Vigor mean: {point_vigor.mean():.4f}")
        print(f"  Shade range: [{point_shade.min():.4f}, {point_shade.max():.4f}]")
        print(f"  Shade mean: {point_shade.mean():.4f} (0=exposed, 1=shaded)")
        print(
            f"  Photosynthesis range: [{point_photosynthesis.min():.4f}, {point_photosynthesis.max():.4f}]"
        )
        print(f"  Photosynthesis mean: {point_photosynthesis.mean():.4f}")

    return {
        "age_range": [point_age.min(), point_age.max()] if len(point_age) > 0 else None,
        "thickness_range": (
            [point_thickness.min(), point_thickness.max()]
            if len(point_thickness) > 0
            else None
        ),
        "vigor_mean": point_vigor.mean() if len(point_vigor) > 0 else None,
        "shade_mean": point_shade.mean() if len(point_shade) > 0 else None,
    }


def analyze_skeleton_bones(grove_data):
    """Analyze advanced skeleton bones data."""
    bones = grove_data.get("skeleton_bones", [])

    if len(bones) == 0:
        return None

    print("\n=== SKELETON BONES (ADVANCED) ===")
    print(f"Total bones generated: {len(bones)}")
    print(f"\nFirst 5 bones:")
    for i in range(min(5, len(bones))):
        print(f"  Bone {i}: {bones[i]}")

    return {"bone_count": len(bones)}


# %% MAIN ANALYSIS


def main():
    """Run all analyses."""
    print("Loading Grove API data...")
    grove_data = load_grove_data()

    points_result = analyze_points(grove_data)
    faces_result = analyze_faces(grove_data)
    uvs_result = analyze_uvs(grove_data)
    skeleton_result = compare_skeleton(grove_data)
    skeleton_info = analyze_skeleton_coordinates(grove_data)
    skeleton_bones_info = analyze_skeleton_bones(grove_data)
    face_attrs_info = analyze_face_attributes(grove_data)
    point_attrs_info = analyze_point_attributes(grove_data)

    print("\n" + "=" * 80)
    print("=== GROVE API DATA SUMMARY ===")
    print("=" * 80)

    print("\n1. GEOMETRY DATA:")
    print(f"   ✓ Points: {len(grove_data['points'])} vertices")
    print(f"   ✓ Faces: {len(grove_data['faces'])} polygons")
    print(f"   ✓ UVs: {len(grove_data['uvs'])} coordinates")
    print(f"   ✓ Coordinate system: Z-up (native Grove API)")

    if skeleton_result:
        print("\n2. SKELETON DATA (RAW):")
        print(f"   ✓ Skeleton points: {len(skeleton_result['skeleton_points'])}")
        print(f"   ✓ Bone chains: {len(skeleton_result['poly_lines'])}")
        total_bones = sum(
            max(0, len(chain) - 1) for chain in skeleton_result["poly_lines"]
        )
        print(f"   ✓ Total bone segments: {total_bones}")
        if skeleton_bones_info:
            print(
                f"   ✓ Advanced bones (with params): {skeleton_bones_info['bone_count']}"
            )
        if len(skeleton_result["branch_id"]) > 0:
            print(
                f"   ✓ Unique branch IDs: {len(np.unique(skeleton_result['branch_id']))}"
            )

    if face_attrs_info:
        section_num = "3" if skeleton_result else "2"
        print(f"\n{section_num}. FACE ATTRIBUTES:")
        print(f"   ✓ Twig long faces: {face_attrs_info['twig_long']}")
        print(f"   ✓ Twig short faces: {face_attrs_info['twig_short']}")
        print(f"   ✓ Twig upward faces: {face_attrs_info['twig_upward']}")
        print(f"   ✓ Twig dead faces: {face_attrs_info['twig_dead']}")
        print(f"   ✓ Dead wood faces: {face_attrs_info['dead_faces']}")
        print(f"   ✓ Branch end faces: {face_attrs_info['end_faces']}")

    if point_attrs_info and point_attrs_info["age_range"]:
        section_num = (
            str(int(section_num) + 1)
            if face_attrs_info
            else ("3" if skeleton_result else "2")
        )
        print(f"\n{section_num}. POINT ATTRIBUTES:")
        print(f"   ✓ Age range: {point_attrs_info['age_range']}")
        print(f"   ✓ Thickness range: {point_attrs_info['thickness_range']}")
        print(f"   ✓ Average vigor: {point_attrs_info['vigor_mean']:.4f}")
        print(f"   ✓ Average shade: {point_attrs_info['shade_mean']:.4f}")

    print(f"\n{'='*80}")
    print("=== DATA INTEGRITY CHECK ===")
    print(f"{'='*80}")
    print("\nAll data extracted directly from Grove API")
    print("No transformations or conversions applied")
    print("Use this data for analysis and export to various formats")
    print(f"\n{'='*80}\n")


if __name__ == "__main__":
    main()
