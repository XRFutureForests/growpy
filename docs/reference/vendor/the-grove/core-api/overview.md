# the_grove_core


## Python API

The Grove Core is built as a Python module. This makes it flexible to work with and to integrate into your pipeline. Growing trees from Python is for experienced developers - if you just want to grow trees, look at the Blender add-on.



Let’s dive in with an example of growing a 10 year old tree, building a model, and saving it to an obj file in just 8 lines of code:
```python
import the_grove_core
grove = the_grove_core.Grove()
grove.simulate(10)
models = grove.build_models({resolution: 32})
obj_string = the_grove_core.io.model_to_obj_string(models[0])
obj_file = open('test.obj'), 'w')
obj_file.write(obj_string)
obj_file.close()
```



Scripting this way, you can simulate a couple of years, change the growth properties, keep growing, prune, smooth, grow some more years, build the model and save to different formats.




## The first steps

If you already installed The Grove in Blender, then the module will already be available in Blender’s scripting window and Python shell, good to go. But Blender uses its own Python interpreter, different from your system’s Python. If you’re using the_grove_core in a project separate from Blender, make sure to put the modules somewhere that the system Python interpreter can find them.



The first line in the example imports `the_grove_core_macos`, which works on Apple silicon Macs. Make sure you import the correct library for your OS - either `the_grove_core_linux`, `the_grove_core_windows`, `the_grove_core_macos` or `the_grove_core_macos_intel`.



Alternatively, you can copy the library for your OS and rename it to `the_grove_core.so` (or `the_grove_core.pyd` on Windows). Now you can simply `import the_grove_core`.
  * From release 2.2, the separate modules are now wrapped in a parent module that makes it easy to import the module across system architectures and operating systems, simply `import the_grove_23_core` and the appropriate module is dynamically loaded.




## The Grove in Blender

The Blender add-on is written in Python, and uses the_grove_core to grow the trees. This part of the code is open source and is a good inspiration for how to use the API.



There’s a good chance that you want to combine the Blender add-on with your own Python code, extending the add-on’s functionality or analyzing the grown trees with your own script. You can access trees that you’ve grown in the add-on in Blender’s scripting window - an example of how to do this is in [the_grove_core.io](./the_grove_core.io.html).




## Gotcha!

Before you start scripting, there is one big gotcha for The Grove Core's Python API. This Python module is written in the Rust programming language. Now Python and Rust do not agree on ownership of data. Python doesn’t mind you changing anything whenever you like, while Rust is very, very protective. What this means is that you have to use get and set methods to make changes.



For example: `trees = Grove.trees` in Python creates a copy, as does `branch.nodes[4].side_branches[0]`.



You would expect `branch.nodes[4].side_branches[0].dead = True` to work, but it will instead create a copy of the side branch and set that branch object to be dead. The original branch will not be changed. Confusing, so try to keep this in mind.



Here’s an example of how to change growth properties:
```python
grove = the_grove_core.Grove()
props = grove.get_properties()
props.grow_nodes = 5
props.favor_bright = 0.7
grove.set_properties(props)
```




## Sub modules

[the_grove_core.Node](./the_grove_core.Node.html)
[the_grove_core.Branch](./the_grove_core.Branch.html)
[the_grove_core.Model](./the_grove_core.Model.html)
[the_grove_core.Node](./the_grove_core.Node.html)
[the_grove_core.Skeleton](./the_grove_core.Skeleton.html)
[the_grove_core.Rotation](./the_grove_core.Rotation.html)
[the_grove_core.Vector](./the_grove_core.Vector.html)
[the_grove_core.Randomizer](./the_grove_core.Randomizer.html)
[the_grove_core.RayTree](./the_grove_core.RayTree.html)
[the_grove_core.io](./the_grove_core.io.html)
[the_grove_core.about](./the_grove_core.about.html)
[the_grove_core.tree_math](./the_grove_core.tree_math.html)



#the grove/the grove core/python api#