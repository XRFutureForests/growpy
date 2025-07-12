import sys
from pathlib import Path
from typing import List

# Add Grove modules to path

# Grove paths
DEFAULT_GROVE_PATH = Path(__file__).parent.parent / "the_grove_22"
DEFAULT_PRESETS_PATH = DEFAULT_GROVE_PATH / "presets"
DEFAULT_MODULES_PATH = DEFAULT_GROVE_PATH / "modules"

sys.path.insert(0, str(DEFAULT_MODULES_PATH))

import the_grove_22_core as gc

def list_species() -> List[str]:
    """Get list of available tree species."""
    species = []
    for preset_file in DEFAULT_PRESETS_PATH.glob("*.seed.json"):
        species_name = preset_file.stem[:-5]
        species.append(species_name)

    return sorted(species)


def validate_csv_data(data) -> None:
    """Validate CSV has required columns."""
    required = ["x", "y", "z", "species"]
    missing = [col for col in required if col not in data.columns]
    if missing:
        raise ValueError(f"Missing columns: {missing}")

    for col in required:
        if data[col].isnull().any():
            raise ValueError(f"Column '{col}' contains missing values")

    # Validate species
    unique_species = data["species"].unique()
    available_species = list_species()
    invalid_species = [s for s in unique_species if s not in available_species]
    if invalid_species:
        raise ValueError(
            f"Invalid species found in CSV: {invalid_species}. "
            f"Available species: {available_species}"
        )


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