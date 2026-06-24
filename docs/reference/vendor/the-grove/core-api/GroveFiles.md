# Working with grove files

_New in Grove 2.3._

Grove simulations can be saved and loaded using JSON serialization. This allows you to persist tree growth state, share simulations, and continue growing from a saved point.

## Saving a grove

```python
import the_grove_core as gc

grove = gc.Grove()
grove.simulate(20)

# Serialize to JSON string
json_string = gc.io.grove_to_json_string(grove)

# Write to file
with open('my_grove.json', 'w') as f:
    f.write(json_string)
```

## Loading a grove

```python
import the_grove_core as gc

with open('my_grove.json', 'r') as f:
    json_string = f.read()

grove = gc.io.grove_from_json_string(json_string)

# Continue growing
grove.simulate(10)
```

## Inspecting grove data

The JSON string can be parsed as a standard Python dictionary:

```python
import json

grove_dict = json.loads(json_string)
# Access tree data
grove_dict['trees'][0]['nodes'][3]['radius']
```

## Blender integration

The Grove in Blender stores the grove as a compressed JSON string in the collection:

```python
import gzip
import bpy
import the_grove_core as gc

grove_collection = bpy.context.collection
json_string = gzip.decompress(grove_collection['grove']).decode('utf-8')
grove = gc.io.grove_from_json_string(json_string)

# Modify and write back
grove.simulate(10)
json_string = gc.io.grove_to_json_string(grove)
grove_collection['grove'] = gzip.compress(bytes(json_string.encode('utf-8')), compresslevel=1)
```
