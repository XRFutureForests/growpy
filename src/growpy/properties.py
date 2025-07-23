"""Advanced Grove properties management based on Blender addon insights."""

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from .config import get_config

# Platform-specific Grove core import with fallback
try:
    import the_grove_22_core as gc
except ImportError:
    gc = None


def create_properties_from_dict(properties_dict: Dict[str, Any]):
    """Create Grove properties object from dictionary.
    
    Args:
        properties_dict: Dictionary of property name-value pairs
        
    Returns:
        Grove Properties object
    """
    if gc is None:
        raise ImportError("Grove core not available")
        
    json_string = json.dumps(properties_dict)
    return gc.io.properties_from_json_string(json_string)


def get_default_properties() -> Dict[str, Any]:
    """Get default property values as found in the Blender addon.
    
    Returns:
        Dictionary with default property values
    """
    return {
        # Growth parameters
        'grow_nodes': 3,
        'grow_length': 0.3,
        
        # Branch addition
        'add_side_branches': 1,
        'add_chance': 1.0,
        'add_chance_reduce': 0.0,
        'add_bud_life': 1,
        'add_only_on_end': 0.0,
        'add_regenerate': 0.05,
        'add_fork': 0.0,
        'add_angle': 0.785398,  # 45 degrees in radians
        'add_up': 0.0,
        'add_horizontal': 0.0,
        'add_planar': 0.0,
        
        # Turning behavior
        'turn_to_light': 0.0,
        'turn_up': 0.2,
        'turn_up_in_shade': 0.0,
        'turn_to_horizon': 0.0,
        'turn_random': 0.087266,  # 5 degrees in radians
        
        # Growth favor
        'favor_end': 0.4,
        'favor_end_reduce': 0.0,
        'shade_avoidance': 0.0,
        'favor_bright': 0.8,
        'favor_rising': 0.0,
        'favor_dwindle': 1.0,
        'favor_thick': 0.0,
        'favor_squeeze': 0.0,
        
        # Branch dropping
        'drop_shaded': 0.3,
        'drop_weak': 0.1,
        'drop_obsolete': 0.1,
        'drop_decay': 0.4,
        
        # Thickness
        'thicken_tips': 0.007,
        'thicken_tips_reduce': 0.0,
        'thicken_join': 0.75,
        'thicken_deadwood': 0.0,
        'thicken_base_scale': 1.2,
        'thicken_base_buttress': 2.0,
        'thicken_base_shape': 0.1,
        'root_distribution': 0.4,
        
        # Bending physics
        'bend_mass': 1.0,
        'bend_twig_mass': 0.1,
        'bend_twig_mass_solidify': 1.0,
        'bend_reaction': 0.5,
        
        # Shading
        'shade_area': 8.0,
        'shade_area_reduce': 0.0,
        'shade_area_depth': 0.5,
        'shade_leaf_sides': False,
        'shade_branches': False,
        'shade_alongside': 2,
        'shade_alongside_diameter': 0.2,
        
        # Auto pruning
        'auto_prune_enabled': True,
        'auto_prune_low': 2.0,
        'auto_prune_keep_thick': 0.01,
        'auto_prune_dangling': 1.0,
        
        # Stake support
        'stake_enabled': False,
        'stake_height': 4.0,
        
        # Sow (seed dispersal)
        'sow_enabled': False,
        'sow_age': 10,
        'sow_chance': 0.2,
        'sow_distance': 8.0,
        'sow_limit': 50,
        
        # Simulation
        'simulation_scale': 1.0,
        
        # Environmental reactions
        'react_attract_strength': 0.3,
        'react_attract_falloff': 1.3,
        'react_deflect_strength': 0.3,
        'react_deflect_falloff': 1.3,
        
        # Surround
        'surround_enabled': False,
        'surround_grow': True,
        'surround_density': 0.7,
        'surround_distance': 7.0,
        'surround_height': 5.0,
        
        # Twigs
        'twig_longevity': 2,
        'twig_wither': 2,
        'twig_density': 0.2,
        'twig_side_on_tips': False,
        
        # Additional twist
        'add_twist': 0.1,
    }


def apply_scale_conversion(properties_dict: Dict[str, Any], simulation_scale: float) -> Dict[str, Any]:
    """Apply scale conversion to scale-dependent properties.
    
    Based on the Blender addon's property conversion system.
    
    Args:
        properties_dict: Dictionary of properties
        simulation_scale: Scale factor to apply
        
    Returns:
        Dictionary with scale-converted properties
    """
    scale_dependent_properties = ['auto_prune_low', 'auto_prune_dangling', 'stake_height']
    
    converted = properties_dict.copy()
    for prop in scale_dependent_properties:
        if prop in converted:
            converted[prop] = converted[prop] / simulation_scale
            
    return converted


def create_property_preset(grove, preset_name: str, save_path: Optional[Path] = None) -> Dict[str, Any]:
    """Create a property preset from a grove's current properties.
    
    Args:
        grove: Grove object
        preset_name: Name for the preset
        save_path: Optional path to save the preset file
        
    Returns:
        Dictionary containing the preset properties
    """
    if gc is None:
        raise ImportError("Grove core not available")
        
    properties = grove.get_properties()
    properties_string = gc.io.properties_to_json_string(properties)
    properties_dict = json.loads(properties_string)
    
    preset = {
        'name': preset_name,
        'properties': properties_dict
    }
    
    if save_path:
        save_path.parent.mkdir(parents=True, exist_ok=True)
        with open(save_path, 'w') as f:
            json.dump(preset, f, indent=2)
    
    return preset


def modify_grove_properties(grove, **property_changes) -> None:
    """Modify specific grove properties without affecting others.
    
    Args:
        grove: Grove object
        **property_changes: Keyword arguments of property names and new values
    """
    if gc is None:
        raise ImportError("Grove core not available")
        
    # Get current properties
    current_props = grove.get_properties()
    
    # Convert to dictionary for modification
    props_string = gc.io.properties_to_json_string(current_props)
    props_dict = json.loads(props_string)
    
    # Apply changes
    props_dict.update(property_changes)
    
    # Convert back and apply
    new_props = create_properties_from_dict(props_dict)
    grove.set_properties(new_props)


def get_core_property_names() -> List[str]:
    """Get list of all core property names that can be set on Grove.
    
    Based on the comprehensive list found in the Blender addon.
    
    Returns:
        List of property names
    """
    return [
        'simulation_scale',
        'add_angle',
        'add_chance',
        'add_only_on_end',
        'add_chance_reduce',
        'add_fork',
        'add_horizontal',
        'add_planar',
        'add_side_branches',
        'add_bud_life',
        'add_regenerate',
        'add_up',
        'add_twist',
        'auto_prune_enabled',
        'auto_prune_low',
        'auto_prune_keep_thick',
        'auto_prune_dangling',
        'bend_mass',
        'bend_twig_mass_solidify',
        'bend_twig_mass',
        'bend_reaction',
        'thicken_deadwood',
        'surround_enabled',
        'surround_grow',
        'surround_density',
        'surround_distance',
        'surround_height',
        'drop_weak',
        'drop_shaded',
        'drop_obsolete',
        'drop_decay',
        'favor_bright',
        'favor_end',
        'favor_end_reduce',
        'favor_rising',
        'favor_dwindle',
        'grow_length',
        'grow_nodes',
        'twig_longevity',
        'twig_density',
        'twig_wither',
        'twig_side_on_tips',
        'shade_area_depth',
        'shade_area',
        'shade_area_reduce',
        'shade_leaf_sides',
        'shade_branches',
        'shade_alongside',
        'shade_alongside_diameter',
        'thicken_join',
        'thicken_tips',
        'thicken_tips_reduce',
        'thicken_base_buttress',
        'thicken_base_scale',
        'thicken_base_shape',
        'turn_to_light',
        'turn_to_horizon',
        'turn_random',
        'turn_up',
        'turn_up_in_shade',
        'react_attract_strength',
        'react_attract_falloff',
        'react_deflect_strength',
        'react_deflect_falloff',
        'stake_enabled',
        'stake_height',
        'sow_enabled',
        'sow_age',
        'sow_chance',
        'sow_distance',
        'sow_limit',
    ]