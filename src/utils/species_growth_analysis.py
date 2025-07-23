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

# Use refactored growpy package
from growpy import apply_species_preset, list_species


class SpeciesGrowthAnalyzer:
    """Analyzes growth patterns for Grove species and creates prediction models."""

    def __init__(self, output_dir: Path, height_model_flushes: int = 75, num_seeds: int = 3):
        """
        Initialize the growth analyzer.

        Args:
            output_dir: Directory to save growth models
            height_model_flushes: Number of growth cycles for height curve generation
            num_seeds: Number of different random seeds to average for robust curves
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.height_model_flushes = height_model_flushes
        self.num_seeds = num_seeds

        # Results storage
        self.height_curves = {}  # species -> list of heights per cycle
        self.growth_models = {}  # species -> sklearn model
        self.analysis_metadata = {}  # species -> analysis info

    def get_available_species(self) -> List[str]:
        """Get list of all available Grove species presets using growpy."""
        try:
            return list_species()
        except Exception:
            # Fallback to manual directory scanning
            presets_dir = Path(__file__).parent.parent / "the_grove_22" / "presets"
            
            if not presets_dir.exists():
                raise FileNotFoundError(f"Presets directory not found: {presets_dir}")

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

    def generate_height_curve_for_species(
        self, species: str
    ) -> Tuple[List[float], Dict[str, Any]]:
        """
        Generate height curve for a single species by simulating growth with multiple seeds.
        Averages results to account for random variation.

        Args:
            species: Species name

        Returns:
            Tuple of (averaged_height_curve, metadata)
        """
        all_curves = []
        seed_metadata = []
        
        # Test multiple seeds to get robust average
        seeds_to_test = [1, 7, 13, 23, 42, 100, 111, 123, 666][:self.num_seeds]
        
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
                apply_species_preset(grove, species)
            except Exception as e:
                # Fallback to manual preset loading
                try:
                    presets_dir = Path(__file__).parent.parent / "the_grove_22" / "presets"
                    preset_path = presets_dir / f"{species}.seed.json"

                    if not preset_path.exists():
                        raise FileNotFoundError(f"Preset file not found: {preset_path}")

                    with open(preset_path, "r") as f:
                        preset_json = f.read()

                    properties = gc.io.properties_from_json_string(preset_json)
                    grove.set_properties(properties)
                except Exception as e2:
                    raise ValueError(f"Failed to apply preset for {species}: {e} (fallback: {e2})")

            # Clear any default trees and add a single tree at origin
            grove.clear_trees()
            grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

            # Record height after each cycle for this seed
            heights_this_seed = []
            max_height_achieved = 0.0

            # Growth simulation
            for cycle in range(self.height_model_flushes):
                grove.simulate(1)

                # Get tree height using more robust method
                current_height = 0.0
                if grove.trees and len(grove.trees) > 0:
                    tree = grove.trees[0]

                    if hasattr(tree, "nodes") and len(tree.nodes) > 0:
                        # Find the highest node Z position
                        max_height = 0.0
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
                                    if (hasattr(node, "side_branches") and node.side_branches):
                                        for side_branch in node.side_branches:
                                            side_max = find_max_height_in_branch(side_branch)
                                            if side_max > local_max:
                                                local_max = side_max
                            return local_max

                        tree_max_height = find_max_height_in_branch(tree)
                        current_height = max(max_height, tree_max_height)
                        
                        # Update max height achieved if current height is higher
                        if current_height > max_height_achieved:
                            max_height_achieved = current_height
                        
                        # Store the maximum height achieved so far (prevents decline)
                        heights_this_seed.append(max_height_achieved)
                    else:
                        heights_this_seed.append(max_height_achieved)
                else:
                    heights_this_seed.append(max_height_achieved)
            
            all_curves.append(heights_this_seed)
            seed_metadata.append({
                'seed': seed,
                'final_height': heights_this_seed[-1] if heights_this_seed else 0.0,
                'max_height': max_height_achieved
            })
            
            seed_progress.set_postfix(seed=seed, height=f"{max_height_achieved:.2f}")

        # Take maximum heights across all seeds to eliminate tree death effects
        if not all_curves:
            raise ValueError(f"No successful growth curves generated for {species}")
        
        # Calculate maximum height at each cycle (best case across all seeds)
        max_heights = []
        for cycle in range(self.height_model_flushes):
            cycle_heights = [curve[cycle] for curve in all_curves if cycle < len(curve)]
            if cycle_heights:
                max_heights.append(max(cycle_heights))
            else:
                max_heights.append(0.0)

        metadata = {
            "species": species,
            "cycles": self.height_model_flushes,
            "num_seeds": len(all_curves),
            "seeds_tested": [m['seed'] for m in seed_metadata],
            "final_height": max_heights[-1] if max_heights else 0.0,
            "max_height": max(max_heights) if max_heights else 0.0,
            "growth_rate": max(max_heights) / self.height_model_flushes if max_heights else 0.0,
            "height_curve": max_heights,
            "seed_results": seed_metadata,
            "note": "Height curve uses maximum height per cycle across multiple seeds to eliminate tree death effects"
        }

        return max_heights, metadata

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
        """Save growth models in species-specific subfolders only."""
        tqdm.write("Saving individual species results...")
        saved_count = 0
        for species in tqdm(
            self.analysis_metadata.keys(), desc="Saving species", leave=False
        ):
            species_dir = self.save_species_results(species)
            saved_count += 1

        tqdm.write(f"Saved {saved_count} species models to individual subfolders in: {self.output_dir}")



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
        "--seeds", type=int, default=3, help="Number of random seeds to average for robust curves"
    )
    parser.add_argument(
        "--species",
        type=str,
        help="Specific species to analyze (if not provided, analyzes all species)",
    )

    args = parser.parse_args()

    # Create analyzer
    analyzer = SpeciesGrowthAnalyzer(args.output_dir, args.cycles, args.seeds)

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

            # Save results
            analyzer.save_growth_models()

            tqdm.write(f"\nSuccess: Generated growth model for {args.species}")
            tqdm.write(f"Results saved to: {species_dir}")
            return True

        except Exception as e:
            tqdm.write(f"\nFailed to analyze {args.species}: {e}")
            return False
    else:
        # Analyze all species
        tqdm.write("Analyzing all species...")
        results = analyzer.analyze_all_species()

        # Save results
        analyzer.save_growth_models()

        # Report results
        successful = sum(1 for success in results.values() if success)
        total = len(results)

        if successful > 0:
            tqdm.write(
                f"\nSuccess: Generated growth models for {successful}/{total} species"
            )
            tqdm.write(f"Models saved to species-specific subfolders in: {args.output_dir}")
            return True
        else:
            tqdm.write(f"\nFailed: No growth models generated")
            return False


if __name__ == "__main__":
    main()
