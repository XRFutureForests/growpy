"""
Advanced Fir Height Growth Analysis for The Grove 2.2.

This utility performs detailed analysis of Fir tree height growth patterns by:
1. Testing different parameter combinations (grow_length, grow_length_reduce, simulation_scale)
2. Implementing dynamic property updates during growth simulation
3. Comparing results against real-world Fir growth data
4. Generating comprehensive visualizations and analysis

The goal is to achieve more realistic growth curves that start steep and gradually
flatten but continue growing, rather than the linear growth followed by sudden stop
observed in the current models.

Real Fir Growth Data (used as target):
- 10 years: 5m
- 25 years: 10m  
- 50 years: 20m
- 75 years: 27m
- 100 years: 35m
- 125 years: 40m
- 150 years: 45m
- 200 years: 50m

Usage:
    python src/growpy/utils/04_fir_height_analysis.py
    python src/growpy/utils/04_fir_height_analysis.py --cycles 200 --output_dir data/fir_analysis
"""

import argparse
import copy
import json
import logging
import sys
import warnings
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import matplotlib.style as mplstyle
import numpy as np
from scipy.optimize import curve_fit
from sklearn.metrics import mean_squared_error, r2_score
from tqdm import tqdm

# Suppress warnings for cleaner output
warnings.filterwarnings('ignore', category=UserWarning)
warnings.filterwarnings('ignore', category=FutureWarning)

# Add src to path for Grove imports
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "the_grove_22" / "modules"))

# Use refactored growpy package
from growpy import GrowPyConfig
from growpy.grove import create_grove

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Suppress verbose matplotlib logging
logging.getLogger("matplotlib").setLevel(logging.WARNING)
logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)


class FirHeightAnalyzer:
    """Advanced analyzer for Fir tree height growth patterns."""

    def __init__(self, assets_dir: Path, output_dir: Path, max_cycles: int = 200):
        """
        Initialize the Fir height analyzer.

        Args:
            assets_dir: Directory containing prepared GrowPy assets
            output_dir: Directory to save analysis results
            max_cycles: Maximum number of growth cycles to simulate
        """
        self.assets_dir = Path(assets_dir)
        self.output_dir = Path(output_dir)
        self.max_cycles = max_cycles
        
        # Validate and create directories
        if not self.assets_dir.exists():
            raise FileNotFoundError(f"Assets directory not found: {self.assets_dir}")
        
        self.presets_dir = self.assets_dir / "presets"
        if not self.presets_dir.exists():
            raise FileNotFoundError(f"Presets directory not found: {self.presets_dir}")
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        # Load base Fir preset
        self.fir_preset_path = self.presets_dir / "Pinaceae - Fir.seed.json"
        if not self.fir_preset_path.exists():
            raise FileNotFoundError(f"Fir preset not found: {self.fir_preset_path}")
        
        with open(self.fir_preset_path, 'r') as f:
            self.base_fir_preset = json.load(f)
        
        logger.info(f"Base Fir preset loaded from: {self.fir_preset_path}")
        logger.info(f"Base parameters - grow_length: {self.base_fir_preset['grow_length']}, "
                   f"add_chance_reduce: {self.base_fir_preset.get('add_chance_reduce', 'N/A')}, "
                   f"favor_dwindle: {self.base_fir_preset.get('favor_dwindle', 'N/A')}, "
                   f"simulation_scale: {self.base_fir_preset['simulation_scale']}")
        
        # Real-world Fir growth data (years -> meters)
        self.real_fir_data = {
            10: 5.0,
            25: 10.0,
            50: 20.0,
            75: 27.0,
            100: 35.0,
            125: 40.0,
            150: 45.0,
            200: 50.0
        }
        
        # Convert to arrays for analysis
        self.real_years = np.array(list(self.real_fir_data.keys()))
        self.real_heights = np.array(list(self.real_fir_data.values()))
        
        # Storage for analysis results
        self.static_results = {}  # parameter_set -> height_curve
        self.dynamic_results = {}  # approach_name -> height_curve
        self.analysis_metadata = {}
        
        logger.info(f"Real Fir data loaded: {len(self.real_fir_data)} data points")
        logger.info(f"Analysis will run for {max_cycles} cycles")

    def calculate_tree_height(self, tree) -> float:
        """
        Calculate the maximum height of a tree using iterative approach to avoid recursion issues.

        Args:
            tree: Grove tree (Branch) object

        Returns:
            Maximum height (z-coordinate) in the tree
        """
        max_height = 0.0
        branches_to_check = [tree]
        
        while branches_to_check:
            current_branch = branches_to_check.pop()
            
            # Check nodes in this branch
            if hasattr(current_branch, "nodes") and current_branch.nodes:
                for node in current_branch.nodes:
                    # Check this node's height
                    if hasattr(node, "pos") and node.pos.z > max_height:
                        max_height = node.pos.z

                    # Add side branches to check list
                    if hasattr(node, "side_branches") and node.side_branches:
                        branches_to_check.extend(node.side_branches)
        
        return max_height

    def apply_preset_to_grove(self, grove, preset_dict: Dict[str, Any]) -> bool:
        """
        Apply a preset dictionary to a grove.

        Args:
            grove: Grove object to apply preset to
            preset_dict: Dictionary containing preset parameters

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert dictionary to properties
            import json

            import the_grove_22_core as gc

            # Convert dict to JSON string and then to Grove properties
            preset_json = json.dumps(preset_dict)
            properties = gc.io.properties_from_json_string(preset_json)
            grove.set_properties(properties)
            
            return True
        except Exception as e:
            logger.error(f"Failed to apply preset to grove: {e}")
            return False
        """
        Apply a preset dictionary to a grove.

        Args:
            grove: Grove object to apply preset to
            preset_dict: Dictionary containing preset parameters

        Returns:
            True if successful, False otherwise
        """
        try:
            # Convert dictionary to properties
            import json

            import the_grove_22_core as gc

            # Convert dict to JSON string and then to Grove properties
            preset_json = json.dumps(preset_dict)
            properties = gc.io.properties_from_json_string(preset_json)
            grove.set_properties(properties)
            
            return True
        except Exception as e:
            logger.error(f"Failed to apply preset to grove: {e}")
            return False

    def simulate_growth_with_preset(self, preset_dict: Dict[str, Any], 
                                  dynamic_updates: Optional[Callable] = None,
                                  seed: int = 42) -> List[float]:
        """
        Simulate tree growth with given preset and optional dynamic updates.

        Args:
            preset_dict: Preset parameters to use
            dynamic_updates: Optional function to call each cycle for dynamic updates
            seed: Random seed for reproducible results

        Returns:
            List of heights for each growth cycle
        """
        try:
            # Import Grove core modules
            import the_grove_22_core as gc

            # Create grove
            grove = gc.Grove()
            grove.clear_trees()
            grove.set_random_seed(seed)
            
            # Apply preset to grove
            if not self.apply_preset_to_grove(grove, preset_dict):
                return []

            # Add a tree at origin
            position = gc.Vector(0, 0, 0)
            direction = gc.Vector(0, 0, 1)
            grove.add_new_tree(position, direction, 0)
            
            height_curve = []
            
            # Simulate growth cycles
            for cycle in range(self.max_cycles):
                # Apply dynamic updates if provided
                if dynamic_updates:
                    try:
                        # Get current trees for dynamic updates
                        trees = grove.trees  # This creates a copy but we need it for height
                        if trees:
                            tree = trees[0]
                            dynamic_updates(grove, tree, cycle)
                    except Exception as e:
                        logger.warning(f"Dynamic update failed at cycle {cycle}: {e}")
                
                # Grow one cycle
                try:
                    grove.simulate(1)
                except Exception as e:
                    logger.warning(f"Growth failed at cycle {cycle}: {e}")
                    break
                
                # Record current height after growth
                try:
                    trees = grove.trees  # Get current state
                    if trees:
                        tree = trees[0]
                        current_height = self.calculate_tree_height(tree)
                        height_curve.append(current_height)
                    else:
                        height_curve.append(0.0)
                except Exception as e:
                    logger.warning(f"Failed to get tree height at cycle {cycle}: {e}")
                    height_curve.append(0.0)
            
            return height_curve
            
        except Exception as e:
            logger.error(f"Growth simulation failed: {e}")
            return []

    def test_static_parameters(self) -> Dict[str, List[float]]:
        """
        Test different static parameter combinations.

        Returns:
            Dictionary mapping parameter descriptions to height curves
        """
        logger.info("Testing static parameter combinations...")
        
        # Define parameter ranges to test - reduced set for faster execution
        grow_length_values = [0.5, 1.0, 1.5, 2.0]  # Focused range
        add_chance_reduce_values = [0.60, 0.80, 0.95]  # Reduced to key values
        favor_dwindle_values = [0.85, 0.95, 1.0]  # Focused range
        simulation_scale_values = [1.0, 2.0]  # Reduced to key values
        
        results = {}
        total_combinations = len(grow_length_values) * len(add_chance_reduce_values) * len(favor_dwindle_values) * len(simulation_scale_values)
        
        # Progress bar for parameter testing
        with tqdm(total=total_combinations, desc="Testing parameter combinations") as pbar:
            for grow_length in grow_length_values:
                for add_chance_reduce in add_chance_reduce_values:
                    for favor_dwindle in favor_dwindle_values:
                        for simulation_scale in simulation_scale_values:
                            # Create modified preset
                            test_preset = copy.deepcopy(self.base_fir_preset)
                            test_preset['grow_length'] = grow_length
                            test_preset['add_chance_reduce'] = add_chance_reduce
                            test_preset['favor_dwindle'] = favor_dwindle
                            test_preset['simulation_scale'] = simulation_scale
                            
                            # Create description
                            param_desc = f"GL{grow_length}_ACR{add_chance_reduce}_FD{favor_dwindle}_SS{simulation_scale}"
                            
                            # Simulate growth
                            height_curve = self.simulate_growth_with_preset(test_preset)
                            
                            if height_curve:
                                results[param_desc] = height_curve
                                
                            pbar.update(1)
        
        logger.info(f"Static parameter testing complete: {len(results)} successful combinations")
        self.static_results = results
        return results

    def logarithmic_growth_function(self, years: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
        """Logarithmic growth function: height = a * log(years + b) + c"""
        return a * np.log(years + b) + c

    def exponential_decay_growth_function(self, years: np.ndarray, a: float, b: float, c: float) -> np.ndarray:
        """Exponential decay growth function: height = a * (1 - exp(-b * years)) + c"""
        return a * (1 - np.exp(-b * years)) + c

    def fit_growth_models_to_real_data(self) -> Dict[str, Dict[str, Any]]:
        """
        Fit mathematical growth models to real Fir data.

        Returns:
            Dictionary containing fitted model parameters and statistics
        """
        logger.info("Fitting growth models to real Fir data...")
        
        models = {}
        
        # Fit logarithmic model
        try:
            popt_log, _ = curve_fit(self.logarithmic_growth_function, self.real_years, self.real_heights,
                                  p0=[10, 1, 0], maxfev=10000)
            
            predicted_log = self.logarithmic_growth_function(self.real_years, *popt_log)
            r2_log = r2_score(self.real_heights, predicted_log)
            rmse_log = np.sqrt(mean_squared_error(self.real_heights, predicted_log))
            
            models['logarithmic'] = {
                'params': {'a': popt_log[0], 'b': popt_log[1], 'c': popt_log[2]},
                'r2': r2_log,
                'rmse': rmse_log,
                'function': self.logarithmic_growth_function
            }
            
            logger.info(f"Logarithmic model: R² = {r2_log:.4f}, RMSE = {rmse_log:.2f}")
            
        except Exception as e:
            logger.warning(f"Failed to fit logarithmic model: {e}")

        # Fit exponential decay model
        try:
            popt_exp, _ = curve_fit(self.exponential_decay_growth_function, self.real_years, self.real_heights,
                                  p0=[50, 0.01, 0], maxfev=10000)
            
            predicted_exp = self.exponential_decay_growth_function(self.real_years, *popt_exp)
            r2_exp = r2_score(self.real_heights, predicted_exp)
            rmse_exp = np.sqrt(mean_squared_error(self.real_heights, predicted_exp))
            
            models['exponential_decay'] = {
                'params': {'a': popt_exp[0], 'b': popt_exp[1], 'c': popt_exp[2]},
                'r2': r2_exp,
                'rmse': rmse_exp,
                'function': self.exponential_decay_growth_function
            }
            
            logger.info(f"Exponential decay model: R² = {r2_exp:.4f}, RMSE = {rmse_exp:.2f}")
            
        except Exception as e:
            logger.warning(f"Failed to fit exponential decay model: {e}")

        return models

    def create_dynamic_grow_length_updater(self, growth_model: Dict[str, Any]) -> Callable:
        """
        Create a dynamic updater function based on fitted growth model.

        Args:
            growth_model: Fitted growth model parameters

        Returns:
            Function that updates grove properties dynamically
        """
        def dynamic_updater(grove, tree, cycle):
            # Calculate target height for next cycle based on model
            target_height_current = growth_model['function'](np.array([cycle + 1]), **growth_model['params'])[0]
            target_height_next = growth_model['function'](np.array([cycle + 2]), **growth_model['params'])[0]
            
            # Calculate desired height increment
            desired_increment = target_height_next - target_height_current
            
            # Get current tree height using our calculation method
            current_height = self.calculate_tree_height(tree)
            
            # Adjust grow_length based on desired increment
            # This is a simplified approach - in reality, the relationship is more complex
            if desired_increment > 0:
                # Scale grow_length to achieve desired increment
                # Base this on the original grow_length and some scaling factor
                base_grow_length = self.base_fir_preset['grow_length']
                scale_factor = desired_increment / base_grow_length if base_grow_length > 0 else 1.0
                
                # Clamp the scale factor to reasonable bounds
                scale_factor = max(0.01, min(scale_factor, 5.0))
                
                new_grow_length = base_grow_length * scale_factor
                
                # Apply updated properties to grove
                props = grove.get_properties()
                props.grow_length = new_grow_length
                # Also adjust add_chance_reduce and favor_dwindle for sustained growth
                props.add_chance_reduce = max(0.7, props.add_chance_reduce)
                props.favor_dwindle = min(1.0, props.favor_dwindle + 0.01)
                grove.set_properties(props)
            
        return dynamic_updater

    def test_dynamic_approaches(self) -> Dict[str, List[float]]:
        """
        Test different dynamic growth approaches.

        Returns:
            Dictionary mapping approach names to height curves
        """
        logger.info("Testing dynamic growth approaches...")
        
        # First, fit models to real data
        growth_models = self.fit_growth_models_to_real_data()
        
        results = {}
        
        # Test model-based dynamic updates
        for model_name, model_data in growth_models.items():
            logger.info(f"Testing dynamic approach with {model_name} model...")
            
            dynamic_updater = self.create_dynamic_grow_length_updater(model_data)
            height_curve = self.simulate_growth_with_preset(
                self.base_fir_preset, 
                dynamic_updates=dynamic_updater
            )
            
            if height_curve:
                results[f"dynamic_{model_name}"] = height_curve

        # Test manual dynamic approaches
        
        # Approach 1: Gradually increase favor_dwindle over time
        def gradual_dwindle_increase(grove, tree, cycle):
            # Start with base value and gradually increase towards 1.0 (no dwindle)
            base_dwindle = self.base_fir_preset.get('favor_dwindle', 0.85)
            target_dwindle = 1.0
            progress = min(cycle / 100.0, 1.0)  # Reach target at cycle 100
            new_dwindle = base_dwindle + (target_dwindle - base_dwindle) * progress
            
            props = grove.get_properties()
            props.favor_dwindle = new_dwindle
            grove.set_properties(props)
        
        logger.info("Testing gradual favor_dwindle increase...")
        height_curve = self.simulate_growth_with_preset(
            self.base_fir_preset,
            dynamic_updates=gradual_dwindle_increase
        )
        if height_curve:
            results["dynamic_gradual_dwindle"] = height_curve

        # Approach 2: Periodic grow_length boost
        def periodic_boost(grove, tree, cycle):
            # Give a small boost to grow_length every 10 cycles
            if cycle % 10 == 0 and cycle > 0:
                props = grove.get_properties()
                current_length = props.grow_length
                boost_factor = 1.05  # Smaller boost
                props.grow_length = current_length * boost_factor
                # Also slightly reduce add_chance_reduce to maintain branching
                props.add_chance_reduce = max(0.3, props.add_chance_reduce - 0.01)
                grove.set_properties(props)
        
        logger.info("Testing periodic boost approach...")
        height_curve = self.simulate_growth_with_preset(
            self.base_fir_preset,
            dynamic_updates=periodic_boost
        )
        if height_curve:
            results["dynamic_periodic_boost"] = height_curve

        # Approach 3: Height-dependent adjustments
        def height_dependent(grove, tree, cycle):
            current_height = self.calculate_tree_height(tree)
            
            props = grove.get_properties()
            
            # Adjust grow_length based on current height
            if current_height < 10:
                # Young tree - allow normal growth
                props.grow_length = self.base_fir_preset['grow_length']
                props.add_chance_reduce = 0.6
                props.favor_dwindle = 0.85
            elif current_height < 30:
                # Mature tree - slower but sustained growth
                props.grow_length = self.base_fir_preset['grow_length'] * 1.2
                props.add_chance_reduce = 0.8
                props.favor_dwindle = 0.95
            else:
                # Old tree - sustained growth for tall trees
                props.grow_length = self.base_fir_preset['grow_length'] * 1.5
                props.add_chance_reduce = 0.9
                props.favor_dwindle = 1.0
            
            grove.set_properties(props)
        
        logger.info("Testing height-dependent approach...")
        height_curve = self.simulate_growth_with_preset(
            self.base_fir_preset,
            dynamic_updates=height_dependent
        )
        if height_curve:
            results["dynamic_height_dependent"] = height_curve

        logger.info(f"Dynamic approaches testing complete: {len(results)} approaches tested")
        self.dynamic_results = results
        return results

    def calculate_fit_statistics(self, simulated_curve: List[float], curve_name: str) -> Dict[str, float]:
        """
        Calculate fit statistics comparing simulated curve to real data.

        Args:
            simulated_curve: Simulated height curve
            curve_name: Name of the curve for logging

        Returns:
            Dictionary with fit statistics
        """
        if not simulated_curve:
            return {}
        
        # Interpolate simulated curve at real data points
        simulated_array = np.array(simulated_curve)
        interpolated_heights = []
        
        for year in self.real_years:
            if year < len(simulated_array):
                interpolated_heights.append(simulated_array[year])
            else:
                # Extrapolate using last value
                interpolated_heights.append(simulated_array[-1])
        
        interpolated_heights = np.array(interpolated_heights)
        
        # Calculate statistics
        try:
            r2 = r2_score(self.real_heights, interpolated_heights)
            rmse = np.sqrt(mean_squared_error(self.real_heights, interpolated_heights))
            max_height = max(simulated_curve)
            final_height = simulated_curve[-1] if simulated_curve else 0
            
            stats = {
                'r2': r2,
                'rmse': rmse,
                'max_height': max_height,
                'final_height': final_height,
                'height_at_200': simulated_curve[199] if len(simulated_curve) > 199 else final_height
            }
            
            logger.debug(f"{curve_name}: R² = {r2:.4f}, RMSE = {rmse:.2f}, Max height = {max_height:.1f}")
            return stats
            
        except Exception as e:
            logger.warning(f"Failed to calculate statistics for {curve_name}: {e}")
            return {}

    def create_comprehensive_plots(self):
        """Create comprehensive visualization plots of all results."""
        logger.info("Creating comprehensive visualization plots...")
        
        # Set up matplotlib style
        mplstyle.use("default")
        plt.style.use("seaborn-v0_8" if "seaborn-v0_8" in plt.style.available else "default")
        
        # Create main comparison plot
        fig, ((ax1, ax2), (ax3, ax4)) = plt.subplots(2, 2, figsize=(20, 16))
        fig.suptitle("Fir Height Growth Analysis - Comprehensive Results", fontsize=20, fontweight="bold")
        
        cycles = np.arange(self.max_cycles)
        
        # Plot 1: Best static parameter combinations
        ax1.set_title("Best Static Parameter Combinations", fontsize=14, fontweight="bold")
        
        # Calculate statistics for all static results and get top 5
        static_stats = {}
        for name, curve in self.static_results.items():
            stats = self.calculate_fit_statistics(curve, name)
            if stats:
                static_stats[name] = stats
        
        # Sort by R² score and take top 5
        top_static = sorted(static_stats.items(), key=lambda x: x[1].get('r2', -1), reverse=True)[:5]
        
        colors = ['blue', 'green', 'red', 'orange', 'purple']
        for i, (name, stats) in enumerate(top_static):
            curve = self.static_results[name]
            label = f"{name} (R²={stats['r2']:.3f})"
            ax1.plot(cycles[:len(curve)], curve, color=colors[i], linewidth=2, alpha=0.8, label=label)
        
        # Plot real data
        ax1.scatter(self.real_years, self.real_heights, color='black', s=100, marker='o', 
                   label='Real Fir Data', zorder=10, edgecolors='white', linewidth=2)
        
        ax1.set_xlabel("Growth Cycles (Years)", fontsize=12)
        ax1.set_ylabel("Height (meters)", fontsize=12)
        ax1.grid(True, alpha=0.3)
        ax1.legend(fontsize=9)
        ax1.set_xlim(0, self.max_cycles)
        
        # Plot 2: Dynamic approaches
        ax2.set_title("Dynamic Growth Approaches", fontsize=14, fontweight="bold")
        
        # Calculate statistics for dynamic results
        dynamic_stats = {}
        for name, curve in self.dynamic_results.items():
            stats = self.calculate_fit_statistics(curve, name)
            if stats:
                dynamic_stats[name] = stats
        
        # Plot all dynamic approaches
        dynamic_colors = ['darkblue', 'darkgreen', 'darkred', 'darkorange', 'darkviolet', 'darkcyan']
        for i, (name, curve) in enumerate(self.dynamic_results.items()):
            stats = dynamic_stats.get(name, {})
            r2_str = f" (R²={stats['r2']:.3f})" if 'r2' in stats else ""
            label = f"{name.replace('dynamic_', '')}{r2_str}"
            color = dynamic_colors[i % len(dynamic_colors)]
            ax2.plot(cycles[:len(curve)], curve, color=color, linewidth=2, alpha=0.8, label=label)
        
        # Plot real data
        ax2.scatter(self.real_years, self.real_heights, color='black', s=100, marker='o', 
                   label='Real Fir Data', zorder=10, edgecolors='white', linewidth=2)
        
        ax2.set_xlabel("Growth Cycles (Years)", fontsize=12)
        ax2.set_ylabel("Height (meters)", fontsize=12)
        ax2.grid(True, alpha=0.3)
        ax2.legend(fontsize=9)
        ax2.set_xlim(0, self.max_cycles)
        
        # Plot 3: Original vs Best approaches
        ax3.set_title("Original vs Best Approaches", fontsize=14, fontweight="bold")
        
        # Plot original Fir curve
        original_curve = self.simulate_growth_with_preset(self.base_fir_preset)
        if original_curve:
            ax3.plot(cycles[:len(original_curve)], original_curve, 'gray', linewidth=3, 
                    alpha=0.7, label='Original Fir Preset', linestyle='--')
        
        # Plot best static approach
        if top_static:
            best_static_name, best_static_stats = top_static[0]
            best_static_curve = self.static_results[best_static_name]
            ax3.plot(cycles[:len(best_static_curve)], best_static_curve, 'blue', linewidth=3, 
                    alpha=0.9, label=f'Best Static (R²={best_static_stats["r2"]:.3f})')
        
        # Plot best dynamic approach
        if dynamic_stats:
            best_dynamic_name = max(dynamic_stats.keys(), key=lambda x: dynamic_stats[x].get('r2', -1))
            best_dynamic_curve = self.dynamic_results[best_dynamic_name]
            best_dynamic_stats = dynamic_stats[best_dynamic_name]
            ax3.plot(cycles[:len(best_dynamic_curve)], best_dynamic_curve, 'red', linewidth=3, 
                    alpha=0.9, label=f'Best Dynamic (R²={best_dynamic_stats["r2"]:.3f})')
        
        # Plot real data
        ax3.scatter(self.real_years, self.real_heights, color='black', s=100, marker='o', 
                   label='Real Fir Data', zorder=10, edgecolors='white', linewidth=2)
        
        ax3.set_xlabel("Growth Cycles (Years)", fontsize=12)
        ax3.set_ylabel("Height (meters)", fontsize=12)
        ax3.grid(True, alpha=0.3)
        ax3.legend(fontsize=11)
        ax3.set_xlim(0, self.max_cycles)
        
        # Plot 4: Growth rate comparison
        ax4.set_title("Growth Rate Analysis", fontsize=14, fontweight="bold")
        
        # Calculate growth rates for real data
        real_growth_rates = []
        for i in range(1, len(self.real_years)):
            rate = (self.real_heights[i] - self.real_heights[i-1]) / (self.real_years[i] - self.real_years[i-1])
            real_growth_rates.append(rate)
        
        real_years_midpoints = [(self.real_years[i] + self.real_years[i-1]) / 2 for i in range(1, len(self.real_years))]
        
        ax4.plot(real_years_midpoints, real_growth_rates, 'ko-', linewidth=3, markersize=8, 
                label='Real Fir Growth Rate', alpha=0.8)
        
        # Calculate and plot growth rates for best approaches
        if top_static:
            best_static_curve = self.static_results[top_static[0][0]]
            static_growth_rates = [best_static_curve[i] - best_static_curve[i-1] 
                                 for i in range(1, len(best_static_curve))]
            ax4.plot(range(1, len(static_growth_rates) + 1), static_growth_rates, 
                    'b-', alpha=0.7, label='Best Static Growth Rate')
        
        if dynamic_stats:
            best_dynamic_name = max(dynamic_stats.keys(), key=lambda x: dynamic_stats[x].get('r2', -1))
            best_dynamic_curve = self.dynamic_results[best_dynamic_name]
            dynamic_growth_rates = [best_dynamic_curve[i] - best_dynamic_curve[i-1] 
                                  for i in range(1, len(best_dynamic_curve))]
            ax4.plot(range(1, len(dynamic_growth_rates) + 1), dynamic_growth_rates, 
                    'r-', alpha=0.7, label='Best Dynamic Growth Rate')
        
        ax4.set_xlabel("Growth Cycles (Years)", fontsize=12)
        ax4.set_ylabel("Growth Rate (meters/year)", fontsize=12)
        ax4.grid(True, alpha=0.3)
        ax4.legend(fontsize=11)
        ax4.set_xlim(0, min(100, self.max_cycles))  # Focus on first 100 cycles
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.93)
        
        # Save comprehensive plot
        comprehensive_plot_path = self.output_dir / "fir_comprehensive_analysis.png"
        plt.savefig(comprehensive_plot_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()
        
        logger.info(f"Comprehensive plot saved to: {comprehensive_plot_path}")
        
        # Create detailed parameter heatmap for static results
        self.create_parameter_heatmap()

    def create_parameter_heatmap(self):
        """Create heatmap showing R² scores for different parameter combinations."""
        logger.info("Creating parameter heatmap...")
        
        # Organize static results by parameters
        param_data = {}
        for name, curve in self.static_results.items():
            try:
                # Parse parameter string: "GL0.3_GLR0.78_SS1.0"
                parts = name.split('_')
                gl = float(parts[0][2:])  # Remove "GL" prefix
                glr = float(parts[1][3:])  # Remove "GLR" prefix
                ss = float(parts[2][2:])  # Remove "SS" prefix
                
                stats = self.calculate_fit_statistics(curve, name)
                r2 = stats.get('r2', 0)
                
                if ss not in param_data:
                    param_data[ss] = {}
                if gl not in param_data[ss]:
                    param_data[ss][gl] = {}
                param_data[ss][gl][glr] = r2
                
            except Exception as e:
                logger.warning(f"Failed to parse parameters from {name}: {e}")
        
        # Create subplots for each simulation_scale value
        ss_values = sorted(param_data.keys())
        fig, axes = plt.subplots(2, 2, figsize=(16, 12))
        fig.suptitle("Parameter Optimization Heatmaps (R² Scores)", fontsize=16, fontweight="bold")
        
        axes = axes.flatten()
        
        for i, ss in enumerate(ss_values[:4]):  # Limit to 4 subplots
            if i >= len(axes):
                break
                
            ax = axes[i]
            
            # Prepare data for heatmap
            gl_values = sorted(param_data[ss].keys())
            glr_values = sorted(set().union(*[param_data[ss][gl].keys() for gl in gl_values]))
            
            heatmap_data = np.zeros((len(gl_values), len(glr_values)))
            
            for j, gl in enumerate(gl_values):
                for k, glr in enumerate(glr_values):
                    if glr in param_data[ss][gl]:
                        heatmap_data[j, k] = param_data[ss][gl][glr]
            
            # Create heatmap
            im = ax.imshow(heatmap_data, cmap='viridis', aspect='auto')
            
            # Set labels
            ax.set_title(f"Simulation Scale = {ss}", fontsize=12, fontweight="bold")
            ax.set_xlabel("grow_length_reduce", fontsize=10)
            ax.set_ylabel("grow_length", fontsize=10)
            
            # Set tick labels
            ax.set_xticks(range(len(glr_values)))
            ax.set_xticklabels([f"{glr:.2f}" for glr in glr_values], rotation=45)
            ax.set_yticks(range(len(gl_values)))
            ax.set_yticklabels([f"{gl:.1f}" for gl in gl_values])
            
            # Add colorbar
            cbar = plt.colorbar(im, ax=ax)
            cbar.set_label("R² Score", fontsize=10)
            
            # Add text annotations for values
            for j in range(len(gl_values)):
                for k in range(len(glr_values)):
                    value = heatmap_data[j, k]
                    if value > 0:
                        color = 'white' if value < 0.5 else 'black'
                        ax.text(k, j, f'{value:.3f}', ha='center', va='center', 
                               color=color, fontsize=8)
        
        plt.tight_layout()
        plt.subplots_adjust(top=0.93)
        
        # Save heatmap
        heatmap_path = self.output_dir / "parameter_optimization_heatmap.png"
        plt.savefig(heatmap_path, dpi=300, bbox_inches="tight", facecolor="white")
        plt.close()
        
        logger.info(f"Parameter heatmap saved to: {heatmap_path}")

    def save_analysis_results(self):
        """Save all analysis results to files."""
        logger.info("Saving analysis results...")
        
        # Prepare comprehensive results dictionary
        results = {
            'metadata': {
                'max_cycles': self.max_cycles,
                'assets_dir': str(self.assets_dir),
                'base_preset': self.base_fir_preset,
                'real_fir_data': self.real_fir_data,
                'analysis_timestamp': str(Path(__file__).stat().st_mtime)
            },
            'static_results': {},
            'dynamic_results': {},
            'statistics': {}
        }
        
        # Add static results with statistics
        for name, curve in self.static_results.items():
            stats = self.calculate_fit_statistics(curve, name)
            results['static_results'][name] = {
                'height_curve': curve,
                'statistics': stats
            }
        
        # Add dynamic results with statistics
        for name, curve in self.dynamic_results.items():
            stats = self.calculate_fit_statistics(curve, name)
            results['dynamic_results'][name] = {
                'height_curve': curve,
                'statistics': stats
            }
        
        # Calculate overall statistics
        all_stats = {}
        for name, data in {**results['static_results'], **results['dynamic_results']}.items():
            if 'statistics' in data and data['statistics']:
                all_stats[name] = data['statistics']
        
        # Find best approaches
        if all_stats:
            best_overall = max(all_stats.keys(), key=lambda x: all_stats[x].get('r2', -1))
            best_static = max([k for k in all_stats.keys() if k in results['static_results']], 
                            key=lambda x: all_stats[x].get('r2', -1), default=None)
            best_dynamic = max([k for k in all_stats.keys() if k in results['dynamic_results']], 
                             key=lambda x: all_stats[x].get('r2', -1), default=None)
            
            results['statistics']['best_approaches'] = {
                'best_overall': best_overall,
                'best_static': best_static,
                'best_dynamic': best_dynamic
            }
            
            if best_overall:
                results['statistics']['best_overall_stats'] = all_stats[best_overall]
        
        # Save results to JSON
        results_path = self.output_dir / "fir_analysis_results.json"
        with open(results_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"Analysis results saved to: {results_path}")
        
        # Save summary report
        self.create_summary_report(results)

    def create_summary_report(self, results: Dict[str, Any]):
        """Create a human-readable summary report."""
        report_path = self.output_dir / "fir_analysis_summary.txt"
        
        with open(report_path, 'w') as f:
            f.write("=" * 80 + "\n")
            f.write("FIR HEIGHT GROWTH ANALYSIS - SUMMARY REPORT\n")
            f.write("=" * 80 + "\n\n")
            
            f.write(f"Analysis Date: {Path(__file__).stat().st_mtime}\n")
            f.write(f"Maximum Cycles Simulated: {self.max_cycles}\n")
            f.write(f"Assets Directory: {self.assets_dir}\n\n")
            
            f.write("REAL FIR DATA (Target):\n")
            f.write("-" * 30 + "\n")
            for year, height in self.real_fir_data.items():
                f.write(f"  {year:3d} years: {height:5.1f}m\n")
            f.write("\n")
            
            f.write("BASE FIR PRESET PARAMETERS:\n")
            f.write("-" * 35 + "\n")
            f.write(f"  grow_length: {self.base_fir_preset['grow_length']}\n")
            f.write(f"  grow_length_reduce: {self.base_fir_preset['grow_length_reduce']}\n")
            f.write(f"  simulation_scale: {self.base_fir_preset['simulation_scale']}\n\n")
            
            # Static results summary
            f.write("STATIC PARAMETER TESTING RESULTS:\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total combinations tested: {len(self.static_results)}\n\n")
            
            if self.static_results:
                # Get top 5 static results
                static_with_stats = []
                for name, curve in self.static_results.items():
                    stats = self.calculate_fit_statistics(curve, name)
                    if stats:
                        static_with_stats.append((name, stats))
                
                static_with_stats.sort(key=lambda x: x[1].get('r2', -1), reverse=True)
                
                f.write("Top 5 Static Parameter Combinations:\n")
                for i, (name, stats) in enumerate(static_with_stats[:5], 1):
                    f.write(f"  {i}. {name}\n")
                    f.write(f"     R² Score: {stats.get('r2', 0):.4f}\n")
                    f.write(f"     RMSE: {stats.get('rmse', 0):.2f}m\n")
                    f.write(f"     Final Height: {stats.get('final_height', 0):.1f}m\n")
                    f.write(f"     Height at 200 years: {stats.get('height_at_200', 0):.1f}m\n\n")
            
            # Dynamic results summary
            f.write("DYNAMIC APPROACH TESTING RESULTS:\n")
            f.write("-" * 40 + "\n")
            f.write(f"Total approaches tested: {len(self.dynamic_results)}\n\n")
            
            if self.dynamic_results:
                dynamic_with_stats = []
                for name, curve in self.dynamic_results.items():
                    stats = self.calculate_fit_statistics(curve, name)
                    if stats:
                        dynamic_with_stats.append((name, stats))
                
                dynamic_with_stats.sort(key=lambda x: x[1].get('r2', -1), reverse=True)
                
                f.write("Dynamic Approaches (ranked by R² Score):\n")
                for i, (name, stats) in enumerate(dynamic_with_stats, 1):
                    f.write(f"  {i}. {name}\n")
                    f.write(f"     R² Score: {stats.get('r2', 0):.4f}\n")
                    f.write(f"     RMSE: {stats.get('rmse', 0):.2f}m\n")
                    f.write(f"     Final Height: {stats.get('final_height', 0):.1f}m\n")
                    f.write(f"     Height at 200 years: {stats.get('height_at_200', 0):.1f}m\n\n")
            
            # Overall conclusions
            f.write("CONCLUSIONS:\n")
            f.write("-" * 15 + "\n")
            
            best_stats = results.get('statistics', {})
            if 'best_approaches' in best_stats:
                best = best_stats['best_approaches']
                f.write(f"Best Overall Approach: {best.get('best_overall', 'N/A')}\n")
                f.write(f"Best Static Approach: {best.get('best_static', 'N/A')}\n")
                f.write(f"Best Dynamic Approach: {best.get('best_dynamic', 'N/A')}\n\n")
                
                if 'best_overall_stats' in best_stats:
                    stats = best_stats['best_overall_stats']
                    f.write(f"Best Overall Performance:\n")
                    f.write(f"  R² Score: {stats.get('r2', 0):.4f}\n")
                    f.write(f"  RMSE: {stats.get('rmse', 0):.2f}m\n")
                    f.write(f"  Final Height: {stats.get('final_height', 0):.1f}m\n")
                    f.write(f"  Target Final Height: 50.0m\n")
                    f.write(f"  Height Difference: {abs(stats.get('final_height', 0) - 50.0):.1f}m\n\n")
            
            f.write("FILES GENERATED:\n")
            f.write("-" * 20 + "\n")
            f.write("  - fir_analysis_results.json (detailed results)\n")
            f.write("  - fir_comprehensive_analysis.png (main plots)\n")
            f.write("  - parameter_optimization_heatmap.png (parameter analysis)\n")
            f.write("  - fir_analysis_summary.txt (this report)\n\n")
            
            f.write("=" * 80 + "\n")
        
        logger.info(f"Summary report saved to: {report_path}")

    def run_complete_analysis(self):
        """Run the complete Fir height analysis."""
        logger.info("Starting complete Fir height analysis...")
        logger.info(f"Output directory: {self.output_dir}")
        
        try:
            # Test static parameter combinations
            logger.info("Phase 1: Testing static parameter combinations...")
            self.test_static_parameters()
            
            # Test dynamic approaches
            logger.info("Phase 2: Testing dynamic growth approaches...")
            self.test_dynamic_approaches()
            
            # Create visualizations
            logger.info("Phase 3: Creating visualizations...")
            self.create_comprehensive_plots()
            
            # Save results
            logger.info("Phase 4: Saving analysis results...")
            self.save_analysis_results()
            
            logger.info("Complete Fir height analysis finished successfully!")
            logger.info(f"Results saved to: {self.output_dir}")
            
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            raise


def main():
    """Main function for command line usage."""
    parser = argparse.ArgumentParser(
        description="Advanced Fir height growth analysis for The Grove 2.2",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
This tool performs comprehensive analysis of Fir tree height growth patterns by:
1. Testing different static parameter combinations
2. Implementing dynamic property updates during growth
3. Comparing results against real-world Fir growth data
4. Generating detailed visualizations and analysis reports

The goal is to achieve realistic growth curves that start steep and gradually
flatten but continue growing, rather than linear growth followed by sudden stop.

Examples:
    # Run complete analysis with default settings
    python src/growpy/utils/04_fir_height_analysis.py
    
    # Run with custom output directory and more cycles
    python src/growpy/utils/04_fir_height_analysis.py --cycles 250 --output_dir data/fir_extended
    
    # Run with verbose logging
    python src/growpy/utils/04_fir_height_analysis.py --verbose
        """
    )
    
    # Get script directory for default paths
    script_dir = Path(__file__).parent.parent.parent.parent  # Go up to project root
    
    parser.add_argument(
        "--assets_dir",
        type=Path,
        default=script_dir / "data" / "assets",
        help="Directory containing prepared GrowPy assets (default: data/assets)"
    )
    parser.add_argument(
        "--output_dir",
        type=Path,
        default=script_dir / "data" / "fir_analysis",
        help="Directory to save analysis results (default: data/fir_analysis)"
    )
    parser.add_argument(
        "--cycles",
        type=int,
        default=200,
        help="Maximum number of growth cycles to simulate (default: 200)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )
    
    args = parser.parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        # Keep matplotlib logging suppressed even in verbose mode
        logging.getLogger("matplotlib").setLevel(logging.WARNING)
        logging.getLogger("matplotlib.font_manager").setLevel(logging.WARNING)
    
    logger.info("Advanced Fir Height Growth Analysis")
    logger.info("=" * 50)
    logger.info(f"Assets directory: {args.assets_dir}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Maximum cycles: {args.cycles}")
    
    # Check assets directory
    if not args.assets_dir.exists():
        logger.error(f"Assets directory not found: {args.assets_dir}")
        logger.error("Please run prepare_assets.py first to copy assets from Grove installation")
        sys.exit(1)
    
    # Check for Fir preset
    fir_preset_path = args.assets_dir / "presets" / "Pinaceae - Fir.seed.json"
    if not fir_preset_path.exists():
        logger.error(f"Fir preset not found: {fir_preset_path}")
        logger.error("Please ensure the Fir preset is available in the assets directory")
        sys.exit(1)
    
    try:
        # Create analyzer and run complete analysis
        analyzer = FirHeightAnalyzer(
            assets_dir=args.assets_dir,
            output_dir=args.output_dir,
            max_cycles=args.cycles
        )
        
        analyzer.run_complete_analysis()
        
        logger.info("\nAnalysis completed successfully!")
        logger.info(f"Check the results in: {args.output_dir}")
        
    except Exception as e:
        logger.error(f"Analysis failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
