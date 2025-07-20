"""
Model export workflows.
"""

import logging
from pathlib import Path
from typing import List, Dict, Any
from tqdm import tqdm

from ..io.grove_io import save_multiple_groves
from ..io.model_io import save_lod_models
from ..config import GrowPyConfig

logger = logging.getLogger(__name__)


def export_grove_jsons(forest_data: list, output_dir: Path, input_name: str = "forest") -> List[Path]:
    """
    Export forest groves as JSON files.
    
    Args:
        forest_data: List of (grove, species_name, tree_count) tuples
        output_dir: Directory to save files
        input_name: Name for output subdirectory
        
    Returns:
        List of saved file paths
    """
    # Create output directory
    grove_dir = output_dir / input_name / "groves"
    grove_dir.mkdir(parents=True, exist_ok=True)
    
    # Save groves
    saved_files = save_multiple_groves(forest_data, grove_dir)
    
    logger.info(f"Exported {len(saved_files)} grove JSON files to {grove_dir}")
    return saved_files


def export_individual_models(forest_data: list, output_dir: Path, 
                           lod_configs: Dict[str, Dict[str, Any]] = None,
                           format: str = "obj", input_name: str = "forest") -> List[Path]:
    """
    Export individual tree models with LOD levels.
    
    Args:
        forest_data: List of (grove, species_name, tree_count) tuples
        output_dir: Directory to save model files
        lod_configs: LOD configurations (uses defaults if None)
        format: Model format ('obj' or 'usd')
        input_name: Name for output subdirectory
        
    Returns:
        List of saved file paths
    """
    if lod_configs is None:
        lod_configs = GrowPyConfig.get_lod_configs()
    
    # Create output directory
    models_dir = output_dir / input_name / "tree_models"
    models_dir.mkdir(parents=True, exist_ok=True)
    
    all_saved_files = []
    
    for grove, species_name, tree_count in tqdm(forest_data, desc="Exporting models", unit="species"):
        # Save LOD models for this species
        saved_files = save_lod_models(grove, species_name, models_dir, lod_configs, format)
        all_saved_files.extend(saved_files)
    
    logger.info(f"Exported {len(all_saved_files)} model files to {models_dir}")
    return all_saved_files


def export_selected_lod_models(forest_data: list, output_dir: Path,
                              lod_levels: List[str], format: str = "obj",
                              input_name: str = "forest") -> List[Path]:
    """
    Export models for selected LOD levels only.
    
    Args:
        forest_data: List of (grove, species_name, tree_count) tuples
        output_dir: Directory to save model files
        lod_levels: List of LOD level names to export
        format: Model format ('obj' or 'usd')
        input_name: Name for output subdirectory
        
    Returns:
        List of saved file paths
    """
    # Get all LOD configs and filter by selected levels
    all_lod_configs = GrowPyConfig.get_lod_configs()
    selected_lod_configs = {lod: all_lod_configs[lod] for lod in lod_levels if lod in all_lod_configs}
    
    if not selected_lod_configs:
        raise ValueError(f"No valid LOD levels found in: {lod_levels}")
    
    return export_individual_models(forest_data, output_dir, selected_lod_configs, format, input_name)