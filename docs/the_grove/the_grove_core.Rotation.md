# [the_grove_core](./the_grove_core.html).Rotation

A high level rotation quaternion class. Written from scratch, purpose-built for The Grove. Here’s an example:
```python
from the_grove_core import Rotation, Vector
from the_grove_core.tree_math import PI
direction = Vector(1.0, 0.0, 0.0)  # Pointing to +X

axis = Vector(0.0, 0.0, 1.0)  # Z-axis

rotated_direction = Rotation(axis, PI).rotate_vector(direction)
```



In this example, rotated_direction will point in the direction of the negative X-axis. The angle is in radians, and PI is 180 degrees.
The Grove uses a right-hand coordinate system with the Z-axis pointing up. Take your right hand and point your thumb to the positive axis you are rotating around. Your other 4 fingers now point the way that a positive angle rotates.




### identity()  Rotation

Create a zero-rotation quaternion that does nothing.




### from_axis_angle(axis, angle)  Rotation

Create a rotation quaternion with an axis and an angle to rotate along that axis. Later you can use Rotation.rotate_vector(vector) to apply the rotation to a Vector object.
  * axis (Vector) - The axis vector to rotate around.
  * angle (float) - The angle of rotation.




### from_vector_to_vector(from, to)  Rotation

Create a rotation quaternion with the shortest rotation from direction A to direction B.
  * from (Vector) - Todo…
  * to (Vector) - Todo…




### z_axis_angle(angle)  Rotation

TODO…
  * angle (float) - Todo…




### from_right_to_vector_z_up(to)  Rotation

Project the to-vector to the floor (X,Y-plane) and calculate the angle between the two. This is the Y-rotation. Then get the angle between a vector pointing right in the X-axis direction, to the projected vector. This is the Z-rotation. Stack the two rotations to get a unified rotation quaternion.
  * to (Vector) - Todo…



#the grove/the grove core/python api#