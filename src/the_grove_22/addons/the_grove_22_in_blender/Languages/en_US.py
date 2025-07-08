# coding=utf-8

dictionary = {

    "": "",

    # Panel titles
    "panel_presets": "Preset",
    "panel_twigs": "Twig",
    "panel_twigs_more": "More",
    "panel_simulation": "Simulation",
    "panel_react": "React",
    "panel_favor": "Favor",
    "panel_drop": "Drop",
    "panel_add": "Add",
    "panel_grow": "Grow",
    "panel_turn": "Turn",
    "panel_thicken": "Thicken",
    "panel_bend": "Bend",
    "panel_shade": "Shade",
    "panel_build": "Build",
    "panel_build_wind": "Wind",
    "panel_build_mesh": "Detail",
    "panel_build_texture": "Texture",


    # User preferences
    "set_presets_path": "Set Presets Folder...",
    "presets_path": "Presets Folder",
    "presets_path_tt":
        "Select the folder where you store presets. All presets in this folder will appear in the presets picker.",

    "set_twigs_path": "Set Twigs Folder...",
    "twigs_path": "Twigs Folder",
    "twigs_path_tt":
        "Select the folder where you store twigs. All twigs in this folder will appear in the twig picker.",

    "set_textures_path": "Set Textures Folder...",
    "textures_path": "Bark Textures Folder",
    "textures_path_tt":
        "Select the folder where you store bark textures. All textures in this folder will appear in the bark texture picker.",

    "widget_scale": "UI Widget Scale",
    "widget_scale_tt":
        "Adjust the size of the radial UI widgets if they appear too small or big on your screen.",


    # Interface messages
    "remove_preset_info": "Remove {}?",
    "overwrite_preset_info": "Overwrite {}?",
    "name_preset_info": "Name your preset.",
    "height_info": "{:.1f} m",
    "age_info": "{} flushes",
    "branch_info": "{} branch",
    "branches_info": "{:,} branches",
    "polygons_info": "{:,} faces",
    "tips_info": "Please read tooltips:",


    # Presets
    "presets_menu": "",
    "presets_menu_tt": "Load preset parameters of tree species",

    "preset_name": "New Name",
    "preset_name_tt": "Name of the preset to save or overwrite",

    "remove_preset": "Remove",
    "remove_preset_tt": "Remove this preset",

    "cancel_action": "Cancel",

    "remove_preset_confirm": "Remove",
    "remove_preset_confirm_tt": "Confirm to remove this preset",

    "rename_preset": "Rename",
    "rename_preset_tt": "Rename this preset",

    "add_preset": "Add",
    "add_preset_tt": "Add a new preset, or overwrite the preset if the name already exists.",

    "overwrite_preset": "Overwrite",
    "overwrite_preset_tt": "Overwrite this preset",

    "overwrite_preset_confirm": "Overwrite",
    "overwrite_preset_confirm_tt": "Confirm to replace and overwrite this preset",

    "save_preset": "Save",
    "save_preset_tt": "Save the adjusted parameters as a preset",

    "import_preset": "Import...",
    "import_preset_tt":
        "A preset is stored in a .seed.json file that you can share with others - "
        "import one to add it to your list of presets.",


    # Simulate
    "simulation_scale":
        "Scale",
    "simulation_scale_tt":
        "Adapt a preset to a different twig size. "
        "An average twig contains one or two years of growth and is around 30cm long. "
        "A preset is designed to match this size. But twig models can be any size you want, from a single leaf up to several years of growth. "
        "The way to match a different size twig is to simply scale the branch model up or down, while keeping the twigs at the original, real life scale.",

    "simulation_flushes": "Flushes",
    "simulation_flushes_tt":
        "Number of years to grow. "
        "Simulate the growth of your tree in small, interactive steps. "
        "After each step you can guide your tree by pruning it, or adjusting its parameters.",

    "simulate": "Grow",
    "simulate_tt":
        "Simulate the natural growth of trees.",

    "restart": "Restart",
    "restart_tt":
        "Tweaking the character of your tree requires experimentation. "
        "Grow, tweak, restart, repeat... that's the way to grow a tree. "
        "Double click for more options.",

    "manual_prune": "Prune",
    "manual_prune_tt":
        "Draw cutting lines to remove or shorten branches.",

    "zoom": "Zoom",
    "zoom_tt": "Double click to walk around your trees.",


    # Favor
    "favor_end": "End",
    "favor_end_tt":
        "Add shorter, less vigorous side branches to promote longer growth from the tip of the branch.",

    "favor_end_reduce": "Reduce",
    "favor_end_reduce_tt":
        "Reduce the effect of favor ends when the branch grows at an angle from vertical.",

    "favor_bright": "Bright",
    "favor_bright_tt":
        "Leaves evaporate water when exposed to light. This creates a steady flow of water from the roots to the leaves. "
        "This flow is strongest on the brightest and leafiest branches that evaporate most water. "
        "The roots celeverly use this to distribute a growth promoting hormone that targets the most successful branches. "
        "Favor Bright simulates the tree's sensitivity to this hormone.",
    
    "favor_rising": "Rising",
    "favor_rising_tt":
        "Favor branches growing upright, over branches growing down. "
        "Boost upward growing branches to get a towering tree. "
        "A value of 1 will go as far as to reduce the vigor of horizontal branches to zero.",


    # Auto-prune tool
    "panel_auto_prune": "Auto Prune",

    "auto_prune_enabled": "Auto Prune",
    "auto_prune_enabled_tt":
        "Automatic, yearly pruning of side branches that clears the base of the tree. "
        "This provides clear views, and allows free passage of people and traffic. "
        "Drop low hanging branches damaged by ground frost. And lose branches to foraging animals. "
        "This pruning is done automatically every year.",

    "auto_prune_low": "Low",
    "auto_prune_low_tt":
        "Auto prune is a yearly pruning of low growing side branches to clear the base of the tree. This pruning gradually kicks in as the tree grows taller, "
        "and to keep the tree healthy, it only ever prunes up to one third the height of the tree.",

    "auto_prune_keep_thick": "Keep Thick",
    "auto_prune_keep_thick_tt":
        "Only prune thinner branches, and keep the thicker ones. "
        "This will allow the tree to grow several big main branches, giving your tree a more natural look - "
        "a look that landscapers aim for when pruning trees that have more space, like in a park. "
        "This happens in nature too, where foraging animals prefer the juicy fresh branches and leave the thick ones be.",

    "auto_prune_dangling": "Dangling",
    "auto_prune_dangling_tt":
        "Branches just above the auto prune height continue growing to the sides and bend down with the increased mass. "
        "These dangling branches can be left to grow like in a weeping willow, or you can trim them back to a set height.",

    # Drop
    "drop_shaded": "Shaded",
    "drop_shaded_tt":
        "Drop shaded branches. "
        "Each year a tree grows countless new branches in all directions. "
        "These sensitive branches explore new space and search for light. "
        "The tree will then invest its energy in the branches that recieve the most light, and it will drop the many shaded ones. "
        "Decrease this value to keep more branches and grow a denser tree, or increase it to drop progressively brighter branches and grow a more transparent and open tree.",

    "drop_obsolete": "Obsolete",
    "drop_obsolete_tt":
        "As the tree grows, lower branches get shaded and small branches drop. "
        "Old main branches will be thicker than needed to support their diminishing foliage. "
        "Unable to support this excess wood, the branch will eventually become obsolete, rot and drop. "
        "This also happens after heavy pruning.",

    "drop_weak": "Weak",  # Futile, Inefficient, Draining, Ineffective, Unproductive, Unsustainable, underperforming
    "drop_weak_tt":
        "As trees grow up, toward the sky, they compete with their neighbors that take away light. "
        "But the biggest competition is the very tree itself, where new leaves above shade the old underneath. "
        "A branch becomes weak when there is too much branch with too little light.",

    "drop_decay": "Decay",
    "drop_decay_tt":
        "The decay rate controls how fast dead branches decompose and crumble off. "
        "Dead wood sticks around and adds to the character and the story of the tree. "
        "Slow decay can be seen along the trunks of many conifer trees.",

    # Add
    "add_side_branches": "Buds",
    "add_side_branches_tt":
        "The number of buds per node directly influences the geometric arrangement of branches, with alternate, opposite, "
        "and whorled patterns corresponding to one, two, and three to six buds, respectively. "
        "The growth vigor together with chance determines how many of these buds will actually develop into new branches.",

    "add_chance": "Chance",
    "add_chance_tt":
        "Chance that a young node creates a new branch. "
        "Not all buds will open and grow a new branch. "
        "Some are damaged by frost or insects, others are suppressed by Favor End.",

    "add_chance_reduce": "Reduce",
    "add_chance_reduce_tt":
        "Reduce the chance of adding side branches to less vigorous branches. "
        "Adding less side branches will make these branches build up less thickness, "
        "and thinner branches bend more under gravity.",

    "add_bud_life": "Bud Life",
    "add_bud_life_tt":
        "On most species, buds only survive a couple of years. "
        "Buds up to this age are viable for growing a new twig. "
        "On others, almost every bud opens and forms mostly a very short twig that is restricted by apical dominance. "
        "Most of these will soon be gone, while few of them escape the repression and grow into new branches.",

    "add_only_on_end": "Only on End",
    "add_only_on_end_tt":
        "Only add new branches to end nodes. "
        "Trees like conifers suppress lateral growth with hormones. "
        "Effectively this means that only nodes that are very close to the tip are free of hormones and are able "
        "to form new branches.",

    "add_fork": "Fork",
    "add_fork_tt":
        "When a branch is particularly strong and grows vigorously, it can develop several buds near "
        "the tip that can overpower the tip bud. The branch then splits into several equally vigorous branches. "
        "Without a dominant branch in the middle to push them to the sides, the forking branches grow at half the regular angle. "
        "Instead of forming a clear single trunk, a forked tree creates a spreading structure of main branches.",

    "add_regenerate": "Regenerate",
    "add_regenerate_tt":
        "Regenerative shoots will form after heavy pruning or natural damage further along the branch. "
        "With less foliage to support, the energy in the excess wood gives rise to regenerateive shoots, to repair the tree and to fill in the gaps. "
        "Not all trees can grow regenerative shoots, like most conifers. Because of this, these species do not respond well to pruning.",

    "add_horizontal": "Horizontal",
    "add_horizontal_tt":
        "Plagiotropism for buds. "
        "Turning of the phyllotaxis angle towards a horizontal orientation.",

    "add_angle": "Angle",
    "add_angle_tt":
        "The angle between the existing branch and a newly added side branch.",

    "add_up": "Up",
    "add_up_tt":
        "A new side branch starts in an upward direction. Use negative values to grow downward instead.",

    "add_twist": "Twist",
    "add_twist_tt":
        "Twist each successive node. "
        "Species like Horse Chestnut have very visible twisting along the length of their branches, "
        "you can clearly see the bark pattern swirling up around the trunk. "
        "Apart from the obvious visual quality, twisting also adds to the phyllotaxic rotation of buds. "
        "This improves branch distribution on trees with opposite branching.",

    "add_planar": "Planar",
    "add_planar_tt": "Similar to turning horizontal, but now new branches sprout planar to the growth direction.",


    # Grow
    "grow_length": "Length",
    "grow_length_tt":
        "A vigorous branch grows by this length with each flush. "
        "Weaker branches will grow shorter.",

    "grow_nodes": "Nodes",
    "grow_nodes_tt":
        "The maximum number of nodes that a branch can grow each year. "
        "Less vigorous branches will grow less nodes.",


    # Turn
    "turn_up": "Up",
    "turn_up_tt":
        "Negative gravitropism. Turn new growth up and away from gravity. "
        "Use negative values to grow downward instead.",

    "turn_up_in_shade": "Up in Shade",
    "turn_up_in_shade_tt": "Turn shaded growth up and away from gravity. Use negative values to grow downward instead.",

    "turn_to_light": "To Light",
    "turn_to_light_tt":
        "Phototropism. "
        "Turn new growth toward the brightest direction. "
        "This is the effect that makes a houseplant grow toward a window. "
        "In a tree, this effect will improve the distribution of branches.",

    "turn_to_horizon": "Horizontal",
    "turn_to_horizon_tt":
        "Plagiotropism. "
        "Turn new growth toward the horizontal plane when a branch is shaded.",

    "turn_random": "Random",
    "turn_random_tt":
        "The branch is free to move in random, uncontrolled directions - unguided by light or gravity.",


    # Interact
    "react_enabled": "React",
    "react_enabled_tt":
        "Use mesh objects to attract, deflect or stop new growth. "
        "Make a building cast shade, or get creative and grow trees within shapes.",

    "react_block_object": "Block",
    "react_block_object_tt":
        "Stop growing after colliding with this object.",

    "react_shade_object": "Shade",
    "react_shade_object_tt":
        "This object blocks light, as in the case of a building or perhaps a rock formation. "
        "Watch how your trees react to challenging conditions, and how they gravitate toward light.",

    "react_deflect_object": "Deflect",
    "react_deflect_object_tt": "Avoid this object.",

    "react_attract_object": "Attract",
    "react_attract_object_tt":
        "Grow towards this object. "
        "Branches can freely grow through this object.",

    "react_vigor_object": "Vigor",
    "react_vigor_object_tt":
        "Select an object that controls the vigor of new growth.",

    "react_force": "Force",
    "react_force_tt":
        "The magnitude of the force that the object exerts on the tree.",

    "react_falloff": "Falloff",
    "react_falloff_tt":
        "The effect is strongest close to the object, and decreases exponentially with distance from the object.",


    # Thicken
    "thicken_tips": "Tips",
    "thicken_tips_tt":
        "The thickness, or diameter, at the growing tip of a vigorous branch.",

    "thicken_tips_reduce": "Reduce",
    "thicken_tips_reduce_tt":
        "Reduce the thickness of growing tips on less vigorous branches. "
        "Thinner growth is more flexible, which greatly affects the shape of the tree. "
        "This is particularly important for droopy conifers, which tend to suppress the vigor of side branches.",

    "thicken_join": "Gain",  # Merge, Join, Combine.
    "thicken_join_tt":
        "Thickness begins at the tip of the branch, and with each junction of two or more branches, "
        "their cross sections join to create a stronger, thicker branch. "
        "This process continues down to the base of the tree. "
        "Varying the rate of growth in thickness will significantly change the shape of the tree. "
        "The added thickness will reinforce the branches and reduce bending.",

    "thicken_base_scale": "Scale",
    "thicken_base_scale_tt":
        "Increase the thickness at the base of the tree.",

    "thicken_base_shape": "Shape",
    "thicken_base_shape_tt":
        "Tweak the shape of Root Scale easing into the trunk.",

    "thicken_base_buttress": "Buttress",
    "thicken_base_buttress_tt":
        "Multiply the Base Scale with root protrusions. "
        "Buttress roots are protrusions along the base, mainly found in tropical trees.",

    "root_distribution": "Distribution",
    "root_distribution_tt":
        "Reach of the Root Scale effect over the trunk.",

    "thicken_deadwood": "Deadwood",
    "thicken_deadwood_tt":
        "When branches are dropped or pruned, the tree will partially heal the wound, "
        "but a small portion of the core will die. The tree will compensate for this "
        "by adding more thickness to the new growth. This process, over time, will "
        "result in a thicker trunk.",


    # Bend
    "bend_mass": "Down",
    "bend_mass_tt":
        "Amount of bending due to branch weight. "
        "How much each branch bends depends on its mass, and its thickness. "
        "Thicker branches weigh more, but their increased cross sections make them exponentially stronger in their fight against gravity. "
        "Bending of branches has a significant impact on the shape of trees, especially when they grow older.",

    "bend_twig_mass": "Twig Mass",
    "bend_twig_mass_tt":
        "The mass attached to each branch tip, which includes a twig's wood, its leaves and fruit. "
        "Trees try to counter this turning new growth upward. "
        "This interplay between bending down and growing upward plays an important role in the formation of either a fastigiate or a weeping tree character.",

    "bend_twig_mass_solidify": "Solidify",
    "bend_twig_mass_solidify_tt":
        "Solidify the bending caused by the weight pulling down on branch tips. "
        "Twig mass varies with the seasons - heavy spring flowers, "
        "big leaves and chunky fruit all pull the branch down. "
        "But when the time comes that the branch grows solid, most of this mass may already have dropped.",

    "bend_reaction": "Up",
    "bend_reaction_tt":
        "Reaction wood enables branches that rapidly grow thicker to actively bend back upward over time. "
        "The effect intensifies as the branch deviates further from a vertical growth direction. "
        "Tilted trees can return to vertical, and vigorous side branches can take over as the new leader.",


    # Shade
    "shade_area": "Leaf Area",
    "shade_area_tt":
        "Area of the combined foliage at the end of each branch, in dm² (10cm x 10cm). "
        "Foliage at the top of the tree's canopy will cast shade on the branches further down the tree.",

    "shade_area_reduce": "Reduce",
    "shade_area_reduce_tt":
        "Decrease the leaf area on less vigorous branches.",

    "shade_area_depth": "Depth",
    "shade_area_depth_tt":
        "Raise the sides of the light-blocking leaf areas to give more depth the shape. "
        "This will cause more shade from the sides of the tree, and more shade in general.",

    "tweak": "Tweak",
    "tweak_tt": "Tweak these parameters with visual feedback in the viewport.",

    "shade_leaf_sides": "Sides",
    "shade_leaf_sides_tt":
        "Also distribute shadow casting leaf areas along the sides of branches. "
        "Most trees can be simulated with just the leaves at the branch tips, a small abstraction that works well. "
        "But on trees with weeping branches, side twigs are needed. Do note that you need a smaller leaf area with this, "
        "because more twigs will be placed.",

    "shade_branches": "Branches",
    "shade_branches_tt": "Most shade comes from leaves, and for some trees you can include the branch geometry in the shade calculation.",
    "shade_alongside": "Alongside",
    "shade_alongside_tt": "In addition to newly grown twigs, trees like pines have old needles alongside their branches.",
    "shade_alongside_diameter": "Diameter",
    "shade_alongside_diameter_tt": "Diameter of shade casting geometry alongside branches.",

    "shade_branches_panel": "Branches",
    "shade_leaves_panel": "Leaves",


    # Build
    "rebuild": "Rebuild",
    "rebuild_tt":
        "Rebuild the 3D models of your trees to update polygon reduction, attributes and the distribution of twigs.",

    "build_resolution": "Resolution",
    "build_resolution_tt":
        "The number of vertices at the base of the tree, where it is at its thickest.",

    "build_resolution_reduce": "Reduce",
    "build_resolution_reduce_tt":
        "Reduce polygons on thinner branches. "
        "Most of a tree's polygons are in its thousands of young branches. "
        "These thin branches can do with less polygons without loosing visual quality.",

    "smooth": "Smooth",
    "smooth_tt":
        "Reduce the angle of sharp corners to create more smoothly curving branches.",

    "texture_bark": "Bark",
    "texture_bark_tt": "Pick a texture",

    "texture_repeat": "Repeat",
    "texture_repeat_tt":
        "The number of times to repeat the bark texture around the girth of the tree base, which is automatically reduced on thinner branches.",


    # Twigs
    "twig_menu": "Twigs",
    "twig_menu_tt":
        "Pick a set of twigs to add them to your tree. "
        "This menu lists every twig it can find in the twigs folder - you can select a folder in Grove's user preferences. "
        "Or you can also pick objects from the current scene.",

    "twig_pick_objects": "Scene Objects",
    "twig_pick_objects_tt": "Pick any 3D object in the scene.",

    "twig_pick_collections": "Collections",
    "twig_pick_collections_tt": "Pick any collection of twig objects in the current file.",

    "twig_no_twigs": "None",
    "twig_no_twigs_tt": "No twigs",

    "twig_object_end": "Long",
    "twig_object_end_tt":
        "Twig object to distribute at branch tips. "
        "End twigs are fresh new growth with leaves and sometimes flowers and later fruit. "
        "End twigs are extensions to existing branches - often more vigorous and longer than side twigs.",

    "twig_object_side": "Short",
    "twig_object_side_tt":
        "New side twigs growing alongside existing branches are often shorter than the elongating twigs at branch ends. "
        "This object will be distributed mostly along the sides of branches, and also on weaker growing branch ends. "
        "Side twigs are fresh new branches that develop along the sides of existing branches. "
        "They carry leaves, and sometimes flowers and later fruit. "
        "Side twigs are often shorter than end twigs, caused by hormonal suppresion of the lead branch that created them. "
        "Only the strongest will eventually grow into full new branches.",

    "twig_object_upward": "Upward",
    "twig_object_upward_tt":
        "Twig model that grows steeply upward nearing the vertical. "
        "Upward twigs are strong growers and are often even longer, with their leaves twisting around in every direction. "
        "This twig is optional and if no twig is selected, it will use a long twig instead.",

    "twig_object_dead": "Dead",
    "twig_object_dead_tt":
        "Model of a weak or dead twig. "
        "This twig is optional and can be used to add detail to the weaker parts of a tree.",

    "twig_wither": "Wither",
    "twig_wither_tt":
        "Number of years (after 'Life') that dead twigs stick around and wither on the tree. "
        "Rebuild to see the effect.",

    "twig_density": "Density",
    "twig_density_tt":
        "Control the density of your tree's foliage by adding more or less side twigs. "
        "This also affects the density of dead twigs. "
        "End twigs are unaffected and are always added to every living branch tip.",

    "twig_view_detail": "View Detail",
    "twig_view_detail_tt":
        "To improve viewport performance, the display resolution is reduced by adding a 'Decimate' modifier to each twig model."
        "Viewports will use the modified, low-resolution model, while render engines will use the original.",

    "twig_hide": "",
    "twig_hide_tt": "Hide twigs in the viewport for a clear view of the branches, and to improve viewport performance.",

    "twig_longevity": "Longevity",
    "twig_longevity_tt":
        "Side twigs appear near the tip of every branch, on new nodes grown this year. "
        "Longevity makes twigs endure for extra years, holding on to them on increasingly older nodes. "
        "Rebuild the tree geometry to see the effect.",

    "twig_side_on_tips": "Side on Tips",
    "twig_side_on_tips_tt":
        "Next to end twigs, also add side twigs to the tip of every branch. "
        "Rebuild the tree geometry to see the effect.",


    # Preferences
    "save_preferences": "Save Preferences",
    "save_preferences_tt": "Save your preferences to remember this setting.",

    "language": "Language",
    "language_tt": "Language to use for the interface and tooltips",

    "use_adaptive_units": "Use Adaptive Units",
    "use_adaptive_units_tt":
        "Grove uses units for several of its parameters, some of which represent tiny distances. "
        "With adaptive units enabled, 0.001m will be displayed as 1mm.",

    "use_scientific_names": "Scientific Names",
    "use_scientific_names_tt":
        "Show twig species using their scientific names, when available. "
        "When disabled, the twig menu displays the common name in English.",

    "grove": "Grove",

    "label_direction": "Direction",

    "add_new_grove": "Add Grove",
    "add_new_grove_tt": "Add a new grove collection.",

    "select_a_grove_collection": "Select a grove collection.",

    "select_linked_branches": "Select Linked Branches",
    "select_linked_branches_tt": "Expand the current selection to the entire branch and its side branches.",

    "select_thicker": "Select Thicker",
    "select_thicker_tt": "Select geometry that belongs to thicker branch nodes, using the 'Thickness' attribute.",
    "select_thicker_threshold": "Threshold",

    "show_dead_preview": "Show Dead",

    "disable_outline": "Disable Outline",
    "disable_outline_tt":
        "Click to disable outline shading for a correct representation of the tree and better visual feedback while tweaking. "
        "Outline shading makes branches appear much thicker than they really are.",

    "set_background": "Brighten Background",
    "set_background_tt":
        "Click to brighten up your viewport background and set it to middle gray. "
        "The improved contrast will make tree branches much easier to see.",


    # Record
    "record_enabled": "Record",
    "record_enabled_tt":
        "Record growth as a sequence of objects in a dedicated collection called 'Record'. "
        "Each step is keyframed for visibility for only a short while. "
        "All these objects in sequence form a growth animation.",

    "record_start": "Start Frame",
    "record_start_tt":
        "Shift the animation forward in time to start at this frame.",

    "record_interval": "Interval",
    "record_interval_tt":
        "Each year is a fluent interpolation, from the initial spring shape of the tree, to its full grown summer shape. "
        "Define the number of frames for this interpolation - and with that the speed of growth. "
        "You can tweak this value at any time, your animation will be updated in an instant.",


    "regrow": "Regrow",
    "regrow_tt":
        "Restart and quickly grow new trees up to the current number of flushes - in on go - skipping opportunities to prune your tree.",

    "placeholder_delay": "Delay",
    "placeholder_delay_tt":
        "The nubmer of years to wait before this tree starts to grow.",

    "panel_build_base": "Base",

    "add_tree": "Add Tree",
    "add_tree_tt":
        "Add an empty object to grow from. "
        "Move, rotate, duplicate or delete this object to grow groups of trees, each at its own location and angle.",

    "old_release_warning_line_1": "Trees grown in old release.",
    "old_release_warning_line_2": "A lot has changed.",
    "old_release_warning_line_3": "Use old release to edit.",

    "grow_together": "Grow Together",
    "grow_together_tt_short":
        "Grow all grove collections at once to grow different species together that compete for light.",
    "grow_together_tt":
        "Grow all separate grove collections together as one, so that you can mix different tree species."
        "With combined shade and phototropism calculations to make them compete for light.",

    "restart_all": "Restart All",
    "restart_all_tt": "Restart every grove collection.",

    "draw": "Draw",
    "draw_tt": "Grow a new branch along a path.",

    "prune_status_draw_lines": "Draw",


    # Bend tool
    "manual_bend": "Bend",
    "manual_bend_tt":
        "A tool inspired by the bonsai technique of bending branches with metal wire, but much more flexible, "
        "able to bend even the thickest of branches, and able to style even a full-grown tree.",

    "bend_status_select_node": "Select Node",

    "bend_tool_distance": "Distance",
    "bend_tool_distance_tt": "Length",

    "bend_tool_bend_button": "Bend",
    "bend_tool_bend_button_tt": "Space",

    "close_button": "Done",
    "close_button_tt": "",

    "close": "Close",

    "turntable": "View",
    "turntable_tt": "",

    "bend_tool_curve": "Curve",
    "bend_tool_curve_tt": "Shape of the bend",
    "bend_tool_curve_simple": "Simple",
    "bend_tool_curve_flexible": "Flexible",
    "bend_tool_curve_s_curve": "S-Curve",


    # Wind
    "wind_vector": "Wind",
    "wind_vector_tt": "Speed and Direction",
    "wind_turbulence": "Turbulence",
    "wind_turbulence_tt": "Lift up twigs and make branches dance in the wind.",

    "wind_shapes": "Shape Keys",
    "wind_shapes_tt":
        "The number of shape keys defines the length of the wind animation, after which it will loop automatically. "
        "Each shape is keyframed 2 frames apart and interpolates fluently from one shape to the next.",

    "label_animating_wind": "Animating Wind...",
    "label_stop": "Stop",

    "wind_breeze": "Breeze",
    "wind_breeze_tt":
        "Breathe life into the twigs with a lively breeze animation. "
        "You can combine it with regular wind animation for a stronger deformation.",

    "calculate_wind": "Wind Shapes",
    "calculate_wind_tt":
        "Add wind animation. "
        "Create a series of shape keys that deform the branches of your tree through time.",

    "grow_tool_growing": "Growing",
    "grow_tool_growing_tt": "Escape to cancel.",
    "grow_tool_building": "Building Mesh",

    # Plant operator.
    "plant": "Plant",
    "plant_tt":
        "Plant a group of trees - create orchards, hedgerows or natural islands of trees. "
        "This tool creates empty objects, which you can freely move around, duplicate or delete.",

    "plant_layout": "Layout",
    "plant_layout_tt": "Plant an orchard, plantation, hedgerow, ring or natural clumps of trees",

    "plant_trees": "Trees",
    "plant_trees_tt": "Number of trees",

    "plant_space": "Space",
    "plant_space_tt": "Distance between trees",

    "plant_random_shift": "Random Shift",
    "plant_random_shift_tt": "Uneven placement",

    "plant_random_seed": "Random Seed",
    "plant_random_seed_tt": "Vary random shifting",

    "plant_delay": "Delay",
    "plant_delay_tt": "Trees far from the center start growing at a later year.",

    "plant_ring_radius": "Radius",
    "plant_ring_radius_tt": "Distance from the middle of the ring",

    "plant_rows_trees_tt": "Number of trees per row",

    "plant_rows": "Rows",
    "plant_rows_tt": "Number of rows",

    "plant_rows_space": "Space",
    "plant_rows_space_tt": "Space between rows",

    "plant_rows_diagonal": "Diagonal",
    "plant_rows_diagonal_tt": "Shift every second row to get a diamond pattern",

    "plant_islands_trees_tt": "Average number of trees per island",

    "plant_islands": "Islands",
    "plant_islands_tt": "Number of tree islands",

    "plant_islands_space": "Islands Space",
    "plant_islands_space_tt": "Average distance between tree islands",

    "plant_islands_clearing": "Clearing",
    "plant_islands_clearing_tt": "Open space in the middle",

    "plant_islands_randomize": "Random",
    "plant_islands_randomize_tt": "Vary the number of trees per island",

    "plant_layout_clump": "Clump",
    "plant_layout_rows": "Rows",
    "plant_layout_ring": "Ring",
    "plant_layout_islands": "Islands",

    "plant_variation_panel": "Variation",
    "plant_diverge": "Diverge",
    "plant_diverge_tt": "Turn the growth direction away from nearby trees.",

    "plant_terrain_panel": "Terrain",
    "plant_terrain_drop": "Drop",
    "plant_terrain_drop_tt": "Project trees to the ground.",

    "plant_terrain_slope": "Slope",
    "plant_terrain_slope_tt": "Take on the slope of the landscape in the rotation.",

    "escape_to_stop": "Escape to stop",

    "replant_grove": "Replant",
    "replant_grove_tt": "Replant.",


    # Surround tool
    "surround_enabled": "Surround",
    "surround_enabled_tt":
        "Surround your trees with shade from all sides. "
        "This will make trees grow taller and lose more of their lower branches. "
        "It allows you to grow trees that resemble those found in a forest, without having to grow an entire forest.",
    "surround_density": "Density",
    "surround_density_tt":
        "Grow in an open field or a dense forest, or anything in between.",
    "surround_height": "Height",
    "surround_height_tt":
        "A fixed height that can be used for established trees or buildings. "
        "Use auto height to let the surroundings grow along with your trees.",
    "surround_grow": "Grow",
    "surround_grow_tt":
        "Automatically increase in height every year - the surrounding trees grow together with your trees.",
    "surround_distance": "Distance",
    "surround_distance_tt": "Clear space to grow in.",


    # File tool
    'file': "File",
    "file_tt": "Save trees for later use, or transfer trees across applications.",

    "file_recent": "Recent",

    "file_import": "Import Trees",
    "file_import_tt": "Import a simulation from a .grove file.",

    "file_export": "Export Trees",
    "file_export_tt": "Export the current simulation to a .grove file.",

    # Roots tool
    "roots": "Roots",
    "roots_tt":
        "Generate surface roots. "
        "Roots usually grow below ground, but can be exposed through soil erosion. "
        "Visually pleasing, surface roots anchor the tree to the ground.",

    "roots_roots_panel": "Roots",
    "roots_number": "Number",
    "roots_number_tt": "Number of main roots",
    "roots_nodes": "Nodes",
    "roots_nodes_tt": "Number of nodes per root",
    "roots_length": "Length",
    "roots_length_tt": "Length between two nodes.",
    "roots_climb": "Climb",
    "roots_climb_tt": "Make roots rise up along the trunk to create a smooth blend.",
    "roots_turn_down": "Grow Down",
    "roots_turn_down_tt": "",

    "roots_branches_panel": "Side Roots",
    "roots_branches_panel_tt" : "",
    "roots_generations": "Generations",
    "roots_generations_tt" :
        "Add further generations of growth to expand the root system in more detail.",
    "roots_density": "Density",
    "roots_density_tt" :
        "Chance of growing a side root. To further increase density, "
        "increase the number of nodes and reduce internode length.",
    "roots_add_angle": "Angle",
    "roots_add_angle_tt": "The angle from the main root.",
    "roots_add_down": "Add Downward",
    "roots_add_down_tt": "New roots start with a downward direction.",

    "roots_variation_panel": "Random",
    "roots_random_heading": "Heading",
    "roots_random_heading_tt": "Creep across the ground.",
    "roots_random_pitch": "Pitch",
    "roots_random_pitch_tt": "Turn up and down while growing.",
    "roots_random_seed": "Seed",
    "roots_random_seed_tt": "Get a different random variation.",

    "roots_thickness_panel": "Thickness",
    "roots_thickness": "Thickness",
    "roots_thickness_tt": "Average thickness of a main root.",
    "roots_thickness_reduce": "Reduce",
    "roots_thickness_reduce_tt": "Reduce thickness of side roots.",
    "roots_thickness_random": "Random",
    "roots_thickness_random_tt": "Randomize the thickness of each root.",

    "roots_terrain_panel": "Terrain",
    "roots_terrain_panel_tt": "",
    "roots_drop": "Drop",
    "roots_drop_tt": "",

    "restart_single_tree": "Single Tree",
    "restart_single_tree_tt":
        "Remove placeholders and plant a single tree at the origin.",

    "restart_revert": "Start Fresh",
    "restart_revert_tt":
        "Reset everything to default, reload the active preset and restart with a single tree.",

    "operator_turntable": "View",
    "operator_turntable_tt":
        "View your trees from eye level - walk around and under the canopy.",

    "stake_enabled": "Stake",
    "stake_enabled_tt": "A stake supports the trunk so that it grows straight up.",
    "stake_height": "Height",
    "stake_height_tt": "Support the tree to this height so that the trunk grows straight up.",


    # Old and unused
    "shade_sensitivity": "Sensitivity",
    "shade_sensitivity_tt":
        "Sensitivity to shade. "
        "Shade is a linear value from light to dark, but processes in nature often respond in an exponential way. "
        "Set to 0 for a slow response to shade, a branch will only react after it receives a substantial amount of shade. "
        "Set to 1 for an immediate reaction, the slightest bit of shade is magnified out of proportion.",

    "shade_elongation": "Longer in Shade",
    "shade_elongation_tt":
        "Shaded branches grow longer or shorter. "
        "Plants growing in shade will grow longer in the hope of finding light. "
        "Together with a decrease in thickness, this creates longer but weaker branches that bend more. "
        "It can initiate the dangling branches often seen at the bottom of the crown.",

    "wind_frequency": "Wind Frequency",
    "wind_frequency_tt":
        "Wind Frequency.",

    "shade_avoidance": "Shade Boost",  # Escape Shade
    "shade_avoidance_tt":
        "Increase or decrease Favor End on shaded branches. "
        "Each branch controls its own Favor End, as a strategy to find light. "
        "The more a branch is shaded, it can either favor its tip growth to escape the shade, "
        "or it can favor side growth in order to take in as much of the dim light as it can. "
        "The latter can be seen in forest floor species like Beech and Hazel.",

    "branching_inefficiency": "Inefficiency",
    "branching_inefficiency_tt":
        "A direct way to limit the vigor of side branches and their consecutive side branches. "
        "A branch attachment is imperfect and limits water transport.",

    "sapwood": "Sapwood",
    "sapwood_tt":
        "Thickness of live wood. This is the live wood that transports water. The branch core within is "
        "dead wood and only acts as a support structure, called heartwood. Increasing "
        "this value will result in less thickness buildup on thicker branches.",

    "placeholder": "Placeholder",

    "label_layers": "Attributes",

    # "fallback_info": "Get ready to grow",
    "fallback_info": "The add-on works",
    "fallback_instructions": "Get ready to grow",
    "fallback_instructions_tt": "Follow the instructions on http://www.thegrove3d.com/info/install/ to install the simulation core.",

    "trial_end": "Buy Now...",
    "trial_end_tt": "Your trial has expired. If you like The Grove, please purchase a license to keep growing awesome trees.",

    "build_skeleton": "Build Skeleton",
    "build_skeleton_tt":
        "Create bones, bone weight groups and wind.",

    "skeleton": "Skeleton",
    "skeleton_tt":
        "Create a bone structure that allows you to deform and animate the trees. "
        "Also add vertex groups to link mesh points to their respective bones. "
        "Optionally, add wind animation to the new bones.",

    "skeleton_panel_bones": "Bones",
    "skeleton_panel_wind": "Wind",
    
    "skeleton_reduce": "Reduce",
    "skeleton_reduce_tt":
        "Skip thin side branches to reduce the number of bones.",

    "skeleton_bias": "Bias",
    "skeleton_bias_tt":
        "Increase to add more bones higher up, decrease to add more bones down below.",

    "skeleton_length": "Length",
    "skeleton_length_tt":
        "Create longer bones to reduce the number of bones.",

    "skeleton_connected": "Connected",
    "skeleton_connected_tt":
        "Blender can build a hierarchy from floating bones, while some other programs require a connected chain of bones. "
        "The connections require a new bone at each branching point, which increases the number of bones.",

    "sow_enabled": "Sow",
    "sow_enabled_tt": "Scatter seeds around existing, older trees to simulate a naturally spreading grove of trees.",

    "sow_age": "Delay",
    "sow_age_tt":
        "Trees must reach this age before they can produce viable seeds. "
        "New trees need time to establish strong root systems and achieve energy surplus before reproduction.",

    "sow_chance": "Chance",
    "sow_chance_tt":
        "The yearly chance that each tree creates a successful offspring."
        "The yearly chance that one of a tree's sown seeds successfully germinates, survives and creates a new tree."
        "Each year, each tree has a chance add a new tree. "
        "In reality, some trees can create thousands of seeds, and hundreds of these seeds can germinate, each year. "
        "But almost none of these survive to grow a proper tree. "
        "To keep the simulation running at a usable speed, keep the chance low.",

    "sow_distance": "Distance",
    "sow_distance_tt":
        "Seeds are scattered within a distance around existing trees.",

    "sow_limit": "Limit",
    "sow_limit_tt":
        "The maxiumum number of trees. Stop adding new trees beyond this number, to keep the simulation running smoothly.",
    
    "build_triangulate": "Triangulate",
    "build_triangulate_tt":
        "Only use triangles to build the tree's branches, no quads.",
    
    "label_cutoff": "Cutoff",
    
    "build_cutoff_thickness": "Thickness",
    "build_cutoff_thickness_tt":
        "Skip building thin branch ends to dramatically reduce the polygon count. "
        "Compensate with bigger twigs that represent more of years of growth.",
    
    "build_cutoff_age": "Age",
    "build_cutoff_age_tt":
        "Skip building the last years of growth to dramatically reduce the polygon count. "
        "Compensate with bigger twigs that represent more of years of growth.",
    
    "build_blend": "Blend",
    "build_blend_tt":
        "Add extra nodes to create a smooth transition from one branch to the other. "
        "This is visually important for thicker branches, but can be disabled for thinner branches to dramatically reduce the polygon count.",
    
    "build_end_cap": "End Cap",
    "build_end_cap_tt":
        "Fill the open ends of branches with additional geometry, or skip this for thinner branches to greatly reduce the number of polygons. "
        "Depending on the distance to the tree and whether or not the tree is in leaf, the thinner ends can be almost invisible anyway.",
    
    "detail_simplify": "Simplify",
    "detail_simplify_tt":
        "Simplify branches by skipping straight nodes with almost no change in direction. This results in a small reduction in polygon count.",
}
