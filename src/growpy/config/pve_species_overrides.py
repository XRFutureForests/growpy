"""
Species-specific PVE attribute overrides.

Provides functionality to load per-species configuration files that override
attributes not available from the Grove API.
"""

import json
from pathlib import Path
from typing import Any, Dict, Optional


def load_species_pve_config(
    species_name: str, config_dir: Optional[Path] = None
) -> Optional[Dict[str, Any]]:
    """
    Load species-specific PVE attribute overrides from JSON config.

    Searches for config file in order:
    1. Specified config_dir
    2. data/assets/pve_configs/
    3. Returns None if not found

    Args:
        species_name: Species name (e.g., "european_beech" or "European beech")
        config_dir: Optional directory to search for config files

    Returns:
        Dictionary with PVE attribute overrides, or None if not found
    """
    # Normalize species name to lowercase with underscores
    normalized_name = species_name.lower().replace(" ", "_")

    search_paths = []

    if config_dir:
        search_paths.append(Path(config_dir) / f"{normalized_name}_pve.json")

    # Default location in assets
    search_paths.append(Path("data/assets/pve_configs") / f"{normalized_name}_pve.json")

    for config_path in search_paths:
        if config_path.exists():
            try:
                with open(config_path, "r") as f:
                    config = json.load(f)
                return config
            except Exception as e:
                print(f"Warning: Failed to load PVE config from {config_path}: {e}")

    return None


def create_example_pve_config(
    output_path: Path, species_name: str = "example_species"
) -> None:
    """
    Create an example PVE species configuration file.

    This shows which attributes can be overridden per species.

    Args:
        output_path: Path to write example config
        species_name: Species name to use in example
    """
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
    with open(output_path, "w", indent=2) as f:
        json.dump(example_config, f, indent=2)

    print(f"Created example PVE config at {output_path}")


def apply_species_overrides(
    pve_preset: Dict[str, Any],
    species_name: str,
    config_dir: Optional[Path] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    """
    Apply species-specific overrides to PVE preset.

    Loads config file and merges overrides into the preset's globalAttributes.

    Args:
        pve_preset: PVE preset dictionary to modify
        species_name: Species name for config lookup
        config_dir: Optional config directory
        verbose: Print override information

    Returns:
        Modified PVE preset dictionary
    """
    config = load_species_pve_config(species_name, config_dir)

    if not config:
        if verbose:
            print(f"No PVE config found for {species_name}, using defaults")
        return pve_preset

    # Merge globalAttributes overrides
    if "globalAttributes" in config:
        override_count = 0
        for key, value in config["globalAttributes"].items():
            # Skip if value is None/null (placeholder to keep Grove/default value)
            if value.get("value") is None:
                continue

            if key in pve_preset["globalAttributes"]:
                # Replace existing value with override
                pve_preset["globalAttributes"][key] = value
                override_count += 1
            else:
                # Add new attribute not in template
                pve_preset["globalAttributes"][key] = value
                override_count += 1

        if verbose:
            print(
                f"Applied {override_count} attribute overrides from config for {species_name}"
            )

    return pve_preset


def create_null_placeholder_config(
    output_path: Path, species_name: str, common_name: str
) -> None:
    """
    Create a PVE config with null placeholders for all overridable attributes.

    Null values signal to use computed values from Grove or sensible defaults.
    Users can edit this file to provide species-specific overrides.

    Includes ALL attributes found in Hazel reference for maximum customizability.

    Args:
        output_path: Path to write config file
        species_name: Normalized species name (e.g., "european_beech")
        common_name: Display name (e.g., "European Beech")
    """
    config = {
        "_comment": f"PVE attribute overrides for {common_name}",
        "_description": "Set values to customize, or leave as null to use computed/default values",
        "_species": species_name,
        "globalAttributes": {
            # Simulation parameters - null = use Grove values
            "cycle": {"isArray": False, "size": 1, "type": "int", "value": None},
            "cycleTime": {"isArray": False, "size": 1, "type": "float", "value": None},
            "randomSeed": {"isArray": False, "size": 1, "type": "int", "value": None},
            # Growth curves - null = use Hazel defaults
            "abscissionSenescense": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "axialElongation": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "axialElongationChild": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "branchingCondition": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "branchingConditionChild": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "lateralElongation": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "lateralElongationChild": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "leafGrowth": {"isArray": True, "size": 1, "type": "float", "value": None},
            "lightDetection": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "trunkGrowth": {"isArray": True, "size": 1, "type": "float", "value": None},
            # Physical parameters - null = use Grove/default values
            "gravitationalForce": {
                "isArray": False,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "guide": {"isArray": True, "size": 1, "type": "float", "value": None},
            # Light-seeking behavior - null = use Hazel defaults
            "phototropism": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "phototropismChild": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            # Branching angles - null = use Hazel defaults
            "phyllotaxy": {"isArray": True, "size": 1, "type": "float", "value": None},
            "phyllotaxyChild": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "phyllotaxyLeaf": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "randomAngle": {"isArray": True, "size": 1, "type": "float", "value": None},
            "randomAngleChild": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            # Crown shape profiles - null = use generated naturalistic profiles
            "plantProfile_1": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "plantProfile_2": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "plantProfile_3": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "plantProfile_4": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "plantProfile_5": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
            # Branch/bud metadata - null = compute from skeleton
            "maxBranchNumber": {
                "isArray": False,
                "size": 1,
                "type": "int",
                "value": None,
            },
            "maxBudNumber": {"isArray": False, "size": 1, "type": "int", "value": None},
            # Compound leaf parameters - null = use defaults (0 for simple leaves)
            "compoundMaxBranchGeneration": {
                "isArray": False,
                "size": 1,
                "type": "int",
                "value": None,
            },
            "compoundMaxBranchNumber": {
                "isArray": False,
                "size": 1,
                "type": "int",
                "value": None,
            },
            # Photogrammetry - null = use default (0 = procedural)
            "photogrammetryTrunk": {
                "isArray": False,
                "size": 1,
                "type": "int",
                "value": None,
            },
            # Scale parameters - null = compute from skeleton or use defaults
            "maxPscale": {"isArray": False, "size": 1, "type": "float", "value": None},
            "minPscale": {"isArray": False, "size": 1, "type": "float", "value": None},
            "max_curve_length": {
                "isArray": False,
                "size": 1,
                "type": "float",
                "value": None,
            },
            "max_pscale": {"isArray": False, "size": 1, "type": "float", "value": None},
            "maxPscales": {"isArray": True, "size": 1, "type": "float", "value": None},
            "maxDavinciPscales": {
                "isArray": True,
                "size": 1,
                "type": "float",
                "value": None,
            },
        },
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)


def extract_pve_overrides_from_reference(
    reference_json_path: Path, output_path: Path, species_name: str
) -> None:
    """
    Extract overridable attributes from a reference PVE JSON (like Hazel).

    Creates a config file with only the attributes that cannot be extracted from Grove.

    Args:
        reference_json_path: Path to reference JSON (e.g., Hazel)
        output_path: Path to write config file
        species_name: Species name for the config
    """
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
