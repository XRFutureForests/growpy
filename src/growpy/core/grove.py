"""
Grove creation and management functions.
"""

from pathlib import Path
from typing import List, Tuple
import the_grove_22_core as gc
from ..species_utils import apply_species_preset as _apply_preset


def create_grove(species: str, random_seed: int = None) -> gc.Grove:
    """
    Create a new Grove with species preset applied.
    
    Args:
        species: Species name
        random_seed: Random seed for reproducible results
        
    Returns:
        Grove object with species preset applied
    """
    grove = gc.Grove()
    
    if random_seed is not None:
        grove.set_random_seed(random_seed)
    
    _apply_preset(grove, species)
    return grove


def add_tree_to_grove(grove: gc.Grove, position: Tuple[float, float, float], 
                     direction: Tuple[float, float, float] = (0, 0, 1), 
                     delay: int = 0) -> None:
    """
    Add a tree to a grove at specified position.
    
    Args:
        grove: Grove object
        position: (x, y, z) coordinates
        direction: Growth direction vector (default: upward)
        delay: Growth delay in cycles
    """
    pos = gc.Vector(position[0], position[1], position[2])
    dir_vec = gc.Vector(direction[0], direction[1], direction[2])
    grove.add_new_tree(pos, dir_vec, delay)


def apply_species_preset(grove: gc.Grove, species: str) -> None:
    """
    Apply species preset to grove.
    
    Args:
        grove: Grove object
        species: Species name
    """
    _apply_preset(grove, species)


def simulate_grove_growth(grove: gc.Grove, cycles: int) -> None:
    """
    Simulate grove growth for specified number of cycles.
    
    Args:
        grove: Grove object
        cycles: Number of growth cycles
    """
    grove.simulate(cycles)


def calculate_shared_light_competition(groves: List[gc.Grove]) -> None:
    """
    Calculate light competition between multiple groves.
    
    Args:
        groves: List of Grove objects
    """
    if len(groves) > 1:
        # Use Grove's built-in light competition
        for i in range(len(groves)):
            for j in range(i + 1, len(groves)):
                groves[i].calculate_shade_together(groves[j])