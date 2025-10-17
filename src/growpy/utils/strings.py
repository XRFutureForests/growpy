"""String utility functions for GrowPy."""


def sanitize_species_name(species: str) -> str:
    """Convert species name to safe filesystem name.

    Args:
        species: Species common name

    Returns:
        Sanitized species name safe for filesystem use
    """
    return (
        "".join(c for c in species if c.isalnum() or c in (" ", "-", "_"))
        .strip()
        .replace(" ", "_")
    )


def sanitize_filename(filename: str) -> str:
    """Convert filename to safe filesystem name.

    Args:
        filename: Original filename

    Returns:
        Sanitized filename safe for filesystem use
    """
    return "".join(c for c in filename if c.isalnum() or c in (".", "-", "_")).strip()
