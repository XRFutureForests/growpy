#!/usr/bin/env python3
"""
Extract PVE species config from Hazel reference JSON.

Creates a config file that can be copied and modified for other species.
"""

import json
from pathlib import Path


def extract_pve_overrides_from_reference(
    reference_json_path: Path, output_path: Path, species_name: str
):
    """Extract overridable attributes from reference JSON."""
    with open(reference_json_path, "r") as f:
        reference = json.load(f)

    global_attrs = reference.get("globalAttributes", {})

    # Extract only non-Grove attributes
    config = {
        "_comment": f"PVE overrides extracted from {reference_json_path.name}",
        "_species": species_name,
        "globalAttributes": {},
    }

    # Attributes to extract (not available from Grove)
    extract_keys = [
        "plantProfile_1",
        "plantProfile_2",
        "plantProfile_3",
        "plantProfile_4",
        "plantProfile_5",
        "maxBranchNumber",
        "maxBudNumber",
        "compoundMaxBranchGeneration",
        "compoundMaxBranchNumber",
        "photogrammetryTrunk",
        "maxPscale",
        "minPscale",
        "max_curve_length",
        "max_pscale",
    ]

    for key in extract_keys:
        if key in global_attrs:
            config["globalAttributes"][key] = global_attrs[key]

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)

    print(f"Extracted PVE overrides to {output_path}")
    print(f"  Extracted {len(config['globalAttributes'])} attributes")


def create_example_pve_config(output_path: Path, species_name: str = "example_species"):
    """Create an example PVE species configuration file."""
    example_config = {
        "_comment": f"PVE attribute overrides for {species_name}",
        "_description": "Override globalAttributes that cannot be extracted from Grove API",
        "globalAttributes": {
            # Crown shape profiles - 100 float arrays defining tree silhouette
            "plantProfile_1": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [0.85] * 100,  # Example: constant 0.85 profile
            },
            "plantProfile_2": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [0.80] * 100,
            },
            "plantProfile_3": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [0.90] * 100,
            },
            "plantProfile_4": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [0.95] * 100,
            },
            "plantProfile_5": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": [0.98] * 100,
            },
            # Optional metadata overrides
            "maxBranchNumber": {
                "isArray": False,
                "size": 1,
                "type": "int",
                "value": 17,
            },
            "maxBudNumber": {"isArray": False, "size": 1, "type": "int", "value": 79},
            # Compound leaf parameters (if species has compound leaves)
            "compoundMaxBranchGeneration": {
                "isArray": False,
                "size": 1,
                "type": "int",
                "value": 0,  # 0 = no compound leaves
            },
            "compoundMaxBranchNumber": {
                "isArray": False,
                "size": 1,
                "type": "int",
                "value": 0,
            },
            # Photogrammetry flag
            "photogrammetryTrunk": {
                "isArray": False,
                "size": 1,
                "type": "int",
                "value": 0,  # 0 = procedural, 1 = photogrammetry
            },
            # Deprecated scale values (usually 0)
            "maxPscale": {"isArray": False, "size": 1, "type": "float", "value": 0.0},
            "minPscale": {"isArray": False, "size": 1, "type": "float", "value": 0.0},
            "max_curve_length": {
                "isArray": False,
                "size": 1,
                "type": "float",
                "value": 0.0,
            },
            "max_pscale": {"isArray": False, "size": 1, "type": "float", "value": 0.0},
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(example_config, f, indent=2)

    print(f"Created example PVE config at {output_path}")


def main():
    """Extract Hazel config and create example."""
    # Navigate to project root (3 levels up from this file)
    project_root = Path(__file__).parent.parent.parent.parent

    # Hazel reference JSON
    hazel_reference = (
        project_root
        / "data"
        / "ProceduralVegetationEditor"
        / "Content"
        / "SampleAssets"
        / "Tree_Common_Hazel_01"
        / "Instances"
        / "Broadleaf_Hazel_04.json"
    )

    output_dir = project_root / "data" / "assets" / "pve_configs"
    output_dir.mkdir(parents=True, exist_ok=True)

    if hazel_reference.exists():
        print("Extracting PVE config from Hazel reference...")
        hazel_output = output_dir / "common_hazel_pve.json"
        extract_pve_overrides_from_reference(
            hazel_reference, hazel_output, "common_hazel"
        )
    else:
        print(f"Warning: Hazel reference not found at {hazel_reference}")

    # Create example template
    print("\nCreating example PVE config template...")
    example_output = output_dir / "example_species_pve.json"
    create_example_pve_config(example_output, "example_species")

    print(f"\n✓ Config files created in {output_dir}")
    print("\nTo use for a specific species:")
    print("1. Copy example_species_pve.json to <species_name>_pve.json")
    print("2. Edit the plantProfile_* arrays to match species crown shape")
    print("3. Adjust other parameters as needed")
    print("4. Place in data/assets/pve_configs/")


if __name__ == "__main__":
    main()
