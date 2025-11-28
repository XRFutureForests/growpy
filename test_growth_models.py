#!/usr/bin/env python3
"""Test growth model predictions."""

import json
import pickle
from pathlib import Path
from sklearn.linear_model import LinearRegression
import numpy as np

models_dir = Path("data/assets/growth_models")

species_list = {
    "Western redcedar": "western_redcedar",
    "European oak": "european_oak",
    "European beech": "european_beech"
}

test_heights = [6.7, 10, 15, 20, 25, 30]

print("=" * 70)
print("GROWTH MODEL PREDICTION TEST")
print("=" * 70)

for species_name, folder in species_list.items():
    print(f"\n{species_name}:")
    print("-" * 70)

    # Load the height curve
    height_curve_path = models_dir / folder / "height_curve.json"
    with open(height_curve_path) as f:
        data = json.load(f)
        heights = data['height_curve']

    print(f"Training data:")
    print(f"  Height range: {min(heights):.2f}m - {max(heights):.2f}m")
    print(f"  Cycle range: 0 - {len(heights)-1}")
    print(f"  Max height reached: {max(heights):.2f}m in {len(heights)-1} cycles")

    # Load the model
    model_path = models_dir / folder / "growth_model.pkl"
    with open(model_path, "rb") as f:
        model = pickle.load(f)

    print(f"\nModel coefficients:")
    print(f"  Slope: {model.coef_[0]:.6f}")
    print(f"  Intercept: {model.intercept_:.6f}")

    # Test predictions
    print(f"\nPredictions for test heights:")
    for h in test_heights:
        pred = model.predict([[h]])[0]
        print(f"  {h:5.1f}m -> {int(pred):3d} cycles (raw: {pred:.1f})")

    # Verify by predicting back from known training data
    print(f"\nVerification (predicting cycles from training data):")
    for cycle_idx in [0, 5, 10, 15, 20, len(heights)-1]:
        h = heights[cycle_idx]
        pred = model.predict([[h]])[0]
        print(f"  Cycle {cycle_idx:2d}: height={h:.2f}m -> predicted {pred:.1f} cycles")

print("\n" + "=" * 70)
