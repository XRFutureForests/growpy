#!/usr/bin/env python3
"""
Script to map species to growth models and update the CSV.
"""

import csv
from pathlib import Path


def create_species_to_growth_model_mapping():
    """Create mapping from species to growth model directories."""

    # Manual mapping based on the CSV and growth_models directory
    # This maps common names to their corresponding growth model directory names
    species_to_growth_model = {
        "European beech": "Fagaceae_Beech",
        "Norway spruce": "Pinaceae_Fir",  # Uses Fir model
        "Scots pine": "Pinaceae_Scots_pine",
        "Silver fir": "Pinaceae_Fir",
        "European oak": "Fagaceae_European_oak",
        "Common ash": "Oleaceae_Ash",
        "Downy birch": "Betulaceae_Downy_birch",
        "Silver birch": "Betulaceae_Silver_birch",
        "Black alder": "Betulaceae_Alder",
        "Hornbeam": "Betulaceae_Hornbeam",
        "Hazel": "Betulaceae_Hazel",
        "Field maple": "Sapindaceae_Field_maple",
        "Sycamore maple": "Sapindaceae_Maple",
        "Small-leaved linden": "Malvaceae_Linden",
        "Horse chestnut": "Sapindaceae_Horse_chestnut",
        "Wild cherry": "Rosaceae_Wild_cherry",
        "Rowan / Mountain ash": "Rosaceae_Hawthorn",  # Uses Hawthorn model
        "Willow": "Salicaceae_Willow",
        "Poplar": "Salicaceae_Grey_poplar",  # Uses Grey poplar model
        "Elm": "Ulmaceae_Elm",
        "Wild apple": "Rosaceae_Wild_apple",
        "Yew": "Taxaceae_Yew",
    }

    return species_to_growth_model


def update_csv_with_growth_models():
    """Update the CSV to include growth models and change Model to Preset."""

    csv_path = Path(
        "/Users/maximiliansperlich/Developer/the-grove/data/tree_asset_lookup.csv"
    )
    growth_models_dir = Path(
        "/Users/maximiliansperlich/Developer/the-grove/data/growth_models"
    )

    # Get the mapping
    species_mapping = create_species_to_growth_model_mapping()

    # Read the current CSV
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            common_name = row["Common Name"].strip()

            # Add growth model if available
            growth_model = species_mapping.get(common_name, "")
            if growth_model and (growth_models_dir / growth_model).exists():
                row["Growth Model"] = growth_model
            else:
                row["Growth Model"] = ""

            # Change 'Model' to 'Preset'
            row["Preset"] = row["Model"]
            del row["Model"]

            rows.append(row)

    # Write the updated CSV
    new_csv_path = (
        csv_path.parent
        / "CommonName-ScientificName-Preset-Twig-BarkTexture-GrowthModel.csv"
    )

    with open(new_csv_path, "w", encoding="utf-8", newline="") as f:
        if rows:
            fieldnames = [
                "Common Name",
                "Scientific Name",
                "Preset",
                "Twig",
                "Bark Texture",
                "Growth Model",
            ]
            writer = csv.DictWriter(f, fieldnames=fieldnames, quoting=csv.QUOTE_ALL)
            writer.writeheader()
            writer.writerows(rows)

    print(f"Updated CSV written to: {new_csv_path}")

    # Show a sample of what was created
    print("\nSample of updated data:")
    for i, row in enumerate(rows[:5]):
        print(f"{row['Common Name']}: {row['Preset']} -> {row['Growth Model']}")


if __name__ == "__main__":
    update_csv_with_growth_models()
