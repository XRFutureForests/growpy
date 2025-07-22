"""Grove creation and management functions."""

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import the_grove_22_core as gc


def list_species() -> List[str]:
    """Get list of available tree species from Grove's presets."""
    grove_root = Path(__file__).parent.parent / "the_grove_22"
    presets_path = grove_root / "presets"

    species = []
    for preset_file in presets_path.glob("*.seed.json"):
        species_name = preset_file.stem[:-5]  # Remove .seed extension
        if species_name and not species_name.startswith("."):
            species.append(species_name)
    return sorted(species)


def create_grove(
    species: Optional[str] = None, random_seed: Optional[int] = None
) -> gc.Grove:
    """Create a new Grove, optionally with species preset and random seed."""
    grove = gc.Grove()
    grove.clear_trees()  # Clear default tree as per documentation

    if random_seed is not None:
        grove.set_random_seed(random_seed)

    if species:
        apply_species_preset(grove, species)

    return grove


def apply_species_preset(grove: gc.Grove, species: str) -> None:
    """Apply species preset to Grove using Grove's core io functionality."""
    grove_root = Path(__file__).parent.parent / "the_grove_22"
    preset_path = grove_root / "presets" / f"{species}.seed.json"

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


def calculate_shared_shade(groves: List[gc.Grove]) -> None:
    """Calculate shared light competition between groves using Grove's core shade system."""
    if len(groves) <= 1:
        return

    # Collect shade geometry from all groves
    all_coords = []
    for grove in groves:
        all_coords.extend(grove.create_shade_geometry_coords())

    # Apply shared shade calculation to each grove
    for grove in groves:
        grove.calculate_shade_together(all_coords)


def save_grove_to_json(grove: gc.Grove, output_path: Path) -> None:
    """Save grove to JSON file using Grove's core io functionality."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    json_string = gc.io.grove_to_json_string(grove)

    with open(output_path, "w") as f:
        f.write(json_string)


def load_grove_from_json(json_path: Path) -> gc.Grove:
    """Load grove from JSON file using Grove's core io functionality."""
    with open(json_path, "r") as f:
        json_string = f.read()

    return gc.io.grove_from_json_string(json_string)
