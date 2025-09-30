"""Convert Unreal PVE JSON exports to Grove preset suggestions.

This utility analyzes PVE JSON files and generates suggested Grove parameters.
Note: This is not a direct conversion but provides informed starting points.
"""

import json
from pathlib import Path
from typing import Dict, Any, Optional


class PVEToGroveConverter:
    """Convert PVE parameters to Grove preset suggestions."""

    def __init__(self, pve_json_path: Path):
        """Initialize converter with PVE JSON file."""
        self.pve_path = Path(pve_json_path)
        self.pve_data = None
        self.grove_preset = {}

    def load_pve(self) -> bool:
        """Load PVE JSON file."""
        try:
            with open(self.pve_path, 'r') as f:
                self.pve_data = json.load(f)
            return True
        except Exception as e:
            print(f"Failed to load PVE file: {e}")
            return False

    def _get_pve_value(self, param_name: str, default=None) -> Any:
        """Extract parameter value from PVE global attributes."""
        if not self.pve_data:
            return default

        attrs = self.pve_data.get('globalAttributes', {})
        if param_name not in attrs:
            return default

        param = attrs[param_name]
        value = param.get('value')

        # Handle array values - take first element as representative
        if isinstance(value, list) and len(value) > 0:
            return value[0]

        return value if value is not None else default

    def convert_growth_parameters(self) -> Dict[str, Any]:
        """Convert growth-related parameters."""
        params = {}

        # Growth cycles - direct mapping
        cycle = self._get_pve_value('cycle', 10)
        params['growth_cycles'] = int(cycle) if cycle else 10

        # Elongation - map to Grove's elongation
        axial = self._get_pve_value('axialElongation', 0.5)
        lateral = self._get_pve_value('lateralElongation', 0.3)

        if axial is not None:
            # Scale to Grove's typical range (0.5-2.0)
            params['elongation'] = max(0.5, min(2.0, float(axial) * 20))

        return params

    def convert_force_parameters(self) -> Dict[str, Any]:
        """Convert physical force parameters."""
        params = {}

        # Gravitational force
        grav_force = self._get_pve_value('gravitationalForce', 0.5)
        if grav_force is not None:
            # PVE uses different scale, normalize to Grove range
            params['gravity_force'] = max(0.0, min(2.0, float(grav_force)))

        # Phototropism
        photo = self._get_pve_value('phototropism', 0.5)
        if photo is not None:
            params['phototropism'] = max(0.0, min(1.0, float(photo)))

        # Gravitropism
        gravi = self._get_pve_value('gravitropism', 0.5)
        if gravi is not None:
            params['gravitropism'] = max(0.0, min(1.0, float(gravi)))

        return params

    def convert_branching_parameters(self) -> Dict[str, Any]:
        """Convert branching-related parameters."""
        params = {}

        # Max branch generation (depth)
        max_gen = self._get_pve_value('compoundMaxBranchGeneration', 5)
        if max_gen is not None:
            params['max_order'] = int(max_gen)

        # Branch number - map to apical dominance
        max_branches = self._get_pve_value('compoundMaxBranchNumber', 10)
        if max_branches is not None:
            # More branches = less dominance
            # Map 1-20 branches to 0.8-0.3 dominance
            branches = max(1, min(20, int(max_branches)))
            params['apical_dominance'] = max(0.3, 0.8 - (branches / 20) * 0.5)

        # Branching condition threshold
        branch_cond = self._get_pve_value('branchingCondition', 0.5)
        if branch_cond is not None:
            params['branching_threshold'] = max(0.0, min(1.0, float(branch_cond)))

        return params

    def convert_random_seed(self) -> Dict[str, Any]:
        """Extract random seed if available."""
        params = {}

        seed = self._get_pve_value('randomSeed')
        if seed is not None:
            params['random_seed'] = int(seed)

        return params

    def convert(self) -> Dict[str, Any]:
        """Perform full conversion to Grove parameters."""
        if not self.pve_data:
            if not self.load_pve():
                return {}

        grove_preset = {
            'name': self.pve_path.stem,
            'description': f'Converted from Unreal PVE: {self.pve_path.name}',
            'source': 'Unreal PVE Export',
            'conversion_notes': [
                'Parameters are suggested starting points, not exact conversions',
                'Manual tuning recommended for best results',
                'Leaf/twig systems handled differently in Grove',
            ],
            'parameters': {}
        }

        # Merge all parameter categories
        grove_preset['parameters'].update(self.convert_growth_parameters())
        grove_preset['parameters'].update(self.convert_force_parameters())
        grove_preset['parameters'].update(self.convert_branching_parameters())
        grove_preset['parameters'].update(self.convert_random_seed())

        # Add Grove-specific defaults not in PVE
        grove_preset['parameters'].setdefault('thickness', 0.01)
        grove_preset['parameters'].setdefault('resolution', 16)

        return grove_preset

    def to_json(self, output_path: Optional[Path] = None) -> str:
        """Convert to JSON format."""
        preset = self.convert()

        json_str = json.dumps(preset, indent=2)

        if output_path:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(json_str)

        return json_str


def convert_pve_directory(input_dir: Path, output_dir: Path) -> None:
    """Convert all PVE JSON files in a directory."""
    input_dir = Path(input_dir)
    output_dir = Path(output_dir)

    json_files = list(input_dir.glob("*.json"))

    if not json_files:
        print(f"No JSON files found in {input_dir}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    for json_file in json_files:
        print(f"Converting: {json_file.name}")

        converter = PVEToGroveConverter(json_file)
        output_file = output_dir / f"{json_file.stem}_grove_preset.json"

        try:
            converter.to_json(output_file)
            print(f"  -> {output_file.name}")
        except Exception as e:
            print(f"  Failed: {e}")


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python pve_to_grove_converter.py <pve_json_file_or_directory> [output_dir]")
        sys.exit(1)

    input_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2]) if len(sys.argv) > 2 else None

    if input_path.is_file():
        converter = PVEToGroveConverter(input_path)
        json_output = converter.to_json(output_path)
        print(json_output)

    elif input_path.is_dir():
        if not output_path:
            output_path = input_path / "grove_presets"
        convert_pve_directory(input_path, output_path)
    else:
        print(f"Path not found: {input_path}")
        sys.exit(1)