# [the_grove_core](./the_grove_core.html).Model

You can build tree models with `Grove.build_models`, which returns a list of Model objects, one for each tree. Or use `Grove.build_as_one_model` to build all trees in the grove as a single Model.



A 3D model consisting of lists of points, faces, uvs and attribute layers. A point is a vector that defines an (x,y,z) coordinate in 3D space. A face (or polygon) is defined by a list of integers. These are indexes to the points list. Most attributes are either point layers or face layers. UVs are face corner / vertex layers.




### apply_uv_aspect_ratio(aspect)

Stretch the UV coordinates to match the aspect ratio of a bark texture. The default aspect is 1, to get no distortion with a square texture. For a texture twice as high as it is wide, the aspect is 2 / 1 = 2.0. Therefore each V-coordinate is multiplied by 2.0.


### get_uvs_flat()

Return the UV map as a flat list of floats, which performs much faster in Python. The list is structure like this `[u1, v1, u2, v2, … ]`.


### get_uvws_flat()

Return the UVW map as a flat list of floats. Some applications like Houdini require a third W component in for each UV coordinate. There is no purpose for this W component in The Grove, so this is set to 0.0. The list is like this `[u1, v1, w1, u2, v2, w2, … ]`.


### get_uv_islands_flat()


### get_directions_flat()

Return the directions as a flat list of floats, which performs much faster in Python.


### get_points_flat()

Turns the list of points (Model.points) from a list of Vector objects into a flat list of floating point (f64) values. The simple list of numbers performs much faster in Python than using Rust data types. The result is a list like `[x, y, z, x, y, z, x, y, z, …]`.


### get_shape_as_tuples()




### set_up_axis(new_up_axis)

Set the up-axis to match your target application’s axis system. For example, Blender uses Z-up, Houdini uses Y-up. This will transform all Vectors in the Model, as well as the orientation attribute’s Quaternions.
  * new_up_axis (string) - Either `"Y"` or `"Z"`.




### set_winding_order(new_winding_order)

A face is created from a list of points in either a clockwise or counter-clockwise order. This winding order determines the intrinsic normal direction of the face. The default winding order for The Grove (and Blender) is clockwise. In most other apps (like Houdini), the standard is counter-clockwise. Use this function to set the correct order for your target application, so that normals point outward.
  * new_winding_order (string) - Either `CLOCKWISE` or `COUNTER_CLOCKWISE`.




### triangulate()

The Grove's trees are built from quads and triangles. After that, you can optionally convert all quads to triangles.
* * *




## Attributes

| Attribute                              | Domain | Type  | Description                                                                                                                                                                                                                                                                                                                                                                                                                  |
|----------------------------------------|--------|-------|------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **face_attribute_tree_index**          | face   | int   | When all trees are built together as one mesh, use this layer to select individual trees. For example in Houdini, `TreeIndex` is added to the geometry as an integer attribute stored on primitives. The faces belonging to each tree are tagged with an ascending integer value, starting at 0. Use a delete or blast node to delete the group `@TreeIndex!=3` to remove anything but the 4th tree in the grove.            |
| **face_attribute_twig_long**           | face   | bool  | Twigs are duplicated at the center of many tiny triangles. The normal of these triangle determines the orientation of each twig. This system proved to be compatible with diverse 3D software. The facel_layer_twig attributes tell which twig should be duplicated at which triangle.                                                                                                                                       |
| **face_attribute_twig_short**          | face   | bool  | See above.                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **face_attribute_twig_upward**         | face   | bool  | See above.                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **face_attribute_twig_dead**           | face   | bool  | See above.                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **face_attribute_dead**                | face   | bool  | Whether the branch is dead.                                                                                                                                                                                                                                                                                                                                                                                                  |
| **face_attribute_branch_index**        | face   | int   | Used for selecting an entire branch and its sub branches.                                                                                                                                                                                                                                                                                                                                                                    |
| **face_attribute_branch_index_parent** | face   | int   | See above.                                                                                                                                                                                                                                                                                                                                                                                                                   |
| **face_attribute_end**                 | face   | bool  | To select branch end cap polygons.                                                                                                                                                                                                                                                                                                                                                                                           |
| **face_attribute_direction**           | face   | tuple | The original growth direction of each branch node, before deformation. A list of tuples with (x, y, z) coordinates. This attribute is used by the Blender add-on to prevent twigs from flipping on branches that are deformed by wind animation. Twig duplication triangle are oriented toward the direction of growth, so for these triangles the direction attribute equals the face normal.                               |
| **point_attribute_age**                | point  | int   | Age of each branch node, the number of cycles / years that the node has been around.                                                                                                                                                                                                                                                                                                                                         |
| **point_attribute_mass**               | point  | float | The mass of the continuation of the branch and all attached sub branches.                                                                                                                                                                                                                                                                                                                                                    |
| **point_attribute_orientation**        | point  | tuple | Orientation of the branch node or twig duplication triangle, in the form of a tuple of 4 float numbers.                                                                                                                                                                                                                                                                                                                      |
| **point_attribute_shade**              | point  | float | Ambient occlusion - from 0.0 for fully exposed branch tips, to 1.0 for branches that are fully shaded by the canopy above and optional React / shade objects. If you instead want the exposure to light, simply invert this number.                                                                                                                                                                                          |
| **point_attribute_thickness**          | point  | float | The diameter at each node, mapped to a range from 0.0 to 1.0, where 1.0 is the thickest node in the tree.                                                                                                                                                                                                                                                                                                                    |
| **point_attribute_vigor**              | point  | float | The growth power of the branch.                                                                                                                                                                                                                                                                                                                                                                                              |
| **point_attribute_photosynthesis**     | point  | float | The combined photosynthesis, which is the exposure to light multiplied by the leaf area of every branch end attached to this node. Photosynthesis travels towards the base of the tree, and with every joining branch it quickly adds up. To get the photosynthesis values into a useful range for shading, divide the attribute by somwhere between 100 to 1000, depending on the size of the tree. Clamp values above 1.0. |
| **point_attribute_pitch**              | point  | float | Vertical orientation of the branch, where 0.0 means facing down, 0.5 horizontal, and 1.0 facing up.                                                                                                                                                                                                                                                                                                                          |












#the grove/the grove core/python api#