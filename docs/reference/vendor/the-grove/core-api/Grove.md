# [the_grove_core](./the_grove_core.html).Grove

The meaning of grove is a group of trees, a small woodland or orchard. A grove is a list of branches that are the trunks of the trees. Each branch is a list of nodes, and each node has a list of sub branches, and so on. Every branch in The Grove is treated equal, even trunks are simply branches.




### build_models( { build_options } )  [model]

Build a list of 3D meshes, one for each of the simulated tree structures. The resolution is the number of points at the base of the tree, which reduces when the branch gets thinner. Returns a list of Model objects, one for each tree int he grove. Each model contains lists of points, faces, uvs and attributes.



Build options can be passed in a dictionary. Calling `build_models({})` will build using defaults. You can include or leave out any option you like - to provide all options use:
```python
models = grove.build_models({
    "resolution": 16,
    "resolution_reduce": 0.8,
    "texture_repeat": 3,
    "build_cutoff_age": 0,
    "build_cutoff_thickness": 0.0,
    "build_blend": True,
    "build_end_cap": True,
})
```
  * **resolution** (int) - The number of points at the base of the tree. Optional, defaults to 16.
  * **reduce** (float) - A float between 0.0 and 1.0, where 0.0 gives no reduction and 1.0 gives very fast reduction when the branch gets thinner. Optional, defaults to 0.8.
  * **texture_repeat** (int) - Repeat the bark texture this number of times around the girth of the trunk. This only affects the UV-map. The number of repetitions is automatically reduced on thinner branches based on the circumference of the first node. Optional, defaults to 3.
  * **build_cutoff_age** (int) - At this age, stop building the rest of the branch.
  * **build_cutoff_thickness** (float) - At this diameter, stop building the rest of the branch.
  * **build_blend** (bool) - add extra geometry to smoothly transition from a main branch to a side branch.
  * **build_end_cap** (bool) - add geometry to close off the end of a branch.




### build_as_one_model( { build_options } )  Model

Build a single 3D model of all trees in the grove. The resolution is the number of points at the base of the tree, which reduces when the branch gets thinner. Returns a model of all trees as one single mesh. Separate trees can be selected using _Model.face_layer_tree_index_.



This function expects the same dictionary with build options as the build_models function above.




### simulate(flushes=1)

Simulate growth for the given number of flushes. The main simulation sequence calls the starter functions in the right order and grows the tree in steps.



Parameters:
  * flushes (int) - The number of growth flushes to simulate. Optional, defaults to 1.




### set_random_seed(seed)

Setting a specific random seed ensures that, when using the same parameters, the simulation will always grow the same tree. _The Grove in Houdini_ uses this to keep the same tree when re-cooking the node network. _The Grove in Blender_ on the other hand uses a new random seed for every tree you grow.



Parameters:
  * seed (int) - A random seed.




### build_skeletons()  [skeleton]

studio edition feature
Build a skeleton structure for physics simulation purposes. Returns a list of skeletons, one for each tree.




### manual_prune(RayTree)

Prune every branch where it intersects with the provided geometry. Takes a RayTree object that has been filled with geometry to prune with.




### manual_draw(start_node_index, guide)

Draw along a guide path. Takes the index of the node.
  * start_node_index (int) - Todo…
  * guide ( [vector] ) - A list of Vector objects.




### replant_tree(tree_index, translation, rotation)

When the tree object gets moved around by the user in a target application, the add-on for that application should call replant_tree to propagate that transformation to all nodes in the tree.




### add_new_tree(position, direction, delay)

Add a new tree to the current grove. **Note**: creating a new Grove already creates a new tree at the origin, you can delete this tree with `Grove.clear_trees()` before adding a new tree at a specific location.
  * position (Vector) - Where to plant the new tree, for example: `the_grove_23_core.Vector(0.0, 0.0, 0.0)`.
  * direction (Vector) - Add an initial direction to the new tree. Very important is that this **direction also determines the length** of the first internode. A length of 0.1 is a good default for this. Do not use a normalized direction vector, because this will create a 1.0 meter internode that will collapse the tree. Here's an example for a tree growing straight up: `the_grove_23_core.Vector(0.0, 0.0, 0.1)`.
  * delay (int) - The number of years to wait before growing. Use 0 to start growing immediately.



### build_shade_geometry -> [Vector]

*New in Grove 2.3.*
Create a stylized representation of the tree's foliage for casting shade.
Returns a list of vectors, where each 3 vectors form a triangle. The shade geometry consists of only triangles, and these do not share points.

### build_shade_geometry_flat -> [Float]

*New in Grove 2.3.*
Same as above. Returns a flat list of floating point values.

### build_shade_geometry_as_tuples -> [(Float, Float, Float)]

*New in Grove 2.3.*
Same as above. Returns a list of tuples.

### remember_orig_pos()

*New in Grove 2.3.*
Very specific function used by the Blender add-on to prevent twigs from flipping during wind animation. For an example of its usage, check OperatorAnimateWind.py of the Blender add-on.

### build_surround_preview() -> [((Float, Float, Float), (Float, Float, Float))]

*New in Grove 2.3.*
Build a preview of the surround object. Returns a list of lines, where each line is a tuple with two 3D coordinates, where each coordinate is a tuple of 3 floats.

### build_surround_preview_2d(surround_height, perspective_matrix, view_width, view_height)

*New in Grove 2.3.*
Create a 2D sketch of the surround object for the current view.
Parameters:
  * surround_height (Float)
  * perspective_matrix - 4x4 tuple of floats
  * view_width (Float)
  * view_height (Float)

Returns a tuple with a list of 2D coordinate tuples (points) and a list of triangle index tuples (indices).

### manual_prune([coords: float])

*Changed in Grove 2.3.* (was `manual_prune(RayTree)` in 2.2)
Prune every branch where it intersects with the provided geometry. The geometry provided must consist of triangles only, represented by a flat list of floating point numbers. Where each 3 numbers are a 3D coordinate, and each 9 values create a triangle.

#the grove/the grove core/python api#