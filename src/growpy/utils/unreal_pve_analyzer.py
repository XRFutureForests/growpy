"""Unreal Engine Procedural Vegetation Editor (PVE) JSON analyzer.

This module analyzes UE PVE exported JSON files to understand the procedural
growth parameters and potentially map them to Grove equivalents.
"""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional
import pandas as pd


class PVEAnalyzer:
    """Analyzer for Unreal Engine PVE JSON exports."""

    def __init__(self, json_path: Path):
        """Initialize analyzer with PVE JSON file."""
        self.json_path = Path(json_path)
        self.data = None
        self.global_attrs = None
        self.points = None
        self.primitives = None

    def load(self) -> bool:
        """Load and parse JSON file."""
        try:
            with open(self.json_path, 'r') as f:
                self.data = json.load(f)

            self.global_attrs = self.data.get('globalAttributes', {})
            self.points = self.data.get('points', {})
            self.primitives = self.data.get('primitives', {})
            return True
        except Exception as e:
            print(f"Failed to load {self.json_path}: {e}")
            return False

    def get_global_parameters(self) -> Dict[str, Any]:
        """Extract key global parameters."""
        if not self.global_attrs:
            return {}

        params = {}

        # Extract specific important parameters
        key_params = [
            'cycle',
            'cycleTime',
            'gravitationalForce',
            'axialElongation',
            'lateralElongation',
            'branchingCondition',
            'leafGrowth',
            'lightDetection',
            'phototropism',
            'gravitropism',
            'compoundMaxBranchGeneration',
            'compoundMaxBranchNumber',
        ]

        for param_name in key_params:
            if param_name in self.global_attrs:
                attr = self.global_attrs[param_name]
                params[param_name] = {
                    'type': attr.get('type'),
                    'size': attr.get('size'),
                    'isArray': attr.get('isArray'),
                    'value': attr.get('value'),
                }

        return params

    def get_point_attributes(self) -> List[str]:
        """Get list of point attribute names."""
        if not self.points:
            return []
        return list(self.points.get('attributes', {}).keys())

    def get_primitive_types(self) -> Dict[str, int]:
        """Get counts of different primitive types."""
        if not self.primitives:
            return {}

        counts = {}
        for prim_list in self.primitives.values():
            if isinstance(prim_list, list):
                for prim in prim_list:
                    if isinstance(prim, dict):
                        prim_type = prim.get('type', 'unknown')
                        counts[prim_type] = counts.get(prim_type, 0) + 1
                    elif isinstance(prim, list):
                        counts['array_element'] = counts.get('array_element', 0) + 1

        return counts

    def summarize(self) -> Dict[str, Any]:
        """Generate comprehensive summary."""
        if not self.data:
            return {}

        summary = {
            'file': str(self.json_path.name),
            'file_size_mb': self.json_path.stat().st_size / (1024 * 1024),
            'top_level_keys': list(self.data.keys()),
            'global_attributes_count': len(self.global_attrs),
            'global_attribute_names': list(self.global_attrs.keys()),
            'point_attribute_names': self.get_point_attributes(),
            'primitive_types': self.get_primitive_types(),
            'key_parameters': self.get_global_parameters(),
        }

        return summary

    def compare_to_grove(self) -> Dict[str, Any]:
        """Compare PVE parameters to Grove equivalents."""
        mapping = {
            'pve_to_grove': {
                'cycle': 'growth_cycles',
                'gravitationalForce': 'gravity_force',
                'phototropism': 'phototropism',
                'gravitropism': 'gravitropism',
                'axialElongation': 'elongation',
                'branchingCondition': 'branching_threshold',
                'compoundMaxBranchGeneration': 'max_order',
            },
            'grove_only': [
                'apical_dominance',
                'random_seed',
                'thickness',
                'resolution',
            ],
            'pve_only': [
                'cycleTime',
                'leafGrowth',
                'abscissionSenescense',
            ],
            'notes': {
                'cycle': 'Direct mapping to growth cycles',
                'gravitationalForce': 'Controls branch drooping',
                'phototropism': 'Light-seeking behavior',
                'gravitropism': 'Gravity response',
                'axialElongation': 'Primary growth direction',
                'branchingCondition': 'When branches form',
            }
        }

        return mapping


def analyze_pve_directory(directory: Path) -> pd.DataFrame:
    """Analyze all PVE JSON files in a directory."""
    json_files = list(directory.glob("*.json"))

    if not json_files:
        print(f"No JSON files found in {directory}")
        return pd.DataFrame()

    results = []

    for json_file in json_files:
        analyzer = PVEAnalyzer(json_file)
        if analyzer.load():
            summary = analyzer.summarize()

            # Flatten for DataFrame
            row = {
                'file': summary['file'],
                'size_mb': round(summary['file_size_mb'], 2),
                'global_attrs': summary['global_attributes_count'],
                'point_attrs': len(summary['point_attribute_names']),
                'primitive_types': ', '.join(f"{k}:{v}" for k, v in summary['primitive_types'].items()),
            }

            # Add key parameter values
            key_params = summary.get('key_parameters', {})
            if 'cycle' in key_params:
                cycle_val = key_params['cycle'].get('value', None)
                row['cycles'] = cycle_val if not isinstance(cycle_val, list) else cycle_val[0] if cycle_val else None

            results.append(row)

    return pd.DataFrame(results)


def extract_grove_preset_hints(json_path: Path) -> Dict[str, Any]:
    """Extract parameters that could inform Grove preset creation."""
    analyzer = PVEAnalyzer(json_path)
    if not analyzer.load():
        return {}

    params = analyzer.get_global_parameters()

    grove_hints = {
        'species_name': json_path.stem,
        'source': 'Unreal PVE Export',
        'suggested_parameters': {}
    }

    # Map PVE parameters to Grove equivalents
    if 'cycle' in params:
        grove_hints['suggested_parameters']['growth_cycles'] = params['cycle'].get('value', [10])[0]

    if 'gravitationalForce' in params:
        grove_hints['suggested_parameters']['gravity_force'] = params['gravitationalForce'].get('value', [0.5])[0]

    if 'phototropism' in params:
        grove_hints['suggested_parameters']['phototropism'] = params['phototropism'].get('value', [0.5])[0]

    if 'gravitropism' in params:
        grove_hints['suggested_parameters']['gravitropism'] = params['gravitropism'].get('value', [0.5])[0]

    return grove_hints


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        path = Path(sys.argv[1])

        if path.is_file():
            analyzer = PVEAnalyzer(path)
            if analyzer.load():
                summary = analyzer.summarize()
                print(json.dumps(summary, indent=2, default=str))

        elif path.is_dir():
            df = analyze_pve_directory(path)
            print(df.to_string())
    else:
        print("Usage: python unreal_pve_analyzer.py <json_file_or_directory>")