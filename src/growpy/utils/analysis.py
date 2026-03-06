"""Species growth analysis for The Grove 2.3 species presets.

This module provides the SpeciesGrowthAnalyzer class for generating height curves
and growth prediction models from Grove species presets.
"""

import json
import logging
import multiprocessing as mp
import pickle
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm


class SimpleLinearModel:
    """Linear regression using numpy polyfit (avoids sklearn BLAS conflicts)."""

    def __init__(self):
        self.coefficients = None

    def fit(self, X, y):
        self.coefficients = np.polyfit(np.asarray(X).flatten(), np.asarray(y), deg=1)
        return self

    def predict(self, X):
        return np.polyval(self.coefficients, np.asarray(X).flatten())


# Add src to path for Grove imports
src_path = Path(__file__).parent.parent.parent
sys.path.insert(0, str(src_path))
sys.path.insert(0, str(src_path / "the_grove_23" / "modules"))

import the_grove_23_core as gc

from .plotting import plot_growth_curves

# Set up logging
logger = logging.getLogger(__name__)


def _process_single_species_for_parallel(args_tuple):
    """Process a single species in a parallel worker.

    This function is designed to be called by multiprocessing workers.
    It takes a tuple of arguments to work around multiprocessing limitations.

    Args:
        args_tuple: Tuple of (species, assets_dir, height_model_flushes, num_seeds,
                              height_growth_threshold, max_cycles_without_growth, timeout_seconds)

    Returns:
        Tuple of (species, success, results_dict, error_message)
    """
    (
        species,
        assets_dir,
        height_model_flushes,
        num_seeds,
        height_growth_threshold,
        max_cycles_without_growth,
        timeout_seconds,
    ) = args_tuple

    try:
        # Create a temporary analyzer instance for this species
        analyzer = SpeciesGrowthAnalyzer(
            assets_dir,
            height_model_flushes,
            num_seeds,
            height_growth_threshold,
            max_cycles_without_growth,
            timeout_seconds,
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
        timeout_seconds: int = 60,
    ):
        """Initialize the growth analyzer.

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
        self.height_curves = {}
        self.dbh_curves = {}
        self.growth_models = {}
        self.analysis_metadata = {}

    def apply_species_preset(self, grove, species: str) -> bool:
        """Apply a species preset to a grove using direct file loading.

        Automatically sets drop_decay=0.0 to prevent trees from dying off
        during long growth simulations (around 100+ cycles).

        Args:
            grove: Grove object to apply preset to
            species: Species name (e.g., "Fagaceae - European oak")

        Returns:
            True if successful, False otherwise
        """
        try:
            preset_file = self.presets_dir / f"{species}.seed.json"
            if not preset_file.exists():
                logger.error(f"Preset file not found: {preset_file}")
                return False

            with open(preset_file, "r") as f:
                preset_data = json.load(f)

            # Override drop_decay to prevent trees from dying off at high cycle counts
            preset_data["drop_decay"] = 0.0

            preset_json = json.dumps(preset_data)
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
        """Get list of all available Grove species presets from preset files."""
        try:
            species_list = []
            preset_files = list(self.presets_dir.glob("*.json"))

            for preset_file in preset_files:
                if preset_file.name.startswith("."):
                    continue

                species_name = preset_file.stem
                if species_name.endswith(".seed"):
                    species_name = species_name[:-5]

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
        """Generate a safe folder name from species preset name.

        Args:
            species: Species name (e.g., "Fagaceae - European oak")

        Returns:
            Growth model name (e.g., "Fagaceae_European_oak")
        """
        safe_name = (
            species.replace(" - ", "_")
            .replace(" ", "_")
            .replace("/", "_")
            .replace("\\", "_")
        )
        safe_name = "".join(c for c in safe_name if c.isalnum() or c in "_-")

        if safe_name.startswith("."):
            safe_name = safe_name[1:]

        logger.debug(
            f"Generated growth model name '{safe_name}' for species '{species}'"
        )
        return safe_name

    def calculate_dbh_at_height(self, tree, target_height: float = 1.3) -> float:
        """Calculate diameter at breast height using linear interpolation.

        Finds the closest nodes below and above the target height and interpolates
        between them to get the exact diameter at the specified height.

        Args:
            tree: The Grove tree object
            target_height: Height at which to measure diameter (default 1.3m for DBH)

        Returns:
            Diameter at the specified height, or 0.0 if tree doesn't reach that height
        """
        if not hasattr(tree, "nodes") or not tree.nodes:
            return 0.0

        trunk_nodes = []
        for node in tree.nodes:
            if hasattr(node, "pos") and hasattr(node, "radius"):
                trunk_nodes.append({"height": node.pos.z, "radius": node.radius})

        if not trunk_nodes:
            return 0.0

        trunk_nodes.sort(key=lambda x: x["height"])
        max_height = trunk_nodes[-1]["height"]

        if max_height < target_height:
            return 0.0

        node_below = None
        node_above = None

        for trunk_node in trunk_nodes:
            if trunk_node["height"] <= target_height:
                node_below = trunk_node
            elif trunk_node["height"] > target_height and node_above is None:
                node_above = trunk_node
                break

        if node_below and node_below["height"] == target_height:
            return node_below["radius"] * 2.0

        if node_below is None:
            if trunk_nodes[0]["height"] >= target_height * 0.95:
                return trunk_nodes[0]["radius"] * 2.0
            else:
                return 0.0

        if node_above is None:
            return node_below["radius"] * 2.0

        height_ratio = (target_height - node_below["height"]) / (
            node_above["height"] - node_below["height"]
        )
        interpolated_radius = node_below["radius"] + height_ratio * (
            node_above["radius"] - node_below["radius"]
        )

        return interpolated_radius * 2.0

    def generate_height_curve_for_species(
        self, species: str
    ) -> Tuple[List[float], List[float], Dict[str, Any]]:
        """Generate height and DBH curves for a species with multiple seeds.

        Args:
            species: Species name

        Returns:
            Tuple of (averaged_height_curve, averaged_dbh_curve, metadata)
        """
        all_height_curves = []
        all_dbh_curves = []
        seed_metadata = []

        seeds_to_test = [1, 7, 13, 23, 42, 100, 111, 123, 666][: self.num_seeds]

        seed_progress = tqdm(
            seeds_to_test,
            desc=f"Testing seeds for {species[:25]}",
            leave=False,
            disable=False,
        )

        for seed in seed_progress:
            try:
                grove = gc.Grove()
                grove.clear_trees()
                grove.set_random_seed(seed)

                if not self.apply_species_preset(grove, species):
                    logger.error(
                        f"Failed to apply species preset for {species} with seed {seed}"
                    )
                    continue

            except Exception as e:
                logger.error(f"Failed to create grove with species {species}: {e}")
                continue

            grove.clear_trees()
            grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)

            heights_this_seed = []
            dbh_this_seed = []
            max_height_achieved = 0.0
            max_dbh_achieved = 0.0
            cycles_without_growth = 0
            simulation_start_time = time.time()

            for cycle in range(self.height_model_flushes):
                grove.simulate(1)

                elapsed_time = time.time() - simulation_start_time
                if elapsed_time > self.timeout_seconds:
                    logger.warning(
                        f"Species {species}, seed {seed}: Simulation timeout after "
                        f"{elapsed_time:.1f} seconds at cycle {cycle + 1}."
                    )
                    break

                current_height = 0.0
                current_dbh = 0.0
                previous_max_height = max_height_achieved

                if grove.trees and len(grove.trees) > 0:
                    tree = grove.trees[0]

                    def find_max_height_in_branch(branch):
                        local_max = 0.0
                        if hasattr(branch, "nodes") and branch.nodes:
                            for node in branch.nodes:
                                if hasattr(node, "pos") and node.pos.z > local_max:
                                    local_max = node.pos.z

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

                    current_height = find_max_height_in_branch(tree)
                    current_dbh = self.calculate_dbh_at_height(tree, target_height=1.3)

                    if current_height > max_height_achieved:
                        max_height_achieved = current_height

                    if current_dbh > max_dbh_achieved:
                        max_dbh_achieved = current_dbh

                    heights_this_seed.append(max_height_achieved)
                    dbh_this_seed.append(max_dbh_achieved)
                else:
                    heights_this_seed.append(max_height_achieved)
                    dbh_this_seed.append(max_dbh_achieved)

                height_increase = max_height_achieved - previous_max_height

                if height_increase < self.height_growth_threshold:
                    cycles_without_growth += 1
                    if cycle > 5:
                        logger.debug(
                            f"Species {species}, seed {seed}, cycle {cycle}: "
                            f"No significant growth ({height_increase:.4f})"
                        )
                else:
                    cycles_without_growth = 0

                if (
                    cycles_without_growth >= self.max_cycles_without_growth
                    and cycle > 10
                ):
                    logger.info(
                        f"Species {species}, seed {seed}: Height growth stopped after "
                        f"{cycle + 1} cycles (max height: {max_height_achieved:.3f})"
                    )
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

            seed_progress.set_postfix(seed=seed)

        if not all_height_curves:
            raise ValueError(f"No successful growth curves generated for {species}")

        max_heights = []
        max_dbhs = []
        max_cycles_achieved = (
            max(len(curve) for curve in all_height_curves) if all_height_curves else 0
        )

        for cycle in range(max_cycles_achieved):
            cycle_heights = [
                curve[cycle] for curve in all_height_curves if cycle < len(curve)
            ]
            cycle_dbhs = [
                curve[cycle] for curve in all_dbh_curves if cycle < len(curve)
            ]

            max_heights.append(max(cycle_heights) if cycle_heights else 0.0)
            max_dbhs.append(max(cycle_dbhs) if cycle_dbhs else 0.0)

        early_terminations = sum(
            1 for meta in seed_metadata if meta.get("early_termination", False)
        )
        timeouts = sum(
            1 for meta in seed_metadata if meta.get("timeout_occurred", False)
        )
        avg_actual_cycles = (
            sum(meta.get("actual_cycles", 0) for meta in seed_metadata)
            / len(seed_metadata)
            if seed_metadata
            else 0
        )
        avg_simulation_time = (
            sum(meta.get("simulation_time", 0) for meta in seed_metadata)
            / len(seed_metadata)
            if seed_metadata
            else 0
        )

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
                max(max_heights) / max_cycles_achieved
                if max_heights and max_cycles_achieved > 0
                else 0.0
            ),
            "dbh_growth_rate": (
                max(max_dbhs) / max_cycles_achieved
                if max_dbhs and max_cycles_achieved > 0
                else 0.0
            ),
            "height_curve": max_heights,
            "dbh_curve": max_dbhs,
            "individual_height_curves": all_height_curves,
            "individual_dbh_curves": all_dbh_curves,
            "seed_results": seed_metadata,
        }

        return max_heights, max_dbhs, metadata

    def create_growth_model_for_species(
        self, species: str, height_curve: List[float]
    ) -> SimpleLinearModel:
        """Create linear regression model to predict required cycles from target height.

        Args:
            species: Species name
            height_curve: List of heights per cycle

        Returns:
            Fitted SimpleLinearModel
        """
        if not height_curve:
            raise ValueError(f"Empty height curve for {species}")

        heights = np.array(height_curve).reshape(-1, 1)
        cycles = np.array(range(len(height_curve)))

        non_zero_mask = heights.flatten() > 0.01
        if np.any(non_zero_mask):
            heights = heights[non_zero_mask]
            cycles = cycles[non_zero_mask]

        if len(heights) < 2:
            raise ValueError(f"Insufficient growth data for {species}")

        model = SimpleLinearModel()
        model.fit(heights, cycles)

        return model

    def _analyze_single_species(self, species: str) -> bool:
        """Core analysis logic for a single species.

        Args:
            species: Species name to analyze

        Returns:
            True if successful, False otherwise
        """
        try:
            height_curve, dbh_curve, metadata = self.generate_height_curve_for_species(
                species
            )
            growth_model = self.create_growth_model_for_species(species, height_curve)

            self.height_curves[species] = height_curve
            self.dbh_curves[species] = dbh_curve
            self.growth_models[species] = growth_model
            self.analysis_metadata[species] = metadata

            self.save_species_results(species)
            return True

        except SystemExit as e:
            tqdm.write(
                f"FATAL: Grove module called sys.exit({e.code}) during {species}"
            )
            raise
        except Exception as e:
            logger.error(f"Failed to analyze species {species}: {e}")
            tqdm.write(f"ERROR analyzing {species}: {e}")
            import traceback

            traceback.print_exc()
            return False

    def analyze_all_species(
        self,
        parallel: bool = True,
        max_workers: Optional[int] = None,
        species_filter: Optional[list] = None,
    ) -> Dict[str, bool]:
        """Analyze all available species (sequential or parallel).

        Args:
            parallel: Whether to use parallel processing (default: True)
            max_workers: Maximum number of parallel workers (default: CPU count - 1)
            species_filter: Optional list of species to process (if None, processes all)

        Returns:
            Dictionary mapping species to success status
        """
        species_list = self.get_available_species()

        # Filter species if requested
        if species_filter:
            species_list = [s for s in species_list if s in species_filter]

        results = {}

        if parallel:
            return self._analyze_parallel(species_list, max_workers)
        else:
            return self._analyze_sequential(species_list)

    def _analyze_sequential(self, species_list: List[str]) -> Dict[str, bool]:
        """Analyze species sequentially.

        Args:
            species_list: List of species names to analyze

        Returns:
            Dictionary mapping species to success status
        """
        results = {}
        progress = tqdm(species_list, desc="Analyzing species (sequential)")

        for species in progress:
            progress.set_description(f"Analyzing: {species[:30]}...")
            results[species] = self._analyze_single_species(species)

            if not results[species]:
                tqdm.write(f"FAILED {species}")

        successful = sum(1 for success in results.values() if success)
        tqdm.write(f"\nAnalysis complete: {successful}/{len(species_list)} species")

        return results

    def _analyze_parallel(
        self, species_list: List[str], max_workers: Optional[int]
    ) -> Dict[str, bool]:
        """Analyze species in parallel.

        Args:
            species_list: List of species names to analyze
            max_workers: Maximum number of parallel workers

        Returns:
            Dictionary mapping species to success status
        """
        results = {}

        if max_workers is None:
            max_workers = max(1, mp.cpu_count() - 1)

        logger.info(
            f"Using {max_workers} parallel workers for {len(species_list)} species"
        )

        process_args = [
            (
                species,
                self.assets_dir,
                self.height_model_flushes,
                self.num_seeds,
                self.height_growth_threshold,
                self.max_cycles_without_growth,
                self.timeout_seconds,
            )
            for species in species_list
        ]

        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            future_to_species = {
                executor.submit(_process_single_species_for_parallel, args): args[0]
                for args in process_args
            }

            progress = tqdm(
                total=len(species_list),
                desc="Analyzing species (parallel)",
                unit="species",
            )

            for future in as_completed(future_to_species):
                species_name = future_to_species[future]

                try:
                    species, success, species_results, error_msg = future.result()

                    if success and species_results is not None:
                        self.height_curves[species] = species_results["height_curve"]
                        self.dbh_curves[species] = species_results["dbh_curve"]
                        self.growth_models[species] = species_results["growth_model"]
                        self.analysis_metadata[species] = species_results["metadata"]

                        self.save_species_results(species)
                        results[species] = True
                    else:
                        tqdm.write(f"FAILED {species}: {error_msg}")
                        results[species] = False

                except Exception as e:
                    tqdm.write(f"FAILED {species_name}: {e}")
                    results[species_name] = False

                progress.update(1)

            progress.close()

        successful = sum(1 for success in results.values() if success)
        tqdm.write(
            f"\nParallel analysis complete: {successful}/{len(species_list)} species"
        )

        return results

    def save_species_results(self, species: str):
        """Save results for a single species in its own subfolder.

        Args:
            species: Species name to save results for

        Returns:
            Path to the species output directory
        """
        growth_model_name = self.get_growth_model_name_for_species(species)
        species_dir = self.output_dir / growth_model_name
        species_dir.mkdir(parents=True, exist_ok=True)

        if species in self.height_curves:
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
            model_path = species_dir / "growth_model.pkl"
            with open(model_path, "wb") as f:
                pickle.dump(self.growth_models[species], f)

        if species in self.analysis_metadata:
            metadata_path = species_dir / "metadata.json"
            with open(metadata_path, "w") as f:
                json.dump(self.analysis_metadata[species], f, indent=2)

        try:
            plot_growth_curves(
                species,
                self.height_curves[species],
                self.dbh_curves[species],
                self.analysis_metadata[species],
                species_dir,
            )
        except Exception as e:
            tqdm.write(f"Warning: Failed to generate plots for {species}: {e}")

        return species_dir

    def save_growth_models(self):
        """Save growth models in species-specific subfolders."""
        tqdm.write("Saving individual species results...")
        saved_count = 0

        for species in tqdm(
            self.analysis_metadata.keys(), desc="Saving species", leave=False
        ):
            self.save_species_results(species)
            saved_count += 1

        tqdm.write(f"Saved {saved_count} species models to: {self.output_dir}")

    def update_lookup_table_with_new_models(self):
        """Update tree asset lookup table with new growth model names."""
        try:
            current_file = Path(__file__)
            package_config = (
                current_file.parent.parent / "config" / "tree_asset_lookup.csv"
            )
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
                    "Lookup table not found in src/growpy/config/, config/, or data/"
                )
                return

            df = pd.read_csv(lookup_table_path)
            updated_count = 0

            for species in self.analysis_metadata.keys():
                preset_name = f"{species}.seed.json"
                new_growth_model_name = self.get_growth_model_name_for_species(species)

                mask = df["Preset"] == preset_name
                if mask.any():
                    df.loc[mask, "Growth Model"] = new_growth_model_name
                    updated_count += 1

            if updated_count > 0:
                backup_path = lookup_table_path.with_suffix(".csv.backup")
                if not backup_path.exists():
                    df_original = pd.read_csv(lookup_table_path)
                    df_original.to_csv(backup_path, index=False)
                    logger.info(f"Created backup: {backup_path}")

                df.to_csv(lookup_table_path, index=False)
                logger.info(
                    f"Updated lookup table with {updated_count} new growth model names"
                )
            else:
                logger.warning("No updates were made to the lookup table")

        except Exception as e:
            logger.error(f"Failed to update lookup table: {e}")

    def generate_lookup_table_summary(self):
        """Generate a summary CSV of species analyzed and their growth models."""
        try:
            summary_path = self.output_dir / "species_analysis_summary.csv"
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

            summary_df = pd.DataFrame(summary_data)
            summary_df.to_csv(summary_path, index=False)

            logger.info(f"Generated species analysis summary: {summary_path}")
            logger.info(f"Summary contains {len(summary_data)} analyzed species")

        except Exception as e:
            logger.error(f"Failed to generate lookup table summary: {e}")


def compare_smoothing_effect(
    preset_path: Path,
    flushes: int = 2,
    smooth_iterations: int = 10,
    build_params: Optional[Dict[str, Any]] = None,
    sample_points: int = 100,
) -> Dict[str, Any]:
    """Compare mesh geometry with and without branch smoothing.

    Creates two identical groves — one smoothed, one unsmoothed — and reports
    differences in vertex count and maximum vertex displacement.

    Useful for validating that smoothing is working and quantifying its effect.

    Args:
        preset_path: Path to a seed.json species preset
        flushes: Number of growth cycles to simulate (default: 2)
        smooth_iterations: Number of smooth() calls to apply (default: 10)
        build_params: Build parameters dict passed to build_models()
        sample_points: Number of vertices to sample when comparing positions

    Returns:
        Dict with keys:
            points_before, points_after, faces_before, faces_after,
            vertices_changed, max_displacement, smoothing_active
    """
    if build_params is None:
        build_params = {}

    with open(preset_path, "r") as f:
        properties = gc.io.properties_from_json_string(f.read())

    def _make_grove() -> gc.Grove:
        grove = gc.Grove()
        grove.set_properties(properties)
        grove.add_new_tree(gc.Vector(0, 0, 0), gc.Vector(0, 0, 1), 0)
        grove.simulate(flushes)
        grove.weigh_and_bend()
        return grove

    grove_base = _make_grove()
    models_before = grove_base.build_models(build_params)
    pts_before = len(models_before[0].points) if models_before else 0
    faces_before = len(models_before[0].faces) if models_before else 0

    grove_smooth = _make_grove()
    for _ in range(smooth_iterations):
        grove_smooth.smooth()
    grove_smooth.weigh_and_bend()
    models_after = grove_smooth.build_models(build_params)
    pts_after = len(models_after[0].points) if models_after else 0
    faces_after = len(models_after[0].faces) if models_after else 0

    vertices_changed = 0
    max_displacement = 0.0

    if pts_before == pts_after and pts_before > 0:
        n = min(sample_points, pts_before)
        for i in range(n):
            pb = models_before[0].points[i]
            pa = models_after[0].points[i]
            dist = ((pa.x - pb.x) ** 2 + (pa.y - pb.y) ** 2 + (pa.z - pb.z) ** 2) ** 0.5
            if dist > 1e-4:
                vertices_changed += 1
                max_displacement = max(max_displacement, dist)

    result = {
        "points_before": pts_before,
        "points_after": pts_after,
        "faces_before": faces_before,
        "faces_after": faces_after,
        "vertices_changed": vertices_changed,
        "max_displacement": max_displacement,
        "smoothing_active": vertices_changed > 0,
    }

    logger.info(
        "Smoothing comparison: pts %d->%d, faces %d->%d, %d vertices moved (max %.4f)",
        pts_before,
        pts_after,
        faces_before,
        faces_after,
        vertices_changed,
        max_displacement,
    )
    return result
