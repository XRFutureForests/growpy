# Simulation files

Simulations are saved within the working .blend file (and the .hip file for Houdini). In Blender, the simulation is attached to the current grove collection. And in Houdini, the simulation is passed along from node-to-node as a detail attribute.

This makes the simulation portable, as it moves with the working file. A copy of a grove collection in Blender also automatically copies the simulation with it. The new copy can be grown independently from the old original. It also play nice with Blender’s undo system.

The simulation data is stored as a json string. If you want to store the simulation in an external file, you can do so. Files are a good way to stash trees for later use, or to transfer trees between Houdini and Blender. In Blender, you can import and export simulations in .grove files using the File operator. In Houdini, you can use the Grove Import and Grove Export nodes.

Note that the external file has a .grove extension, but it is in fact a zipped json file (.json.zip). You can rename it, then unzip it – the resulting .json file is a simple text file that is easy to work with, just very long.
