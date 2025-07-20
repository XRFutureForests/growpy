"""Species utilities with integrated mapping support."""

import logging
from pathlib import Path
from typing import List, Optional
import the_grove_22_core as gc

logger = logging.getLogger(__name__)

# Grove paths
DEFAULT_GROVE_PATH = Path(__file__).parent.parent.parent / "the_grove_22"
DEFAULT_PRESETS_PATH = DEFAULT_GROVE_PATH / "presets"


def list_species() -> List[str]:
    """Get list of available tree species."""
    species = []
    for preset_file in DEFAULT_PRESETS_PATH.glob("*.seed.json"):
        species_name = preset_file.stem[:-5]  # Remove .seed extension
        if species_name and not species_name.startswith("."):
            species.append(species_name)
    return sorted(species)


def apply_species_preset(grove: gc.Grove, species: str, use_mapping: bool = True) -> str:
    """
    Apply species preset to Grove with optional mapping lookup.

    Args:
        grove: Grove object
        species: Species name (scientific, common, or preset name)
        use_mapping: Whether to use species mapping for resolution
        
    Returns:
        The actual preset file name that was applied
        
    Raises:
        FileNotFoundError: If no suitable preset is found
    """
    preset_name = species
    
    if use_mapping:
        # Try to resolve species through mapping system
        try:
            from .mapping import get_model_template
            mapped_template = get_model_template(species)
            if mapped_template:
                preset_name = mapped_template
                logger.info(f"Mapped species '{species}' to template '{preset_name}'")
        except ImportError:
            logger.warning("Mapping module not available, using direct species name")
    
    # Remove .seed.json if already included
    if preset_name.endswith('.seed.json'):
        preset_name = preset_name[:-10]
    
    preset_path = DEFAULT_PRESETS_PATH / f"{preset_name}.seed.json"
    
    if not preset_path.exists():
        # Fallback: try the original species name if mapping failed
        if preset_name != species:
            fallback_path = DEFAULT_PRESETS_PATH / f"{species}.seed.json"
            if fallback_path.exists():
                preset_path = fallback_path
                preset_name = species
                logger.info(f"Using fallback preset '{species}' for '{species}'")
            else:
                raise FileNotFoundError(f"Species preset not found: {species} (tried '{preset_name}' and '{species}')")
        else:
            raise FileNotFoundError(f"Species preset not found: {species}")

    try:
        with open(preset_path, "r") as f:
            preset_json = f.read()

        properties = gc.io.properties_from_json_string(preset_json)
        grove.set_properties(properties)
        
        logger.debug(f"Applied species preset: {preset_path.name}")
        return preset_path.name
        
    except Exception as e:
        raise RuntimeError(f"Failed to apply species preset '{preset_path.name}': {e}")


def get_species_preset_path(species: str) -> Path:
    """Get path to species preset file."""
    return DEFAULT_PRESETS_PATH / f"{species}.seed.json"


def validate_species_name(species: str, use_mapping: bool = True) -> bool:
    """
    Validate that species name exists in presets or mapping table.
    
    Args:
        species: Species name to validate
        use_mapping: Whether to check mapping table as well as direct presets
        
    Returns:
        True if species can be resolved to a valid preset
    """
    # Check direct preset match first
    if species in list_species():
        return True
    
    if use_mapping:
        try:
            from .mapping import get_model_template
            return get_model_template(species) is not None
        except ImportError:
            pass
    
    return False


def resolve_species_name(species: str, use_mapping: bool = True) -> Optional[str]:
    """
    Resolve species name to actual preset file name.
    
    Args:
        species: Species name (scientific, common, or preset name)
        use_mapping: Whether to use mapping table for resolution
        
    Returns:
        Preset file name (without .seed.json) if found, None otherwise
    """
    # Try direct preset match first
    if species in list_species():
        return species
    
    if use_mapping:
        try:
            from .mapping import get_model_template
            mapped_template = get_model_template(species)
            if mapped_template:
                # Remove .seed.json extension if present
                if mapped_template.endswith('.seed.json'):
                    return mapped_template[:-10]
                return mapped_template
        except ImportError:
            pass
    
    return None


def list_mapped_species() -> List[str]:
    """
    Get list of all species available through the mapping system.
    
    Returns:
        List of scientific names from the mapping table
    """
    try:
        from .mapping import get_species_mapper
        mapper = get_species_mapper()
        return mapper.list_all_species()
    except ImportError:
        logger.warning("Mapping system not available")
        return []


def get_species_info(species: str) -> Optional[dict]:
    """
    Get comprehensive information about a species.
    
    Args:
        species: Species name
        
    Returns:
        Dictionary with species information or None if not found
    """
    try:
        from .mapping import get_species_assets
        assets = get_species_assets(species)
        if assets:
            return {
                'common_name': assets.common_name,
                'scientific_name': assets.scientific_name,
                'model_template': assets.model_template,
                'twig_name': assets.twig_name,
                'bark_texture': assets.bark_texture,
                'has_twig': assets.twig_name is not None,
                'preset_exists': validate_species_name(assets.model_template, use_mapping=False)
            }
    except ImportError:
        pass
    
    # Fallback for direct preset lookup
    if validate_species_name(species, use_mapping=False):
        return {
            'species_name': species,
            'model_template': f"{species}.seed.json",
            'preset_exists': True
        }
    
    return None