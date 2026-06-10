"""Filename formatting utilities for tree export output.

Provides consistent formatting of height, DBH, and density values
for use in exported filenames across the pipeline.
"""



def format_height_for_filename(height_m: float) -> str:
    """Format height in meters for filename: h15m = 15 meters (rounded).

    Args:
        height_m: Height in meters

    Returns:
        Formatted string like 'h15m' for 15 meters
    """
    return f"h{round(height_m):02d}m"


def format_dbh_for_filename(dbh_m: float) -> str:
    """Format DBH in meters for filename: d32cm = 0.32m (32cm).

    Args:
        dbh_m: DBH in meters

    Returns:
        Formatted string like 'd32cm' for 32 centimeters
    """
    cm = int(round(dbh_m * 100))
    return f"d{cm:02d}cm"


def format_density_for_filename(twig_density: float | None) -> str:
    """Map twig_density float to dataset density label.

    Args:
        twig_density: Twig density value (0.0 to 1.0+)

    Returns:
        'full', 'reduced', or 'bare'
    """
    if twig_density is None or twig_density >= 0.9:
        return "full"
    if twig_density <= 0.01:
        return "bare"
    return "reduced"
