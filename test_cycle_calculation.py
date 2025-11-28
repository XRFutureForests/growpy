#!/usr/bin/env python3
"""Debug growth cycle calculation."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

import pandas as pd
import pickle
from growpy import get_config
from growpy.core.tree import calculate_growth_cycles_from_height

# Load test CSV
csv_path = Path("data/input/test.csv")
forest_data = pd.read_csv(csv_path)

print("=" * 70)
print("GROWTH CYCLE CALCULATION DEBUG")
print("=" * 70)

print("\nInput data from test.csv:")
print(forest_data[["fid", "species", "height"]])

print("\nCalling calculate_growth_cycles_from_height()...")
try:
    calculate_growth_cycles_from_height(forest_data)
    print("Success!")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\nResulting growth_cycles and delay:")
print(forest_data[["fid", "species", "height", "growth_cycles", "delay"]])

print("\n" + "=" * 70)

# Now manually verify the predictions
print("\nMANUAL VERIFICATION:")
print("=" * 70)

config = get_config()
for i, tree in forest_data.iterrows():
    species = tree["species"]
    height = tree["height"]

    print(f"\n{i+1}. {species} at height {height}m:")

    try:
        growth_model_path = config.get_growth_model_path(species)
        print(f"   Model path: {growth_model_path}")

        model_path = growth_model_path / "growth_model.pkl"
        print(f"   Model file: {model_path}")
        print(f"   File exists: {model_path.exists()}")

        if model_path.exists():
            with open(model_path, "rb") as f:
                model = pickle.load(f)

            prediction = model.predict([[height]])[0]
            prediction_int = int(prediction)

            print(f"   Raw prediction: {prediction:.1f} cycles")
            print(f"   Int prediction: {prediction_int} cycles")
            print(f"   Stored in DataFrame: {forest_data.at[i, 'growth_cycles']} cycles")
    except Exception as e:
        print(f"   ERROR: {e}")
        import traceback
        traceback.print_exc()

print("\n" + "=" * 70)
