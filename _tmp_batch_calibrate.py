"""Batch calibration for all species with yield tables."""
import sys
from pathlib import Path

src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path / "the_grove_23" / "modules"))
sys.path.insert(0, str(src_path))

from growpy.cli.compare_growth import run_comparison

# Species -> (table_id, yield_class)
# Chosen: mid-range yield classes for representative growth
SPECIES_CONFIG = {
    "Norway spruce": (2, 12),    # Fichte Bayern YC 12
    "European beech": (10, 8),   # Buche Braunschweig YC 8
    "European oak": (11, 6),     # Eiche Ungarn YC 6
    "Silver birch": (21, 4),     # Birke YC 4
    "Common ash": (12, 8),       # Esche YC 8
    "Silver fir": (5, 12),       # Tanne NWD YC 12
    "Scots pine": (9, 6),        # Kiefer Litschau YC 6
}

for species, (table_id, yc) in SPECIES_CONFIG.items():
    print(f"\n{'=' * 60}")
    print(f"  {species} (table {table_id}, YC {yc})")
    print(f"{'=' * 60}")
    run_comparison(
        species,
        table_id=table_id,
        yield_class=yc,
        calibrate=True,
    )
    print()
