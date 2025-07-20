"""
Grove JSON input/output operations.
"""

import logging
from pathlib import Path
import the_grove_22_core as gc

logger = logging.getLogger(__name__)


def save_grove_json(grove: gc.Grove, file_path: Path, species_name: str = None, 
                   tree_count: int = None) -> None:
    """
    Save grove as JSON file.
    
    Args:
        grove: Grove object to save
        file_path: Path to save JSON file
        species_name: Optional species name for metadata
        tree_count: Optional tree count for metadata
    """
    # Ensure directory exists
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        # Create the JSON string
        json_string = gc.io.grove_to_json_string(grove)
        
        # Save to file
        with open(file_path, 'w') as f:
            f.write(json_string)
        
        logger.info(f"Saved grove to {file_path}")
        
        if species_name and tree_count:
            logger.debug(f"Grove contains {tree_count} {species_name} trees")
            
    except Exception as e:
        raise ValueError(f"Failed to save grove JSON: {e}")


def load_grove_json(file_path: Path) -> gc.Grove:
    """
    Load grove from JSON file.
    
    Args:
        file_path: Path to JSON file
        
    Returns:
        Grove object
        
    Raises:
        FileNotFoundError: If file doesn't exist
        ValueError: If file is invalid
    """
    if not file_path.exists():
        raise FileNotFoundError(f"Grove JSON file not found: {file_path}")
    
    try:
        with open(file_path, 'r') as f:
            json_string = f.read()
        
        grove = gc.io.grove_from_json_string(json_string)
        logger.info(f"Loaded grove from {file_path}")
        
        return grove
        
    except Exception as e:
        raise ValueError(f"Failed to load grove JSON: {e}")


def save_multiple_groves(groves_data: list, output_dir: Path) -> list:
    """
    Save multiple groves to JSON files.
    
    Args:
        groves_data: List of (grove, species_name, tree_count) tuples
        output_dir: Directory to save files
        
    Returns:
        List of saved file paths
    """
    saved_files = []
    
    for grove, species_name, tree_count in groves_data:
        # Create filename
        safe_species_name = species_name.replace(" ", "_").replace("_-_", "_")
        filename = f"{safe_species_name}_grove.json"
        file_path = output_dir / filename
        
        # Save grove
        save_grove_json(grove, file_path, species_name, tree_count)
        saved_files.append(file_path)
    
    return saved_files