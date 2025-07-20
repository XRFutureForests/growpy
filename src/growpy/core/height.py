"""
Height calculation and curve generation functions.
"""

import logging
from typing import List, Tuple
import the_grove_22_core as gc
from ..config import GrowPyConfig
from .grove import create_grove, simulate_grove_growth

logger = logging.getLogger(__name__)


def calculate_tree_height(grove: gc.Grove, tree_index: int = 0) -> float:
    """
    Calculate tree height by finding the maximum Z-coordinate of all nodes.
    
    Args:
        grove: Grove object containing trees
        tree_index: Index of the tree to measure (default: 0)
        
    Returns:
        Tree height as float
        
    Raises:
        ValueError: If tree index is invalid or grove is empty
    """
    if not grove.trees:
        raise ValueError("Grove contains no trees")
        
    if tree_index < 0 or tree_index >= len(grove.trees):
        raise ValueError(f"Invalid tree index {tree_index}. Grove has {len(grove.trees)} trees")
    
    max_z = 0.0

    def traverse_branch(branch):
        nonlocal max_z
        if not hasattr(branch, 'nodes'):
            return
            
        for node in branch.nodes:
            if hasattr(node, 'pos') and hasattr(node.pos, 'z'):
                if node.pos.z > max_z:
                    max_z = node.pos.z

            if hasattr(node, 'side_branches'):
                for side_branch in node.side_branches:
                    traverse_branch(side_branch)

    traverse_branch(grove.trees[tree_index])
    return max_z


def generate_height_curve(species: str, max_cycles: int, random_seed: int = None) -> List[float]:
    """
    Generate height growth curve for a single species.
    
    Args:
        species: Species name
        max_cycles: Maximum number of growth cycles
        random_seed: Random seed for reproducible results
        
    Returns:
        List of heights for each cycle
    """
    grove = create_grove(species, random_seed)
    grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
    
    heights = []
    for cycle in range(max_cycles):
        simulate_grove_growth(grove, 1)
        height = calculate_tree_height(grove)
        heights.append(height)
        
        # Early termination if growth stops
        if len(heights) >= 2 and abs(heights[-1] - heights[-2]) < 0.001:
            logger.debug(f"Growth stopped for {species} at cycle {cycle}")
            break
    
    return heights


def generate_height_curves_for_species(species_list: List[str], max_cycles: int, 
                                     random_seed: int = None) -> dict:
    """
    Generate height curves for multiple species.
    
    Args:
        species_list: List of species names
        max_cycles: Maximum number of growth cycles
        random_seed: Random seed for reproducible results
        
    Returns:
        Dictionary mapping species names to height curves
    """
    curves = {}
    
    for species in species_list:
        logger.info(f"Generating height curve for {species}")
        curves[species] = generate_height_curve(species, max_cycles, random_seed)
    
    return curves