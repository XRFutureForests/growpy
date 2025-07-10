# React

_Set up an environment to attract, deflect, or stop new branches as they grow. Avoid a building, or let it cast shade. Or get creative and grow inside a shape!_


## Forces of nature

So far, the shape of your 3D tree has been based on genetics. Now it’s time to add a second influence: the environment it grows in. With _React_ , you can use any mesh object as an environment. Set it up to avoid buildings, simulate a dominant wind direction and grow inside a shape. There are 4 effects in which an object can influence growth. You can combine multiple types of react objects to simulate many effects.
  * It can _Block_ growth when a branch hits its surface.
  * It can _Deflect_ growth when a branch gets closer.
  * It can _Shade_ growth – the tree reacts by bending away, toward light.
  * It can also _Attract_ growth, as if it were a light.

This is a good place to clear up a common misconception. Plants do not grow towards direct sunlight. If they did, they would all lean south. They would soon lose balance, as gravity would not be in their favor. Plants bend only to indirect sunlight, the light bouncing around the sky all around us. It is the sky’s blue color that a plant senses and loves.


## Environment objects

Use the 4 pickers to pick objects for each reaction type – _Block_ , _Attract_ , _Deflect_ and _Shade_. A simple mesh object with just several polygons can have a striking effect. Or use the stylized shape of a building to avoid it. Use complex shapes to create a topiary.

The _Attract_ and _Deflect_ interaction types have a _Radius_ of influence. When a branch grows within this proximity, it gets influenced by the object. The closer it gets, the more powerful this effect becomes. The _Strength_ parameter multiplies this influence.

Environments are not static. Surrounding trees come and go, changing the tree’s exposure to light and wind. Try enabling interaction for just the last years, to simulate a windswept tree. Or even use an animated object to make the growing tree follow it.

![](https://www.thegrove3d.com/wp-content/uploads/2019/10/Release8React.jpg)


## Example file

Here’s an example file that perfectly illustrates the possibilities of the react system. In the file, two trees grow together to fill up the shape of the number 8. This uses a balance between block, attract and deflect. The trees are not only pruned, they also flow beautifully by following the curves of the shape.

In reality, a shape like this would need some kind of a support structure. For this simulation, I have simply disabled bending. This is an important step if you want to grow shapes like these.

This file also has _Record_ enabled, to record the yearly growth as an animation.

To start using this file, first click _Restart_. This is necessary because the simulation data isn’t available on your computer yet. Then click _Grow_ , and continue growing until the shape is filled fully.

[TheGrove11ReactExample.zip (for release 11)](https://www.thegrove3d.com/wp-content/uploads/2020/01/TheGrove11ReactExample.zip)

Your browser does not support the video tag.
