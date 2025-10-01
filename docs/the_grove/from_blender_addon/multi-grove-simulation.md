# Multi-Grove Simulation System (From Blender Addon Analysis)

Based on analysis of `OperatorGrowTogether.py`, this document outlines how Grove handles multi-species forest simulation with shared light competition.

## Overview

The "Grow Together" feature allows multiple Grove instances (different tree species) to simulate growth simultaneously while competing for light resources. This creates realistic forest dynamics where different species interact.

## Core Architecture

### Grove Collection and Loading
```python
def invoke(self, context, _):
    # Load all groves from all collections
    for collection in bpy.data.collections:
        if 'GROVE22_Properties' in collection and collection.GROVE22_Properties.unique_id != '':
            grove = load_grove(collection)
            if grove:
                self.list_of_groves.append(grove)
                self.list_of_collections.append(collection)
                self.list_of_properties.append(collection.GROVE22_Properties)
```

### Multi-Grove Data Structure
The system maintains parallel lists for managing multiple groves:
- `list_of_groves`: Grove simulation objects
- `list_of_collections`: Blender collections containing the trees
- `list_of_properties`: Property sets for each grove

## Light Competition Algorithm

### Shared Shade Geometry Creation
```python
# Create combined shade geometry from all groves
coords = []
for i, grove in enumerate(self.list_of_groves):
    grove.set_properties(self.list_of_properties[i].convert_to_core_properties())
    coords.extend(grove.create_shade_geometry_coords())
```

### Key Performance Optimization
The original implementation used vector objects:
```python
# Slower original approach (commented out in code)
vectors = []
for i, grove in enumerate(self.list_of_groves):
    grove.set_properties(self.list_of_properties[i].convert_to_core_properties())
    vectors.extend(grove.create_shade_geometry())

coords = []
for vector in vectors:
    coords.extend([vector.x, vector.y, vector.z])
```

The optimized version directly creates coordinate arrays:
```python
# Much faster optimized approach
coords = []
for i, grove in enumerate(self.list_of_groves):
    grove.set_properties(self.list_of_properties[i].convert_to_core_properties())
    coords.extend(grove.create_shade_geometry_coords())
```

### Shared Light Calculation
```python
# Apply shared shade calculation to all groves
for i, grove in enumerate(self.list_of_groves):
    grove.calculate_shade_together(coords)
    grove.simulate(1)
```

## Simulation Loop

### Synchronized Growth
```python
if self.current_year != self.simulation_flushes_dial.value:
    self.current_year += 1
    
    # Step 1: Create shared shade geometry
    coords = []
    for i, grove in enumerate(self.list_of_groves):
        grove.set_properties(self.list_of_properties[i].convert_to_core_properties())
        coords.extend(grove.create_shade_geometry_coords())
    
    # Step 2: Simulate all groves with shared light
    for i, grove in enumerate(self.list_of_groves):
        grove.calculate_shade_together(coords)
        grove.simulate(1)
```

### Progress Calculation
```python
if self.current_year > 0:
    # Exponential progress calculation for UI feedback
    exponent = 1
    if self.simulation_flushes_dial.value > 4:
        exponent = 1.8
    # Plus one for build step
    progress = pow(self.current_year / (self.simulation_flushes_dial.value + 1), exponent)
    self.progress_dial.progress = max(1, int(progress * 100)) / 100.0
```

## Build and Save Process

### Post-Simulation Building
```python
def after_growing(self, context):
    self.growing = False
    self.building = False
    self.current_year = 0
    self.progress_dial.progress = -1.0
    
    # Build and save all groves
    for i, grove in enumerate(self.list_of_groves):
        build(context, self.list_of_properties[i], grove, self.list_of_collections[i], rebuild=False)
        save_grove(grove, self.list_of_collections[i])
```

### Timer-Based Building
```python
if self.build_step:
    progress = self.progress_dial.progress + (100 - self.progress_dial.progress) / 2.0
    self.progress_dial.progress = progress / 100.0
    
    for i, grove in enumerate(self.list_of_groves):
        build(context, self.list_of_properties[i], grove, self.list_of_collections[i], rebuild=False)
        save_grove(grove, self.list_of_collections[i])
    
    self.progress_dial.progress = 1.0
    self.build_step = False
    self.done = True
```

## Feature Restrictions

### Disabled Features in Multi-Grove Mode
```python
self.interface.info_bar = []
if properties.surround_enabled and properties.surround_density != 0:
    self.interface.info_bar.append('Surround disabled')
if properties.record_enabled:
    self.interface.info_bar.append('Record disabled')
if properties.react_block_object or properties.react_shade_object or \
   properties.react_attract_object or properties.react_deflect_object:
    if properties.react_enabled:
        self.interface.info_bar.append('React disabled')

# Force disable recording
self.grove_properties.record_enabled = False  # Doesn't work well!
```

## User Interface Integration

### Tool Controls
```python
# Interface widgets for multi-grove simulation
close_button = TouchButton(action='Back', label=t('close_button'), ...)
restart_button = TouchButton(action='Restart', label=t('restart_all'), ...)
simulation_flushes_dial = TouchSlider(
    action='GrowYears', label=t('simulation_flushes'), 
    value_min=1, value_max=20, value_default=5, ...
)
progress_dial = TouchProgress(
    action='Progress', label=t('grow_together'), ...
)
```

### Restart All Functionality
```python
elif action == 'Restart':
    for i, grove in enumerate(self.list_of_groves):
        collection = self.list_of_collections[i]
        properties = self.list_of_properties[i]
        clean_grove(collection)
        clean_record(collection)
        grove = create_new_trees(context, collection, properties)
        self.list_of_groves[i] = grove
        build(context, properties, grove, collection, rebuild=False)
        save_grove(grove, collection)
```

## Key API Functions for Multi-Grove

### Essential Grove Methods
- `grove.create_shade_geometry_coords()`: Get shade geometry as coordinate array
- `grove.calculate_shade_together(coords)`: Apply shared shade calculation
- `grove.simulate(steps)`: Simulate growth with current light conditions
- `grove.set_properties(properties)`: Apply species-specific properties

### Performance Considerations
1. **Coordinate Arrays**: Use `create_shade_geometry_coords()` instead of vector objects
2. **Batch Processing**: Set all properties before shade calculations
3. **Memory Management**: The system uses garbage collection control for performance
4. **Progress Feedback**: Exponential progress calculation provides smooth UI updates

## Architecture Insights

1. **Species Independence**: Each grove maintains its own properties and behavior
2. **Shared Environment**: Light competition is the primary interaction mechanism
3. **Synchronized Timing**: All groves advance one step at a time in lockstep
4. **Feature Isolation**: Some features (recording, surround, react) are disabled to prevent conflicts
5. **Scalable Design**: The system can handle arbitrary numbers of grove collections
6. **UI Integration**: Real-time progress feedback and control during simulation

## Implementation Notes for GrowPy

1. **Collection Detection**: Find all collections with Grove properties using unique IDs
2. **Property Conversion**: Each grove needs its properties converted before shade calculation
3. **Coordinate Optimization**: Use coordinate arrays rather than vector objects for performance
4. **Error Handling**: The system gracefully handles missing or invalid groves
5. **Memory Efficiency**: Shared coordinate arrays minimize memory usage for large forests