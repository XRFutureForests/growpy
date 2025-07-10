# [the_grove_core](./the_grove_core.html).Skeleton

Use `Grove.build_skeletons` to build a list of skeletons, one for each tree.
  * Skeleton.points `[(float, float, float)]` \- a list of tuples that represents the coordinates of the bone joints.
  * Skeleton.poly_lines `[[int]]` \- a list where each element is a list of integers that connects the joints in `Skeleton.points`.
  * Skeleton.location `(float, float, float)` \- the origin point of the skeleton.



Here’s a quick example on how to get a skeleton.
```python
import the_grove_core_macos as gc

grove = gc.Grove()
grove.simulate(3)
skeletons = grove.build_skeletons()
skeleton = skeletons[0]
```




## Attributes

| Attribute                    | Domain | Type  | Description                                                                                                                                                                                                              |
|------------------------------|--------|-------|--------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| **face_attribute_branch_id** | face   | int   | A list of integers, one for each poly_line in Skeleton.poly_lines. This is the unique ID that matches a poly_line in `Skeleton.poly_lines` to a tree model’s `branch_id` attribute (`Model.face_attribute_branch_index`) |
| **point_attribute_age**      | point  | int   | Number of flushes that the node has been around for.                                                                                                                                                                     |
| **point_attribute_mass**     | point  | float | Total mass of the attached remainder of the branch. So the first node in the tree will have the full tree’s mass.                                                                                                        |
| **point_attribute_radius**   | point  | float | Radius of the branch node.                                                                                                                                                                                               |



#the grove/the grove core/python api#