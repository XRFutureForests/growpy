"""
Species growth analysis utility for The Grove 2.2.

This utility generates height curves and age prediction models for all Grove species presets.
It should be run once to create growth models that can be used by all forest simulations.

Usage:
    python src/utils/species_growth_analysis.py --output_dir data/growth_models
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple, Any
import pickle
import json
import argparse

# Add src to path for Grove imports
src_path = Path(__file__).parent.parent
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "the_grove_22" / "modules"))

import pandas as pd
import numpy as np
from sklearn.linear_model import LinearRegression
import the_grove_22_core as gc


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
                if species_name.endswith('.seed'):
                    species_name = species_name[:-5]
                    
                if species_name and not species_name.startswith("."):
                    species_list.append(species_name)
            except Exception:
                continue
                
        return sorted(species_list)
        
    def generate_height_curve_for_species(self, species: str) -> Tuple[List[float], Dict[str, Any]]:
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
            
        # Add a single tree at origin
        grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
        
        # Record height after each cycle
        heights = []
        
        for cycle in range(self.height_model_flushes):
            grove.simulate(1)
            
            # Get tree height (Z coordinate of highest point)
            if grove.trees:
                tree = grove.trees[0]
                max_height = 0.0
                
                # Find highest point in tree structure (including branches)
                def traverse_branch(branch):
                    nonlocal max_height
                    for node in branch.nodes:
                        if node.pos.z > max_height:
                            max_height = node.pos.z
                        
                        # Check side branches recursively
                        if node.side_branches:
                            for side_branch in node.side_branches:
                                traverse_branch(side_branch)
                
                traverse_branch(tree)
                heights.append(max_height)
            else:
                heights.append(0.0)
                
        metadata = {
            'species': species,
            'cycles': self.height_model_flushes,
            'final_height': heights[-1] if heights else 0.0,
            'max_height': max(heights) if heights else 0.0,
            'growth_rate': heights[-1] / self.height_model_flushes if heights else 0.0
        }
        
        return heights, metadata
        
    def create_growth_model_for_species(self, species: str, height_curve: List[float]) -> LinearRegression:
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
        
        print(f"Analyzing {len(species_list)} species...")
        
        for i, species in enumerate(species_list):
            print(f"Analyzing {i+1}/{len(species_list)}: {species}")
            
            try:
                # Generate height curve
                height_curve, metadata = self.generate_height_curve_for_species(species)
                
                # Create growth model
                growth_model = self.create_growth_model_for_species(species, height_curve)
                
                # Store results
                self.height_curves[species] = height_curve
                self.growth_models[species] = growth_model
                self.analysis_metadata[species] = metadata
                
                print(f"  - Final height: {metadata['final_height']:.2f}")
                print(f"  - Growth rate: {metadata['growth_rate']:.3f} units/cycle")
                
                results[species] = True
                
            except Exception as e:
                print(f"  - FAILED: {e}")
                results[species] = False
                
        successful = sum(1 for success in results.values() if success)
        print(f"\nAnalysis complete: {successful}/{len(species_list)} species")
        
        return results
        
    def save_growth_models(self):
        """Save all growth models and metadata to files."""
        # Save growth models as pickle
        models_path = self.output_dir / "species_growth_models.pkl"
        with open(models_path, 'wb') as f:
            pickle.dump(self.growth_models, f)
        print(f"Saved growth models: {models_path}")
        
        # Save height curves as JSON
        curves_path = self.output_dir / "species_height_curves.json"
        with open(curves_path, 'w') as f:
            json.dump(self.height_curves, f, indent=2)
        print(f"Saved height curves: {curves_path}")
        
        # Save metadata as JSON
        metadata_path = self.output_dir / "species_analysis_metadata.json"
        with open(metadata_path, 'w') as f:
            json.dump(self.analysis_metadata, f, indent=2)
        print(f"Saved analysis metadata: {metadata_path}")
        
    def create_prediction_summary(self):
        """Create human-readable summary of growth analysis."""
        summary_path = self.output_dir / "growth_analysis_summary.txt"
        
        with open(summary_path, 'w') as f:
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
                
        print(f"Created summary: {summary_path}")


class GrowthModelLoader:
    """Utility class to load and use pre-generated growth models."""
    
    def __init__(self, models_dir: Path):
        """
        Initialize the model loader.
        
        Args:
            models_dir: Directory containing saved growth models
        """
        self.models_dir = Path(models_dir)
        self.growth_models = {}
        self.height_curves = {}
        self.metadata = {}
        
        self._load_models()
        
    def _load_models(self):
        """Load growth models from saved files."""
        # Load growth models
        models_path = self.models_dir / "species_growth_models.pkl"
        if models_path.exists():
            with open(models_path, 'rb') as f:
                self.growth_models = pickle.load(f)
                
        # Load height curves  
        curves_path = self.models_dir / "species_height_curves.json"
        if curves_path.exists():
            with open(curves_path, 'r') as f:
                self.height_curves = json.load(f)
                
        # Load metadata
        metadata_path = self.models_dir / "species_analysis_metadata.json"
        if metadata_path.exists():
            with open(metadata_path, 'r') as f:
                self.metadata = json.load(f)
                
    def predict_cycles_for_height(self, species: str, target_height: float) -> int:
        """
        Predict required growth cycles for target height.
        
        Args:
            species: Species name
            target_height: Target height
            
        Returns:
            Predicted cycles needed
        """
        if species not in self.growth_models:
            # Default fallback based on rough estimate
            return max(1, int(target_height * 4))  # Rough heuristic
            
        model = self.growth_models[species]
        predicted = model.predict([[target_height]])[0]
        return max(1, int(predicted))
        
    def get_available_species(self) -> List[str]:
        """Get list of species with growth models."""
        return list(self.growth_models.keys())
        
    def calculate_forest_delays(self, forest_data: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate delay values for all trees in forest to synchronize growth.
        
        Args:
            forest_data: DataFrame with columns: x, y, z, species, height
            
        Returns:
            DataFrame with added 'predicted_cycles' and 'delay' columns
        """
        if 'height' not in forest_data.columns:
            raise ValueError("Forest data must include 'height' column")
            
        enhanced_data = forest_data.copy()
        max_cycles = 0
        
        # Calculate required cycles for each tree
        predicted_cycles = []
        for _, row in enhanced_data.iterrows():
            cycles = self.predict_cycles_for_height(row['species'], row['height'])
            predicted_cycles.append(cycles)
            max_cycles = max(max_cycles, cycles)
            
        enhanced_data['predicted_cycles'] = predicted_cycles
        
        # Calculate delays to synchronize all trees  
        # Delay = max_cycles - required_cycles
        enhanced_data['delay'] = max_cycles - enhanced_data['predicted_cycles']
        
        return enhanced_data, max_cycles


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description="Generate growth models for all Grove species"
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default="data/growth_models", 
        help="Directory to save growth models"
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=75,
        help="Number of growth cycles for analysis"
    )
    
    args = parser.parse_args()
    
    # Create analyzer
    analyzer = SpeciesGrowthAnalyzer(args.output_dir, args.cycles)
    
    # Analyze all species
    results = analyzer.analyze_all_species()
    
    # Save results
    analyzer.save_growth_models()
    analyzer.create_prediction_summary()
    
    # Report results
    successful = sum(1 for success in results.values() if success)
    total = len(results)
    
    if successful > 0:
        print(f"\nSuccess: Generated growth models for {successful}/{total} species")
        print(f"Models saved to: {args.output_dir}")
        return True
    else:
        print(f"\nFailed: No growth models generated")
        return False


if __name__ == "__main__":
    main()