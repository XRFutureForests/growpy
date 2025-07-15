# [the_grove_core](./the_grove_core.html).io

The io module is for input and output of entire simulations, presets, and tree models as USD or OBJ files.

### grove_from_json_string(json_string)  Grove

Load a Grove object from a serialized string. Could be a string read from a file, or a string stored in a working file in a target application. The Grove in Houdini stores this string on the geometry in a detail attribute. The Grove in Blender stores it in the grove collection.

Parameters:

* json_string (string) - A previously saved simulation.

Here’s an example. Let’s say you’ve been growing a tree in the Blender add-on, and now want to access the trees in either the Python console or a script in the text editor:

```python
import the_grove_core
import gzip
import bpy


# assuming the grove collection is active

grove_collection = bpy.context.collection

# The Grove in Blender compresses the json string to save space.

json_string = gzip.decompress(grove_collection['grove']).decode('utf-8')
grove = the_grove_core.io.grove_from_json_string(json_string)


# Now let's modify it.

grove.simulate(10)


# And if you want to, you can write back the result. The rebuild your grove in the UI and you'll see the extra 10 years appear.

json_string = the_grove_core.io.grove_to_json_string(grove)
json_string = gzip.compress(bytes(json_string.encode('utf-8')), compresslevel=1)
grove_collection['grove'] = json_string
```

### grove_to_json_string(Grove)  string

Serialize this Grove object to a json string. The string can be stored in a target application’s working file, or dumped to a file on disk.

### properties_to_json_string(Properties)  string

Save the growth parameters (properties) to a JSON string. You can store this string to a preset `.seed.json` file.

### properties_from_json_string(json_string)

The Grove’s growth parameters are stored in preset files with the `.seed.json` extension. These are simple text files in the JSON format. You can read a preset properties (growth parameters) from a json string, for example the contents of a preset .seed.json file.
The reading of presets is forgiving, any parameters missing in the json file are set to defaults. Parameters that are not recognized are silently skipped.

### grove_to_svg_string(Grove)  string

studio edition feature
Render a 2D sketch as SVG (Scalable Vector Graphics). The sketch fits all trees and is rendered from a flat front view. Returns a string that you can write to an SVG file. This is an experimental feature that needs more work.

### model_to_obj_string(Model)  String

studio edition feature
Convert a single tree model to an OBJ model. You can write the returned string directly to a .obj file. For an example, look below at the similar `model_to_usda_string`.
The .obj format is basic. It includes vertices, faces, UVs, and the faces are joined in groups, one for the branches, and four others for each type of twig duplicator triangle. The twig geometry itself is not included.

Parameters:

* Model ([the_grove_core.Model](./the_grove_core.Model.html)) - A built model object.

### model_to_usda_string(Model)  String

studio edition feature
Convert a single tree model to a USD model. You can write the returned string directly to a .usda file. The USD model contains the mesh, UV maps and attributes. When you import a USD file in Houdini, be sure to unpack the geometry to polygons upon import, to see the attributes. Also, at the time of writing, Blender 3.5.0’s USD importer does not import custom attributes other than the UV map.

Note that while `Grove.build` returns a list of all built tree models in the current grove, this function only takes one tree model at a time. Here’s an example of how to write each tree to a separate .usda files:

```python
import the_grove_core

grove = the_grove_core.Grove()

# A new grove defaults to one tree - let's add a second tree.

grove.add_new_tree(
    the_grove_core.Vector(1.0, 0.0, 0.0),  # Location

    the_grove_core.Vector(0.0, 0.0001, 0.1),  # Direction

    0);  # Number of cycles to wait before starting to grow.

grove.simulate(30)
models = grove.build_models({resolution: 32})

for i in range(len(models)):
    usda_string = the_grove_core.io.model_to_usda_string(models[i])
    usda_file = open('/Users/name/Desktop/tree' + str(i) + '.usda', 'w')
    usda_file.write(usda_string)
    usda_file.close()
```

Each tree’s `Xform` contains a transformation to place the tree where it belongs.

You can combine this example with the earlier example at the top of this page to export the current grove of trees in the Blender add-on. You could add a new layer in a separate .usda file that references in all the separate trees, let’s call it grove.usda:

```python
#usda 1.0

()

def Xform "Grove"
{
 def "Tree0" (
  append references = @./tree0.usda@
 )
 {}
 def "Tree1" (
  append references = @./tree1.usda@
 )
 {}
}
```

Importing this USDA file will load in all the trees as one grove. Chances are you’re wondering why The Grove doesn’t do this work for you. Well, USD is flexible, and each studio uses it in its own way. This way you can easily piece together your own custom exporter with your own naming conventions, and perhaps even add some extra data along the way.

# the grove/the grove core/python api #
