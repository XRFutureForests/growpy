"""Minimal twig enhancement for USD files."""

from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np

# Platform-specific Grove core import with fallback
try:
    import the_grove_22_core as gc
except ImportError:
    print("Warning: the_grove_22_core not available")
    gc = None

from pxr import Usd, Vt

usda_file = Path(
    "/Users/maximiliansperlich/Developer/the-grove/data/output/small_demo/Norwayspruce_LOD1_High_002.usda"
)


stage = Usd.Stage.Open(str(usda_file))
[x for x in stage.Traverse()]
tree = stage.GetPrimAtPath("/Tree/Tree")
tree.GetPropertyNames()

# Extract attributes from the tree
face_vertex_counts = list(tree.GetAttribute("faceVertexCounts").Get())  # Number of vertices per face
face_vertex_indices = list(tree.GetAttribute("faceVertexIndices").Get())  # Indices of vertices for each face

# Extract points and other attributes
points = list(tree.GetAttribute("points").Get())
uv = list(tree.GetAttribute("primvars:st").Get())  # UV
age = list(tree.GetAttribute("primvars:Age").Get())
dead = list(tree.GetAttribute("primvars:Dead").Get())
thickness = list(tree.GetAttribute("primvars:Thickness").Get())
twig_end = list(tree.GetAttribute("primvars:TwigEnd").Get())  # Long / Apical
twig_side = list(tree.GetAttribute("primvars:TwigSide").Get())  # Short / Lateral
twig_upward = list(tree.GetAttribute("primvars:TwigUpward").Get())  # Upward
twig_dead = list(tree.GetAttribute("primvars:TwigDead").Get())  # Dead

# Convert attributes to numpy arrays
face_vertex_indices_np = np.array(face_vertex_indices)
face_vertex_counts_np = np.array(face_vertex_counts)
split_indices = np.cumsum(face_vertex_counts_np)[:-1]
faces_numpy = np.split(face_vertex_indices_np, split_indices)
faces_tuples = [list(face) for face in faces_numpy]

# Filter faces based on twig attributes
faces_end = [face for (face, end) in zip(faces_tuples, twig_end) if end==1]
faces_side = [face for (face, side) in zip(faces_tuples, twig_side) if side==1]
faces_upward = [face for (face, upward) in zip(faces_tuples, twig_upward) if upward==1]
faces_dead = [face for (face, dead) in zip(faces_tuples, twig_dead) if dead==1]

def calculate_centroid(points: Vt.Vec3fArray, face: List[int]) -> np.ndarray:
    """Calculate the centroid of a face."""
    face_points = np.array([points[i] for i in face])
    return tuple(np.mean(face_points, axis=0))

def calculate_normal(points: Vt.Vec3fArray, face: List[int]) -> np.ndarray:
    """Calculate the normal vector of a face."""
    face_points = np.array([points[i] for i in face])
    v1 = face_points[1] - face_points[0]
    v2 = face_points[2] - face_points[0]
    normal = np.cross(v1, v2)
    return tuple(normal / np.linalg.norm(normal))

def calculate_quaternion_from_normal(normal: np.ndarray) -> List[float]:
    """Calculate a quaternion that rotates from the default up direction to the normal vector."""
    normal = normal / np.linalg.norm(normal)  # Ensure normalized
    
    # Default up direction (assuming twigs point up by default)
    up = np.array([0.0, 1.0, 0.0])
    
    # If normal is already pointing up, return identity quaternion
    if np.allclose(normal, up):
        return [1.0, 0.0, 0.0, 0.0]  # w, x, y, z
    
    # If normal is pointing down, rotate 180 degrees around X axis
    if np.allclose(normal, -up):
        return [0.0, 1.0, 0.0, 0.0]  # w, x, y, z
    
    # Calculate rotation axis (cross product of up and normal)
    axis = np.cross(up, normal)
    axis = axis / np.linalg.norm(axis)
    
    # Calculate rotation angle
    dot_product = np.dot(up, normal)
    angle = np.arccos(np.clip(dot_product, -1.0, 1.0))
    
    # Convert to quaternion
    half_angle = angle * 0.5
    sin_half = np.sin(half_angle)
    cos_half = np.cos(half_angle)
    
    # Return quaternion as (w, x, y, z)
    return (
        cos_half,           # w
        axis[0] * sin_half, # x
        axis[1] * sin_half, # y
        axis[2] * sin_half  # z
    )

centroid_end = [calculate_centroid(points, face) for face in faces_end]
normal_end = [calculate_normal(points, face) for face in faces_end]
centroid_side = [calculate_centroid(points, face) for face in faces_side]
normal_side = [calculate_normal(points, face) for face in faces_side]
quaternion_side = [calculate_quaternion_from_normal(n) for n in normal_side]
centroid_upward = [calculate_centroid(points, face) for face in faces_upward]
normal_upward = [calculate_normal(points, face) for face in faces_upward]
centroid_dead = [calculate_centroid(points, face) for face in faces_dead]
normal_dead = [calculate_normal(points, face) for face in faces_dead]

with open("twig_side.txt", "w") as f:
    for _ in range(len(centroid_side)):
        f.write("0, ")
    f.write("\n")
    for centroid in centroid_side:
        f.write(f"{centroid}, ")
    f.write("\n")
    for quaternion in quaternion_side:
        f.write(f"{quaternion}, ")
    f.write("\n")
