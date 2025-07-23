# Grove Serialization and I/O System (From Blender Addon Analysis)

Based on analysis of `File.py` and I/O patterns throughout the Blender addon, this document outlines Grove's serialization and file handling system.

## Core Serialization API

### Save Grove to JSON
```python
def save_grove(grove, grove_collection):
    # Convert grove to JSON string
    data = the_grove_core.io.grove_to_json_string(grove)
    
    # Compress for efficiency
    bytes = data.encode('utf-8')
    compressed_data = gzip.compress(bytes, compresslevel=1)
    
    # Encode to base64 for Blender compatibility
    data_string = base64.b64encode(compressed_data).decode('utf-8')
    
    # Store as custom property on collection
    grove_collection['grove'] = data_string
```

### Load Grove from JSON
```python
def load_grove(grove_collection):
    data_string = grove_collection['grove']
    
    # Handle legacy byte format (Blender < 4.2)
    if type(data_string) is bytes:
        compressed_data = data_string
    else:
        # Modern base64 string format (Blender 4.2+)
        compressed_data = base64.b64decode(data_string.encode('utf-8'))
    
    # Decompress and deserialize
    data = gzip.decompress(compressed_data).decode('utf-8')
    grove = the_grove_core.io.grove_from_json_string(data)
    return grove
```

## Data Encoding Evolution

### Blender Version Compatibility
The serialization system handles breaking changes in Blender 4.2:

**Pre-Blender 4.2 (Legacy):**
- Could store byte arrays directly as custom properties
- Raw compressed data stored as bytes

**Blender 4.2+ (Current):**
- Only simple Python types (strings, numbers) allowed in custom properties
- Null characters in byte arrays cause premature termination
- Solution: Base64 encoding to convert bytes to safe strings

### Compression Strategy
```python
# Level 1 compression provides good balance of speed vs size
compressed_data = gzip.compress(bytes, compresslevel=1)
```

## File Management System

### Recent Files Tracking
The addon maintains a list of recently accessed Grove files:

```python
def recent_files():
    """Return list of recently opened .grove files"""
    # Implementation tracks file paths for quick access
    return file_list

def import_path(file_path):
    """Import a grove from a specific file path"""
    # Load and apply grove from file
```

### File Operations Integration
The file system integrates with Blender's file browser:

```python
# File import operator
elif action == 'import':
    bpy.ops.the_grove_22.import_grove("INVOKE_DEFAULT")

# File export operator  
elif action == 'export':
    bpy.ops.the_grove_22.export_grove("INVOKE_DEFAULT")

# Recent file access
elif action == 'import_recent_1':
    context.window.cursor_modal_set('WAIT')
    import_path(recent_files()[-1])
    context.window.cursor_modal_restore()
```

## Property Serialization

### Property Conversion Pipeline
```python
# Convert Blender properties to Grove core format
def convert_to_core_properties(self):
    properties_dictionary = {}
    for parameter in self.core_properties:
        if parameter in ['auto_prune_low', 'auto_prune_dangling', 'stake_height']:
            # Scale-dependent properties
            properties_dictionary[parameter] = getattr(self, parameter) / self.simulation_scale
        else:
            properties_dictionary[parameter] = getattr(self, parameter)
    
    json_string = json.dumps(properties_dictionary)
    return the_grove_core.io.properties_from_json_string(json_string)

# Read properties from Grove core
def read_from_core_properties(self, props):
    for parameter in self.core_properties:
        if hasattr(self, parameter) and hasattr(props, parameter):
            if parameter in ['auto_prune_low', 'auto_prune_dangling', 'stake_height']:
                self[parameter] = getattr(props, parameter) * self.simulation_scale
            else:
                self[parameter] = getattr(props, parameter)
```

### Property Categories in Serialization
The system serializes 80+ core properties including:
- Growth parameters (`grow_nodes`, `grow_length`)
- Branch behavior (`add_chance`, `turn_to_light`)
- Environmental responses (`shade_avoidance`, `favor_bright`)
- Physical properties (`bend_mass`, `thicken_tips`)
- Pruning settings (`auto_prune_enabled`, `drop_weak`)

## Storage Location Strategy

### Blender Collection Integration
Grove stores simulation data directly in Blender collections as custom properties:

```python
# Each grove collection gets a unique identifier
properties.unique_id = generate_unique_id()

# Simulation data stored as collection custom property
grove_collection['grove'] = serialized_data

# Properties stored as collection property group
grove_collection.GROVE22_Properties = properties
```

### Benefits of Collection Storage
1. **Embedded Data**: Grove data travels with the Blender file
2. **No External Dependencies**: No need for separate .grove files
3. **Version Control Friendly**: Text-based serialization
4. **Multi-Grove Support**: Each collection can contain different species
5. **Blender Integration**: Leverages Blender's native data management

## Error Handling and Validation

### Robust Loading
```python
def load_grove(grove_collection):
    try:
        data_string = grove_collection['grove']
        # ... decompression and deserialization
        grove = the_grove_core.io.grove_from_json_string(data)
        return grove
    except KeyError:
        # No grove data found
        return None
    except Exception as e:
        # Handle corruption or version mismatches
        print(f"Error loading grove: {e}")
        return None
```

### Property Validation
```python
# Property validation during conversion
for parameter in self.core_properties:
    if hasattr(self, parameter) and hasattr(props, parameter):
        # Only set if both source and target have the property
        self[parameter] = getattr(props, parameter)
    else:
        print("Skipping parameter " + parameter)
```

## Performance Optimizations

### Compression Benefits
- Raw JSON can be large for complex trees
- Level 1 gzip compression provides ~60-80% size reduction
- Fast compression/decompression suitable for real-time operations

### Base64 Encoding Overhead
- ~33% size increase from Base64 encoding
- Still net reduction due to gzip compression
- Ensures compatibility with Blender's property system

### Memory Management
```python
# Efficient byte handling
bytes = data.encode('utf-8')  # Encode once
compressed_data = gzip.compress(bytes, compresslevel=1)  # Compress in memory
data_string = base64.b64encode(compressed_data).decode('utf-8')  # Final encoding
```

## Data Migration Strategy

### Backward Compatibility
The system gracefully handles both old and new data formats:

```python
if type(data_string) is bytes:
    # Legacy format - can still be read
    compressed_data = data_string
else:
    # New format - decode base64 first
    compressed_data = base64.b64decode(data_string.encode('utf-8'))
```

### Future-Proofing
- JSON-based serialization allows for schema evolution
- Property validation handles missing or new properties
- Compression layer can be changed without affecting format

## Key Insights for GrowPy

1. **Embedded Storage**: Consider storing Grove data within project files rather than separate files
2. **Compression Essential**: Large tree simulations benefit significantly from compression
3. **Property Validation**: Robust property handling prevents errors during load/save
4. **Version Compatibility**: Plan for format evolution with backward compatibility
5. **Performance Balance**: Level 1 compression provides good speed/size tradeoff
6. **Error Recovery**: Graceful handling of missing or corrupted data prevents crashes
7. **Base64 Encoding**: May be necessary for compatibility with certain storage systems
8. **Scale Handling**: Some properties need scale-dependent conversion during serialization