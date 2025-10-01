# [the_grove_core](./the_grove_core.html).Vector

An (X, Y, Z) vector class with all the math needed to grow trees. Written from scratch, purpose-built for The Grove.




### Operators

You can use regular math operators like +, -, / and * with Vector objects.




### angle(b)  Vector

Calculate the angle (in radians) between this vector and vector b.



Parameters:
  * b (Vector)




### cross(b)  Vector

The cross product between this Vector and Vector b. The cross product is used to create a vector that is perpendicular to both input vectors. The perpendicular vector is ofte used as an axis of rotation.




### dot(b)  Vector

Vector dot product.




### as_tuple()  tuple

Return a tuple of 3 floating point numbers from a Vector’s x, y and z components.




### flip_y_z()  Vector

Return a new Vector in y-up coordinate space, the new vector becomes (x, z, -y).




### length()  float

Returns the length (or magnitude) of this Vector.




### lerp(b, amount)  Vector

Linear interpolation from this vector to vector b. This function is useful for interpolating coordinates in 3D space, while **slerp** (spherical linear interpolation) is used for interpolating directions.



Parameters:
  * b (Vector) - the Vector to interpolate towards.
  * amount (float) - from 0 to 1, the amount of interpolation, where 1 will result in vector b.




### normalized()  Vector

Set the magnitude or length of the vector to 1 while keeping the same direction. Note that it does not change this Vector, but instead returns a new, normalized Vector.




### slerp(b, amount)  Vector

Spherical linear interpolation - rotate the direction of this vector toward the direction of vector b.



Parameters:
  * b (Vector) - the vector to rotate towards.
  * amount (float) - from 0 to 1, the amount of rotation, where 1 will rotate this vector fully to the direction of vector b. This keeps the magnitude (length) of the original vector, unlike the **lerp** (linear interpolation) function.




### Vector(x, y, z)  Vector

Create a Vector to represent a position or direction in 3D space. A Vector can be manipulated with a range of math functions.



Parameters:
  * x (float) - X-coordinate
  * y (float) - Y-coordinate
  * z (float) - Z-coordinate




#the grove/the grove core/python api#