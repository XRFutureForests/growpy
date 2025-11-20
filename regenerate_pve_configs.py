"""
Regenerate PVE config files with species-specific overrides only.
These configs provide only the attributes that cannot be extracted from Grove API.
"""

import json
import math
from pathlib import Path


def generate_profile(base_values, variation=0.02):
    """Generate a 100-point crown profile with natural variation."""
    angles = [2 * math.pi * i / 100 for i in range(100)]
    profile = []
    for i, angle in enumerate(angles):
        base = base_values[i % len(base_values)]
        var = variation * math.sin(angle * 5 + i * 0.1)
        profile.append(round(base + var, 2))
    return profile


# Example species config
example_config = {
    "_comment": "PVE species-specific overrides for example species. Only includes attributes that cannot be extracted from Grove API.",
    "_description": "Growth curves (phototropism, phyllotaxy, etc.) come from pve_growth_defaults.py. Only override plantProfiles and compound leaf parameters here.",
    "_species": "example_species",
    "globalAttributes": {
        "plantProfile_1": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.85, 0.90, 0.95, 1.0, 0.95, 0.90]),
        },
        "plantProfile_2": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.82, 0.88, 0.94, 1.0, 0.94, 0.88]),
        },
        "plantProfile_3": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.88, 0.92, 0.97, 1.0, 0.97, 0.92]),
        },
        "plantProfile_4": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.90, 0.94, 0.98, 1.0, 0.98, 0.94]),
        },
        "plantProfile_5": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.92, 0.96, 0.99, 1.0, 0.99, 0.96]),
        },
        "compoundMaxBranchGeneration": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": 0,
        },
        "compoundMaxBranchNumber": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": 1,
        },
    },
}

# European beech config
beech_config = {
    "_comment": "PVE species-specific overrides for European beech (Fagus sylvatica). Dense, rounded crown with smooth bark.",
    "_description": "Beech has a dense, rounded crown. Simple leaves (not compound). Growth curves handled by pve_growth_defaults.py.",
    "_species": "european_beech",
    "globalAttributes": {
        "plantProfile_1": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.88, 0.92, 0.96, 1.0, 0.96, 0.92]),
        },
        "plantProfile_2": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.86, 0.90, 0.95, 1.0, 0.95, 0.90]),
        },
        "plantProfile_3": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.90, 0.94, 0.98, 1.0, 0.98, 0.94]),
        },
        "plantProfile_4": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.92, 0.96, 0.99, 1.0, 0.99, 0.96]),
        },
        "plantProfile_5": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.94, 0.97, 1.0, 1.0, 1.0, 0.97]),
        },
        "compoundMaxBranchGeneration": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": 0,
        },
        "compoundMaxBranchNumber": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": 1,
        },
    },
}

# Common hazel config
hazel_config = {
    "_comment": "PVE species-specific overrides for common hazel (Corylus avellana). Multi-stemmed shrub.",
    "_description": "Hazel is a multi-stemmed shrub/small tree with simple leaves. Rounded, irregular crown.",
    "_species": "common_hazel",
    "globalAttributes": {
        "plantProfile_1": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.82, 0.88, 0.94, 1.0, 0.94, 0.88]),
        },
        "plantProfile_2": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.80, 0.86, 0.92, 1.0, 0.92, 0.86]),
        },
        "plantProfile_3": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.84, 0.90, 0.96, 1.0, 0.96, 0.90]),
        },
        "plantProfile_4": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.86, 0.92, 0.98, 1.0, 0.98, 0.92]),
        },
        "plantProfile_5": {
            "isArray": True,
            "size": 1,
            "type": "float",
            "value": generate_profile([0.88, 0.94, 0.99, 1.0, 0.99, 0.94]),
        },
        "compoundMaxBranchGeneration": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": 0,
        },
        "compoundMaxBranchNumber": {
            "isArray": False,
            "size": 1,
            "type": "int",
            "value": 1,
        },
    },
}


def main():
    output_dir = Path("data/assets/pve_configs")
    output_dir.mkdir(parents=True, exist_ok=True)

    with open(output_dir / "example_species_pve.json", "w") as f:
        json.dump(example_config, f, indent=2)

    with open(output_dir / "european_beech_pve.json", "w") as f:
        json.dump(beech_config, f, indent=2)

    with open(output_dir / "common_hazel_pve.json", "w") as f:
        json.dump(hazel_config, f, indent=2)

    print("Successfully regenerated PVE config files:")
    print("- example_species_pve.json (generic template with varied profiles)")
    print("- european_beech_pve.json (dense, rounded crown)")
    print("- common_hazel_pve.json (irregular, multi-stemmed crown)")
    print("\nAll configs include only species-specific overrides:")
    print("  - plantProfile_1 through plantProfile_5 (crown shapes)")
    print("  - compoundMaxBranchGeneration and compoundMaxBranchNumber")
    print("\nGrowth curves come from pve_growth_defaults.py")


if __name__ == "__main__":
    main()
