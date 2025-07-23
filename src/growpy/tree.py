"""Tree model and individual tree management functions."""

import json
import pickle
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression

# Platform-specific Grove core import with fallback
try:
    import the_grove_22_core as gc
except ImportError:
    print("Warning: the_grove_22_core not available, some functions may not work")
    gc = None

from .config import get_config


def calculate_growth_cycles_from_height(forest_data: pd.DataFrame) -> None:
    """Calculate growth cycles using height prediction models with global config."""
    # Get global config (creates default if none set)
    config = get_config()

    # Use growth models for species-specific predictions
    forest_data["growth_cycles"] = 0
    for i, tree in forest_data.iterrows():
        species = tree["species"]
        height = tree["height"]
        growth_model_path = config.get_growth_model_path(species)

        model_path = growth_model_path / "growth_model.pkl"
        model = pickle.load(open(model_path, "rb"))
        growth_cycles = int(model.predict([[height]])[0])
        forest_data.at[i, "growth_cycles"] = growth_cycles

    max_cycles = forest_data["growth_cycles"].max()
    forest_data["delay"] = max_cycles - forest_data["growth_cycles"]


def save_tree_to_usd(model, output_path: Path) -> None:
    """Save 3D model to USD file using Grove's native USD output."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    usd_string = gc.io.model_to_usda_string(model)
    with open(output_path, "w") as f:
        f.write(usd_string)


def build_lod_models(
    grove, lod_configs: Dict[str, Dict[str, Any]]
) -> Dict[str, List]:
    """Build multiple LOD variants of grove models.
    
    Args:
        grove: Grove object
        lod_configs: Dictionary of LOD configurations from config.get_lod_configs()
        
    Returns:
        Dictionary mapping LOD names to lists of models
    """
    if gc is None:
        raise ImportError("Grove core not available")
        
    lod_models = {}
    for lod_name, config in lod_configs.items():
        lod_models[lod_name] = grove.build_models(config)
    return lod_models


def build_spring_models(grove, lod_configs: Dict[str, Dict[str, Any]]) -> Dict[str, List]:
    """Build spring shape models for growth animation.
    
    Args:
        grove: Grove object
        lod_configs: Dictionary of LOD configurations
        
    Returns:
        Dictionary mapping LOD names to lists of spring models
    """
    if gc is None:
        raise ImportError("Grove core not available")
        
    spring_models = {}
    for lod_name, config in lod_configs.items():
        spring_models[lod_name] = grove.build_spring_shape(config)
    return spring_models


def get_model_attributes(model) -> Dict[str, Any]:
    """Extract all available attributes from a Grove model.
    
    Args:
        model: Grove model object
        
    Returns:
        Dictionary containing all model attributes and data
    """
    if gc is None:
        raise ImportError("Grove core not available")
        
    attributes = {
        # Geometry data
        'points': model.get_points_as_tuples(),
        'points_flat': model.get_points_flat(),
        'faces': model.faces,
        'uvs_flat': model.get_uvs_flat(),
        'uv_islands_flat': model.get_uv_islands_flat(),
        'directions_flat': model.get_directions_flat(),
        
        # Location
        'location': (model.location.x, model.location.y, model.location.z),
    }
    
    # Point (vertex) attributes - only if available
    if hasattr(model, 'point_attribute_age'):
        attributes['point_attribute_age'] = model.point_attribute_age
    if hasattr(model, 'point_attribute_thickness'):
        attributes['point_attribute_thickness'] = model.point_attribute_thickness
    if hasattr(model, 'point_attribute_photosynthesis'):
        attributes['point_attribute_photosynthesis'] = model.point_attribute_photosynthesis
    if hasattr(model, 'point_attribute_shade'):
        attributes['point_attribute_shade'] = model.point_attribute_shade
    if hasattr(model, 'point_attribute_vigor'):
        attributes['point_attribute_vigor'] = model.point_attribute_vigor
    if hasattr(model, 'point_attribute_bone_id'):
        attributes['point_attribute_bone_id'] = model.point_attribute_bone_id
    if hasattr(model, 'point_attribute_pitch'):
        attributes['point_attribute_pitch'] = model.point_attribute_pitch
        
    # Face attributes - only if available
    if hasattr(model, 'face_attribute_branch_id'):
        attributes['face_attribute_branch_id'] = model.face_attribute_branch_id
    if hasattr(model, 'face_attribute_branch_id_parent'):
        attributes['face_attribute_branch_id_parent'] = model.face_attribute_branch_id_parent
    if hasattr(model, 'face_attribute_dead'):
        attributes['face_attribute_dead'] = model.face_attribute_dead
    if hasattr(model, 'face_attribute_twig_long'):
        attributes['face_attribute_twig_long'] = model.face_attribute_twig_long
    if hasattr(model, 'face_attribute_twig_short'):
        attributes['face_attribute_twig_short'] = model.face_attribute_twig_short
    if hasattr(model, 'face_attribute_twig_upward'):
        attributes['face_attribute_twig_upward'] = model.face_attribute_twig_upward
    if hasattr(model, 'face_attribute_twig_dead'):
        attributes['face_attribute_twig_dead'] = model.face_attribute_twig_dead
    if hasattr(model, 'face_attribute_end'):
        attributes['face_attribute_end'] = model.face_attribute_end
        
    return attributes


def merge_lod_models():
    """Read multiple LOD USD files by species and merge them into a single USD file."""
    config = get_config()
    pass


def read_usda_file(file_path: str) -> Dict[str, Any]:
    """
    Read a USDA file and extract mesh data including twig attributes.

    Args:
        file_path: Path to the USDA file

    Returns:
        Dictionary containing parsed USDA data with keys:
        - 'points': List of 3D vertex positions as tuples (x, y, z)
        - 'face_vertex_counts': List of vertex counts per face
        - 'face_vertex_indices': List of vertex indices for faces
        - 'twig_end': List of TwigEnd attribute values per face
        - 'twig_side': List of TwigSide attribute values per face
        - 'twig_upward': List of TwigUpward attribute values per face
        - 'twig_dead': List of TwigDead attribute values per face
        - 'transform_matrix': 4x4 transformation matrix
        - 'normals': Face normals (if available)

    Raises:
        FileNotFoundError: If the USDA file doesn't exist
        ValueError: If the USDA file format is invalid
    """
    file_path_obj = Path(file_path)
    if not file_path_obj.exists():
        raise FileNotFoundError(f"USDA file not found: {file_path}")

    try:
        with open(file_path_obj, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception as e:
        raise ValueError(f"Error reading USDA file: {e}")

    usda_data = {
        "points": [],
        "face_vertex_counts": [],
        "face_vertex_indices": [],
        "twig_end": [],
        "twig_side": [],
        "twig_upward": [],
        "twig_dead": [],
        "transform_matrix": np.eye(4),
        "normals": [],
    }

    # Extract points (vertices)
    points_match = re.search(r"point3f\[\] points = \[(.*?)\]", content, re.DOTALL)
    if points_match:
        points_str = points_match.group(1)
        # Parse coordinate tuples like (-0.0161, -0.0632, -0.0002)
        coord_pattern = r"\(([-\d.e]+),\s*([-\d.e]+),\s*([-\d.e]+)\)"
        coords = re.findall(coord_pattern, points_str)
        usda_data["points"] = [(float(x), float(y), float(z)) for x, y, z in coords]

    # Extract face vertex counts
    counts_match = re.search(
        r"int\[\] faceVertexCounts = \[(.*?)\]", content, re.DOTALL
    )
    if counts_match:
        counts_str = counts_match.group(1)
        usda_data["face_vertex_counts"] = [
            int(x.strip()) for x in counts_str.split(",") if x.strip()
        ]

    # Extract face vertex indices
    indices_match = re.search(
        r"int\[\] faceVertexIndices = \[(.*?)\]", content, re.DOTALL
    )
    if indices_match:
        indices_str = indices_match.group(1)
        usda_data["face_vertex_indices"] = [
            int(x.strip()) for x in indices_str.split(",") if x.strip()
        ]

    # Extract twig attributes
    for twig_type in ["TwigEnd", "TwigSide", "TwigUpward", "TwigDead"]:
        attr_key = twig_type.lower().replace("twig", "twig_")
        pattern = rf"int\[\] primvars:{twig_type} = \[(.*?)\]"
        match = re.search(pattern, content, re.DOTALL)
        if match:
            attr_str = match.group(1)
            usda_data[attr_key] = [
                int(x.strip()) for x in attr_str.split(",") if x.strip()
            ]

    # Extract transformation matrix
    matrix_match = re.search(
        r"matrix4d xformOp:transform = \(\((.*?)\)\)", content, re.DOTALL
    )
    if matrix_match:
        matrix_str = matrix_match.group(1)
        # Remove parentheses and parse matrix values
        matrix_str = re.sub(r"[()]", "", matrix_str)
        values = [float(x.strip()) for x in matrix_str.split(",") if x.strip()]
        if len(values) == 16:
            usda_data["transform_matrix"] = np.array(values).reshape(4, 4)

    # Extract normals if available
    normals_match = re.search(r"normal3f\[\] normals = \[(.*?)\]", content, re.DOTALL)
    if normals_match:
        normals_str = normals_match.group(1)
        normal_pattern = r"\(([-\d.e]+),\s*([-\d.e]+),\s*([-\d.e]+)\)"
        normals = re.findall(normal_pattern, normals_str)
        usda_data["normals"] = [(float(x), float(y), float(z)) for x, y, z in normals]

    return usda_data


def calculate_face_centers_and_normals(
    points: List[Tuple[float, float, float]],
    face_vertex_counts: List[int],
    face_vertex_indices: List[int],
) -> Tuple[List[Tuple[float, float, float]], List[Tuple[float, float, float]]]:
    """
    Calculate face centers and normals from mesh data.

    Args:
        points: List of vertex positions
        face_vertex_counts: Number of vertices per face
        face_vertex_indices: Vertex indices for each face

    Returns:
        Tuple of (face_centers, face_normals)
    """
    face_centers = []
    face_normals = []

    idx = 0
    for count in face_vertex_counts:
        # Get vertex indices for this face
        face_indices = face_vertex_indices[idx : idx + count]
        idx += count

        # Get face vertices
        face_verts = [points[i] for i in face_indices]

        # Calculate face center
        center_x = sum(v[0] for v in face_verts) / len(face_verts)
        center_y = sum(v[1] for v in face_verts) / len(face_verts)
        center_z = sum(v[2] for v in face_verts) / len(face_verts)
        face_centers.append((center_x, center_y, center_z))

        # Calculate face normal (for triangles and quads)
        if len(face_verts) >= 3:
            # Use first three vertices to calculate normal
            v1 = np.array(face_verts[1]) - np.array(face_verts[0])
            v2 = np.array(face_verts[2]) - np.array(face_verts[0])
            normal = np.cross(v1, v2)

            # Normalize
            norm = np.linalg.norm(normal)
            if norm > 0:
                normal = normal / norm

            face_normals.append(tuple(normal))
        else:
            # Default normal pointing up
            face_normals.append((0.0, 1.0, 0.0))

    return face_centers, face_normals
