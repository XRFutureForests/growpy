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
from growpy.core.grove import create_grove

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress verbose matplotlib logging (font finding, etc.)
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)


def process_single_species_parallel(args_tuple):
    """
    Process a single species in parallel.

    This function is designed to be called by multiprocessing workers.
    It takes a tuple of arguments to work around multiprocessing limitations.

    Args:
        args_tuple: Tuple of (species, assets_dir, height_model_flushes, num_seeds, height_growth_threshold, max_cycles_without_growth, timeout_seconds)

    Returns:
        Tuple of (species, success, results_dict, error_message)
    """
    species, assets_dir, height_model_flushes, num_seeds, height_growth_threshold, max_cycles_without_growth, timeout_seconds = args_tuple

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
        analyzer = SpeciesGrowthAnalyzer(
            assets_dir, height_model_flushes, num_seeds, 
            height_growth_threshold, max_cycles_without_growth, timeout_seconds
        )

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
        self, 
        assets_dir: Path, 
        height_model_flushes: int = 75, 
        num_seeds: int = 3,
        height_growth_threshold: float = 0.01,
        max_cycles_without_growth: int = 10,
        timeout_seconds: int = 60
    ):
        """
        Initialize the growth analyzer.

        Args:
            assets_dir: Directory containing prepared GrowPy assets
            height_model_flushes: Number of growth cycles for height curve generation
            num_seeds: Number of different random seeds to average for robust curves
            height_growth_threshold: Minimum height increase to consider as growth
            max_cycles_without_growth: Number of cycles without growth before stopping
            timeout_seconds: Maximum time in seconds for growth simulation per seed
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
        
        # Height monitoring configuration
        self.height_growth_threshold = height_growth_threshold
        self.max_cycles_without_growth = max_cycles_without_growth
        self.timeout_seconds = timeout_seconds

        # Results storage
        self.height_curves = {}  # species -> list of heights per cycle
        self.dbh_curves = {}  # species -> list of DBH values per cycle
        self.growth_models = {}  # species -> sklearn model
        self.analysis_metadata = {}  # species -> analysis info

    def apply_species_preset(self, grove, species: str) -> bool:
        """
        Apply a species preset to a grove using direct file loading.

        Args:
            grove: Grove object to apply preset to
            species: Species name (e.g., "Fagaceae - European oak")

        Returns:
            True if successful, False otherwise
        """
        try:
            # Find the preset file directly in the assets directory
            preset_file = self.presets_dir / f"{species}.seed.json"
            if not preset_file.exists():
                logger.error(f"Preset file not found: {preset_file}")
                return False

            # Use Grove's built-in method to load and apply preset
            with open(preset_file, "r") as f:
                preset_json = f.read()

            # Use Grove's io.properties_from_json_string method for proper preset loading
            properties = gc.io.properties_from_json_string(preset_json)
            grove.set_properties(properties)

            logger.debug(
                f"Applied preset for species: {species} from file: {preset_file}"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to apply species preset {species}: {e}")
            return False

    def get_available_species(self) -> List[str]:
        """Get list of all available Grove species presets directly from preset files."""
        try:
            species_list = []

            # Get all preset files from the assets directory
            preset_files = list(self.presets_dir.glob("*.json"))

            for preset_file in preset_files:
                # Skip hidden files and special presets
                if preset_file.name.startswith("."):
                    continue

                # Extract species name from filename (remove .seed.json extension)
                species_name = preset_file.stem
                if species_name.endswith(".seed"):
                    species_name = species_name[:-5]  # Remove .seed

                # Skip empty names
                if species_name:
                    species_list.append(species_name)

            logger.info(
                f"Found {len(species_list)} species presets in assets directory"
            )
            return sorted(species_list)

        except Exception as e:
            logger.error(f"Failed to get available species from directory: {e}")
            return []

    def get_growth_model_name_for_species(self, species: str) -> str:
        """
        Generate a growth model folder name directly from the species preset name.

        Args:
            species: Species name (e.g., "Fagaceae - European oak")

        Returns:
            Growth model name based on preset name (e.g., "Fagaceae_European_oak")
        """
        # Convert species name to a safe folder name by replacing problematic characters
        safe_name = (
            species.replace(" - ", "_")
            .replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )

        # Remove any other problematic characters
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")

        # Ensure it doesn't start with a dot or special character
        if safe_name.startswith("."):
            safe_name = safe_name[1:]

        logger.debug(
            f"Generated growth model name '{safe_name}' for species '{species}'"
        )
        return safe_name

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
            # Create grove directly using Grove core instead of using growpy wrapper
            try:
                grove = gc.Grove()
                grove.clear_trees()
                grove.set_random_seed(seed)

                # Apply species preset directly
                if not self.apply_species_preset(grove, species):
                    logger.error(
                        f"Failed to apply species preset for {species} with seed {seed}"
                    )
                    continue

            except Exception as e:
                logger.error(f"Failed to create grove with species {species}: {e}")
                continue

            # Clear any default trees and add a single tree at origin
            grove.clear_trees()
            grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

            # Record height and DBH after each cycle for this seed
            heights_this_seed = []
            dbh_this_seed = []
            max_height_achieved = 0.0
            max_dbh_achieved = 0.0

            # Growth simulation with height monitoring and timeout
            cycles_without_growth = 0
            simulation_start_time = time.time()
            
            for cycle in range(self.height_model_flushes):
                grove.simulate(1)

                # Check for timeout
                elapsed_time = time.time() - simulation_start_time
                if elapsed_time > self.timeout_seconds:
                    logger.warning(f"Species {species}, seed {seed}: Simulation timeout after {elapsed_time:.1f} seconds at cycle {cycle + 1}. Exiting growth simulation.")
                    break

                # Get tree height by finding the highest point in the entire tree structure
                current_height = 0.0
                current_dbh = 0.0
                previous_max_height = max_height_achieved

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

                # Monitor height growth and exit early if growth stops
                height_increase = max_height_achieved - previous_max_height
                
                if height_increase < self.height_growth_threshold:
                    cycles_without_growth += 1
                    if cycle > 5:  # Only start monitoring after some initial cycles
                        logger.debug(f"Species {species}, seed {seed}, cycle {cycle}: No significant height growth ({height_increase:.4f}), cycles without growth: {cycles_without_growth}")
                else:
                    cycles_without_growth = 0  # Reset counter when growth is detected
                    logger.debug(f"Species {species}, seed {seed}, cycle {cycle}: Height increased by {height_increase:.4f}")

                # Exit loop if no growth for several consecutive cycles
                if cycles_without_growth >= self.max_cycles_without_growth and cycle > 10:
                    logger.info(f"Species {species}, seed {seed}: Height growth stopped after {cycle + 1} cycles (max height: {max_height_achieved:.3f}). Exiting growth simulation early.")
                    break

            all_height_curves.append(heights_this_seed)
            all_dbh_curves.append(dbh_this_seed)
            actual_cycles = len(heights_this_seed)
            final_elapsed_time = time.time() - simulation_start_time
            seed_metadata.append(
                {
                    "seed": seed,
                    "final_height": heights_this_seed[-1] if heights_this_seed else 0.0,
                    "max_height": max_height_achieved,
                    "final_dbh": dbh_this_seed[-1] if dbh_this_seed else 0.0,
                    "max_dbh": max_dbh_achieved,
                    "actual_cycles": actual_cycles,
                    "early_termination": actual_cycles < self.height_model_flushes,
                    "cycles_without_growth": cycles_without_growth,
                    "simulation_time": final_elapsed_time,
                    "timeout_occurred": final_elapsed_time > self.timeout_seconds,
                }
            )

            seed_progress.set_postfix(
                seed=seed,
            )

        # Take maximum values across all seeds to eliminate tree death effects
        if not all_height_curves:
            raise ValueError(f"No successful growth curves generated for {species}")

        # Calculate maximum height and DBH at each cycle (best case across all seeds)
        max_heights = []
        max_dbhs = []
        
        # Find the maximum number of cycles across all seeds
        max_cycles_achieved = max(len(curve) for curve in all_height_curves) if all_height_curves else 0
        
        for cycle in range(max_cycles_achieved):
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

        # Count early terminations and timeouts
        early_terminations = sum(1 for meta in seed_metadata if meta.get("early_termination", False))
        timeouts = sum(1 for meta in seed_metadata if meta.get("timeout_occurred", False))
        avg_actual_cycles = sum(meta.get("actual_cycles", 0) for meta in seed_metadata) / len(seed_metadata) if seed_metadata else 0
        avg_simulation_time = sum(meta.get("simulation_time", 0) for meta in seed_metadata) / len(seed_metadata) if seed_metadata else 0

        metadata = {
            "species": species,
            "planned_cycles": self.height_model_flushes,
            "actual_max_cycles": max_cycles_achieved,
            "avg_actual_cycles": avg_actual_cycles,
            "avg_simulation_time": avg_simulation_time,
            "early_terminations": early_terminations,
            "timeouts": timeouts,
            "num_seeds": len(all_height_curves),
            "seeds_tested": [m["seed"] for m in seed_metadata],
            "final_height": max_heights[-1] if max_heights else 0.0,
            "max_height": max(max_heights) if max_heights else 0.0,
            "final_dbh": max_dbhs[-1] if max_dbhs else 0.0,
            "max_dbh": max(max_dbhs) if max_dbhs else 0.0,
            "growth_rate": (
                max(max_heights) / max_cycles_achieved if max_heights and max_cycles_achieved > 0 else 0.0
            ),
            "dbh_growth_rate": (
                max(max_dbhs) / max_cycles_achieved if max_dbhs and max_cycles_achieved > 0 else 0.0
            ),
            "height_curve": max_heights,
            "dbh_curve": max_dbhs,
            "individual_height_curves": all_height_curves,  # Store individual seed curves
            "individual_dbh_curves": all_dbh_curves,  # Store individual seed curves
            "seed_results": seed_metadata,
            "note": "Height and DBH curves use maximum values per cycle across multiple seeds. Growth simulation may terminate early when height stops increasing for multiple consecutive cycles or timeout (60s) is reached.",
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
        footer_text = f"Analysis: {metadata['num_seeds']} seeds, {metadata['actual_max_cycles']} max cycles (avg: {metadata['avg_actual_cycles']:.1f}) | Avg time: {metadata['avg_simulation_time']:.1f}s | Seeds tested: {', '.join([str(s) for s in metadata['seeds_tested']])}"
        if metadata['early_terminations'] > 0:
            footer_text += f" | Early terminations: {metadata['early_terminations']}/{metadata['num_seeds']}"
        if metadata['timeouts'] > 0:
            footer_text += f" | Timeouts: {metadata['timeouts']}/{metadata['num_seeds']}"
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
            (species, self.assets_dir, self.height_model_flushes, self.num_seeds, 
             self.height_growth_threshold, self.max_cycles_without_growth, self.timeout_seconds)
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
        # Create species-specific subfolder using growth model name from lookup table
        growth_model_name = self.get_growth_model_name_for_species(species)
        species_dir = self.output_dir / growth_model_name
        species_dir.mkdir(parents=True, exist_ok=True)

        if species in self.height_curves:
            # Save height curve as JSON
            curve_path = species_dir / "height_curve.json"
            with open(curve_path, "w") as f:
                json.dump(
                    {
                        "species": species,
                        "height_curve": self.height_curves[species],
                        "actual_cycles": len(self.height_curves[species]),
                        "metadata": self.analysis_metadata.get(species, {}),
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
                        "actual_cycles": len(self.dbh_curves[species]),
                        "metadata": self.analysis_metadata.get(species, {}),
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

    def update_lookup_table_with_new_models(self):
        """Update the tree asset lookup table with new growth model names based on analyzed species."""
        try:
            # Find lookup table using same hierarchy as load_species_lookup()
            # Priority: src/growpy/config/ > config/ > data/
            current_file = Path(__file__)
            package_config = current_file.parent.parent / "config" / "tree_asset_lookup.csv"
            project_root = self.assets_dir.parent
            project_config = project_root.parent / "config" / "tree_asset_lookup.csv"
            data_path = project_root / "tree_asset_lookup.csv"

            if package_config.exists():
                lookup_table_path = package_config
            elif project_config.exists():
                lookup_table_path = project_config
            elif data_path.exists():
                lookup_table_path = data_path
            else:
                logger.warning(
                    f"Lookup table not found in src/growpy/config/, config/, or data/, skipping update"
                )
                return

            # Read the current lookup table
            df = pd.read_csv(lookup_table_path)

            # Create a mapping of preset names to new growth model names
            updated_count = 0
            for species in self.analysis_metadata.keys():
                preset_name = f"{species}.seed.json"
                new_growth_model_name = self.get_growth_model_name_for_species(species)

                # Find rows with matching preset name
                mask = df["Preset"] == preset_name
                if mask.any():
                    # Update the Growth Model column for matching rows
                    df.loc[mask, "Growth Model"] = new_growth_model_name
                    updated_count += 1
                    logger.debug(
                        f"Updated lookup table: {preset_name} -> {new_growth_model_name}"
                    )
                else:
                    logger.debug(
                        f"No matching preset found in lookup table for: {preset_name}"
                    )

            # Save the updated lookup table
            if updated_count > 0:
                # Create a backup of the original file
                backup_path = lookup_table_path.with_suffix(".csv.backup")
                if not backup_path.exists():
                    df_original = pd.read_csv(lookup_table_path)
                    df_original.to_csv(backup_path, index=False)
                    logger.info(
                        f"Created backup of original lookup table: {backup_path}"
                    )

                # Save the updated table
                df.to_csv(lookup_table_path, index=False)
                logger.info(
                    f"Updated lookup table with {updated_count} new growth model names"
                )
                logger.info(f"Updated lookup table saved to: {lookup_table_path}")
            else:
                logger.warning("No updates were made to the lookup table")

        except Exception as e:
            logger.error(f"Failed to update lookup table: {e}")

    def generate_lookup_table_summary(self):
        """Generate a summary of the species analyzed and their growth model names."""
        try:
            summary_path = self.output_dir / "species_analysis_summary.csv"

            # Create summary data
            summary_data = []
            for species in self.analysis_metadata.keys():
                metadata = self.analysis_metadata[species]
                growth_model_name = self.get_growth_model_name_for_species(species)

                summary_data.append(
                    {
                        "Species": species,
                        "Preset_File": f"{species}.seed.json",
                        "Growth_Model_Name": growth_model_name,
                        "Final_Height": metadata.get("final_height", 0.0),
                        "Max_Height": metadata.get("max_height", 0.0),
                        "Final_DBH": metadata.get("final_dbh", 0.0),
                        "Max_DBH": metadata.get("max_dbh", 0.0),
                        "Growth_Rate": metadata.get("growth_rate", 0.0),
                        "Planned_Cycles": metadata.get("planned_cycles", 0),
                        "Actual_Max_Cycles": metadata.get("actual_max_cycles", 0),
                        "Avg_Actual_Cycles": metadata.get("avg_actual_cycles", 0.0),
                        "Avg_Simulation_Time": metadata.get("avg_simulation_time", 0.0),
                        "Early_Terminations": metadata.get("early_terminations", 0),
                        "Timeouts": metadata.get("timeouts", 0),
                        "Seeds_Tested": len(metadata.get("seeds_tested", [])),
                    }
                )

            # Create DataFrame and save
            summary_df = pd.DataFrame(summary_data)
            summary_df.to_csv(summary_path, index=False)

            logger.info(f"Generated species analysis summary: {summary_path}")
            logger.info(f"Summary contains {len(summary_data)} analyzed species")

        except Exception as e:
            logger.error(f"Failed to generate lookup table summary: {e}")


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description="Generate growth models for Grove species from prepared assets. Features intelligent height monitoring to detect when tree growth plateaus and automatically stop simulation early to save time. Also includes timeout protection to prevent infinite loops.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Analyze all species with default settings (parallel processing, height monitoring, 60s timeout)
    python src/growpy/utils/species_growth_analysis.py
    
    # Analyze all species with custom height monitoring and timeout parameters
    python src/growpy/utils/species_growth_analysis.py --height-threshold 0.005 --max-cycles-without-growth 15 --timeout 120
    
    # Analyze all species with custom assets directory (parallel processing)
    python src/growpy/utils/species_growth_analysis.py --assets_dir data/assets
    
    # Analyze all species sequentially (no parallel processing)
    python src/growpy/utils/species_growth_analysis.py --no-parallel
    
    # Analyze all species with custom number of workers
    python src/growpy/utils/species_growth_analysis.py --workers 4
    
    # Analyze specific species with detailed height monitoring
    python src/growpy/utils/species_growth_analysis.py --species "Fagaceae - European oak" --verbose
    
Height Monitoring & Timeout Protection:
    The script automatically monitors tree height growth and stops simulation early when:
    - Height increase per cycle falls below --height-threshold (default: 0.01 units)
    - No significant growth occurs for --max-cycles-without-growth consecutive cycles (default: 10)
    - Simulation time exceeds --timeout seconds per seed (default: 60)
    - This prevents wasting computation time on trees that have reached their growth plateau or are stuck
    
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
        "--cycles", type=int, default=125, help="Number of growth cycles for analysis"
    )
    parser.add_argument(
        "--seeds",
        type=int,
        default=1,
        help="Number of random seeds to average for robust curves",
    )
    parser.add_argument(
        "--height-threshold",
        type=float,
        default=0.05,
        help="Minimum height increase to consider as growth (default: 0.05)",
    )
    parser.add_argument(
        "--max-cycles-without-growth",
        type=int,
        default=3,
        help="Number of cycles without growth before stopping (default: 3)",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Maximum time in seconds for growth simulation per seed (default: 300)",
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
        default=3,
        help="Number of parallel workers (default: CPU count - 1)",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        # Keep matplotlib logging suppressed even in verbose mode
        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)

    # Determine parallel processing settings
    use_parallel = args.parallel and not args.no_parallel
    max_workers = args.workers

    logger.info("Grove Species Growth Analysis")
    logger.info("=" * 40)
    logger.info(f"Assets directory: {args.assets_dir}")
    logger.info(f"Growth cycles: {args.cycles}")
    logger.info(f"Random seeds: {args.seeds}")
    logger.info(f"Height threshold: {args.height_threshold}")
    logger.info(f"Max cycles without growth: {args.max_cycles_without_growth}")
    logger.info(f"Timeout: {args.timeout} seconds")
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
    analyzer = SpeciesGrowthAnalyzer(
        args.assets_dir, 
        args.cycles, 
        args.seeds,
        args.height_threshold,
        args.max_cycles_without_growth,
        args.timeout
    )

    if args.species:
        # Analyze single species
        logger.info(f"Analyzing single species: {args.species}")

        available_species = analyzer.get_available_species()
        if args.species not in available_species:
            logger.error(f"Species '{args.species}' not found in available presets")
            logger.info(f"Available species: {', '.join(available_species[:10])}...")
            sys.exit(1)


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
        logger.info(f"Planned cycles: {metadata['planned_cycles']}, Actual max cycles: {metadata['actual_max_cycles']}")
        logger.info(f"Average actual cycles: {metadata['avg_actual_cycles']:.1f}")
        logger.info(f"Average simulation time: {metadata['avg_simulation_time']:.1f} seconds")
        if metadata['early_terminations'] > 0:
            logger.info(f"Early terminations: {metadata['early_terminations']}/{metadata['num_seeds']} seeds")
        else:
            logger.info("No early terminations occurred")
        if metadata['timeouts'] > 0:
            logger.warning(f"Timeouts occurred: {metadata['timeouts']}/{metadata['num_seeds']} seeds")
        else:
            logger.info("No timeouts occurred")

        # Save results
        analyzer.save_growth_models()

    else:
        # Analyze all species
        logger.info("Analyzing all available species...")
        results = analyzer.analyze_all_species(
            parallel=use_parallel, max_workers=max_workers
        )

        # Save results
        analyzer.save_growth_models()


if __name__ == "__main__":
    # For Windows multiprocessing support
    mp.set_start_method("spawn", force=True)
    main()
