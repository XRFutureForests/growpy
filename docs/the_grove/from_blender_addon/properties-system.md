# Grove Properties System (From Blender Addon Analysis)

Based on analysis of `Properties.py` in the Blender addon, this document outlines the comprehensive properties system used by Grove.

## Property Categories

### Simulation Control
- `simulation_scale`: Overall tree scale (default: 1.0)
- `simulation_flushes`: Number of growth cycles (default: 8)

### Sow (Seed Dispersal)
- `sow_enabled`: Enable seed dispersal (default: False)
- `sow_age`: Age when trees start producing seeds (default: 10)
- `sow_chance`: Probability of seed production (default: 0.2)
- `sow_distance`: Seed dispersal distance (default: 8.0)
- `sow_limit`: Maximum number of offspring (default: 50)

### Recording (Animation)
- `record_enabled`: Enable growth animation recording (default: False)
- `record_interval`: Frames between growth steps (default: 3)
- `record_start_frame`: Animation start frame (default: 1)

### Surround (Environmental Competition)
- `surround_enabled`: Enable surrounding tree competition (default: False)
- `surround_density`: Density of surrounding trees (default: 0.7)
- `surround_height`: Height of surrounding trees (default: 5.0)
- `surround_distance`: Distance to surrounding trees (default: 7.0)
- `surround_grow`: Whether surround trees grow with main tree (default: True)

### React (Environmental Forces)
- `react_enabled`: Enable environmental reaction (default: False)
- `react_block_object`: Object that blocks growth
- `react_shade_object`: Object that casts shade
- `react_attract_object`: Object that attracts growth
- `react_attract_strength`: Attraction force strength (default: 0.3)
- `react_attract_falloff`: Attraction falloff rate (default: 1.3)
- `react_deflect_object`: Object that deflects growth
- `react_deflect_strength`: Deflection force strength (default: 0.3)
- `react_deflect_falloff`: Deflection falloff rate (default: 1.3)
- `react_vigor_object`: Object that affects tree vigor

### Auto Pruning
- `auto_prune_enabled`: Enable automatic pruning (default: True)
- `auto_prune_low`: Height below which to prune (default: 2.0)
- `auto_prune_keep_thick`: Minimum thickness to keep (default: 0.01)
- `auto_prune_dangling`: Length of dangling branches to prune (default: 1.0)

### Stake (Support Structure)
- `stake_enabled`: Enable stake support (default: False)
- `stake_height`: Height of stake support (default: 4.0)

### Growth Behavior
- `favor_end`: Preference for terminal growth (default: 0.4)
- `favor_end_reduce`: Reduction of end preference over time (default: 0.0)
- `shade_avoidance`: Tendency to avoid shade (default: 0.0)
- `favor_bright`: Preference for bright areas (default: 0.8)
- `favor_rising`: Preference for upward growth (default: 0.0)
- `favor_dwindle`: Rate of branch thinning (default: 1.0)
- `favor_thick`: Preference for thick branches (default: 0.0)
- `favor_squeeze`: Branch compression factor (default: 0.0)

### Branch Dropping
- `drop_shaded`: Rate of dropping shaded branches (default: 0.3)
- `drop_weak`: Rate of dropping weak branches (default: 0.1)
- `drop_obsolete`: Rate of dropping obsolete branches (default: 0.1)
- `drop_decay`: Rate of branch decay (default: 0.4)

### Branch Addition
- `add_side_branches`: Number of side branches to add (default: 1)
- `add_chance`: Probability of adding branches (default: 1.0)
- `add_chance_reduce`: Reduction of branch addition over time (default: 0.0)
- `add_bud_life`: Lifespan of buds (default: 1)
- `add_only_on_end`: Preference for adding branches at tips (default: 0.0)
- `add_regenerate`: Rate of branch regeneration (default: 0.05)
- `add_fork`: Probability of forking (default: 0.0)
- `add_angle`: Angle of new branches in radians (default: 45°)
- `add_up`: Upward bias for new branches (default: 0.0)
- `add_horizontal`: Horizontal orientation preference (default: 0.0)
- `add_planar`: Planar growth preference (default: 0.0)

### Growth Parameters
- `grow_nodes`: Number of nodes to grow per step (default: 3)
- `grow_length`: Length of growth segments (default: 0.3)

### Turning Behavior
- `turn_to_light`: Tendency to turn toward light (default: 0.0)
- `turn_up`: Tendency to turn upward (default: 0.2)
- `turn_up_in_shade`: Increased upward turning in shade (default: 0.0)
- `turn_to_horizon`: Tendency to turn horizontal (default: 0.0)
- `turn_random`: Random turning angle in radians (default: 5°)

### Thickness and Structure
- `thicken_tips`: Thickness of branch tips (default: 0.007)
- `thicken_tips_reduce`: Reduction of tip thickness over time (default: 0.0)
- `thicken_join`: Thickness at branch junctions (default: 0.75)
- `thicken_deadwood`: Thickness of dead branches (default: 0.0)
- `thicken_base_scale`: Scale factor for tree base (default: 1.2)
- `thicken_base_buttress`: Buttress root prominence (default: 2.0)
- `thicken_base_shape`: Shape of tree base (default: 0.1)
- `root_distribution`: Distribution of root thickness (default: 0.4)

### Bending Physics
- `bend_mass`: Mass factor for bending (default: 1.0)
- `bend_twig_mass`: Mass of twigs for bending (default: 0.1)
- `bend_twig_mass_solidify`: Solidification of twig mass (default: 1.0)
- `bend_reaction`: Branch reaction to bending forces (default: 0.5)

### Shading System
- `shade_area`: Area of shade cast by leaves (default: 8.0)
- `shade_area_reduce`: Reduction of shade area over time (default: 0.0)
- `shade_area_depth`: Depth factor for shade (default: 0.5)
- `shade_leaf_sides`: Whether leaves cast shade on both sides (default: False)
- `shade_branches`: Whether branches cast shade (default: False)
- `shade_alongside`: Number of neighboring branches to consider (default: 2)
- `shade_alongside_diameter`: Diameter threshold for neighboring branches (default: 0.2)

### Wind Animation
- `wind_iterations`: Quality of wind shape calculation (default: 4)
- `wind_breeze`: Strength of breeze animation (default: 0.2)

### Mesh Building
- `build_cutoff_age`: Minimum age to build branches (default: 0)
- `build_cutoff_thickness`: Minimum thickness to build (default: 0.0)
- `build_resolution`: Cross-section resolution (default: 16)
- `build_resolution_reduce`: Resolution reduction rate (default: 0.78)
- `build_triangulate`: Whether to triangulate mesh (default: False)
- `build_blend`: Whether to blend branch joints (default: True)
- `build_end_cap`: Whether to cap branch ends (default: True)
- `detail_simplify`: Whether to simplify detail (default: True)
- `add_twist`: Amount of branch twist (default: 0.1)

### Texture System
- `texture_bark`: Path to bark texture
- `bark_material_name`: Name of bark material
- `texture_aspect_ratio`: Aspect ratio of texture (default: 3.0)
- `texture_repeat`: Number of texture repeats (default: 3)

### Twig System
- `twig_menu`: Selected twig type
- `twig_hide`: Whether to hide twigs (default: False)
- `twig_object_end`: End twig object
- `twig_object_side`: Side twig object
- `twig_object_upward`: Upward twig object
- `twig_object_dead`: Dead twig object
- `twig_side_on_tips`: Whether side twigs appear on tips (default: False)
- Collection variants for all twig types
- `twig_longevity`: Lifespan of twigs (default: 2)
- `twig_wither`: Time for twigs to wither (default: 2)
- `twig_density`: Density of twig placement (default: 0.2)
- `twig_view_detail`: Level of detail for viewport display (default: 0.3)

## Property Conversion System

The addon uses a sophisticated property conversion system:

### Core Properties List
80+ properties are marked as "core properties" that get converted and passed to the Grove simulation engine.

### Scale-Dependent Properties
Some properties are automatically adjusted based on `simulation_scale`:
- `auto_prune_low`
- `auto_prune_dangling` 
- `stake_height`

### JSON Conversion
Properties are converted to JSON and passed to the core:

```python
def convert_to_core_properties(self):
    properties_dictionary = {}
    for parameter in self.core_properties:
        if parameter in scale_dependent_properties:
            properties_dictionary[parameter] = getattr(self, parameter) / self.simulation_scale
        else:
            properties_dictionary[parameter] = getattr(self, parameter)
    
    json_string = json.dumps(properties_dictionary)
    return the_grove_core.io.properties_from_json_string(json_string)
```

## Property Management Features

1. **Preset System**: Properties can be saved/loaded as presets
2. **Real-time Updates**: Many properties have callback functions that update the tree immediately
3. **UI Integration**: All properties have associated UI elements with tooltips and validation
4. **Translation Support**: Property names and descriptions support multiple languages
5. **Type Safety**: Properties use Blender's typed property system with validation and ranges