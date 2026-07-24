"""Grove operations for forest simulation."""

from typing import Any

import the_grove_23_core as gc

from ..config import get_config


def create_grove(species: str | None = None, radius: float = 0.0) -> gc.Grove:
    """Create a new Grove instance with optional species preset.

    Args:
        species: Optional species name for loading preset
        radius: Surround radius (meters) to select a radius-specific calibrated
            preset for. 0 = base/open-grown preset (default).

    Returns:
        Initialized Grove instance
    """
    config = get_config()
    grove = gc.Grove()
    grove.clear_trees()

    if config.random_seed is not None:
        grove.set_random_seed(config.random_seed)

    if species:
        preset_path = config.get_preset_path(species, radius)
        with open(preset_path) as f:
            preset_json = f.read()
        properties = gc.io.properties_from_json_string(preset_json)
        grove.set_properties(properties)

    return grove


def grow_and_build_roots(
    grove: gc.Grove,
    build_params: dict[str, Any] | None = None,
) -> list[Any]:
    """Simulate root growth and build root meshes for all trees.

    Combines grove.grow_roots() and grove.build_roots() into a single call,
    matching the pattern from the Grove API exploration scripts.

    Args:
        grove: Grove instance (must have been simulated first)
        build_params: Build parameters dict (same keys as build_models()).
                      Defaults to empty dict (Grove API defaults).

    Returns:
        List of root model objects, one per tree in the grove
    """
    grove.grow_roots()
    return grove.build_roots(build_params or {})


def add_tree_to_grove(
    grove: gc.Grove, position: tuple[float, float, float], delay: int = 0
) -> None:
    """Add a tree to grove at specified position with optional growth delay.

    Args:
        grove: Grove instance to add tree to
        position: (x, y, z) coordinates for tree base
        delay: Growth delay in cycles
    """
    position_vector = gc.Vector(*position)
    direction_vector = gc.Vector(0, 0, 1)
    grove.add_new_tree(position_vector, direction_vector, delay)


def enable_surround(
    grove: gc.Grove,
    density: float = 0.7,
    distance: float = 7.0,
    height: float = 5.0,
    grow: bool = True,
) -> bool:
    """Enable Grove's built-in Surround light-competition shell on a grove.

    Surround shades the tree(s) against a statistical shell of virtual
    neighbours instead of simulating real neighbour trees, giving the tall,
    slender, self-pruned form of a forest-grown tree at a fraction of the cost
    of a multi-tree competition cluster.

    Note: Grove disables Surround when a grove holds more than one simulated
    tree together (multi-grove shade takes over), so this is meant for
    single-tree groves.

    Args:
        grove: Grove instance to configure.
        density: Surround tree density (0..1, Grove default 0.7).
        distance: Distance to the surrounding shell in metres (Grove default 7).
        height: Height of the surrounding shell in metres (Grove default 5).
        grow: Whether the shell grows together with the tree (Grove default True).

    Returns:
        True if the surround properties were applied, False if the running
        Grove build does not expose them.
    """
    props = grove.get_properties()
    if not hasattr(props, "surround_enabled"):
        return False
    props.surround_enabled = True
    props.surround_density = float(density)
    props.surround_distance = float(distance)
    props.surround_height = float(height)
    props.surround_grow = bool(grow)
    grove.set_properties(props)
    return True
