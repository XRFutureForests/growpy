"""
Extract all PVE attributes from Broadleaf_Hazel_04.json reference file.
Creates config files with complete attribute set for documentation purposes.
"""

import json
from pathlib import Path

# Read Hazel reference
hazel_path = Path(
    "data/ProceduralVegetationEditor/Content/SampleAssets/Tree_Common_Hazel_01/Instances/Broadleaf_Hazel_04.json"
)
with open(hazel_path, "r") as f:
    hazel_ref = json.load(f)

hazel_attrs = hazel_ref["globalAttributes"]

# Create configs for each species
configs = {
    "example_species": {
        "_comment": "PVE config for example species with all Broadleaf_Hazel_04.json attributes.",
        "_description": "All 38 Hazel attributes listed. 'value': null means preserve Grove/default data. Override by setting specific values (arrays or numbers). Grove fills: cycle, cycleTime, gravitationalForce, randomSeed, maxBranchNumber, maxBudNumber, maxPscale, minPscale, max_pscale, max_curve_length. Growth curves from pve_growth_defaults.py.",
        "_species": "example_species",
    },
    "european_beech": {
        "_comment": "PVE config for European beech (Fagus sylvatica) with all Broadleaf_Hazel_04.json attributes.",
        "_description": "Beech: dense rounded crown, simple leaves. 'value': null preserves Grove/default data. Override by setting specific values. Grove fills: cycle, cycleTime, gravitationalForce, randomSeed, maxBranchNumber, maxBudNumber, maxPscale, minPscale, max_pscale, max_curve_length. Growth curves from pve_growth_defaults.py.",
        "_species": "european_beech",
    },
    "common_hazel": {
        "_comment": "PVE config for common hazel (Corylus avellana) with all Broadleaf_Hazel_04.json attributes.",
        "_description": "Hazel: multi-stemmed shrub, simple leaves, irregular crown. 'value': null preserves Grove/default data. Override by setting specific values. Grove fills: cycle, cycleTime, gravitationalForce, randomSeed, maxBranchNumber, maxBudNumber, maxPscale, minPscale, max_pscale, max_curve_length. Growth curves from pve_growth_defaults.py.",
        "_species": "common_hazel",
    },
}

# Add all globalAttributes from Hazel
for species, config in configs.items():
    config["globalAttributes"] = {}

    for attr_name, attr_value in hazel_attrs.items():
        # Copy structure with null values as placeholder (preserves Grove/default data)
        config["globalAttributes"][attr_name] = {
            "isArray": attr_value.get("isArray", False),
            "size": attr_value.get("size", 1),
            "type": attr_value.get("type", "float"),
            "value": None,  # null = don't override, keep Grove/default value
        }

# Write config files
output_dir = Path("data/assets/pve_configs")
output_dir.mkdir(parents=True, exist_ok=True)

for species, config in configs.items():
    output_path = output_dir / f"{species}_pve.json"
    with open(output_path, "w") as f:
        json.dump(config, f, indent=2)
    print(
        f"Created {output_path.name} with {len(config['globalAttributes'])} attributes"
    )

print("\nAll config files now include complete Broadleaf_Hazel_04.json attribute set.")
print(
    "Null placeholders mean: allow Grove/default population; non-null values are preserved."
)
print("Population sources:")
print(
    "  - Grove API: cycle, cycleTime, gravitationalForce, randomSeed, maxBranchNumber, maxBudNumber, size limits"
)
print(
    "  - Growth defaults: curve arrays (axialElongation, branchingCondition, phototropism, etc.)"
)
print("  - Explicit species overrides: any non-null arrays or scalars you set here")
