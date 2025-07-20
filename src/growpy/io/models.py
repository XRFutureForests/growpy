"""
3D model input/output operations.
"""

import logging
from pathlib import Path
from typing import Dict, List, Any
import the_grove_22_core as gc

logger = logging.getLogger(__name__)


def save_model(model, file_path: Path, format: str = "obj") -> None:
    """
    Save 3D model to file.
    
    Args:
        model: Grove model object
        file_path: Path to save model file
        format: File format ('obj' or 'usd')
        
    Raises:
        ValueError: If format is not supported
    """
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        if format.lower() == "obj":
            model_string = gc.io.model_to_obj_string(model)
        elif format.lower() == "usd":
            model_string = gc.io.model_to_usda_string(model)
        else:
            raise ValueError(f"Unsupported format: {format}")
        
        with open(file_path, 'w') as f:
            f.write(model_string)
        
        logger.info(f"Saved model to {file_path}")
        
    except Exception as e:
        raise ValueError(f"Failed to save model: {e}")


def save_multiple_models(models: List, file_paths: List[Path], 
                        format: str = "obj") -> List[Path]:
    """
    Save multiple models to files.
    
    Args:
        models: List of Grove model objects
        file_paths: List of file paths
        format: File format ('obj' or 'usd')
        
    Returns:
        List of saved file paths
    """
    if len(models) != len(file_paths):
        raise ValueError("Number of models must match number of file paths")
    
    saved_files = []
    
    for model, file_path in zip(models, file_paths):
        save_model(model, file_path, format)
        saved_files.append(file_path)
    
    return saved_files


def save_lod_models(grove: gc.Grove, species_name: str, output_dir: Path,
                   lod_configs: Dict[str, Dict[str, Any]], format: str = "obj") -> List[Path]:
    """
    Save models for all LOD levels.
    
    Args:
        grove: Grove object
        species_name: Species name for file naming
        output_dir: Directory to save models
        lod_configs: Dictionary of LOD configurations
        format: File format ('obj' or 'usd')
        
    Returns:
        List of saved file paths
    """
    saved_files = []
    safe_species_name = species_name.replace(" ", "_").replace("_-_", "_")
    
    # Create species directory
    species_dir = output_dir / safe_species_name
    species_dir.mkdir(parents=True, exist_ok=True)
    
    for lod_name, lod_settings in lod_configs.items():
        # Build models for this LOD level
        models = grove.build_models(lod_settings)
        
        # Save each model
        for tree_index, model in enumerate(models):
            filename = f"{safe_species_name}_tree_{tree_index:03d}_{lod_name}.{format}"
            file_path = species_dir / filename
            
            save_model(model, file_path, format)
            saved_files.append(file_path)
    
    return saved_files


def load_model_data(file_path: Path) -> str:
    """
    Load model data from file.
    
    Args:
        file_path: Path to model file
        
    Returns:
        Model data as string
        
    Raises:
        FileNotFoundError: If file doesn't exist
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Model file not found: {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            data = f.read()
        
        logger.info(f"Loaded model data from {file_path}")
        return data
        
    except Exception as e:
        raise ValueError(f"Failed to load model data: {e}")