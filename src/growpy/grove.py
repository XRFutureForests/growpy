"""Grove creation and management functions."""

from pathlib import Path
from typing import Any, Dict, Optional, Tuple

import pandas as pd
import the_grove_22_core as gc

from .config import get_config


def create_grove(species: Optional[str] = None) -> gc.Grove:
    """Create a new Grove, optionally with species preset, using global config seed."""
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


def apply_species_preset(grove: gc.Grove, species: str) -> None:
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
    grove: gc.Grove,
    position: Tuple[float, float, float],
    direction: Tuple[float, float, float] = (0, 0, 1),
    delay: int = 0,
) -> None:
    """Add a tree to grove at specified position."""
    position_vector = gc.Vector(*position)
    direction_vector = gc.Vector(*direction)
    grove.add_new_tree(position_vector, direction_vector, delay)


def save_grove_to_json(grove: gc.Grove, output_path: Path) -> None:
    """Save grove to JSON file using Grove's core io functionality."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_string = gc.io.grove_to_json_string(grove)

    with open(output_path, "w") as f:
        f.write(json_string)
