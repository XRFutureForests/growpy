"""Convert Grove tree models to Unreal Engine PVE JSON format.

This utility exports Grove skeletons as PVE-compatible JSON files that can be
imported into Unreal Engine's Procedural Vegetation Editor.

The conversion extracts:
- Skeleton polylines as PVE curves
- Branch positions as point cloud
- Branch hierarchy information
- Growth parameters as global attributes
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import sys

# Add src to path for imports
src_path = Path(__file__).parent.parent.parent
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))

try:
    import the_grove_22_core as gc
    GROVE_AVAILABLE = True
except ImportError:
    gc = None
    GROVE_AVAILABLE = False


class GroveToPVEConverter:
    """Convert Grove tree models to UE PVE JSON format."""

    def __init__(self, grove, species_name: str):
        """Initialize converter with Grove instance."""
        if not GROVE_AVAILABLE:
            raise ImportError("Grove core not available")

        self.grove = grove
        self.species_name = species_name
        self.skeletons = None
        self.pve_data = {
            'globalAttributes': {},
            'points': {
                'attributes': {},
                'positions': []
            },
            'primitives': {
                'attributes': {},
                'points': []
            }
        }

    def extract_skeleton(self) -> bool:
        """Extract skeleton data from Grove."""
        try:
            self.skeletons = self.grove.build_skeletons()
            return bool(self.skeletons)
        except Exception as e:
            print(f"Failed to extract skeleton: {e}")
            return False

    def _convert_skeleton_to_points(self, skeleton) -> Tuple[List[List[float]], List[List[int]]]:
        """Convert Grove skeleton to PVE point cloud and polylines.

        Returns:
            Tuple of (positions, polylines)
            - positions: List of [x, y, z] coordinates
            - polylines: List of point index lists forming branches
        """
        positions = []
        polylines = []

        # Grove skeleton has 'points' and 'poly_lines'
        points = skeleton.points
        poly_lines = skeleton.poly_lines

        # Convert points to position list
        for point in points:
            # Point is a Vector or tuple (x, y, z)
            if hasattr(point, 'x'):
                positions.append([float(point.x), float(point.y), float(point.z)])
            else:
                positions.append([float(point[0]), float(point[1]), float(point[2])])

        # Convert polylines (already lists of point indices)
        for poly_line in poly_lines:
            polylines.append(list(poly_line))

        return positions, polylines

    def add_global_attributes(self, grove_properties: Optional[Dict[str, Any]] = None):
        """Add global attributes from Grove properties.

        Args:
            grove_properties: Optional dict of Grove parameters to include
        """
        attrs = self.pve_data['globalAttributes']

        # Default attributes that PVE expects
        if grove_properties:
            # Map Grove parameters to PVE equivalents
            if 'random_seed' in grove_properties:
                attrs['randomSeed'] = {
                    'type': 'int',
                    'size': 1,
                    'isArray': False,
                    'value': grove_properties['random_seed']
                }

            # Approximate cycles from grove simulation
            if 'growth_cycles' in grove_properties:
                attrs['cycle'] = {
                    'type': 'int',
                    'size': 1,
                    'isArray': False,
                    'value': grove_properties['growth_cycles']
                }

            if 'gravity_force' in grove_properties:
                attrs['gravitationalForce'] = {
                    'type': 'float',
                    'size': 1,
                    'isArray': False,
                    'value': grove_properties['gravity_force']
                }

            if 'phototropism' in grove_properties:
                attrs['phototropism'] = {
                    'type': 'float',
                    'size': 1,
                    'isArray': True,
                    'value': [
                        grove_properties['phototropism'],
                        grove_properties.get('phototropism_child', grove_properties['phototropism']),
                        0.0,
                        0.5
                    ]
                }

        # Add basic default attributes
        attrs.setdefault('cycle', {
            'type': 'int',
            'size': 1,
            'isArray': False,
            'value': 10
        })

        attrs.setdefault('cycleTime', {
            'type': 'float',
            'size': 1,
            'isArray': False,
            'value': 0.333
        })

        attrs.setdefault('compoundMaxBranchGeneration', {
            'type': 'int',
            'size': 1,
            'isArray': False,
            'value': grove_properties.get('max_order', 5) if grove_properties else 5
        })

        attrs.setdefault('randomSeed', {
            'type': 'int',
            'size': 1,
            'isArray': False,
            'value': 0
        })

    def convert(self, grove_properties: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Perform full conversion to PVE JSON format.

        Args:
            grove_properties: Optional Grove parameters to include in export

        Returns:
            PVE-compatible JSON data structure
        """
        if not self.skeletons:
            if not self.extract_skeleton():
                raise ValueError("Failed to extract skeleton from Grove")

        # Use first skeleton (main tree)
        skeleton = self.skeletons[0]

        # Convert skeleton to points and polylines
        positions, polylines = self._convert_skeleton_to_points(skeleton)

        # Populate PVE data structure
        self.pve_data['points']['positions'] = positions
        self.pve_data['primitives']['points'] = polylines

        # Add global attributes
        self.add_global_attributes(grove_properties)

        # Add minimal point attributes that PVE expects
        # Most will be empty since we're exporting skeleton only
        self.pve_data['points']['attributes'] = {
            'P': {
                'type': 'float',
                'size': 3,
                'isArray': True,
                'value': []  # Already in positions
            },
            'pscale': {
                'type': 'float',
                'size': 1,
                'isArray': True,
                'value': []
            },
            'generation': {
                'type': 'int',
                'size': 1,
                'isArray': True,
                'value': []
            }
        }

        return self.pve_data

    def save_json(self, output_path: Path) -> bool:
        """Save PVE JSON to file.

        Args:
            output_path: Path for output JSON file

        Returns:
            True if successful
        """
        try:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            with open(output_path, 'w') as f:
                json.dump(self.pve_data, f, indent=2)

            return True
        except Exception as e:
            print(f"Failed to save JSON: {e}")
            return False


def export_grove_to_pve(
    grove,
    species_name: str,
    output_path: Path,
    grove_properties: Optional[Dict[str, Any]] = None
) -> bool:
    """Export a Grove tree to PVE JSON format.

    Args:
        grove: Grove instance with simulated tree
        species_name: Name of the tree species
        output_path: Path for output JSON file
        grove_properties: Optional Grove parameters to include

    Returns:
        True if successful
    """
    try:
        converter = GroveToPVEConverter(grove, species_name)
        converter.convert(grove_properties)
        return converter.save_json(output_path)
    except Exception as e:
        print(f"Export failed: {e}")
        return False


def export_grove_forest_to_pve(
    forest_data,
    output_dir: Path,
    grove_properties: Optional[Dict[str, Any]] = None
) -> List[Path]:
    """Export multiple Grove trees (forest) to PVE JSON files.

    Args:
        forest_data: List of (grove, species_name, tree_count) tuples
        output_dir: Directory for output JSON files
        grove_properties: Optional Grove parameters to include

    Returns:
        List of successfully exported file paths
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    exported_files = []

    for grove, species_name, tree_count in forest_data:
        # Clean species name for filename
        clean_name = "".join(c for c in species_name if c.isalnum() or c in (' ', '-', '_'))
        clean_name = clean_name.replace(' ', '_')

        output_path = output_dir / f"{clean_name}_grove_export.json"

        print(f"Exporting {species_name}...")
        if export_grove_to_pve(grove, species_name, output_path, grove_properties):
            exported_files.append(output_path)
            print(f"  -> {output_path.name}")
        else:
            print(f"  Failed to export {species_name}")

    return exported_files


if __name__ == "__main__":
    print("Grove to PVE Converter")
    print("Use this module via Python API:")
    print()
    print("  from growpy import create_grove")
    print("  from growpy.utils.grove_to_pve_converter import export_grove_to_pve")
    print()
    print("  grove = create_grove('European beech')")
    print("  grove.simulate(10)")
    print("  export_grove_to_pve(grove, 'Beech', 'output/beech.json')")