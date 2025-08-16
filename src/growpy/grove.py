"""Minimal grove operations for forest simulation."""

from typing import Optional, Tuple

from .common import gc, ensure_grove_available
from .config import get_config


def create_grove(species: Optional[str] = None):
    """Create a new Grove with optional species preset."""
    ensure_grove_available()

    config = get_config()
    grove = gc.Grove()
    grove.clear_trees()

    if config.random_seed is not None:
        grove.set_random_seed(config.random_seed)

    if species:
        preset_path = config.get_preset_path(species)
        with open(preset_path, "r") as f:
            preset_json = f.read()
        properties = gc.io.properties_from_json_string(preset_json)
        grove.set_properties(properties)

    return grove


def add_tree_to_grove(
    grove, position: Tuple[float, float, float], delay: int = 0
) -> None:
    """Add a tree to grove at specified position."""
    position_vector = gc.Vector(*position)
    direction_vector = gc.Vector(0, 0, 1)
    grove.add_new_tree(position_vector, direction_vector, delay)
