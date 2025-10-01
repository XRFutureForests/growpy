# Install


## First install the core

  1. Get **The Grove 2.2 Core** and unzip the package.
  2. Place the folder **the_grove_22** somewhere you can easily access it in the future – it provides a folder structure that is ready to be filled with twigs, bark textures, presets and add-ons. This is the suggested structure that will work great for most users.
  3. Let’s take a look inside:

  * The **addons** folder is where you’ll later unzip both the Blender or Houdini add-on.
  * At the core of The Grove is the Python module that simulates trees and builds the 3D models. The add-ons provide two very different user interfaces for the same module. **The Grove Core** resides is in the **modules** folder.
  * Tree species are stored as JSON files in the **presets** folder that the Core and the two add-ons all use together.
  * Bark textures are image files that can be unzipped to the **textures** folder.
  * Twigs packages can be unzipped in the **twigs** folder, where the files of each twig would reside in a separate sub folder like Ash, Willow or Oak.


## Install the Blender add-on

The Blender add-on uses the core module, adds a user interface and a bunch of awesome tools for interactive simulation. The Blender add-on works in Blender version 4.2 LTS, 4.3 and 4.4.
  1. Go to where you just installed the core.
  2. Unzip **The Grove in Blender** and place it in the **addons** folder.
  3. Open Blender, and add a new script directory in `Edit > Preferences > File Paths > Script Directories`. Point it to the location of **the_grove_22** like so:
  4. **Restart Blender** and enable the add-on in `Edit > Preferences > Add-ons`.
  5. When using the default structure of **The Grove Core** , it will automatically find the twigs, textures and presets folders, and you’re good to go!
  6. Optionally you can expand the preferences to configure different paths. Or for a studio setup, you can configure the paths using `config.json` in the root folder of the add-on. When no path is set in the preferences, it first checks the `config.json` file, and the fallback is the default folder structure. A user can override all this by providing their own paths.

To check your installation, you should see the tab `Grove 2.2` in the 3D view sidebar.


## Install the Houdini add-on

The Houdini add-on uses the core module and plugs it into Houdini’s procedural node network to grow and build trees that are ready for Houdini’s dynamics. Available with the Studio edition, the Houdini add-on works on Windows, Linux and macOS, in Houdini versions 19.5 and up, with Python versions 3.7 and up. And it will probably even work in future versions.
  1. Go to where you just installed the core.
  2. Unzip **The Grove in Houdini** and place it in the **addons** folder.
  3. Find your `$HOUDINI_USER_PREF_DIR`. The default location is `~/Library/Preferences/houdini/20.5` on macOS, `C:\Users\user_name\Documents\houdini20.5\` on Windows, or `~/houdini20.5/` on Linux.
  4. In `$HOUDINI_USER_PREF_DIR`, find the **packages** folder or create it if it doesn’t exist yet (mind the lower case name). Copy the file `the_grove_22_in_houdini.json` from `the_grove_22/addons/the_grove_22_in_houdini/` to this **packages** folder.
  5. Edit this configuration JSON file and point `THEGROVE22` to the path to **the_grove_22**. If you use the default folder structure, it will find both the add-on and the core module. You’re good to go.

To check your installation, first restart Houdini. Inside a new geometry node, the TAB menu should now include a section for `The Grove`. Try `the_grove_example.hip` to see how you can wire up the nodes.
