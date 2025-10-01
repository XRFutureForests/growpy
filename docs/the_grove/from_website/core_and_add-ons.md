# Core and add-ons

The Grove Core is not a traditional standalone application in the sense that it does not have its own UI. Add-ons for Blender and Houdini add two completely different user experiences, right inside your favorite 3D app.

The natural simulation runs in the independent Core module. Tree growth is powered by this high-performance library written in Rust, a language known for its speed and stability, to allow you to grow trees fast and without compromise. The Core is compiled as a Python library module that runs on Windows, Linux and macOS.

The Core does all the hard work, from growing your trees, to ray-traced shade calculation, to physical wire simulation, to building the finished 3D models including UVs and attributes. The modular Core is also built for portability – both the Blender add-on and the Houdini add-on both use the same core – all that is left for a new target application is high-level functionality and UI. The Core is portable to any app with a Python API, starting with Blender and Houdini.

So here we are with the powerful core and two add-ons:


### Python

![Python code showing scripted growing with the Core API.](https://www.thegrove3d.com/wp-content/uploads/2024/09/core_module_vertical.jpg)

The Grove Core is the compiled Python module that runs the simulation. Add-ons can import the same module into any application with a Python API, or you can even import the core into Python itself.


### Blender

![UI of the Blender add-on.](https://www.thegrove3d.com/wp-content/uploads/2024/09/blender_addon_vertical.jpg)

The Grove in Blender adds a bunch of awesome tools for interactive simulation – grow, prune, draw, react, add wind… with 8 years of polish, and still improving.


### Houdini

![The Houdini add-on has a node based workflow.](https://www.thegrove3d.com/wp-content/uploads/2024/09/houdini_addon_vertical.jpg)

The Grove in Houdini plugs into Houdini’s procedural node network to grow and build trees that are ready for Houdini’s dynamics. Available now with the Studio edition.
