"""
Forest growth simulation with light competition.
"""

from typing import List

import the_grove_22_core as gc
from tqdm import tqdm


def simulate_forest_growth(forest_data, config, growth_cycles: int) -> None:
    if not forest_data:
        return
    grove_objects = _extract_grove_objects(forest_data)
    for _ in tqdm(range(growth_cycles), desc="Growing forest", unit="cycle"):
        shade_coordinates = _collect_shade_geometry(grove_objects)
        _simulate_growth_cycle(grove_objects, shade_coordinates)


def _extract_grove_objects(forest_data) -> List[gc.Grove]:
    return [grove for grove, _, _ in forest_data]


def _collect_shade_geometry(grove_objects: List[gc.Grove]) -> List:
    coordinates = []
    for grove in grove_objects:
        coordinates.extend(grove.create_shade_geometry_coords())
    return coordinates


def _simulate_growth_cycle(
    grove_objects: List[gc.Grove], shade_coordinates: List
) -> None:
    for grove in grove_objects:
        grove.calculate_shade_together(shade_coordinates)
        grove.simulate(1)
