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
        if species_name and not species_name.startswith(
            "."
        ):  # Filter out invalid names
            species.append(species_name)

    return sorted(species)


def validate_csv_data(data) -> None:
    """Validate CSV has required columns."""

    # The validate_csv_data function has been removed as it is deprecated.


def apply_species_preset(grove, species: str) -> None:
    """
    Apply species preset to Grove using Grove's built-in preset loading.

    Args:
        grove: Grove object
        species: Species name
    """
    preset_path = DEFAULT_PRESETS_PATH / f"{species}.seed.json"

    # Read preset file
    with open(preset_path, "r") as f:
        preset_json = f.read()

    # Use Grove's built-in preset loading
    properties = gc.io.properties_from_json_string(preset_json)
    grove.set_properties(properties)
    return None
