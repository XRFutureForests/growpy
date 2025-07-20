"""
Height analysis and modeling workflows.
"""

import logging
from pathlib import Path
from typing import List, Dict
import pandas as pd
import pickle

from ..core.height import generate_height_curves_for_species
from ..core.prediction import create_species_prediction_models
from ..config import GrowPyConfig

logger = logging.getLogger(__name__)


def analyze_species_heights(species_list: List[str], config: GrowPyConfig = None,
                           output_dir: Path = None) -> Dict[str, List[float]]:
    """
    Analyze height growth curves for multiple species.
    
    Args:
        species_list: List of species names
        config: Configuration object
        output_dir: Directory to save results (optional)
        
    Returns:
        Dictionary mapping species to height curves
    """
    if config is None:
        config = GrowPyConfig()
    
    logger.info(f"Analyzing height curves for {len(species_list)} species")
    
    # Generate height curves
    height_curves = generate_height_curves_for_species(
        species_list, config.height_model_cycles, config.random_seed
    )
    
    # Save results if output directory provided
    if output_dir:
        _save_height_curves(height_curves, output_dir)
    
    return height_curves


def create_height_models(height_curves: Dict[str, List[float]], 
                        output_dir: Path = None) -> Dict:
    """
    Create prediction models from height curves.
    
    Args:
        height_curves: Dictionary mapping species to height curves
        output_dir: Directory to save models (optional)
        
    Returns:
        Dictionary of trained prediction models
    """
    logger.info(f"Creating prediction models for {len(height_curves)} species")
    
    # Create models
    models = create_species_prediction_models(height_curves)
    
    # Save models if output directory provided
    if output_dir:
        _save_prediction_models(models, output_dir)
    
    return models


def load_height_models(models_dir: Path) -> Dict:
    """
    Load prediction models from directory.
    
    Args:
        models_dir: Directory containing saved models
        
    Returns:
        Dictionary of loaded models
    """
    models_file = models_dir / "height_models.pkl"
    
    if not models_file.exists():
        raise FileNotFoundError(f"Models file not found: {models_file}")
    
    try:
        with open(models_file, 'rb') as f:
            models = pickle.load(f)
        
        logger.info(f"Loaded {len(models)} height models from {models_file}")
        return models
        
    except Exception as e:
        raise ValueError(f"Failed to load models: {e}")


def _save_height_curves(height_curves: Dict[str, List[float]], output_dir: Path) -> None:
    """Save height curves to CSV file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Convert to DataFrame
    max_length = max(len(curve) for curve in height_curves.values())
    curves_data = {}
    
    for species, curve in height_curves.items():
        # Pad curve to max length
        padded_curve = curve + [None] * (max_length - len(curve))
        curves_data[species] = padded_curve
    
    df = pd.DataFrame(curves_data)
    df.index.name = "cycle"
    
    # Save to CSV
    curves_file = output_dir / "height_curves.csv"
    df.to_csv(curves_file)
    
    logger.info(f"Saved height curves to {curves_file}")


def _save_prediction_models(models: Dict, output_dir: Path) -> None:
    """Save prediction models to file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    models_file = output_dir / "height_models.pkl"
    
    try:
        with open(models_file, 'wb') as f:
            pickle.dump(models, f)
        
        logger.info(f"Saved {len(models)} prediction models to {models_file}")
        
    except Exception as e:
        raise ValueError(f"Failed to save models: {e}")