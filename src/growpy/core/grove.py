"""Grove creation and management functions."""

from typing import List, Tuple
import the_grove_22_core as gc
from .species import apply_species_preset


def create_grove(species: str, random_seed: int = None) -> gc.Grove:
    """Create a new Grove with species preset applied."""
    grove = gc.Grove()
    if random_seed is not None:
        grove.set_random_seed(random_seed)
    apply_species_preset(grove, species)
    return grove


def add_tree_to_grove(grove: gc.Grove, position: Tuple[float, float, float], 
                     direction: Tuple[float, float, float] = (0, 0, 1), 
                     delay: int = 0) -> None:
    """Add a tree to a grove at specified position."""
    pos = gc.Vector(position[0], position[1], position[2])
    dir_vec = gc.Vector(direction[0], direction[1], direction[2])
    grove.add_new_tree(pos, dir_vec, delay)


def calculate_shared_light_competition(groves: List[gc.Grove]) -> None:
    """Calculate shared light competition between multiple groves."""
    if len(groves) > 1:
        all_coords = []
        for grove in groves:
            all_coords.extend(grove.create_shade_geometry_coords())
        for grove in groves:
            grove.calculate_shade_together(all_coords)