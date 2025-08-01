"""
Species growth analysis utility for The Grove 2.2.

This utility generates height curves and age prediction models for Grove species presets
from the prepared GrowPy assets directory. This script works exclusively with the
prepared assets and does not require access to The Grove 2.2 installation.

Run prepare_assets.py first to copy species presets from Grove installation.

Usage:
    python src/growpy/utils/species_growth_analysis.py
    python src/growpy/utils/species_growth_analysis.py --assets_dir data/assets
    python src/growpy/utils/species_growth_analysis.py --species "Fagaceae - European oak" --cycles 25
"""

import argparse
import json
import logging
import multiprocessing as mp
import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

# Scientific computing imports
import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
import numpy as np
import pandas as pd
from sklearn.linear_model import LinearRegression
from tqdm import tqdm

# Add src to path for Grove imports
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "the_grove_22" / "modules"))

import the_grove_22_core as gc

# Use refactored growpy package
from growpy import GrowPyConfig

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def process_single_species_parallel(args_tuple):
    """
    Process a single species in parallel.

    This function is designed to be called by multiprocessing workers.
    It takes a tuple of arguments to work around multiprocessing limitations.

    Args:
        args_tuple: Tuple of (species, assets_dir, height_model_flushes, num_seeds)

    Returns:
        Tuple of (species, success, results_dict, error_message)
    """
    species, assets_dir, height_model_flushes, num_seeds = args_tuple

    try:
        # Set up logging for this process
        process_logger = logging.getLogger(f"species_{species}")

        # Import Grove modules inside the worker process to avoid pickling issues
        import sys
        from pathlib import Path

        # Add src to path for Grove imports
        src_path = Path(assets_dir).parent.parent / "src"
        sys.path.insert(0, str(src_path))
        sys.path.insert(0, str(src_path / "the_grove_22" / "modules"))

        import the_grove_22_core as gc

        from growpy import GrowPyConfig

        # Create a temporary analyzer instance for this species
        analyzer = SpeciesGrowthAnalyzer(assets_dir, height_model_flushes, num_seeds)

        # Generate height and DBH curves
        height_curve, dbh_curve, metadata = analyzer.generate_height_curve_for_species(
            species
        )

        # Create growth model
        growth_model = analyzer.create_growth_model_for_species(species, height_curve)

        # Prepare results dictionary
        results = {
            "height_curve": height_curve,
            "dbh_curve": dbh_curve,
            "metadata": metadata,
            "growth_model": growth_model,
        }

        return (species, True, results, None)

    except Exception as e:
        error_msg = f"Failed to process {species}: {str(e)}"
        return (species, False, None, error_msg)


class SpeciesGrowthAnalyzer:
    """Analyzes growth patterns for Grove species and creates prediction models."""

    def __init__(
        self, assets_dir: Path, height_model_flushes: int = 75, num_seeds: int = 3
    ):
        """
        Initialize the growth analyzer.

        Args:
            assets_dir: Directory containing prepared GrowPy assets
            height_model_flushes: Number of growth cycles for height curve generation
            num_seeds: Number of different random seeds to average for robust curves
        """
        self.assets_dir = Path(assets_dir)
        self.presets_dir = self.assets_dir / "presets"
        self.output_dir = self.assets_dir / "growth_models"

        # Validate assets directory
        if not self.assets_dir.exists():
            raise FileNotFoundError(f"Assets directory not found: {self.assets_dir}")

        if not self.presets_dir.exists():
            raise FileNotFoundError(f"Presets directory not found: {self.presets_dir}")

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.height_model_flushes = height_model_flushes
        self.num_seeds = num_seeds

        # Results storage
        self.height_curves = {}  # species -> list of heights per cycle
        self.dbh_curves = {}  # species -> list of DBH values per cycle
        self.growth_models = {}  # species -> sklearn model
        self.analysis_metadata = {}  # species -> analysis info

    def apply_species_preset(self, grove, species: str) -> bool:
        """
        Apply a species preset to a grove from the assets directory.

        Args:
            grove: Grove object to apply preset to
            species: Species name

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the preset file
            preset_file = self.presets_dir / f"{species}.seed.json"
            if not preset_file.exists():
                logger.error(f"Preset file not found: {preset_file}")
                return False

            # Load and apply preset
            with open(preset_file, "r") as f:
                preset_data = json.load(f)

            # Apply preset properties to grove
            # This is a simplified version - you may need to adapt based on the exact preset structure
            if "properties" in preset_data:
                for prop_name, prop_value in preset_data["properties"].items():
                    if hasattr(grove, prop_name):
                        setattr(grove, prop_name, prop_value)

            logger.debug(f"Applied preset for species: {species}")
            return True

        except Exception as e:
            logger.error(f"Failed to apply species preset {species}: {e}")
            return False

    def get_available_species(self) -> List[str]:
        """Get list of all available Grove species presets from assets directory."""
        try:
            species_list = []

            # Get all .json preset files
            preset_files = list(self.presets_dir.glob("*.json"))

            for preset_file in preset_files:
                # Skip hidden files and special presets
                if preset_file.name.startswith("."):
                    continue

                # Extract species name from filename (remove .seed.json extension)
                species_name = preset_file.stem
                if species_name.endswith(".seed"):
                    species_name = species_name[:-5]  # Remove .seed

                species_list.append(species_name)

            logger.info(
                f"Found {len(species_list)} species presets in assets directory"
            )
            return sorted(species_list)

        except Exception as e:
            logger.error(f"Failed to get available species: {e}")
            # Fallback to GrowPyConfig if available
            try:
                config = GrowPyConfig()
                return config.get_available_species()
            except Exception:
                # Final fallback to manual directory scanning
                presets_dir = Path(__file__).parent.parent / "the_grove_22" / "presets"

                if not presets_dir.exists():
                    raise FileNotFoundError(
                        f"Presets directory not found: {presets_dir}"
                    )

                species_list = []
                for preset_file in presets_dir.glob("*.seed.json"):
                    try:
                        species_name = preset_file.stem
                        if species_name.endswith(".seed"):
                            species_name = species_name[:-5]

                        if species_name and not species_name.startswith("."):
                            species_list.append(species_name)
                    except Exception:
                        continue

                return sorted(species_list)

    def calculate_dbh_at_height(self, tree, target_height: float = 1.3) -> float:
        """
        Calculate the diameter at breast height (1.3m by default) for a tree using linear interpolation.

        This method finds the closest nodes below and above the target height and interpolates
        between them to get the exact diameter at the specified height.

        Args:
            tree: The Grove tree object
            target_height: Height at which to measure diameter (default 1.3m for DBH)

        Returns:
            Diameter at the specified height, or 0.0 if tree doesn't reach that height
        """
        if not hasattr(tree, "nodes") or not tree.nodes:
            return 0.0

        # Collect all trunk nodes (main stem) with their heights and radii
        trunk_nodes = []
        for node in tree.nodes:
            if hasattr(node, "pos") and hasattr(node, "radius"):
                trunk_nodes.append(
                    {"height": node.pos.z, "radius": node.radius, "node": node}
                )

        if not trunk_nodes:
            return 0.0

        # Sort nodes by height
        trunk_nodes.sort(key=lambda x: x["height"])

        # Check if tree reaches the target height
        max_height = trunk_nodes[-1]["height"]
        if max_height < target_height:
            return 0.0

        # Find nodes immediately below and above target height
        node_below = None
        node_above = None

        for i, trunk_node in enumerate(trunk_nodes):
            if trunk_node["height"] <= target_height:
                node_below = trunk_node
            elif trunk_node["height"] > target_height and node_above is None:
                node_above = trunk_node
                break

        # Case 1: Exact match found
        if node_below and node_below["height"] == target_height:
            return node_below["radius"] * 2.0

        # Case 2: Target height is at or below the lowest node
        if node_below is None:
            if (
                trunk_nodes[0]["height"] >= target_height * 0.95
            ):  # Close enough tolerance
                return trunk_nodes[0]["radius"] * 2.0
            else:
                return 0.0

        # Case 3: Target height is above all nodes (shouldn't happen due to earlier check)
        if node_above is None:
            return node_below["radius"] * 2.0

        # Case 4: Interpolate between the two closest nodes
        height_below = node_below["height"]
        height_above = node_above["height"]
        radius_below = node_below["radius"]
        radius_above = node_above["radius"]

        # Linear interpolation formula: y = y1 + (x - x1) * (y2 - y1) / (x2 - x1)
        height_ratio = (target_height - height_below) / (height_above - height_below)
        interpolated_radius = radius_below + height_ratio * (
            radius_above - radius_below
        )

        return interpolated_radius * 2.0

    def generate_height_curve_for_species(
        self, species: str
    ) -> Tuple[List[float], List[float], Dict[str, Any]]:
        """
        Generate height and DBH curves for a single species by simulating growth with multiple seeds.
        Averages results to account for random variation.

        Args:
            species: Species name

        Returns:
            Tuple of (averaged_height_curve, averaged_dbh_curve, metadata)
        """
        all_height_curves = []
        all_dbh_curves = []
        seed_metadata = []

        # Test multiple seeds to get robust average
        seeds_to_test = [1, 7, 13, 23, 42, 100, 111, 123, 666][: self.num_seeds]

        seed_progress = tqdm(
            seeds_to_test,
            desc=f"Testing seeds for {species[:25]}",
            leave=False,
            disable=False,
        )

        for seed in seed_progress:
            grove = gc.Grove()
            grove.set_random_seed(seed)

            # Apply species preset using growpy
            try:
                # Apply species preset
                if not self.apply_species_preset(grove, species):
                    logger.error(f"Failed to apply preset for {species}")
                    continue
            except Exception as e:
                # Fallback to manual preset loading
                try:
                    presets_dir = (
                        Path(__file__).parent.parent / "the_grove_22" / "presets"
                    )
                    preset_path = presets_dir / f"{species}.seed.json"

                    if not preset_path.exists():
                        raise FileNotFoundError(f"Preset file not found: {preset_path}")

                    with open(preset_path, "r") as f:
                        preset_json = f.read()

                    properties = gc.io.properties_from_json_string(preset_json)
                    grove.set_properties(properties)
                except Exception as e2:
                    raise ValueError(
                        f"Failed to apply preset for {species}: {e} (fallback: {e2})"
                    )

            # Clear any default trees and add a single tree at origin
            grove.clear_trees()
            grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

            # Record height and DBH after each cycle for this seed
            heights_this_seed = []
            dbh_this_seed = []
            max_height_achieved = 0.0
            max_dbh_achieved = 0.0

            # Growth simulation
            for cycle in range(self.height_model_flushes):
                grove.simulate(1)

                # Get tree height by finding the highest point in the entire tree structure
                current_height = 0.0
                current_dbh = 0.0

                if grove.trees and len(grove.trees) > 0:
                    tree = grove.trees[0]

                    # Recursive function to find max height in any branch (following Grove docs pattern)
                    def find_max_height_in_branch(branch):
                        """
                        Recursively find the maximum Z position in a branch and all its sub-branches.
                        Based on The Grove documentation tree traversal pattern.
                        """
                        local_max = 0.0
                        if hasattr(branch, "nodes") and branch.nodes:
                            for node in branch.nodes:
                                # Check this node's height
                                if hasattr(node, "pos") and node.pos.z > local_max:
                                    local_max = node.pos.z

                                # Recursively check all side branches from this node
                                if (
                                    hasattr(node, "side_branches")
                                    and node.side_branches
                                ):
                                    for side_branch in node.side_branches:
                                        side_max = find_max_height_in_branch(
                                            side_branch
                                        )
                                        if side_max > local_max:
                                            local_max = side_max
                        return local_max

                    # Find the maximum height in the entire tree (trunk + all branches)
                    current_height = find_max_height_in_branch(tree)

                    # Calculate DBH (diameter at breast height - 1.3m)
                    current_dbh = self.calculate_dbh_at_height(tree, target_height=1.3)

                    # Update max height achieved if current height is higher
                    if current_height > max_height_achieved:
                        max_height_achieved = current_height

                    # Update max DBH achieved if current DBH is higher
                    if current_dbh > max_dbh_achieved:
                        max_dbh_achieved = current_dbh

                    # Store the maximum values achieved so far (prevents decline)
                    heights_this_seed.append(max_height_achieved)
                    dbh_this_seed.append(max_dbh_achieved)
                else:
                    # No trees found, use previous max values
                    heights_this_seed.append(max_height_achieved)
                    dbh_this_seed.append(max_dbh_achieved)

            all_height_curves.append(heights_this_seed)
            all_dbh_curves.append(dbh_this_seed)
            seed_metadata.append(
                {
                    "seed": seed,
                    "final_height": heights_this_seed[-1] if heights_this_seed else 0.0,
                    "max_height": max_height_achieved,
                    "final_dbh": dbh_this_seed[-1] if dbh_this_seed else 0.0,
                    "max_dbh": max_dbh_achieved,
                }
            )

            seed_progress.set_postfix(
                seed=seed,
                height=f"{max_height_achieved:.2f}",
                dbh=f"{max_dbh_achieved:.3f}",
            )

        # Take maximum values across all seeds to eliminate tree death effects
        if not all_height_curves:
            raise ValueError(f"No successful growth curves generated for {species}")

        # Calculate maximum height and DBH at each cycle (best case across all seeds)
        max_heights = []
        max_dbhs = []
        for cycle in range(self.height_model_flushes):
            cycle_heights = [
                curve[cycle] for curve in all_height_curves if cycle < len(curve)
            ]
            cycle_dbhs = [
                curve[cycle] for curve in all_dbh_curves if cycle < len(curve)
            ]

            if cycle_heights:
                max_heights.append(max(cycle_heights))
            else:
                max_heights.append(0.0)

            if cycle_dbhs:
                max_dbhs.append(max(cycle_dbhs))
            else:
                max_dbhs.append(0.0)

        metadata = {
            "species": species,
            "cycles": self.height_model_flushes,
            "num_seeds": len(all_height_curves),
            "seeds_tested": [m["seed"] for m in seed_metadata],
            "final_height": max_heights[-1] if max_heights else 0.0,
            "max_height": max(max_heights) if max_heights else 0.0,
            "final_dbh": max_dbhs[-1] if max_dbhs else 0.0,
            "max_dbh": max(max_dbhs) if max_dbhs else 0.0,
            "growth_rate": (
                max(max_heights) / self.height_model_flushes if max_heights else 0.0
            ),
            "dbh_growth_rate": (
                max(max_dbhs) / self.height_model_flushes if max_dbhs else 0.0
            ),
            "height_curve": max_heights,
            "dbh_curve": max_dbhs,
            "individual_height_curves": all_height_curves,  # Store individual seed curves
            "individual_dbh_curves": all_dbh_curves,  # Store individual seed curves
            "seed_results": seed_metadata,
            "note": "Height and DBH curves use maximum values per cycle across multiple seeds to eliminate tree death effects",
        }

        return max_heights, max_dbhs, metadata

    def create_growth_model_for_species(
        self, species: str, height_curve: List[float]
    ) -> LinearRegression:
        """
        Create linear regression model to predict required cycles from target height.

        Args:
            species: Species name
            height_curve: List of heights per cycle

        Returns:
            Fitted sklearn LinearRegression model
        """
        if not height_curve:
            raise ValueError(f"Empty height curve for {species}")

        # Prepare training data: height -> required cycles
        heights = np.array(height_curve).reshape(-1, 1)
        cycles = np.array(range(len(height_curve)))

        # Remove zero heights at beginning (before growth starts)
        non_zero_mask = heights.flatten() > 0.01
        if np.any(non_zero_mask):
            heights = heights[non_zero_mask]
            cycles = cycles[non_zero_mask]

        if len(heights) < 2:
            raise ValueError(f"Insufficient growth data for {species}")

        # Fit linear model: cycles = f(height)
        model = LinearRegression()
        model.fit(heights, cycles)

        return model

    def plot_growth_curves(self, species: str, species_dir: Path) -> None:
        """
        Create and save plots of height and DBH growth curves.

        Args:
            species: Species name
            species_dir: Directory to save plots
        """
        if species not in self.height_curves or species not in self.dbh_curves:
            return

        # Set up matplotlib style
        mplstyle.use("default")
        plt.style.use(
            "seaborn-v0_8" if "seaborn-v0_8" in plt.style.available else "default"
        )

        # Create figure with subplots
        fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(12, 10))
        fig.suptitle(f"Growth Curves for {species}", fontsize=16, fontweight="bold")

        cycles = list(range(len(self.height_curves[species])))
        height_curve = self.height_curves[species]
        dbh_curve = self.dbh_curves[species]
        metadata = self.analysis_metadata[species]

        # Get individual seed curves if available
        individual_height_curves = metadata.get("individual_height_curves", [])
        individual_dbh_curves = metadata.get("individual_dbh_curves", [])
        seeds_tested = metadata.get("seeds_tested", [])

        # Plot individual seed curves (lighter colors, thinner lines)
        colors = [
            "lightblue",
            "lightgreen",
            "lightcoral",
            "lightyellow",
            "lightpink",
            "lightgray",
            "lightsteelblue",
            "lightsalmon",
            "lightseagreen",
        ]

        for i, (height_curve_seed, seed) in enumerate(
            zip(individual_height_curves, seeds_tested)
        ):
            color = colors[i % len(colors)]
            cycles_seed = list(range(len(height_curve_seed)))
            ax1.plot(
                cycles_seed,
                height_curve_seed,
                color=color,
                linewidth=1.0,
                alpha=0.6,
                linestyle="--",
                label=f"Seed {seed}",
            )

        # Plot aggregated height curve (bold line on top)
        ax1.plot(
            cycles,
            height_curve,
            "b-",
            linewidth=3.0,
            marker="o",
            markersize=4,
            alpha=0.9,
            label="Maximum (aggregated)",
            zorder=10,
        )

        ax1.set_xlabel("Growth Cycles", fontsize=12)
        ax1.set_ylabel("Height (units)", fontsize=12)
        ax1.set_title("Height Growth Over Time", fontsize=14, fontweight="bold")
        ax1.grid(True, alpha=0.3)
        ax1.set_xlim(0, len(cycles) - 1)
        ax1.legend(loc="lower right", fontsize=9)

        # Add height statistics as text
        height_text = f"Max Height: {metadata['max_height']:.2f}\nFinal Height: {metadata['final_height']:.2f}\nGrowth Rate: {metadata['growth_rate']:.3f} units/cycle"
        ax1.text(
            0.02,
            0.98,
            height_text,
            transform=ax1.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="wheat", alpha=0.8),
        )

        # Plot individual DBH seed curves (lighter colors, thinner lines)
        for i, (dbh_curve_seed, seed) in enumerate(
            zip(individual_dbh_curves, seeds_tested)
        ):
            color = colors[i % len(colors)]
            cycles_seed = list(range(len(dbh_curve_seed)))
            ax2.plot(
                cycles_seed,
                dbh_curve_seed,
                color=color,
                linewidth=1.0,
                alpha=0.6,
                linestyle="--",
                label=f"Seed {seed}",
            )

        # Plot aggregated DBH curve (bold line on top)
        ax2.plot(
            cycles,
            dbh_curve,
            "g-",
            linewidth=3.0,
            marker="s",
            markersize=4,
            alpha=0.9,
            label="Maximum (aggregated)",
            zorder=10,
        )

        ax2.set_xlabel("Growth Cycles", fontsize=12)
        ax2.set_ylabel("DBH - Diameter at Breast Height (units)", fontsize=12)
        ax2.set_title("DBH Growth Over Time", fontsize=14, fontweight="bold")
        ax2.grid(True, alpha=0.3)
        ax2.set_xlim(0, len(cycles) - 1)
        ax2.legend(loc="lower right", fontsize=9)

        # Add DBH statistics as text
        dbh_text = f"Max DBH: {metadata['max_dbh']:.3f}\nFinal DBH: {metadata['final_dbh']:.3f}\nDBH Growth Rate: {metadata['dbh_growth_rate']:.4f} units/cycle"
        ax2.text(
            0.02,
            0.98,
            dbh_text,
            transform=ax2.transAxes,
            fontsize=10,
            verticalalignment="top",
            bbox=dict(boxstyle="round", facecolor="lightgreen", alpha=0.8),
        )

        # Add analysis metadata as footer
        footer_text = f"Analysis: {metadata['num_seeds']} seeds, {metadata['cycles']} cycles | Seeds tested: {', '.join(map(str, metadata['seeds_tested']))}"
        fig.text(0.5, 0.02, footer_text, ha="center", fontsize=9, style="italic")

        plt.tight_layout()
        plt.subplots_adjust(top=0.93, bottom=0.08)

        # Save plot
        plot_path = species_dir / "growth_curves.png"
        plt.savefig(plot_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()

        # Also create a combined plot showing height vs DBH correlation
        fig, ax = plt.subplots(1, 1, figsize=(10, 8))

        # Plot individual seed data points with different colors/markers
        seed_colors = [
            "lightblue",
            "lightgreen",
            "lightcoral",
            "lightyellow",
            "lightpink",
            "lightgray",
            "lightsteelblue",
            "lightsalmon",
            "lightseagreen",
        ]

        for i, (height_curve_seed, dbh_curve_seed, seed) in enumerate(
            zip(individual_height_curves, individual_dbh_curves, seeds_tested)
        ):
            if len(height_curve_seed) > 0 and len(dbh_curve_seed) > 0:
                cycles_seed = list(range(len(height_curve_seed)))
                scatter_seed = ax.scatter(
                    height_curve_seed,
                    dbh_curve_seed,
                    c=cycles_seed,
                    cmap="plasma",
                    s=30,
                    alpha=0.5,
                    marker="o",
                    label=f"Seed {seed}",
                    edgecolors="none",
                )

        # Plot aggregated data points (larger, more prominent)
        scatter = ax.scatter(
            height_curve,
            dbh_curve,
            c=cycles,
            cmap="viridis",
            s=80,
            alpha=0.9,
            marker="s",
            label="Maximum (aggregated)",
            edgecolors="black",
            linewidth=0.5,
        )

        ax.set_xlabel("Height (units)", fontsize=12)
        ax.set_ylabel("DBH - Diameter at Breast Height (units)", fontsize=12)
        ax.set_title(
            f"Height vs DBH Relationship for {species}", fontsize=14, fontweight="bold"
        )
        ax.grid(True, alpha=0.3)
        ax.legend(loc="lower right", fontsize=9)

        # Add colorbar for the main aggregated data
        cbar = plt.colorbar(scatter)
        cbar.set_label("Growth Cycle (Aggregated)", fontsize=12)

        # Add trend line for aggregated data
        if len(height_curve) > 1:
            z = np.polyfit(height_curve, dbh_curve, 1)
            p = np.poly1d(z)
            ax.plot(
                height_curve,
                p(height_curve),
                "r--",
                alpha=0.8,
                linewidth=2,
                label="Trend line",
            )

            # Calculate R-squared for aggregated data
            correlation = np.corrcoef(height_curve, dbh_curve)[0, 1]
            r_squared = correlation**2
            ax.text(
                0.02,
                0.98,
                f"R² = {r_squared:.3f} (aggregated)",
                transform=ax.transAxes,
                fontsize=12,
                verticalalignment="top",
                bbox=dict(boxstyle="round", facecolor="white", alpha=0.8),
            )

        plt.tight_layout()

        # Save correlation plot
        correlation_plot_path = species_dir / "height_dbh_correlation.png"
        plt.savefig(
            correlation_plot_path, dpi=300, bbox_inches="tight", facecolor="white"
        )
        plt.close()

    def analyze_species(self, species: str) -> bool:
        """
        Analyze a single species and store results.

        Args:
            species: Species name to analyze

        Returns:
            True if successful, False otherwise
        """
        try:
            # Generate height and DBH curves
            height_curve, dbh_curve, metadata = self.generate_height_curve_for_species(
                species
            )

            # Create growth model
            growth_model = self.create_growth_model_for_species(species, height_curve)

            # Store results
            self.height_curves[species] = height_curve
            self.dbh_curves[species] = dbh_curve
            self.growth_models[species] = growth_model
            self.analysis_metadata[species] = metadata

            return True

        except Exception as e:
            logger.error(f"Failed to analyze species {species}: {e}")
            return False

    def analyze_all_species(
        self, parallel: bool = True, max_workers: Optional[int] = None
    ) -> Dict[str, bool]:
        """
        Analyze all available species and create growth models.

        Args:
            parallel: Whether to use parallel processing (default: True)
            max_workers: Maximum number of parallel workers (default: CPU count - 1)

        Returns:
            Dictionary mapping species to success status
        """
        if parallel:
            return self.analyze_all_species_parallel(max_workers)
        else:
            return self.analyze_all_species_sequential()

    def analyze_all_species_sequential(self) -> Dict[str, bool]:
        """
        Analyze all available species sequentially (original implementation).

        Returns:
            Dictionary mapping species to success status
        """
        species_list = self.get_available_species()
        results = {}

        # Progress bar for species analysis
        species_progress = tqdm(species_list, desc="Analyzing species (sequential)")

        for species in species_progress:
            species_progress.set_description(f"Analyzing: {species[:30]}...")

            try:
                # Generate height and DBH curves
                height_curve, dbh_curve, metadata = (
                    self.generate_height_curve_for_species(species)
                )

                # Create growth model
                growth_model = self.create_growth_model_for_species(
                    species, height_curve
                )

                # Store results
                self.height_curves[species] = height_curve
                self.dbh_curves[species] = dbh_curve
                self.growth_models[species] = growth_model
                self.analysis_metadata[species] = metadata

                # Save individual species results immediately
                self.save_species_results(species)

                results[species] = True

            except Exception as e:
                tqdm.write(f"FAILED {species}: {e}")
                results[species] = False

        successful = sum(1 for success in results.values() if success)
        tqdm.write(f"\nAnalysis complete: {successful}/{len(species_list)} species")

        return results

    def analyze_all_species_parallel(
        self, max_workers: Optional[int] = None
    ) -> Dict[str, bool]:
        """
        Analyze all available species using parallel processing.

        Args:
            max_workers: Maximum number of parallel workers (default: CPU count - 1)

        Returns:
            Dictionary mapping species to success status
        """
        species_list = self.get_available_species()
        results = {}

        # Determine number of workers
        if max_workers is None:
            max_workers = max(1, mp.cpu_count() - 1)  # Leave one CPU free

        logger.info(
            f"Using {max_workers} parallel workers for {len(species_list)} species"
        )

        # Prepare arguments for parallel processing
        process_args = [
            (species, self.assets_dir, self.height_model_flushes, self.num_seeds)
            for species in species_list
        ]

        # Use ProcessPoolExecutor for parallel execution
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            future_to_species = {
                executor.submit(process_single_species_parallel, args): args[0]
                for args in process_args
            }

            # Progress bar for completed tasks
            completed_progress = tqdm(
                total=len(species_list),
                desc="Analyzing species (parallel)",
                unit="species",
            )

            # Collect results as they complete
            for future in as_completed(future_to_species):
                species_name = future_to_species[future]

                try:
                    species, success, species_results, error_msg = future.result()

                    if success and species_results is not None:
                        # Store results
                        self.height_curves[species] = species_results["height_curve"]
                        self.dbh_curves[species] = species_results["dbh_curve"]
                        self.growth_models[species] = species_results["growth_model"]
                        self.analysis_metadata[species] = species_results["metadata"]

                        # Save individual species results immediately
                        self.save_species_results(species)

                        results[species] = True
                    else:
                        tqdm.write(f"FAILED {species}: {error_msg}")
                        results[species] = False

                except Exception as e:
                    tqdm.write(f"FAILED {species_name}: {e}")
                    results[species_name] = False

                completed_progress.update(1)

            completed_progress.close()

        successful = sum(1 for success in results.values() if success)
        tqdm.write(
            f"\nParallel analysis complete: {successful}/{len(species_list)} species"
        )

        return results

    def save_species_results(self, species: str):
        """Save results for a single species in its own subfolder."""
        # Create species-specific subfolder directly under output_dir
        species_safe = species.replace(" - ", "_").replace(" ", "_").replace("/", "_")
        species_dir = self.output_dir / species_safe
        species_dir.mkdir(parents=True, exist_ok=True)

        if species in self.height_curves:
            # Save height curve as JSON
            curve_path = species_dir / "height_curve.json"
            with open(curve_path, "w") as f:
                json.dump(
                    {
                        "species": species,
                        "height_curve": self.height_curves[species],
                        "cycles": len(self.height_curves[species]),
                    },
                    f,
                    indent=2,
                )

        if species in self.dbh_curves:
            # Save DBH curve as JSON
            dbh_curve_path = species_dir / "dbh_curve.json"
            with open(dbh_curve_path, "w") as f:
                json.dump(
                    {
                        "species": species,
                        "dbh_curve": self.dbh_curves[species],
                        "cycles": len(self.dbh_curves[species]),
                    },
                    f,
                    indent=2,
                )

        if species in self.growth_models:
            # Save growth model as pickle
            model_path = species_dir / "growth_model.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(self.growth_models[species], f)

        if species in self.analysis_metadata:
            # Save metadata as JSON
            metadata_path = species_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(self.analysis_metadata[species], f, indent=2)

        # Generate and save plots
        try:
            self.plot_growth_curves(species, species_dir)
        except Exception as e:
            tqdm.write(f"Warning: Failed to generate plots for {species}: {e}")

        return species_dir

    def save_growth_models(self):
        """Save growth models in species-specific subfolders only."""
        tqdm.write("Saving individual species results...")
        saved_count = 0
        for species in tqdm(
            self.analysis_metadata.keys(), desc="Saving species", leave=False
        ):
            species_dir = self.save_species_results(species)
            saved_count += 1

        tqdm.write(
            f"Saved {saved_count} species models to individual subfolders in: {self.output_dir}"
        )


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description="Generate growth models for Grove species from prepared assets",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze all species with default assets directory (parallel processing)
    python src/growpy/utils/species_growth_analysis.py
    
    # Analyze all species with custom assets directory (parallel processing)
    python src/growpy/utils/species_growth_analysis.py --assets_dir data/assets
    
    # Analyze all species sequentially (no parallel processing)
    python src/growpy/utils/species_growth_analysis.py --no-parallel
    
    # Analyze all species with custom number of workers
    python src/growpy/utils/species_growth_analysis.py --workers 4
    
    # Analyze specific species
    python src/growpy/utils/species_growth_analysis.py --species "Fagaceae - European oak"
    
Note: Run prepare_assets.py first to copy species presets from Grove installation.
      Parallel processing significantly speeds up analysis when processing multiple species.
        """,
    )

    # Get script directory for default paths
    script_dir = Path(__file__).parent.parent.parent.parent  # Go up to project root

    parser.add_argument(
        "--assets_dir",
        type=Path,
        default=script_dir / "data" / "assets",
        help="Directory containing prepared GrowPy assets (default: data/assets)",
    )
    parser.add_argument(
        "--cycles", type=int, default=75, help="Number of growth cycles for analysis"
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=3,
        help="Number of random seeds to average for robust curves",
    )
    parser.add_argument(
        "--species",
        type=str,
        help="Specific species to analyze (if not provided, analyzes all species)",
    )
    parser.add_argument("--verbose", action="store_true", help="Enable verbose logging")
    parser.add_argument(
        "--parallel",
        action="store_true",
        default=True,
        help="Use parallel processing (default: True)",
    )
    parser.add_argument(
        "--no-parallel",
        action="store_true",
        help="Disable parallel processing (run sequentially)",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=None,
        help="Number of parallel workers (default: CPU count - 1)",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determine parallel processing settings
    use_parallel = args.parallel and not args.no_parallel
    max_workers = args.workers

    logger.info("Grove Species Growth Analysis")
    logger.info("=" * 40)
    logger.info(f"Assets directory: {args.assets_dir}")
    logger.info(f"Parallel processing: {'Enabled' if use_parallel else 'Disabled'}")
    if use_parallel and max_workers:
        logger.info(f"Max workers: {max_workers}")
    elif use_parallel:
        logger.info(f"Max workers: {max(1, mp.cpu_count() - 1)} (CPU count - 1)")

    # Check assets directory
    if not args.assets_dir.exists():
        logger.error(f"Assets directory not found: {args.assets_dir}")
        logger.error(
            "Please run prepare_assets.py first to copy assets from Grove installation"
        )
        sys.exit(1)

    # Check for presets directory
    presets_dir = args.assets_dir / "presets"
    if not presets_dir.exists():
        logger.error(f"Presets directory not found: {presets_dir}")
        logger.error("Please run prepare_assets.py first to copy species presets")
        sys.exit(1)

    # Create analyzer
    analyzer = SpeciesGrowthAnalyzer(args.assets_dir, args.cycles, args.seeds)

    if args.species:
        # Analyze single species
        logger.info(f"Analyzing single species: {args.species}")

        available_species = analyzer.get_available_species()
        if args.species not in available_species:
            logger.error(f"Species '{args.species}' not found in available presets")
            logger.info(f"Available species: {', '.join(available_species[:10])}...")
            sys.exit(1)

        try:
            # Generate height and DBH curves
            height_curve, dbh_curve, metadata = (
                analyzer.generate_height_curve_for_species(args.species)
            )

            # Create growth model
            growth_model = analyzer.create_growth_model_for_species(
                args.species, height_curve
            )

            # Store results
            analyzer.height_curves[args.species] = height_curve
            analyzer.dbh_curves[args.species] = dbh_curve
            analyzer.growth_models[args.species] = growth_model
            analyzer.analysis_metadata[args.species] = metadata

            # Save individual species results
            species_dir = analyzer.save_species_results(args.species)

            logger.info(f"Final height: {metadata['final_height']:.2f}")
            logger.info(f"Growth rate: {metadata['growth_rate']:.3f} units/cycle")
            logger.info(f"Max height: {metadata['max_height']:.2f}")
            logger.info(f"Final DBH: {metadata['final_dbh']:.3f}")
            logger.info(f"Max DBH: {metadata['max_dbh']:.3f}")

            # Save results
            analyzer.save_growth_models()

            logger.info(f"Success: Generated growth model for {args.species}")
            logger.info(f"Results saved to: {species_dir}")

        except Exception as e:
            logger.error(f"Failed to analyze {args.species}: {e}")
            sys.exit(1)
    else:
        # Analyze all species
        logger.info("Analyzing all available species...")
        results = analyzer.analyze_all_species(
            parallel=use_parallel, max_workers=max_workers
        )

        # Save results
        analyzer.save_growth_models()

        successful = sum(1 for success in results.values() if success)
        total = len(results)

        logger.info(f"Analysis completed: {successful}/{total} species successful")

        if successful > 0:
            logger.info(
                f"Models saved to species-specific subfolders in: {analyzer.output_dir}"
            )
        else:
            logger.error("No species were successfully analyzed")
            sys.exit(1)
            species_dir = analyzer.save_species_results(args.species)

            tqdm.write(f"Final height: {metadata['final_height']:.2f}")
            tqdm.write(f"Growth rate: {metadata['growth_rate']:.3f} units/cycle")
            tqdm.write(f"Max height: {metadata['max_height']:.2f}")
            tqdm.write(f"Final DBH: {metadata['final_dbh']:.3f}")
            tqdm.write(f"Max DBH: {metadata['max_dbh']:.3f}")


if __name__ == "__main__":
    # For Windows multiprocessing support
    mp.set_start_method("spawn", force=True)
    main()
