"""
Species mapping and asset assignment module.

This module provides functionality to map species to their appropriate
model templates, twig assets, and bark textures using a centralized lookup table.
Includes fallback logic for species missing specific assets.
"""

import logging
from pathlib import Path
from typing import Dict, List, Optional, NamedTuple
import pandas as pd

logger = logging.getLogger(__name__)


class SpeciesAssets(NamedTuple):
    """Asset mapping for a species."""
    common_name: str
    scientific_name: str
    model_template: str  # .seed.json file
    twig_name: Optional[str]  # Twig directory name, None if no twig
    bark_texture: str  # Bark texture file


class SpeciesMapper:
    """
    Manages species-to-asset mappings with fallback logic.
    
    Loads a CSV lookup table that maps species to their model templates,
    twig assets, and bark textures. Provides fallback assignments for
    species that lack specific assets.
    """
    
    def __init__(self, lookup_table_path: Optional[Path] = None):
        """
        Initialize the species mapper.
        
        Args:
            lookup_table_path: Path to the CSV lookup table. If None, uses default location.
        """
        if lookup_table_path is None:
            # Default lookup table location
            lookup_table_path = Path(__file__).parent.parent.parent.parent / "data" / "CommonName-ScientificName-Model-Twig-BarkTexture.csv"
        
        self.lookup_table_path = Path(lookup_table_path)
        self._species_map: Dict[str, SpeciesAssets] = {}
        self._common_name_map: Dict[str, str] = {}  # common name -> scientific name
        self._load_lookup_table()
    
    def _load_lookup_table(self) -> None:
        """Load the species lookup table from CSV."""
        if not self.lookup_table_path.exists():
            logger.warning(f"Species lookup table not found: {self.lookup_table_path}")
            return
        
        try:
            df = pd.read_csv(self.lookup_table_path)
            logger.info(f"Loading species mapping from {self.lookup_table_path}")
            
            for _, row in df.iterrows():
                common_name = row["Common Name"].strip()
                scientific_name = row["Scientific Name"].strip()
                model = row["Model"].strip()
                twig = row["Twig"].strip() if row["Twig"].strip() != "—" else None
                bark = row["Bark Texture"].strip()
                
                assets = SpeciesAssets(
                    common_name=common_name,
                    scientific_name=scientific_name,
                    model_template=model,
                    twig_name=twig,
                    bark_texture=bark
                )
                
                # Map by scientific name (primary key)
                self._species_map[scientific_name] = assets
                
                # Also map by common name for convenience
                self._common_name_map[common_name.lower()] = scientific_name
                
            logger.info(f"Loaded {len(self._species_map)} species mappings")
            
        except Exception as e:
            logger.error(f"Failed to load species lookup table: {e}")
            raise
    
    def get_species_assets(self, species_identifier: str) -> Optional[SpeciesAssets]:
        """
        Get asset mapping for a species.
        
        Args:
            species_identifier: Species name (scientific or common name)
            
        Returns:
            SpeciesAssets if found, None otherwise
        """
        # Try direct scientific name lookup first
        if species_identifier in self._species_map:
            return self._species_map[species_identifier]
        
        # Try common name lookup
        scientific_name = self._common_name_map.get(species_identifier.lower())
        if scientific_name:
            return self._species_map[scientific_name]
        
        return None
    
    def get_model_template(self, species_identifier: str) -> Optional[str]:
        """Get the model template (.seed.json) for a species."""
        assets = self.get_species_assets(species_identifier)
        return assets.model_template if assets else None
    
    def get_twig_name(self, species_identifier: str) -> Optional[str]:
        """Get the twig directory name for a species."""
        assets = self.get_species_assets(species_identifier)
        return assets.twig_name if assets else None
    
    def get_bark_texture(self, species_identifier: str) -> Optional[str]:
        """Get the bark texture file for a species."""
        assets = self.get_species_assets(species_identifier)
        return assets.bark_texture if assets else None
    
    def find_species_by_model(self, model_template: str) -> List[str]:
        """Find all species that use a specific model template."""
        return [
            scientific_name for scientific_name, assets in self._species_map.items()
            if assets.model_template == model_template
        ]
    
    def find_species_by_twig(self, twig_name: str) -> List[str]:
        """Find all species that use a specific twig."""
        return [
            scientific_name for scientific_name, assets in self._species_map.items()
            if assets.twig_name == twig_name
        ]
    
    def get_species_with_missing_twigs(self) -> List[str]:
        """Get list of species that have no twig assigned."""
        return [
            scientific_name for scientific_name, assets in self._species_map.items()
            if assets.twig_name is None
        ]
    
    def get_fallback_twig(self, species_identifier: str) -> Optional[str]:
        """
        Get a fallback twig for species without assigned twigs.
        
        This uses simple heuristics based on family or growth form.
        You can extend this logic as needed.
        """
        assets = self.get_species_assets(species_identifier)
        if not assets or assets.twig_name is not None:
            return assets.twig_name if assets else None
        
        # Simple fallback logic based on family patterns
        model_template = assets.model_template.lower()
        
        if "fagaceae" in model_template:  # Oak family
            return "EuropeanOakTwig"
        elif "pinaceae" in model_template:  # Pine family
            return "ScotsPineTwig"
        elif "betulaceae" in model_template:  # Birch family
            return "PaperBirchTwig"
        elif "salicaceae" in model_template:  # Willow family
            return "WhiteWillowTwig"
        elif "rosaceae" in model_template:  # Rose family
            return "WildAppleTwig"
        else:
            # Generic deciduous fallback
            return "EuropeanOakTwig"
    
    def list_all_species(self) -> List[str]:
        """Get list of all species (scientific names) in the lookup table."""
        return list(self._species_map.keys())
    
    def list_all_models(self) -> List[str]:
        """Get list of all unique model templates."""
        return list(set(assets.model_template for assets in self._species_map.values()))
    
    def list_all_twigs(self) -> List[str]:
        """Get list of all unique twig names (excluding None)."""
        return list(set(
            assets.twig_name for assets in self._species_map.values() 
            if assets.twig_name is not None
        ))
    
    def validate_assets(self, grove_path: Path, twigs_path: Path, textures_path: Path) -> Dict[str, List[str]]:
        """
        Validate that all referenced assets exist.
        
        Returns:
            Dictionary with 'missing_models', 'missing_twigs', 'missing_textures' lists
        """
        missing = {
            'missing_models': [],
            'missing_twigs': [],
            'missing_textures': []
        }
        
        presets_path = grove_path / "presets"
        
        for scientific_name, assets in self._species_map.items():
            # Check model template
            model_path = presets_path / assets.model_template
            if not model_path.exists():
                missing['missing_models'].append(f"{scientific_name}: {assets.model_template}")
            
            # Check twig (if assigned)
            if assets.twig_name:
                twig_path = twigs_path / assets.twig_name
                if not twig_path.exists():
                    missing['missing_twigs'].append(f"{scientific_name}: {assets.twig_name}")
            
            # Check bark texture (if textures_path provided)
            if textures_path:
                bark_path = textures_path / assets.bark_texture
                if not bark_path.exists():
                    missing['missing_textures'].append(f"{scientific_name}: {assets.bark_texture}")
        
        return missing


# Global instance for easy access
_default_mapper = None

def get_species_mapper(lookup_table_path: Optional[Path] = None) -> SpeciesMapper:
    """Get the default species mapper instance."""
    global _default_mapper
    if _default_mapper is None or lookup_table_path is not None:
        _default_mapper = SpeciesMapper(lookup_table_path)
    return _default_mapper


# Convenience functions for backward compatibility
def get_species_assets(species_identifier: str) -> Optional[SpeciesAssets]:
    """Get asset mapping for a species using the default mapper."""
    return get_species_mapper().get_species_assets(species_identifier)

def get_model_template(species_identifier: str) -> Optional[str]:
    """Get the model template for a species using the default mapper."""
    return get_species_mapper().get_model_template(species_identifier)

def get_twig_name(species_identifier: str) -> Optional[str]:
    """Get the twig name for a species using the default mapper."""
    return get_species_mapper().get_twig_name(species_identifier)

def get_bark_texture(species_identifier: str) -> Optional[str]:
    """Get the bark texture for a species using the default mapper."""
    return get_species_mapper().get_bark_texture(species_identifier)