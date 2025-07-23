"""Grove creation and management functions."""

import base64
import gzip
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

from .config import get_config

# Platform-specific Grove core import with fallback
try:
    import the_grove_22_core as gc
except ImportError:
    print("Warning: the_grove_22_core not available, some functions may not work")
    gc = None


def create_grove(species: Optional[str] = None):
    """Create a new Grove, optionally with species preset, using global config seed."""
    if gc is None:
        raise ImportError("Grove core not available - cannot create grove")
        
    # Get global config (creates default if none set)
    config = get_config()
    
    grove = gc.Grove()
    grove.clear_trees()  # Clear default tree as per documentation

    # Always use seed from global config
    if config.random_seed is not None:
        grove.set_random_seed(config.random_seed)

    if species:
        apply_species_preset(grove, species)

    return grove


def apply_species_preset(grove, species: str) -> None:
    """Apply species preset to Grove using Grove's core io functionality and global config."""
    # Get global config (creates default if none set)
    config = get_config()
    
    # Try to get full preset path from config first (most robust)
    preset_path = config.get_preset_path(species)

    with open(preset_path, "r") as f:
        preset_json = f.read()

    properties = gc.io.properties_from_json_string(preset_json)
    grove.set_properties(properties)


def add_tree_to_grove(
    grove,
    position: Tuple[float, float, float],
    direction: Tuple[float, float, float] = (0, 0, 1),
    delay: int = 0,
) -> None:
    """Add a tree to grove at specified position."""
    position_vector = gc.Vector(*position)
    direction_vector = gc.Vector(*direction)
    grove.add_new_tree(position_vector, direction_vector, delay)


def save_grove_to_json(grove, output_path: Path, compress: bool = True) -> None:
    """Save grove to JSON file using Grove's core io functionality with optional compression.
    
    Args:
        grove: Grove object to save
        output_path: Path where to save the grove
        compress: Whether to use gzip compression (recommended for large groves)
    """
    if gc is None:
        raise ImportError("Grove core not available - cannot save grove")
        
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_string = gc.io.grove_to_json_string(grove)

    if compress:
        # Use compression like the Blender addon for efficiency
        compressed_data = gzip.compress(json_string.encode('utf-8'), compresslevel=1)
        # Save as binary file
        with open(output_path.with_suffix('.grove'), "wb") as f:
            f.write(compressed_data)
    else:
        with open(output_path, "w") as f:
            f.write(json_string)


def load_grove_from_file(file_path: Path):
    """Load grove from file (supports both compressed .grove and plain JSON).
    
    Args:
        file_path: Path to the grove file
        
    Returns:
        Loaded Grove object
    """
    if gc is None:
        raise ImportError("Grove core not available - cannot load grove")
        
    if not file_path.exists():
        raise FileNotFoundError(f"Grove file not found: {file_path}")
    
    if file_path.suffix == '.grove':
        # Compressed format
        with open(file_path, "rb") as f:
            compressed_data = f.read()
        json_string = gzip.decompress(compressed_data).decode('utf-8')
    else:
        # Plain JSON format
        with open(file_path, "r") as f:
            json_string = f.read()
    
    return gc.io.grove_from_json_string(json_string)


def get_grove_properties(grove):
    """Get grove properties for modification.
    
    Args:
        grove: Grove object
        
    Returns:
        Properties object that can be modified and reapplied
    """
    if gc is None:
        raise ImportError("Grove core not available")
    return grove.get_properties()


def set_grove_properties(grove, properties) -> None:
    """Set grove properties.
    
    Args:
        grove: Grove object
        properties: Properties object to apply
    """
    if gc is None:
        raise ImportError("Grove core not available")
    grove.set_properties(properties)


def update_physics(grove) -> None:
    """Update grove physics calculations (weight and bending).
    
    This is useful after modifying properties that affect physics.
    
    Args:
        grove: Grove object to update
    """
    if gc is None:
        raise ImportError("Grove core not available")
    grove.weigh_and_bend()


def simulate_grove_growth(grove, cycles: int, 
                         update_physics: bool = True) -> None:
    """Simulate grove growth for specified number of cycles.
    
    Args:
        grove: Grove object
        cycles: Number of growth cycles to simulate
        update_physics: Whether to update physics before simulation
    """
    if gc is None:
        raise ImportError("Grove core not available")
        
    if update_physics:
        grove.weigh_and_bend()
        
    grove.simulate(cycles)
