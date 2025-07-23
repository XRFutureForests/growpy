"""Twig assignment and USD integration for tree models."""

import json
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import the_grove_22_core as gc

from .config import get_config
from .tree import calculate_face_centers_and_normals, read_usda_file


class TwigData:
    """Data class to store twig position and attribute information."""

    def __init__(
        self,
        position: Tuple[float, float, float],
        normal: Tuple[float, float, float],
        twig_type: str,
        rotation: Optional[Tuple[float, float, float, float]] = None,
    ):
        """
        Initialize twig data.

        Args:
            position: 3D position (x, y, z) of the twig base
            normal: Surface normal direction (x, y, z)
            twig_type: Type of twig ('end', 'side', 'upward', 'dead')
            rotation: Optional quaternion rotation (x, y, z, w)
        """
        self.position = position
        self.normal = normal
        self.twig_type = twig_type
        self.rotation = rotation or self._calculate_rotation_from_normal(normal)

    def _calculate_rotation_from_normal(
        self, normal: Tuple[float, float, float]
    ) -> Tuple[float, float, float, float]:
        """
        Calculate quaternion rotation from surface normal.

        The Grove expects twigs to point along the X-axis, so we need to rotate
        from the X-axis to align with the surface normal.

        Args:
            normal: Surface normal direction

        Returns:
            Quaternion rotation (x, y, z, w)
        """
        # Default twig direction is along X-axis
        default_dir = np.array([1.0, 0.0, 0.0])
        target_dir = np.array(normal)

        # Normalize vectors
        target_dir = target_dir / np.linalg.norm(target_dir)

        # Calculate rotation axis and angle
        cross = np.cross(default_dir, target_dir)
        dot = np.dot(default_dir, target_dir)

        # Handle edge cases
        if np.allclose(cross, 0):
            if dot > 0:
                # Same direction
                return (0.0, 0.0, 0.0, 1.0)
            else:
                # Opposite direction, rotate 180 degrees around Y-axis
                return (0.0, 1.0, 0.0, 0.0)

        # Calculate quaternion
        axis = cross / np.linalg.norm(cross)
        angle = math.acos(np.clip(dot, -1.0, 1.0))

        half_angle = angle / 2.0
        w = math.cos(half_angle)
        sin_half = math.sin(half_angle)
        x = axis[0] * sin_half
        y = axis[1] * sin_half
        z = axis[2] * sin_half

        return (x, y, z, w)


def extract_twig_positions_from_usda(usda_data: Dict[str, Any]) -> List[TwigData]:
    """
    Extract twig positions and attributes from parsed USDA data.

    Args:
        usda_data: Parsed USDA data from read_usda_file()

    Returns:
        List of TwigData objects containing position, normal, and type information
    """
    twig_positions = []

    # Get mesh data
    points = usda_data.get("points", [])
    face_vertex_counts = usda_data.get("face_vertex_counts", [])
    face_vertex_indices = usda_data.get("face_vertex_indices", [])

    # Get twig attributes
    twig_end = usda_data.get("twig_end", [])
    twig_side = usda_data.get("twig_side", [])
    twig_upward = usda_data.get("twig_upward", [])
    twig_dead = usda_data.get("twig_dead", [])

    if not points or not face_vertex_counts:
        return twig_positions

    # Calculate face centers and normals
    face_centers, face_normals = calculate_face_centers_and_normals(
        points, face_vertex_counts, face_vertex_indices
    )

    # Extract transformation matrix for coordinate transformation
    transform = usda_data.get("transform_matrix", np.eye(4))

    # Process each face and check for twig attributes
    num_faces = len(face_centers)

    for i in range(num_faces):
        center = face_centers[i]
        normal = face_normals[i]

        # Apply transformation to position and normal
        pos_homo = np.array([center[0], center[1], center[2], 1.0])
        transformed_pos = transform @ pos_homo
        final_position = (transformed_pos[0], transformed_pos[1], transformed_pos[2])

        # Transform normal (only rotation, no translation)
        normal_homo = np.array([normal[0], normal[1], normal[2], 0.0])
        transformed_normal = transform @ normal_homo
        final_normal = (
            transformed_normal[0],
            transformed_normal[1],
            transformed_normal[2],
        )

        # Normalize the transformed normal
        norm_length = math.sqrt(sum(x * x for x in final_normal))
        if norm_length > 0:
            final_normal = tuple(x / norm_length for x in final_normal)

        # Check twig attributes (attributes are per-face)
        twig_types = []

        if i < len(twig_end) and twig_end[i] == 1:
            twig_types.append("end")
        if i < len(twig_side) and twig_side[i] == 1:
            twig_types.append("side")
        if i < len(twig_upward) and twig_upward[i] == 1:
            twig_types.append("upward")
        if i < len(twig_dead) and twig_dead[i] == 1:
            twig_types.append("dead")

        # Create TwigData objects for each twig type found at this face
        for twig_type in twig_types:
            twig_data = TwigData(
                position=final_position, normal=final_normal, twig_type=twig_type
            )
            twig_positions.append(twig_data)

    return twig_positions


def extract_twigs_from_usda_file(file_path: str) -> List[TwigData]:
    """
    Complete pipeline to extract twig positions from a USDA file.

    Args:
        file_path: Path to the USDA file

    Returns:
        List of TwigData objects with position, normal, and type information

    Raises:
        FileNotFoundError: If the USDA file doesn't exist
        ValueError: If the USDA file format is invalid
    """
    # Read and parse the USDA file
    usda_data = read_usda_file(file_path)

    # Extract twig positions and attributes
    twig_positions = extract_twig_positions_from_usda(usda_data)

    return twig_positions


def save_twig_data_to_csv(twig_data: List[TwigData], output_path: str) -> None:
    """
    Save twig data to a CSV file for analysis or further processing.

    Args:
        twig_data: List of TwigData objects
        output_path: Path where to save the CSV file
    """
    if not twig_data:
        print("No twig data to save")
        return

    # Convert to pandas DataFrame
    data_rows = []
    for twig in twig_data:
        row = {
            "position_x": twig.position[0],
            "position_y": twig.position[1],
            "position_z": twig.position[2],
            "normal_x": twig.normal[0],
            "normal_y": twig.normal[1],
            "normal_z": twig.normal[2],
            "twig_type": twig.twig_type,
            "rotation_x": twig.rotation[0],
            "rotation_y": twig.rotation[1],
            "rotation_z": twig.rotation[2],
            "rotation_w": twig.rotation[3],
        }
        data_rows.append(row)

    df = pd.DataFrame(data_rows)
    df.to_csv(output_path, index=False)
    print(f"Saved {len(twig_data)} twig positions to {output_path}")


def analyze_twig_distribution(twig_data: List[TwigData]) -> Dict[str, Any]:
    """
    Analyze the distribution of twig types and positions.

    Args:
        twig_data: List of TwigData objects

    Returns:
        Dictionary with analysis results
    """
    if not twig_data:
        return {}

    # Count twig types
    type_counts = {}
    positions = []

    for twig in twig_data:
        twig_type = twig.twig_type
        type_counts[twig_type] = type_counts.get(twig_type, 0) + 1
        positions.append(twig.position)

    # Calculate position statistics
    positions_array = np.array(positions)

    analysis = {
        "total_twigs": len(twig_data),
        "twig_type_counts": type_counts,
        "position_bounds": {
            "min_x": float(np.min(positions_array[:, 0])),
            "max_x": float(np.max(positions_array[:, 0])),
            "min_y": float(np.min(positions_array[:, 1])),
            "max_y": float(np.max(positions_array[:, 1])),
            "min_z": float(np.min(positions_array[:, 2])),
            "max_z": float(np.max(positions_array[:, 2])),
        },
        "position_centroid": {
            "x": float(np.mean(positions_array[:, 0])),
            "y": float(np.mean(positions_array[:, 1])),
            "z": float(np.mean(positions_array[:, 2])),
        },
    }

    return analysis
