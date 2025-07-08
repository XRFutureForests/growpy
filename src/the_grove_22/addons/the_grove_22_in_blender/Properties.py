
""" A unique group with all properties is stored in each grove collection.
    Most of these properties define the way a tree grows, and this subset can be saved to a preset.
    Other properties define how the tree model is built, keep track of the age, number of branches etc.
    Properties are shown in The Grove's UI in a layout defined in Panels.py.

    Copyright 2014 - 2025, Wybren van Keulen, The Grove """


from math import radians

import bpy
import bpy.utils.previews
from bpy.props import  FloatProperty, IntProperty, BoolProperty, StringProperty, EnumProperty, PointerProperty

from .Operators.OperatorBuild import update_twigs_callback, update_twigs_density_callback, change_simulation_scale
from .Operators.OperatorBuild import set_view_detail, update_wind_breeze, do_twig_hide, retime
from .Presets import list_presets, read_preset, remove_imported_file_preset
from .Languages.Translation import t
from .Twigs import list_twigs, append_twigs
from .Textures import list_textures, swap_textures

from .Core import import_core
the_grove_core = import_core()

import json


class GROVE22_Properties(bpy.types.PropertyGroup):
    """ All of Grove's tree growing properties, stored in a grove collection. """

    height: FloatProperty(name='height', default=0.0, description='', options={'HIDDEN'})
    age: IntProperty(name='age', default=0, description='', options={'HIDDEN'})
    age_of_last_grown_tree: IntProperty(name='age_of_last_grown_tree', default=0, description='', options={'HIDDEN'})
    number_of_polygons: IntProperty(name='polygons', default=0, description='', options={'HIDDEN'})
    number_of_branches: IntProperty(name=t(''), description='', default=0, soft_min=0)

    do_twig_previews: BoolProperty(name="Do Load Preset", default=False, options={'HIDDEN'})

    is_tool_active_prune: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_restart: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_zoom: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_file: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_plant: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_roots: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_bend: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_draw: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_grow: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_grow_together: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_regrow: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_build: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_tweak_surround: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_tweak_shade: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_animate_wind: BoolProperty(name='', default=False, options={'HIDDEN'})
    is_tool_active_build_skeleton: BoolProperty(name='', default=False, options={'HIDDEN'})

    has_wind_animation: BoolProperty(name='', default=False, options={'HIDDEN'})

    unique_id: StringProperty(name='ID', description='', default="")


    # Preset
    presets_list = []

    def presets(self, context):
        """ Fill the presets menu. """

        # if not GROVE22_Properties.presets_list:
        # GROVE22_Properties.presets_list = list_presets()
        # return GROVE22_Properties.presets_list

        # The above only lists presets when reloading scripts or when the code asks to refresh the list.
        # This interferes with other versions of Grove.
        # All of which store the presets list in GROVE22_Properties.
        # So for now, simply list the presets every time.

        return list_presets()

    preset_name: StringProperty(name=t('preset_name'), description=t('preset_name_tt'), default="")

    def read_preset_callback(self, context):
        """ This function is triggered when picking a preset from the menu.
            It reads the selected preset and it deletes the temporary imported file preset if present. """

        name = self.presets_menu
        remove_imported_file_preset(self, name)
        read_preset(name, self)
        self.preset_name = name

        self.show_remove_preset_box = False
        self.show_add_preset_box = False
        self.show_overwrite_preset_box = False

    presets_menu: EnumProperty(
        name=t('presets_menu'), description=t('presets_menu_tt'),
        items=presets, update=read_preset_callback)

    def do_show_add_preset_box(self, _):
        """ Open the UI box that allows adding a new preset. """

        if self.show_add_preset_box:
            self.show_remove_preset_box = False
        self.show_overwrite_preset_box = False

    show_add_preset_box: BoolProperty(
        name=t('save_preset'), description=t('save_preset_tt'),
        default=False,
        update=do_show_add_preset_box)

    show_overwrite_preset_box: BoolProperty(
        name=t('save_preset'), description=t('save_preset_tt'),
        default=False)

    def do_show_remove_preset_box(self, _):
        """ Open the UI box that allows deleting the current preset. """

        if self.show_remove_preset_box:
            self.show_add_preset_box = False
            self.show_overwrite_preset_box = False

    show_remove_preset_box: BoolProperty(
        name=t('remove_preset'), description=t('remove_preset_tt'),
        default=False,
        update=do_show_remove_preset_box)


    # Twig

    twigs_list = []

    def list_twigs(self, context):
        """ Find all twigs and create a list to fill the menu. """

        if not GROVE22_Properties.twigs_list or context.preferences.addons[__package__].preferences.refresh_twigs:
            GROVE22_Properties.twigs_list = list_twigs(context)
            context.preferences.addons[__package__].preferences.refresh_twigs = False
        return GROVE22_Properties.twigs_list

    def change_twig_menu(self, context):
        """ A selection was made in the twigs menu. """

        if self.twig_menu == t('twig_pick_collections'):
            self.do_twig_collections = True
        else:
            self.do_twig_collections = False

        if (self.twig_menu != t('twig_no_twigs') and
                self.twig_menu != t('twig_pick_objects') and
                self.twig_menu != t('twig_pick_collections')):
            append_twigs(self, context)
            set_view_detail(self)
        else:
            update_twigs_callback(self, context)

        self.twig_hide = False

    twig_menu: EnumProperty(
        name=t('twig_menu'),
        items=list_twigs,
        update=change_twig_menu,
        description=t('twig_menu_tt'))

    twig_hide: BoolProperty(
        name=t('twig_hide'), description=t('twig_hide_tt'),
        default=False,
        update=do_twig_hide)

    twig_object_end: PointerProperty(
        name=t('twig_object_end'), description=t('twig_object_end_tt'),
        type=bpy.types.Object,
        update=update_twigs_callback)

    twig_object_side: PointerProperty(
        name=t('twig_object_side'), description=t('twig_object_side_tt'),
        type=bpy.types.Object,
        update=update_twigs_callback)

    twig_side_on_tips: BoolProperty(
        name=t('twig_side_on_tips'), description=t('twig_side_on_tips_tt'),
        default=False)

    twig_object_upward: PointerProperty(
        name=t('twig_object_upward'), description=t('twig_object_upward_tt'),
        type=bpy.types.Object,
        update=update_twigs_callback)

    twig_object_dead: PointerProperty(
        name=t('twig_object_dead'), description=t('twig_object_dead_tt'),
        type=bpy.types.Object,
        update=update_twigs_callback)

    do_twig_collections: BoolProperty(name='', default=False, options={'HIDDEN'})

    twig_collection_long: PointerProperty(
        name=t('twig_object_end'), description=t('twig_object_end_tt'),
        type=bpy.types.Collection,
        update=update_twigs_callback)

    twig_collection_short: PointerProperty(
        name=t('twig_object_side'), description=t('twig_object_side_tt'),
        type=bpy.types.Collection,
        update=update_twigs_callback)

    twig_collection_upward: PointerProperty(
        name=t('twig_object_upward'), description=t('twig_object_upward_tt'),
        type=bpy.types.Collection,
        update=update_twigs_callback)

    twig_collection_dead: PointerProperty(
        name=t('twig_object_dead'), description=t('twig_object_dead_tt'),
        type=bpy.types.Collection,
        update=update_twigs_callback)

    twig_longevity: IntProperty(
        name=t('twig_longevity'), description=t('twig_longevity_tt'),
        default=2, min=1, soft_max=10)

    twig_wither: IntProperty(
        name=t('twig_wither'), description=t('twig_wither_tt'),
        default=2, min=0, soft_max=10)

    twig_density: FloatProperty(
        name=t('twig_density'), description=t('twig_density_tt'),
        default=0.2, min=0.0, max=1.0, step=10, precision=1, subtype='FACTOR',
        update=update_twigs_density_callback)

    def change_twig_view_detail(self, context):
        """ Update each of the decimate modifiers attached to twig objects. """

        set_view_detail(self)

    twig_view_detail: FloatProperty(
        name=t('twig_view_detail'), description=t('twig_view_detail_tt'),
        default=0.3, min=0.1, max=1.0, step=10, precision=1, subtype='FACTOR',
        update=change_twig_view_detail)


    # Simulate

    simulation_scale: FloatProperty(
        name=t('simulation_scale'),
        default=1.0, min=0.1, soft_min=0.1, soft_max=5.0, step=1, precision=1,
        update=change_simulation_scale,
        description=t('simulation_scale_tt'))

    simulation_flushes: IntProperty(
        name=t('simulation_flushes'), description=t('simulation_flushes_tt'),
        default=8, min=1, soft_max=20)


    # Sow

    sow_enabled: BoolProperty(
        name=t('sow_enabled'), description=t('sow_enabled_tt'),
        default=False)

    sow_age: IntProperty(
        name=t('sow_age'),
        default=10, min=1, soft_max=50,
        description=t('sow_age_tt'))

    sow_chance: FloatProperty(
        name=t('sow_chance'), description=t('sow_chance_tt'), subtype='FACTOR',
        default=0.2, soft_min=0.0, soft_max=1.0, step=10)

    sow_distance: FloatProperty(
        name=t('sow_distance'), description=t('sow_distance_tt'), subtype='FACTOR',
        default=8.0, soft_min=1.0, soft_max=50.0, step=10)

    sow_limit: IntProperty(
        name=t('sow_limit'),
        default=50, min=2, soft_max=100,
        description=t('sow_limit_tt'))


    # Record

    record_enabled: BoolProperty(
        name=t('record_enabled'), description=t('record_enabled_tt'),
        default=False)

    def change_interval(self, context):
        """ When changing the record interval or record start frame, update the keyframes. """

        retime(context.collection, self)

    record_interval: IntProperty(
        name=t('record_interval'),
        default=3, min=1, soft_max=50,
        description=t('record_interval_tt'),
        update=change_interval)

    record_start_frame: IntProperty(
        name=t('record_start'),
        default=1, min=0, soft_max=250,
        description=t('record_start_tt'),
        update=change_interval)


    # Surround

    surround_enabled: BoolProperty(
        name=t('surround_enabled'), description=t('surround_enabled_tt'),
        default=False)

    surround_density: FloatProperty(
        name=t('surround_density'), description=t('surround_density_tt'),
        default=0.7, min=0.0, max=1.0, step=10, precision=1, subtype='FACTOR')

    surround_height: FloatProperty(
        name=t('surround_height'), description=t('surround_height_tt'),
        default=5.0, soft_min=0.0, soft_max=50.0, step=100, precision=1,
        unit='LENGTH')

    surround_distance: FloatProperty(
        name=t('surround_distance'), description=t('surround_distance_tt'),
        default=7.0, min=2.0, soft_max=15.0, step=100, precision=1,
        unit='LENGTH')

    surround_grow: BoolProperty(
        name=t('surround_grow'), description=t('surround_grow_tt'),
        default=True)


    # React

    react_enabled: BoolProperty(
        name=t('react_enabled'), description=t('react_enabled_tt'), default=False)

    react_block_object: PointerProperty(
        name=t('react_block_object'), description=t('react_block_object_tt'),
        type=bpy.types.Object)

    react_shade_object: PointerProperty(
        name=t('react_shade_object'), description=t('react_shade_object_tt'),
        type=bpy.types.Object)

    react_attract_object: PointerProperty(
        name=t('react_attract_object'), description=t('react_attract_object_tt'),
        type=bpy.types.Object)

    react_attract_strength: FloatProperty(
        name=t('react_force'), description=t('react_force_tt'),
        default=0.3, soft_min=0.0, soft_max=1.0, subtype='FACTOR')

    react_attract_falloff: FloatProperty(
        name=t('react_falloff'), description=t('react_falloff_tt'),
        default=1.3, soft_min=0.0, soft_max=2.0, step=10)

    react_deflect_object: PointerProperty(
        name=t('react_deflect_object'), description=t('react_deflect_object_tt'),
        type=bpy.types.Object)

    react_deflect_strength: FloatProperty(
        name=t('react_force'), description=t('react_force_tt'),
        default=0.3, soft_min=0.0, soft_max=1.0, subtype='FACTOR')

    react_deflect_falloff: FloatProperty(
        name=t('react_falloff'), description=t('react_falloff_tt'),
        default=1.3, soft_min=0.0, soft_max=2.0, step=10)

    react_vigor_object: PointerProperty(
        name=t('react_vigor_object'), description=t('react_vigor_object_tt'),
        type=bpy.types.Object)


    # Auto prune

    auto_prune_enabled: BoolProperty(
        name=t('auto_prune_enabled'), description=t('auto_prune_enabled_tt'), default=True)

    auto_prune_low: FloatProperty(
        name=t('auto_prune_low'), description=t('auto_prune_low_tt'),
        default=2.0, soft_min=0.0, soft_max=10.0, step=50, precision=3, subtype='DISTANCE', unit='LENGTH')

    auto_prune_keep_thick: FloatProperty(
        name=t('auto_prune_keep_thick'), description=t('auto_prune_keep_thick_tt'),
        default=0.01, soft_min=0.0, soft_max=0.1, step=0.1, precision=3, unit='LENGTH')

    auto_prune_dangling: FloatProperty(
        name=t('auto_prune_dangling'), description=t('auto_prune_dangling_tt'),
        default=1.0, soft_min=0.0, soft_max=10.0, step=50, precision=3, subtype='DISTANCE', unit='LENGTH')


    # Stake

    stake_enabled: BoolProperty(
        name=t('stake_enabled'), description=t('stake_enabled_tt'), default=False)

    stake_height: FloatProperty(
        name=t('stake_height'), description=t('stake_height_tt'),
        default=4.0, soft_min=0.0, soft_max=10.0, step=50, precision=3, subtype='DISTANCE', unit='LENGTH')


    # Favor

    favor_end: FloatProperty(
        name=t('favor_end'), description=t('favor_end_tt'),
        default=0.4, soft_min=0.0, max=1.0, step=10, subtype='FACTOR')

    favor_end_reduce: FloatProperty(
        name=t('favor_end_reduce'), description=t('favor_end_reduce_tt'),
        default=0.0, soft_min=0.0, max=1.0, step=10, subtype='FACTOR')

    shade_avoidance: FloatProperty(
        name=t('shade_avoidance'), description=t('shade_avoidance_tt'),
        default=0.0, soft_min=-1.0, soft_max=1.0, step=10)

    favor_bright: FloatProperty(
        name=t('favor_bright'), description=t('favor_bright_tt'),
        default=0.8, min=0.0, max=1.0, step=10, subtype='FACTOR')

    favor_rising: FloatProperty(
        name=t('favor_rising'), description=t('favor_rising_tt'),
        default=0.0, min=-1.0, soft_min=0.0, soft_max=1.0, step=10, subtype='FACTOR')

    favor_dwindle: FloatProperty(
        name='favor_dwindle', description='favor_dwindle_tt',
        default=1.0, min=0.0, max=1.0, step=10, subtype='FACTOR')

    favor_thick: FloatProperty(
        name='Favor Thick', description='',
        default=0.0, soft_min=-1.0, soft_max=1.0, step=10)

    favor_squeeze: FloatProperty(
        name='Squeeze', description=t('favor_rising_tt'),
        default=0.0, min=-1.0, soft_min=0.0, soft_max=1.0, step=10, subtype='FACTOR')


    # Drop

    drop_shaded: FloatProperty(
        name=t('drop_shaded'), description=t('drop_shaded_tt'),
        default=0.3, min=0.0, max=1.0, step=10, subtype='FACTOR')

    drop_weak: FloatProperty(
        name=t('drop_weak'), description=t('drop_weak_tt'),
        default=0.1, soft_min=0.0, soft_max=1.0, step=10, subtype='FACTOR')

    drop_obsolete: FloatProperty(
        name=t('drop_obsolete'), description=t('drop_obsolete_tt'),
        default=0.1, soft_min=0.0, soft_max=1.0, step=5, subtype='FACTOR')

    drop_decay: FloatProperty(
        name=t('drop_decay'), description=t('drop_decay_tt'),
        default=0.4, soft_min=0.0, soft_max=1.0, step=10, subtype='FACTOR')


    # Add

    add_side_branches: IntProperty(
        name=t('add_side_branches'), description=t('add_side_branches_tt'),
        default=1, soft_min=1, soft_max=6, step=1)

    add_chance: FloatProperty(
        name=t('add_chance'), description=t('add_chance_tt'), subtype='FACTOR',
        default=1.0, soft_min=0.0, soft_max=1.0, step=10)

    add_chance_reduce: FloatProperty(
        name=t('add_chance_reduce'), description=t('add_chance_reduce_tt'), subtype='FACTOR',
        default=0.0, soft_min=0.0, soft_max=1.0, step=10)

    add_bud_life: IntProperty(
        name=t("add_bud_life"), description=t('add_bud_life_tt'),
        default=1, soft_min=1, soft_max=40)

    add_only_on_end: FloatProperty(
        name=t('add_only_on_end'), description=t('add_only_on_end_tt'), subtype='FACTOR',
        default=0.0, soft_min=0.0, soft_max=1.0, step=10)

    add_regenerate: FloatProperty(
        name=t('add_regenerate'), description=t('add_regenerate_tt'),
        default=0.05, soft_min=0.0, soft_max=1.0, step=10, subtype='FACTOR')

    add_fork: FloatProperty(
        name=t('add_fork'), description=t('add_fork_tt'), subtype='FACTOR',
        default=0.0, soft_min=0.0, soft_max=1.0, step=10)

    add_angle: FloatProperty(
        name=t("add_angle"), description=t('add_angle_tt'),
        default=radians(45.0), min=radians(1.0), max=radians(90.0), step=500, subtype='ANGLE', unit='ROTATION')

    add_up: FloatProperty(
        name=t('add_up'), description=t('add_up_tt'),
        default=0.0, soft_min=-1.0, soft_max=1.0, step=10)

    add_horizontal: FloatProperty(
        name=t('add_horizontal'), description=t('add_horizontal_tt'), subtype='FACTOR',
        default=0.0, soft_min=0.0, soft_max=1.0, step=10)

    add_planar: FloatProperty(
        name=t('add_planar'), description=t('add_planar_tt'),
        default=0.0, soft_min=0.0, soft_max=1.0, step=10)


    # Grow

    grow_nodes: IntProperty(
        name=t('grow_nodes'), description=t('grow_nodes_tt'),
        default=3, min=1, soft_max=20)

    grow_length: FloatProperty(
        name=t('grow_length'), description=t('grow_length_tt'),
        default=0.3, soft_min=0.01, soft_max=1.0, subtype='DISTANCE', unit='LENGTH')


    # Turn

    turn_to_light: FloatProperty(
        name=t('turn_to_light'), description=t('turn_to_light_tt'), subtype='FACTOR',
        default=0.0, soft_min=0.0, soft_max=1.0, step=10)

    turn_up: FloatProperty(
        name=t('turn_up'), description=t('turn_up_tt'), subtype='FACTOR',
        default=0.2, min=-1.0, soft_min=0.0, soft_max=1.0, step=10)

    turn_up_in_shade: FloatProperty(
        name=t('turn_up_in_shade'), description=t('turn_up_in_shade_tt'), subtype='FACTOR',
        default=0.0, soft_min=0.0, soft_max=1.0, step=10)

    turn_to_horizon: FloatProperty(
        name=t("turn_to_horizon"), description=t('turn_to_horizon_tt'), subtype='FACTOR',
        default=0.0, soft_min=0.0, soft_max=1.0, step=10)

    turn_random: FloatProperty(
        name=t('turn_random'), description=t('turn_random_tt'),
        default=radians(5.0), min=radians(0.0), max=radians(90.0), step=100,
        subtype='ANGLE', unit='ROTATION')


    # Thicken

    thicken_tips: FloatProperty(
        name=t('thicken_tips'), description=t('thicken_tips_tt'),
        default=0.007, soft_min=0.002, soft_max=0.02, step=0.001, precision=3, unit='LENGTH')

    thicken_tips_reduce: FloatProperty(
        name=t('thicken_tips_reduce'), description=t('thicken_tips_reduce_tt'),
        default=0.0, soft_min=0.0, soft_max=1.0, step=10, subtype='FACTOR')

    thicken_join: FloatProperty(
        name=t('thicken_join'), description=t('thicken_join_tt'),
        default=0.75, soft_min=0.0, soft_max=1.0, max=1.5, step=10, precision=2, subtype='FACTOR')

    thicken_deadwood: FloatProperty(
        name=t('thicken_deadwood'), description=t('thicken_deadwood_tt'),
        default=0.0, min=0.0, soft_max=1.0, step=1, precision=2, subtype='FACTOR')

    thicken_base_scale: FloatProperty(
        name=t('thicken_base_scale'), description=t('thicken_base_scale_tt'),
        default=1.2, soft_min=1.0, soft_max=5.0, step=10, precision=1)

    thicken_base_buttress: FloatProperty(
        name=t('thicken_base_buttress'), description=t('thicken_base_buttress_tt'),
        default=2.0, soft_min=0.0, soft_max=10.0, step=20, precision=1)

    thicken_base_shape: FloatProperty(
        name=t('thicken_base_shape'), description=t('thicken_base_shape_tt'),
        default=0.1, soft_min=0.01, soft_max=0.1, step=10, precision=2)

    root_distribution: FloatProperty(
        name=t('root_distribution'), description=t('root_distribution_tt'),
        default=0.4, soft_min=0.01, soft_max=1.0, step=10, precision=2)


    # Bend

    bend_mass: FloatProperty(
        name=t('bend_mass'), description=t('bend_mass_tt'),
        default=1.0, soft_min=0.0, soft_max=2.0, step=10)

    bend_twig_mass: FloatProperty(
        name=t('bend_twig_mass'), description=t('bend_twig_mass_tt'),
        default=0.1, soft_min=0.0, soft_max=2.0, step=10)

    bend_twig_mass_solidify: FloatProperty(
        name=t('bend_twig_mass_solidify'), description=t('bend_twig_mass_solidify_tt'),
        default=1.0, soft_min=0.0, soft_max=1.0, step=10, subtype='FACTOR')

    bend_reaction: FloatProperty(
        name=t('bend_reaction'), description=t('bend_reaction_tt'),
        default=0.5, soft_min=0.0, soft_max=1.0, step=1, precision=2, subtype='FACTOR')


    # Shade

    shade_area: FloatProperty(
        name=t('shade_area'), description=t('shade_area_tt'),
        default=8.0, min=0.01, soft_min=0.05, soft_max=30.0, step=100, precision=1)

    shade_area_reduce: FloatProperty(
        name=t('shade_area_reduce'), description=t('shade_area_reduce_tt'),
        default=0.0, min=0.0, soft_max=1.0, step=10, precision=1, subtype='FACTOR')

    shade_area_depth: FloatProperty(
        name=t('shade_area_depth'), description=t('shade_area_depth_tt'),
        default=0.5, soft_min=-1.0, min=-1.0, soft_max=1.0, step=10, precision=1)

    shade_leaf_sides: BoolProperty(
        name=t('shade_leaf_sides'), description=t('shade_leaf_sides_tt'),
        default=False)

    shade_branches: BoolProperty(
        name=t('shade_branches'), description=t('shade_branches_tt'),
        default=False)

    shade_alongside: IntProperty(
        name=t('shade_alongside'), description=t('shade_alongside_tt'),
        default=2, min=0, soft_max=10)

    shade_alongside_diameter: FloatProperty(
        name=t('shade_alongside_diameter'), description=t('shade_alongside_diameter_tt'),
        default=0.2, soft_min=0.05, soft_max=1.0, step=0.1, precision=3, unit='LENGTH')


    # Build Wind

    wind_iterations: IntProperty(
        name='Iterations', description='Quality of wind shapes.',
        default=4, min=1, soft_max=10, step=1)

    wind_breeze: FloatProperty(
        name=t('wind_breeze'), description=t('wind_breeze_tt'),
        default=0.2, min=0.0, max=1.0, step=10, precision=1, subtype='FACTOR',
        update=update_wind_breeze)


    # Build Mesh
    
    build_cutoff_age: IntProperty(
        name=t('build_cutoff_age'), description=t('build_cutoff_age_tt'),
        default=0, min=0, soft_min=0, soft_max=10)
    
    build_cutoff_thickness: FloatProperty(
        name=t('build_cutoff_thickness'), description=t('build_cutoff_thickness_tt'),
        default=0.0, soft_min=0.0, soft_max=1.0, step=0.001, precision=3, unit='LENGTH')
    
    build_resolution: IntProperty(
        name=t('build_resolution'), description=t('build_resolution_tt'),
        default=16, min=3, soft_min=4, soft_max=64)

    build_resolution_reduce: FloatProperty(
        name=t('build_resolution_reduce'), description=t('build_resolution_reduce_tt'),
        default=0.78, min=0.0, soft_max=1.0, step=10, precision=1, subtype='FACTOR')
    
    build_triangulate: BoolProperty(
        name=t('build_triangulate'), description=t('build_triangulate_tt'), default=False)
    
    build_blend: BoolProperty(
        name=t('build_blend'), description=t('build_blend_tt'), default=True)
    
    build_end_cap: BoolProperty(
        name=t('build_end_cap'), description=t('build_end_cap_tt'), default=True)
    
    detail_simplify: BoolProperty(
        name=t('detail_simplify'), description=t('detail_simplify_tt'), default=True)

    add_twist: FloatProperty(
        name=t('add_twist'), description=t('add_twist_tt'),
        default=0.1, soft_min=0.0, soft_max=1.0, step=500, precision=2, subtype='ANGLE', unit='ROTATION')


    # Build Texture

    textures_list = []

    def textures(self, context):
        """ Return a list of all bark textures. Refresh it when needed. """

        if (not GROVE22_Properties.textures_list or
                context.preferences.addons[__package__].preferences.refresh_textures):
            GROVE22_Properties.textures_list = list_textures(context)
            context.preferences.addons[__package__].preferences.refresh_textures = False
        return GROVE22_Properties.textures_list

    def trigger_swap_textures(self, context):
        """ A selection was made in the bark textures menu - apply the selected texture. """

        context.window.cursor_modal_set('WAIT')
        swap_textures(self, context)
        self.previous_texture_repeat = self.texture_repeat
        context.window.cursor_modal_restore()

    texture_bark: EnumProperty(
        name=t('texture_bark'),
        items=textures,
        update=trigger_swap_textures,
        description=t('texture_bark_tt'))

    bark_material_name: StringProperty(
        name='', description='',
        default='', maxlen=1024)

    texture_aspect_ratio: FloatProperty(
        name='texture_aspect_ratio', description='', default=3.0)

    texture_repeat: IntProperty(
        name=t('texture_repeat'), description=t('texture_repeat_tt'),
        default=3, min=1, soft_max=10,
        update=trigger_swap_textures)

    previous_texture_repeat: IntProperty(
        name='previous_texture_repeat',
        default=3,
        options={'HIDDEN'})


    core_properties = [
        'simulation_scale',
        'add_angle',
        'add_chance',
        'add_only_on_end',
        'add_chance_reduce',
        'add_fork',
        'add_horizontal',
        'add_planar',
        'add_side_branches',
        'add_bud_life',
        'add_regenerate',
        'add_up',
        'add_twist',
        'auto_prune_enabled',
        'auto_prune_low',
        'auto_prune_keep_thick',
        'auto_prune_dangling',
        'bend_mass',
        'bend_twig_mass_solidify',
        'bend_twig_mass',
        'bend_reaction',
        'thicken_deadwood',
        'surround_enabled',
        'surround_grow',
        'surround_density',
        'surround_distance',
        'surround_height',
        'drop_weak',
        'drop_shaded',
        'drop_obsolete',
        'drop_decay',
        'favor_bright',
        'favor_end',
        'favor_end_reduce',
        'favor_rising',
        'favor_dwindle',
        'grow_length',
        'grow_nodes',
        'twig_longevity',
        'twig_density',
        'twig_wither',
        'twig_side_on_tips',
        'shade_area_depth',
        'shade_area',
        'shade_area_reduce',
        'shade_leaf_sides',
        'shade_branches',
        'shade_alongside',
        'shade_alongside_diameter',
        'thicken_join',
        'thicken_tips',
        'thicken_tips_reduce',
        'thicken_base_buttress',
        'thicken_base_scale',
        'thicken_base_shape',
        'turn_to_light',
        'turn_to_horizon',
        'turn_random',
        'turn_up',
        'turn_up_in_shade',
        'react_attract_strength',
        'react_attract_falloff',
        'react_deflect_strength',
        'react_deflect_falloff',
        'stake_enabled',
        'stake_height',
        'sow_enabled',
        'sow_age',
        'sow_chance',
        'sow_distance',
        'sow_limit',
    ]

    def convert_to_core_properties(self):
        """ Convert the properties that are needed for simulation to the core. """

        properties_dictionary = {}
        for parameter in self.core_properties:
            if parameter in ['auto_prune_low', 'auto_prune_dangling', 'stake_height']:
                properties_dictionary[parameter] = getattr(self, parameter) / self.simulation_scale
            else:
                properties_dictionary[parameter] = getattr(self, parameter)

        json_string = json.dumps(properties_dictionary)
        return the_grove_core.io.properties_from_json_string(json_string)

    def read_from_core_properties(self, props):
        """ Read properties from a grove object. Like when importing a .grove file.
            The inverse of the above function convert_to_core_properties. """

        for parameter in self.core_properties:
            if hasattr(self, parameter) and hasattr(props, parameter):
                if parameter in ['auto_prune_low', 'auto_prune_dangling', 'stake_height']:
                    self[parameter] = getattr(props, parameter) * self.simulation_scale
                else:
                    self[parameter] = getattr(props, parameter)
        else:
            print("Skipping parameter " + parameter)
