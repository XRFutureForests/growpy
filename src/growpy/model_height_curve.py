import pickle
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# Now import our modules
import the_grove_22_core as gc
from config import GrowPyConfig
from helper import apply_species_preset
from sklearn.linear_model import LinearRegression
from tqdm import tqdm

# Data paths
DEFAULT_DATA_PATH = Path(__file__).parent.parent.parent / "data"


def calculate_tree_height(grove, tree_index=0):
    """Calculate tree height by finding the maximum Z-coordinate of all nodes."""
    max_z = 0.0

    def traverse_branch(branch):
        nonlocal max_z
        for node in branch.nodes:
            # node.pos is the absolute position as Vector(x, y, z)
            if node.pos.z > max_z:
                max_z = node.pos.z

            # Recursively check side branches
            for side_branch in node.side_branches:
                traverse_branch(side_branch)

    # Get the first tree (trunk branch)
    if grove.trees and len(grove.trees) > tree_index:
        traverse_branch(grove.trees[tree_index])

    return max_z


csv_path = Path(DEFAULT_DATA_PATH / "demo_forest.csv")
data = pd.read_csv(csv_path)
species = data["species"].unique().tolist()

config = GrowPyConfig()
config.growth_cycles = 15

height_curves = pd.DataFrame(index=species, columns=range(config.growth_cycles))

for spec in species:
    grove = gc.Grove()
    # Clear default tree as recommended in Grove documentation
    grove.clear_trees()

    if config.random_seed:
        grove.set_random_seed(config.random_seed)

    # Apply species preset using Grove's built-in system
    apply_species_preset(grove, species=spec)

    props = grove.get_properties()

    grove.set_properties(props)

    position = gc.Vector(0.0, 0.0, 0.0)
    direction = gc.Vector(0.0, 0.0, 1.0)
    delay = 0

    grove.add_new_tree(position, direction, delay)
    heights = []
    for _ in tqdm(range(config.growth_cycles), desc="Calculating height curve"):
        grove.simulate(1)
        heights.append(calculate_tree_height(grove, 0))
    # Store the height curve for the species
    height_curves.loc[spec] = heights

# Save the height curves to a CSV file
height_curves.to_csv(DEFAULT_DATA_PATH / "height_curves.csv")

height_curves = pd.read_csv(DEFAULT_DATA_PATH / "height_curves.csv", index_col=0)

# Plot the height curves
plt.figure(figsize=(12, 6))
for spec in species:
    plt.plot(height_curves.columns, height_curves.loc[spec], label=spec)
plt.title("Tree Height Curves")
plt.xlabel("Growth Cycle")
plt.ylabel("Height (m)")
plt.legend()
plt.grid()
plt.savefig(DEFAULT_DATA_PATH / "height_curves.png")
# Create linear models to predict age from height

# Dictionary to store models for each species
height_to_age_models = {}

for spec in species:
    # Get height data for this species
    heights = np.array(height_curves.loc[spec].values)
    ages = np.array(range(1, height_curves.shape[1] + 1))

    # Create and fit linear regression model
    model = LinearRegression()
    model.fit(heights.reshape(-1, 1), ages.reshape(-1, 1))

    # Store the model
    height_to_age_models[spec] = model

# Save the models
with open(DEFAULT_DATA_PATH / "height_to_age_models.pkl", "wb") as f:
    pickle.dump(height_to_age_models, f)


# Example function to predict age from height
def predict_age_from_height(species_name: str, height: float) -> float:
    """Predict tree age from height using the linear model for the given species."""
    if species_name not in height_to_age_models:
        raise ValueError(f"No model available for species: {species_name}")

    model = height_to_age_models[species_name]
    predicted_age = model.predict([[height]])[0][0]
    return max(0, int(predicted_age))  # Ensure age is not negative


data["predicted_age"] = data.apply(
    lambda row: predict_age_from_height(row["species"], row["height"]), axis=1
)
data.to_csv(DEFAULT_DATA_PATH / "demo_forest_with_predicted_age.csv", index=False)
