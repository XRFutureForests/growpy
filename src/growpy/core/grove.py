"""Grove operations for forest simulation."""

from typing import Optional, Tuple

try:
    import the_grove_22_core as gc
    GROVE_CORE_AVAILABLE = True
except ImportError:
    gc = None
    GROVE_CORE_AVAILABLE = False

from ..config import get_config


def create_grove(species: Optional[str] = None):
    """Create a new Grove instance with optional species preset.

    Creates an empty Grove simulation instance. If a species name is provided,
    loads and applies the species-specific growth parameters from preset files.

    Args:
        species: Optional species name (e.g., "European Beech", "Scots Pine").
                 If provided, loads preset from config.presets_path

    Returns:
        Initialized Grove instance ready for tree placement and simulation

    Raises:
        ImportError: If Grove core (the_grove_22_core) is not available
        FileNotFoundError: If species preset file not found
    """
    if not GROVE_CORE_AVAILABLE:
        raise ImportError("Grove core (the_grove_22_core) not available")

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
    """Add a tree to grove at specified position with optional growth delay.

    Trees are added with upward growth direction (Z-axis up).

    Args:
        grove: Grove instance to add tree to
        position: (x, y, z) coordinates for tree base position
        delay: Growth delay in cycles (0 = start growing immediately)
    """
    position_vector = gc.Vector(*position)
    direction_vector = gc.Vector(0, 0, 1)
    grove.add_new_tree(position_vector, direction_vector, delay)
