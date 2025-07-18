"""
Grove creation and tree simulation utilities.
"""

from typing import List, Tuple

import pandas as pd
import the_grove_22_core as gc

from ..species_utils import apply_species_preset

ForestData = List[Tuple[gc.Grove, str, int]]
TreePosition = gc.Vector
TreeDirection = gc.Vector


def create_groves_from_data(
    data: pd.DataFrame, growth_cycles: int, config
) -> ForestData:
    forest_data = []
    for species_name, species_group in data.groupby("species"):
        grove = _create_grove_for_species(
            str(species_name), species_group, growth_cycles, config
        )
        forest_data.append((grove, str(species_name), len(species_group)))
    return forest_data


def _create_grove_for_species(
    species_name: str, species_data: pd.DataFrame, max_cycles: int, config
) -> gc.Grove:
    grove = gc.Grove()
    grove.clear_trees()
    if config.random_seed:
        grove.set_random_seed(config.random_seed)
    apply_species_preset(grove, species_name)
    _add_trees_to_grove(grove, species_data, max_cycles, config)
    return grove


def _add_trees_to_grove(
    grove: gc.Grove, species_data: pd.DataFrame, max_cycles: int, config
) -> None:
    for _, tree_row in species_data.iterrows():
        position = _create_tree_position(tree_row)
        direction = _create_default_direction()
        delay = _calculate_simple_delay(tree_row, max_cycles, config)
        grove.add_new_tree(position, direction, delay)


def _create_tree_position(tree_row: pd.Series) -> TreePosition:
    x, y, z = float(tree_row.x), float(tree_row.y), float(tree_row.z)
    return gc.Vector(x, y, z)


def _create_default_direction() -> TreeDirection:
    return gc.Vector(0.0, 0.0, 1.0)


def _calculate_simple_delay(tree_row: pd.Series, max_cycles: int, config) -> int:
    required_cycles = tree_row["required_cycles"]
    delay = max_cycles - required_cycles
    return max(0, delay)
