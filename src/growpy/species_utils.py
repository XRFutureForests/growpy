"""Species utilities - streamlined and focused."""

from pathlib import Path
from typing import List
import the_grove_22_core as gc

# Grove paths
DEFAULT_GROVE_PATH = Path(__file__).parent.parent / "the_grove_22"
DEFAULT_PRESETS_PATH = DEFAULT_GROVE_PATH / "presets"


def list_species() -> List[str]:
    """Get list of available tree species."""
    species = []
    for preset_file in DEFAULT_PRESETS_PATH.glob("*.seed.json"):
        species_name = preset_file.stem[:-5]  # Remove .seed extension
        if species_name and not species_name.startswith("."):
            species.append(species_name)
    return sorted(species)


def apply_species_preset(grove: gc.Grove, species: str) -> None:
    """
    Apply species preset to Grove.

    Args:
        grove: Grove object
        species: Species name
    """
    preset_path = DEFAULT_PRESETS_PATH / f"{species}.seed.json"
    
    if not preset_path.exists():
        raise FileNotFoundError(f"Species preset not found: {species}")

    with open(preset_path, "r") as f:
        preset_json = f.read()

    properties = gc.io.properties_from_json_string(preset_json)
    grove.set_properties(properties)


def get_species_preset_path(species: str) -> Path:
    """Get path to species preset file."""
    return DEFAULT_PRESETS_PATH / f"{species}.seed.json"


def validate_species_name(species: str) -> bool:
    """Validate that species name exists in presets."""
    return species in list_species()