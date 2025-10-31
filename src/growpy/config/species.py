"""Species data management for GrowPy."""

from typing import Any, Dict, Tuple

from .paths import _find_species_row


def get_species_data(species: str) -> Dict[str, Any]:
    """Get all data for a species from lookup table.

    Args:
        species: Species name

    Returns:
        Dict with species data
    """
    row = _find_species_row(species)
    return row.to_dict()


def get_species_colors(species: str) -> Tuple[str, str]:
    """Get branch and leaf colors for species.

    Args:
        species: Species name

    Returns:
        Tuple of (branch_color, leaf_color) as hex strings
    """
    row = _find_species_row(species)
    branch_color = row.get("Branch Color", "#7f7266")
    leaf_color = row.get("Leaf Color", "#4c9933")
    return (str(branch_color), str(leaf_color))
