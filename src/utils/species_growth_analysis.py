"""
Species growth analysis utility for The Grove 2.2.

This utility generates height curves and age prediction models for Grove species presets.
The GrowthModelLoader class has been moved to growpy.growth_models module.

Usage:
    python src/utils/species_growth_analysis.py --output_dir data/growth_models
    python src/utils/species_growth_analysis.py --species "Fagaceae - European oak" --cycles 25
"""

import argparse
import json
import pickle
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Add src to path for Grove imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "the_grove_22" / "modules"))

import numpy as np
import pandas as pd
import the_grove_22_core as gc
from sklearn.linear_model import LinearRegression
from tqdm import tqdm


class SpeciesGrowthAnalyzer:
    """Analyzes growth patterns for Grove species and creates prediction models."""

    def __init__(self, output_dir: Path, height_model_flushes: int = 75):
        """
        Initialize the growth analyzer.

        Args:
            output_dir: Directory to save growth models
            height_model_flushes: Number of growth cycles for height curve generation
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.height_model_flushes = height_model_flushes

        # Results storage
        self.height_curves = {}  # species -> list of heights per cycle
        self.growth_models = {}  # species -> sklearn model
        self.analysis_metadata = {}  # species -> analysis info

    def get_available_species(self) -> List[str]:
        """Get list of all available Grove species presets."""
        # Find presets directory relative to this script
        presets_dir = Path(__file__).parent.parent / "the_grove_22" / "presets"

        if not presets_dir.exists():
            raise FileNotFoundError(f"Presets directory not found: {presets_dir}")

        species_list = []
        for preset_file in presets_dir.glob("*.seed.json"):
            try:
                # Remove .seed.json extension to get species name
                species_name = preset_file.stem
                if species_name.endswith(".seed"):
                    species_name = species_name[:-5]

                if species_name and not species_name.startswith("."):
                    species_list.append(species_name)
            except Exception:
                continue

        return sorted(species_list)

    def generate_height_curve_for_species(
        self, species: str
    ) -> Tuple[List[float], Dict[str, Any]]:
        """
        Generate height curve for a single species by simulating growth.

        Args:
            species: Species name

        Returns:
            Tuple of (height_curve, metadata)
        """
        grove = gc.Grove()
        grove.set_random_seed(42)  # Consistent results

        # Apply species preset
        try:
            # Load preset from file system
            presets_dir = Path(__file__).parent.parent / "the_grove_22" / "presets"
            preset_path = presets_dir / f"{species}.seed.json"

            if not preset_path.exists():
                raise FileNotFoundError(f"Preset file not found: {preset_path}")

            with open(preset_path, "r") as f:
                preset_json = f.read()

            # Apply preset to grove
            properties = gc.io.properties_from_json_string(preset_json)
            grove.set_properties(properties)

        except Exception as e:
            raise ValueError(f"Failed to apply preset for {species}: {e}")

        # Clear any default trees and add a single tree at origin
        grove.clear_trees()  # Remove the default tree
        grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

        # Record height after each cycle
        heights = []

        # Progress bar for growth cycles
        cycle_progress = tqdm(
            range(self.height_model_flushes),
            desc=f"Growing {species}",
            leave=False,
            disable=False,
        )

        for cycle in cycle_progress:
            grove.simulate(1)

            # Get tree height using more robust method
            if grove.trees and len(grove.trees) > 0:
                tree = grove.trees[0]  # Get the main trunk

                if hasattr(tree, "nodes") and len(tree.nodes) > 0:
                    # Method 1: Simple approach - find the highest node Z position
                    max_height = 0.0

                    # Traverse all nodes in the main trunk
                    for node in tree.nodes:
                        if node.pos.z > max_height:
                            max_height = node.pos.z

                    # Also check side branches recursively
                    def find_max_height_in_branch(branch):
                        local_max = 0.0
                        if hasattr(branch, "nodes"):
                            for node in branch.nodes:
                                if node.pos.z > local_max:
                                    local_max = node.pos.z

                                # Check side branches
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

                    # Get max height from entire tree structure
                    tree_max_height = find_max_height_in_branch(tree)
                    max_height = max(max_height, tree_max_height)

                    heights.append(max_height)

                    # Update progress bar with current height
                    cycle_progress.set_postfix(height=f"{max_height:.2f}")

                    # Debug output for first few cycles and every 10 cycles after
                    if cycle < 5 or cycle % 10 == 0:
                        side_branch_count = sum(
                            (
                                len(node.side_branches)
                                if hasattr(node, "side_branches") and node.side_branches
                                else 0
                            )
                            for node in tree.nodes
                        )
                        tqdm.write(
                            f"  Cycle {cycle + 1}: height = {max_height:.3f}, nodes = {len(tree.nodes)}, side_branches = {side_branch_count}"
                        )
                else:
                    heights.append(0.0)
                    tqdm.write(f"  Cycle {cycle + 1}: No nodes found in tree")
            else:
                heights.append(0.0)
                tqdm.write(f"  Cycle {cycle + 1}: No trees found in grove")

        metadata = {
            "species": species,
            "cycles": self.height_model_flushes,
            "final_height": heights[-1] if heights else 0.0,
            "max_height": max(heights) if heights else 0.0,
            "growth_rate": heights[-1] / self.height_model_flushes if heights else 0.0,
            "height_curve": heights,  # Include full curve for debugging
        }

        return heights, metadata

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

    def predict_required_cycles(self, species: str, target_height: float) -> int:
        """
        Predict number of cycles required to reach target height.

        Args:
            species: Species name
            target_height: Target height

        Returns:
            Predicted number of cycles
        """
        if species not in self.growth_models:
            raise ValueError(f"No growth model available for {species}")

        model = self.growth_models[species]
        predicted_cycles = model.predict([[target_height]])[0]

        # Ensure reasonable bounds
        return max(1, min(int(predicted_cycles), self.height_model_flushes * 2))

    def analyze_all_species(self) -> Dict[str, bool]:
        """
        Analyze all available species and create growth models.

        Returns:
            Dictionary mapping species to success status
        """
        species_list = self.get_available_species()
        results = {}

        # Progress bar for species analysis
        species_progress = tqdm(species_list, desc="Analyzing species")

        for species in species_progress:
            species_progress.set_description(f"Analyzing: {species[:30]}...")

            try:
                # Generate height curve
                height_curve, metadata = self.generate_height_curve_for_species(species)

                # Create growth model
                growth_model = self.create_growth_model_for_species(
                    species, height_curve
                )

                # Store results
                self.height_curves[species] = height_curve
                self.growth_models[species] = growth_model
                self.analysis_metadata[species] = metadata

                # Save individual species results immediately
                self.save_species_results(species)

                species_progress.set_postfix(
                    height=f"{metadata['final_height']:.2f}",
                    rate=f"{metadata['growth_rate']:.3f}",
                )

                results[species] = True

            except Exception as e:
                tqdm.write(f"FAILED {species}: {e}")
                results[species] = False

        successful = sum(1 for success in results.values() if success)
        tqdm.write(f"\nAnalysis complete: {successful}/{len(species_list)} species")

        return results

    def save_species_results(self, species: str):
        """Save results for a single species in its own subfolder."""
        # Create species-specific subfolder
        species_safe = species.replace(" - ", "_").replace(" ", "_").replace("/", "_")
        species_dir = self.output_dir / "species" / species_safe
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

        return species_dir

    def save_growth_models(self):
        """Save all growth models and metadata to files."""
        # Save global models as before
        models_path = self.output_dir / "species_growth_models.pkl"
        with open(models_path, "wb") as f:
            pickle.dump(self.growth_models, f)

        curves_path = self.output_dir / "species_height_curves.json"
        with open(curves_path, "w") as f:
            json.dump(self.height_curves, f, indent=2)

        metadata_path = self.output_dir / "species_analysis_metadata.json"
        with open(metadata_path, "w") as f:
            json.dump(self.analysis_metadata, f, indent=2)

        # Also save individual species results
        tqdm.write("Saving individual species results...")
        for species in tqdm(
            self.analysis_metadata.keys(), desc="Saving species", leave=False
        ):
            species_dir = self.save_species_results(species)

        tqdm.write(f"Saved growth models: {models_path}")
        tqdm.write(f"Saved height curves: {curves_path}")
        tqdm.write(f"Saved analysis metadata: {metadata_path}")
        tqdm.write(
            f"Saved individual species results to: {self.output_dir / 'species'}"
        )

    def create_prediction_summary(self):
        """Create human-readable summary of growth analysis."""
        summary_path = self.output_dir / "growth_analysis_summary.txt"

        with open(summary_path, "w") as f:
            f.write("Grove Species Growth Analysis Summary\n")
            f.write("=" * 40 + "\n\n")

            f.write(f"Analysis Parameters:\n")
            f.write(f"- Growth cycles: {self.height_model_flushes}\n")
            f.write(f"- Species analyzed: {len(self.analysis_metadata)}\n\n")

            f.write("Species Growth Summary:\n")
            f.write("-" * 25 + "\n")

            for species, metadata in sorted(self.analysis_metadata.items()):
                f.write(f"{species}:\n")
                f.write(f"  Final height: {metadata['final_height']:.2f}\n")
                f.write(f"  Growth rate: {metadata['growth_rate']:.3f} units/cycle\n")
                f.write(f"  Max height: {metadata['max_height']:.2f}\n\n")

        tqdm.write(f"Created summary: {summary_path}")


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description="Generate growth models for Grove species"
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default="data/growth_models",
        help="Directory to save growth models",
    )
    parser.add_argument(
        "--cycles", type=int, default=75, help="Number of growth cycles for analysis"
    )
    parser.add_argument(
        "--species",
        type=str,
        help="Specific species to analyze (if not provided, analyzes all species)",
    )

    args = parser.parse_args()

    # Create analyzer
    analyzer = SpeciesGrowthAnalyzer(args.output_dir, args.cycles)

    if args.species:
        # Analyze single species
        tqdm.write(f"Analyzing single species: {args.species}")
        try:
            # Generate height curve
            height_curve, metadata = analyzer.generate_height_curve_for_species(
                args.species
            )

            # Create growth model
            growth_model = analyzer.create_growth_model_for_species(
                args.species, height_curve
            )

            # Store results
            analyzer.height_curves[args.species] = height_curve
            analyzer.growth_models[args.species] = growth_model
            analyzer.analysis_metadata[args.species] = metadata

            # Save individual species results
            species_dir = analyzer.save_species_results(args.species)

            tqdm.write(f"Final height: {metadata['final_height']:.2f}")
            tqdm.write(f"Growth rate: {metadata['growth_rate']:.3f} units/cycle")
            tqdm.write(f"Max height: {metadata['max_height']:.2f}")

            # Save global results
            analyzer.save_growth_models()
            analyzer.create_prediction_summary()

            tqdm.write(f"\nSuccess: Generated growth model for {args.species}")
            tqdm.write(f"Individual results saved to: {species_dir}")
            tqdm.write(f"Global models saved to: {args.output_dir}")
            return True

        except Exception as e:
            tqdm.write(f"\nFailed to analyze {args.species}: {e}")
            return False
    else:
        # Analyze all species
        tqdm.write("Analyzing all species...")
        results = analyzer.analyze_all_species()

        # Save global results
        analyzer.save_growth_models()
        analyzer.create_prediction_summary()

        # Report results
        successful = sum(1 for success in results.values() if success)
        total = len(results)

        if successful > 0:
            tqdm.write(
                f"\nSuccess: Generated growth models for {successful}/{total} species"
            )
            tqdm.write(f"Models saved to: {args.output_dir}")
            return True
        else:
            tqdm.write(f"\nFailed: No growth models generated")
            return False


if __name__ == "__main__":
    main()
