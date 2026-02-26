
""" This is the main user interface of Grove.
    The panels appear in the UI region of Blender's 3D space.
    Copyright 2014 - 2025, Wybren van Keulen, The Grove """


from os.path import join, dirname, exists

import bpy

from .Languages.Translation import t
from .Presets import presets_path

from .Core import import_core
the_grove_core = import_core()


def get_icons_directory():
    """ Check the theme to see the brightness of the panel background.
        Use either bright or dark icons to contrast the background. """

    try:
        background = bpy.context.preferences.themes['Default'].view_3d.space.panelcolors.back
    except AttributeError:
        background = bpy.context.preferences.themes['Default'].user_interface.wcol_regular.inner

    if background[0] < 0.4:
        return join(join(dirname(__file__), "Resources"), "IconsBright")
    else:
        return join(join(dirname(__file__), "Resources"), "IconsDark")


def load_icons(icon_names):
    icons = bpy.utils.previews.new()
    icons_directory = get_icons_directory()
    for icon_name in icon_names:
        icons.load(icon_name, join(icons_directory, icon_name + ".png"), 'IMAGE')

    return icons


class GroveBasePanel:
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Grove 2.2"

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'OBJECT' and
            'grove' in context.collection)

        # return (
        #     context.mode == 'OBJECT' and
        #     (context.collection.GROVE22_Properties is not None) and
        #     context.collection.GROVE22_Properties.unique_id != '')

    def draw(self, context):
        self.layout.use_property_split = True
        self.layout.use_property_decorate = False


class PanelGrove(GroveBasePanel, bpy.types.Panel):
    bl_label = t('grove')
    bl_idname = "GROVE22_PT_Grove"

    icon_names = ["IconGrowTogether", "IconAdd"]    
    icons = load_icons(icon_names)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def draw(self, context):
        super().draw(context)

        if context.preferences.addons[__package__.split('.')[0]].preferences.edition == 'FALLBACK':
            layout = self.layout
            row = layout.row()
            row.scale_y = 1.0
            row.label(text=t('fallback_info'), icon='CHECKMARK')
            row = layout.row()
            row.scale_y = 1.6
            row.operator("the_grove_22.instructions", icon="URL")
            return

        if context.preferences.addons[__package__.split('.')[0]].preferences.is_trial:
            layout = self.layout

            days_left = the_grove_core.about.days_left()
            if days_left > 0:
                row = layout.row()
                row.scale_y = 1.0
                if days_left == 1:
                    row.label(text='Last day of trial.', icon='INFO')
                else:
                    row.label(text=str(days_left) + ' days left in trial.', icon='INFO')
            else:
                row = layout.row()
                row.scale_y = 1.0
                row.label(text='Expired trial.', icon='INFO')
                row = layout.row()
                row.scale_y = 1.6
                row.operator("the_grove_22.trial_end", icon="URL")
                return

        properties = context.collection.GROVE22_Properties
        layout = self.layout

        old_grove = False
        if hasattr(context.collection, 'THEGROVE10_Properties'):
            if 'unique_id' in context.collection.THEGROVE10_Properties:
                if context.collection.THEGROVE10_Properties['unique_id'] != '':
                    old_grove = True
        if hasattr(context.collection, 'THEGROVE11_Properties') and \
                context.collection.THEGROVE11_Properties.unique_id != '':
            old_grove = True

        if old_grove:
            layout.label(text=t('old_release_warning_line_1'), icon='INFO')
            layout.label(text=t('old_release_warning_line_2'), icon='THREE_DOTS')
            layout.label(text=t('old_release_warning_line_3'), icon='THREE_DOTS')

        if not('GROVE22_Properties' in context.collection and context.collection.GROVE22_Properties.unique_id != ''):
            row = layout.row()
            row.scale_y = 1.0
            row.label(text=t('select_a_grove_collection'), icon='INFO')
        row = layout.row()
        row.scale_y = 1.6
        row.operator("the_grove_22.add", text=t('add_new_grove'), icon_value=self.icons["IconAdd"].icon_id)
        # row.operator("the_grove_22.add", text=t('add_new_grove'), icon='ADD')

        show_set_background = (
            context.area.spaces[0].shading.background_type == 'THEME' and
            context.preferences.themes[0].view_3d.space.gradients.high_gradient[0] < 0.5)
        show_set_background = (
            show_set_background or
            (context.area.spaces[0].shading.background_type == 'VIEWPORT' and
             context.area.spaces[0].shading.background_color[0] < 0.214))
        show_disable_outline = context.area.spaces[0].shading.show_object_outline
        show_warnings = show_set_background or show_disable_outline

        if show_warnings:
            layout.separator()
            layout.label(text=t('tips_info'), icon='INFO')

            if show_disable_outline:
                row = layout.row()
                row.scale_y = 1.4
                row.operator(
                    "the_grove_22.disable_outline", text=t('disable_outline'), icon='OPTIONS')

            if show_set_background:
                row = layout.row()
                row.scale_y = 1.4
                row.operator(
                    "the_grove_22.set_background", text=t('set_background'), icon='OPTIONS')

        if context.collection.GROVE22_Properties.unique_id == '':
            if context.preferences.addons[__package__].preferences.twigs_path == '':
                row = layout.row(align=True)
                row.scale_y = 1.4
                row.operator(
                    "the_grove_22.set_twigs_path", text=t("set_twigs_path"), icon='NEWFOLDER')

            if context.preferences.addons[__package__].preferences.textures_path == '':
                row = layout.row(align=True)
                row.scale_y = 1.4
                row.operator(
                    "the_grove_22.set_textures_path", text=t("set_textures_path"), icon='NEWFOLDER')

        if 'GROVE22_Properties' in context.collection and context.collection.GROVE22_Properties.unique_id != '':
            properties = context.collection.GROVE22_Properties
            layout = self.layout

            row = layout.row()
            row.scale_y = 1.6
            row.operator(
                "the_grove_22.grow_together",
                text=t("grow_together"),
                icon_value=self.icons["IconGrowTogether"].icon_id,
                depress=properties.is_tool_active_grow_together)


class PanelPresets(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_presets")
    bl_idname = "GROVE22_PT_Presets"

    def draw(self, context):
        super().draw(context)
        properties = context.collection.GROVE22_Properties
        layout = self.layout
        layout.use_property_split = False

        row = layout.row(align=True)
        row.scale_y = 1.2
        row.prop(properties, "presets_menu")
        row.prop(properties, "show_add_preset_box", text="", icon='ADD')  # ADD, RNA_ADD, PRESET_NEW, COLLAPSEMENU

        if properties.show_overwrite_preset_box:
            box = layout.box()
            row = box.row()
            row.scale_y = 1.3
            row.label(text=t('overwrite_preset_info').format(properties.preset_name), icon='INFO')
            flow = box.grid_flow(row_major=False, columns=0, even_columns=False, even_rows=False, align=True)
            flow.scale_y = 1.4
            col = flow.column(align=True)
            col.operator("the_grove_22.preset_cancel", icon='LOOP_BACK')
            col = flow.column(align=True)
            col.operator("the_grove_22.preset_overwrite", icon='FILE_TICK')

        elif properties.show_add_preset_box:
            box = layout.box()
            row = box.row()
            row.scale_y = 1.3
            row.label(text=t('name_preset_info'), icon='INFO')
            box.use_property_split = True
            col = box.column(align=True)
            col.scale_y = 1.2
            col.prop(properties, "preset_name", text='')
            box.use_property_split = False

            flow = box.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
            flow.scale_y = 1.65
            col = flow.column(align=True)

            new_name_exists = exists(join(presets_path(), properties.preset_name + ".seed.json"))
            if properties.presets_menu == properties.preset_name or new_name_exists:
                col.enabled = False
            col.operator("the_grove_22.preset_rename", icon='SORTALPHA')
            col = flow.column(align=True)
            col.operator("the_grove_22.preset_save", text=t('save_preset'), icon='FILE_TICK') 

            col = flow.column(align=True)
            col.operator("the_grove_22.preset_import", text=t('import_preset'), icon='IMPORT')

            col = flow.column(align=True)
            col.prop(properties, "show_remove_preset_box", icon='REMOVE')

            row = box.row()
            row.scale_y = 1.65
            row.operator("the_grove_22.preset_cancel", icon='LOOP_BACK')

        elif properties.show_remove_preset_box:
            box = layout.box()
            row = box.row()
            row.scale_y = 1.3
            row.label(text=t('remove_preset_info').format(properties.presets_menu), icon='INFO')
            flow = box.grid_flow(row_major=False, columns=0, even_columns=False, even_rows=False, align=True)
            flow.scale_y = 1.4
            col = flow.column(align=True)
            col.operator("the_grove_22.preset_cancel", icon='LOOP_BACK')
            col = flow.column(align=True)
            col.operator("the_grove_22.preset_remove", icon='TRASH')


class PanelTwigs(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_twigs")
    bl_idname = "GROVE22_PT_Twigs"

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties
        layout = self.layout

        if context.preferences.addons[__package__].preferences.twigs_path == '':
            row = layout.row(align=True)
            row.scale_y = 1.6
            row.operator("the_grove_22.set_twigs_path", text=t("set_twigs_path"), icon='NEWFOLDER')

        row = layout.row(align=True)
        row.scale_y = 1.2
        if properties.twig_menu == t('twig_no_twigs'):
            row.prop(properties, "twig_menu", text="")
        else:
            row.prop(properties, "twig_menu", text="")
            if properties.twig_hide:
                row.prop(properties, "twig_hide", icon='HIDE_ON')
            else:
                row.prop(properties, "twig_hide", icon='HIDE_OFF')

            if properties.do_twig_previews:
                if properties.twig_menu != t('twig_pick_objects') and properties.twig_menu != t('twig_no_twigs'):
                    row = layout.row(align=False)
                    row.scale_y = 1.3
                    row.template_icon_view(properties, "twig_menu", text="")

        if properties.twig_menu != t('twig_no_twigs'):
            if properties.do_twig_collections:
                layout.prop(properties, "twig_collection_long", icon='GROUP')
                layout.prop(properties, "twig_collection_short", icon='GROUP')
                layout.prop(properties, "twig_collection_upward", icon='GROUP')
                layout.prop(properties, "twig_collection_dead", icon='GROUP')
            else:
                layout.prop(properties, "twig_object_end", icon='MESH_CUBE')
                layout.prop(properties, "twig_object_side", icon='MESH_CUBE')
                layout.prop(properties, "twig_object_upward", icon='MESH_CUBE')
                layout.prop(properties, "twig_object_dead", icon='MESH_CUBE')

            lateral_set = properties.do_twig_collections and properties.twig_collection_short or \
                not properties.do_twig_collections and properties.twig_object_side
            dead_set = properties.do_twig_collections and properties.twig_collection_dead or \
                not properties.do_twig_collections and properties.twig_object_dead

            if lateral_set or dead_set:
                layout.separator()

            col = layout.column(align=False)
            self.layout.prop(properties, "wind_breeze")
            if lateral_set:
                col.prop(properties, "twig_density")
            if dead_set:
                col.prop(properties, "twig_wither")


class PanelTwigsMore(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_twigs_more")
    bl_idname = "GROVE22_PT_TwigsMore"
    bl_parent_id = "GROVE22_PT_Twigs"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'OBJECT' and
            (context.collection.GROVE22_Properties is not None) and
            context.collection.GROVE22_Properties.unique_id != '' and
            context.collection.GROVE22_Properties.twig_menu != t('twig_no_twigs'))

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties

        col = self.layout.column()
        col.prop(properties, "twig_longevity")
        col.prop(properties, "twig_view_detail")
        col.prop(properties, "twig_side_on_tips")


class PanelSimulate(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_simulation")
    bl_idname = "GROVE22_PT_Simulate"

    icon_names = [
        "IconGrow", "IconRegrow", "IconPrune", "IconRestart", "IconBend", "IconZoom", "IconPlant",
        "IconDraw", "IconFile", "IconTweak", "IconRoots", "IconBuild", "IconSmooth", "IconAnimate", "IconSkeleton"
    ]
    icons = load_icons(icon_names)

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties
        layout = self.layout

        layout.prop(properties, "simulation_scale")
        layout.prop(properties, "simulation_flushes")

        # Draw info.
        layout.separator()
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        col = flow.column()
        col.label(icon='DOT', text=t('age_info').format(properties.age))
        col = flow.column()
        col.label(icon='DOT', text=t('height_info').format(properties.height * properties.simulation_scale))

        # Draw actions.
        layout.separator()

        expired_trial = \
            context.preferences.addons[__package__.split('.')[0]].preferences.is_trial \
            and the_grove_core.about.days_left() == 0

        if expired_trial:
            row = layout.row()
            row.scale_y = 1.0
            row.label(text='Expired trial.', icon='INFO')
            row = layout.row()
            row.scale_y = 1.6
            row.operator("the_grove_22.trial_end", icon="URL")
            layout.separator()

        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=True)
        flow.scale_y = 1.65

        col = flow.column(align=True)

        if expired_trial:
            col.enabled = False

        col.operator(
            "the_grove_22.grow",
            icon_value=self.icons["IconGrow"].icon_id,
            depress=properties.is_tool_active_grow).do_regrow = False
        col.operator(
            "the_grove_22.prune",
            icon_value=self.icons["IconPrune"].icon_id,
            depress=properties.is_tool_active_prune)
        if context.preferences.addons[__package__].preferences.edition != 'STARTER':
            col.operator(
                "the_grove_22.draw",
                icon_value=self.icons["IconDraw"].icon_id,
                depress=properties.is_tool_active_draw)
        col.operator(
            "the_grove_22.roots",
            icon_value=self.icons["IconRoots"].icon_id,
            depress=properties.is_tool_active_roots)
        col.operator(
            "the_grove_22.zoom",
            icon_value=self.icons["IconZoom"].icon_id,
            depress=properties.is_tool_active_zoom)

        col = flow.column(align=True)

        if expired_trial:
            col.enabled = False

        col.operator(
            "the_grove_22.regrow",
            icon_value=self.icons["IconRegrow"].icon_id,
            depress=properties.is_tool_active_regrow)
        if context.preferences.addons[__package__].preferences.edition != 'STARTER':
            col.operator(
                "the_grove_22.bend",
                icon_value=self.icons["IconBend"].icon_id,
                depress=properties.is_tool_active_bend)
        col.operator(
            "the_grove_22.plant",
            icon_value=self.icons["IconPlant"].icon_id,
            depress=properties.is_tool_active_plant)
        col.operator(
            "the_grove_22.file",
            icon_value=self.icons["IconFile"].icon_id,
            depress=properties.is_tool_active_file)
        col.operator(
            "the_grove_22.restart",
            icon_value=self.icons["IconRestart"].icon_id,
            depress=properties.is_tool_active_restart)

        layout.separator()


class PanelSow(GroveBasePanel, bpy.types.Panel):

        bl_label = t("sow_enabled")
        bl_idname = "GROVE22_PT_Sow"
        bl_options = {'DEFAULT_CLOSED'}

        def draw_header(self, context):
            """ Add a checkmark to the panel header. """

            properties = context.collection.GROVE22_Properties
            self.layout.prop(properties, "sow_enabled", text="")

        def draw(self, context):
            super().draw(context)

            properties = context.collection.GROVE22_Properties

            col = self.layout.column()
            col.enabled = properties.sow_enabled
            col.prop(properties, "sow_age")
            col.prop(properties, "sow_chance")
            col.prop(properties, "sow_distance")
            col.prop(properties, "sow_limit")


class PanelRecord(GroveBasePanel, bpy.types.Panel):

    bl_label = t("record_enabled")
    bl_idname = "GROVE22_PT_Record"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'OBJECT' and
            (context.collection.GROVE22_Properties is not None) and
            context.collection.GROVE22_Properties.unique_id != '' and 
            context.preferences.addons[__package__].preferences.edition != 'STARTER')

    def draw_header(self, context):
        """ Add a checkmark to the panel header. """

        properties = context.collection.GROVE22_Properties
        self.layout.prop(properties, "record_enabled", text="")

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties

        col = self.layout.column()
        col.enabled = properties.record_enabled
        col.prop(properties, "record_interval")
        col.prop(properties, "record_start_frame")


class PanelReact(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_react")
    bl_idname = "GROVE22_PT_React"
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'OBJECT' and
            (context.collection.GROVE22_Properties is not None) and
            context.collection.GROVE22_Properties.unique_id != '' and
            context.preferences.addons[__package__].preferences.edition != 'STARTER')

    def draw_header(self, context):
        """ Add a checkmark to the panel header. """

        properties = context.collection.GROVE22_Properties
        self.layout.prop(properties, "react_enabled", text="")

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties
        layout = self.layout
        layout.enabled = properties.react_enabled

        layout.prop(properties, "react_shade_object", icon='MESH_CUBE')

        layout.prop(properties, "react_block_object", icon='MESH_CUBE')

        layout.prop(properties, "react_deflect_object", icon='MESH_CUBE')
        if properties.react_deflect_object is not None:
            col = layout.column()
            col.prop(properties, "react_deflect_strength")
            col.prop(properties, "react_deflect_falloff")
            col.separator()

        layout.prop(properties, "react_attract_object", icon='MESH_CUBE')
        if properties.react_attract_object is not None:
            col = layout.column()
            col.prop(properties, "react_attract_strength")
            col.prop(properties, "react_attract_falloff")


class PanelStake(GroveBasePanel, bpy.types.Panel):

    bl_label = t("stake_enabled")
    bl_idname = "GROVE22_PT_Stake"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):

        properties = context.collection.GROVE22_Properties
        self.layout.prop(properties, "stake_enabled", text="")

    def draw(self, context):

        properties = context.collection.GROVE22_Properties
        layout = self.layout
        layout.enabled = properties.stake_enabled
        layout.use_property_split = True
        layout.use_property_decorate = False

        layout.prop(properties, "stake_height")


class PanelAutoPrune(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_auto_prune")
    bl_idname = "GROVE22_PT_AutoPrune"

    def draw_header(self, context):
        properties = context.collection.GROVE22_Properties
        self.layout.prop(properties, "auto_prune_enabled", text="")

    def draw(self, context):
        properties = context.collection.GROVE22_Properties
        layout = self.layout
        layout.enabled = properties.auto_prune_enabled
        layout.use_property_split = True
        layout.use_property_decorate = False

        col = layout.column()
        col.prop(properties, "auto_prune_low")
        col.prop(properties, "auto_prune_keep_thick")
        col.prop(properties, "auto_prune_dangling")


class PanelFlow(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_favor")
    bl_idname = "GROVE22_PT_Favor"

    def draw(self, context):
        super().draw(context)
        properties = context.collection.GROVE22_Properties
        layout = self.layout

        col = layout.column()
        col.prop(properties, "favor_bright")

        col = layout.column(align=True)
        col.prop(properties, "favor_end")
        # col.prop(properties, "shade_avoidance")
        col.prop(properties, "favor_end_reduce")

        col = layout.column()
        col.prop(properties, "favor_rising")
        
        # col = layout.column()
        # col.prop(properties, "favor_dwindle")


class PanelDrop(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_drop")
    bl_idname = "GROVE22_PT_Drop"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        super().draw(context)
        properties = context.collection.GROVE22_Properties

        col = self.layout.column()
        col.prop(properties, "drop_weak")
        col.prop(properties, "drop_shaded")
        col.prop(properties, "drop_obsolete")
        col.prop(properties, "drop_decay")


class PanelAdd(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_add")
    bl_idname = "GROVE22_PT_Add"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties
        layout = self.layout
        
        layout.prop(properties, "add_side_branches")

        col = layout.column(align=True)
        col.prop(properties, "add_chance")
        col.prop(properties, "add_chance_reduce")
        col = layout.column(align=False)
        col.prop(properties, "add_only_on_end")

        layout.separator()

        col = layout.column()
        col.prop(properties, "add_regenerate")
        col.prop(properties, "add_fork")
        # col.prop(properties, "add_bud_life")

        layout.separator()

        layout.label(text=t('label_direction') + ':')
        col = layout.column()
        col.prop(properties, "add_angle")
        # col.prop(properties, "add_twist")
        col.prop(properties, "add_horizontal")
        col.prop(properties, "add_up")
        # flow.prop(properties, "add_planar")


class PanelTurn(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_turn")
    bl_idname = "GROVE22_PT_Turn"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties

        col = self.layout.column()
        # col = self.layout.column(align=True)
        col.prop(properties, "turn_up")
        # col.prop(properties, "turn_up_in_shade")
        col.prop(properties, "turn_to_horizon")
        col.prop(properties, "turn_to_light")
        col.prop(properties, "turn_random")
        col.prop(properties, "add_twist")


class PanelGrow(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_grow")
    bl_idname = "GROVE22_PT_Grow"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        super().draw(context)
        properties = context.collection.GROVE22_Properties

        col = self.layout.column()
        col.prop(properties, "grow_length")
        col.prop(properties, "grow_nodes")


class PanelThicken(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_thicken")
    bl_idname = "GROVE22_PT_Thicken"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        super().draw(context)
        
        properties = context.collection.GROVE22_Properties
        
        col = self.layout.column()
        col.prop(properties, "thicken_join")
        col.prop(properties, "thicken_deadwood")

        col = self.layout.column(align=True)
        col.prop(properties, "thicken_tips")
        col.prop(properties, "thicken_tips_reduce")


class PanelBend(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_bend")
    bl_idname = "GROVE22_PT_Bend"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties
        layout = self.layout

        col = layout.column(align=True)
        col.prop(properties, "bend_mass")

        col = layout.column(align=True)
        col.prop(properties, "bend_twig_mass")
        col.prop(properties, "bend_twig_mass_solidify")

        col = layout.column(align=False)
        col.prop(properties, "bend_reaction")


class PanelSurround(GroveBasePanel, bpy.types.Panel):

    bl_label = t("surround_enabled")
    bl_idname = "GROVE22_PT_Surround"
    bl_options = {'DEFAULT_CLOSED'}

    def draw_header(self, context):
        properties = context.collection.GROVE22_Properties
        self.layout.prop(properties, "surround_enabled", text="")

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties
        self.layout.enabled = properties.surround_enabled

        col = self.layout.column(align=False)
        row = col.row()
        row.prop(properties, "surround_density")
        row.operator(
            "the_grove_22.tweak_surround",
            text="", icon_value=PanelSimulate.icons["IconTweak"].icon_id,
            depress=properties.is_tool_active_tweak_surround)
        col.prop(properties, "surround_distance")
        row = col.row(align=True)
        cola = row.column(align=True)
        cola.enabled = not properties.surround_grow
        cola.prop(properties, "surround_height")
        col.prop(properties, "surround_grow")


class PanelShade(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_shade")
    bl_idname = "GROVE22_PT_Shade"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties
        layout = self.layout

        col = layout.column(align=True)
        row = col.row(align=True)
        row.prop(properties, "shade_area")
        row.operator(
            "the_grove_22.tweak_shade", text="",
            icon_value=PanelSimulate.icons["IconTweak"].icon_id,
            depress=properties.is_tool_active_tweak_shade)
        col.prop(properties, "shade_area_reduce")

        layout.prop(properties, "shade_area_depth")
        # layout.prop(properties, "shade_leaf_sides")
        
        col = layout.column(align=True)
        row = col.row(align=True)
        col.prop(properties, "shade_alongside")
        col.prop(properties, "shade_alongside_diameter")
        layout.prop(properties, "shade_branches")


class PanelBuild(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_build")
    bl_idname = "GROVE22_PT_Build"

    def draw(self, context):
        super().draw(context)
        properties = context.collection.GROVE22_Properties

        row = self.layout.row(align=True)
        row.scale_y = 1.6
        if context.preferences.addons[__package__].preferences.edition != 'STARTER':
            row.operator(
                "the_grove_22.build_skeleton",
                icon_value=PanelSimulate.icons["IconSkeleton"].icon_id,
                depress=properties.is_tool_active_build_skeleton)

        row = self.layout.row(align=True)
        row.scale_y = 1.6
        if context.preferences.addons[__package__].preferences.edition != 'STARTER':
            row.operator(
                "the_grove_22.animate_wind",
                icon_value=PanelSimulate.icons["IconAnimate"].icon_id,
                depress=properties.is_tool_active_animate_wind)
        
        row = self.layout.row(align=True)
        row.scale_y = 1.6
        row.operator("the_grove_22.build", icon_value=PanelSimulate.icons["IconBuild"].icon_id)
        if context.preferences.addons[__package__].preferences.edition != 'STARTER':
            row.operator("the_grove_22.smooth", icon_value=PanelSimulate.icons["IconSmooth"].icon_id)


class PanelBuildBase(GroveBasePanel, bpy.types.Panel):
            
    bl_label = t("panel_build_base")
    bl_idname = "GROVE22_PT_BuildBase"
    bl_parent_id = "GROVE22_PT_Build"
    bl_options = {'DEFAULT_CLOSED'}
    
    def draw(self, context):
        super().draw(context)
    
        properties = context.collection.GROVE22_Properties
    
        col = self.layout.column()
        col.prop(properties, "thicken_base_scale")
        col.prop(properties, "thicken_base_shape")
        col.prop(properties, "thicken_base_buttress")


class PanelBuildTexture(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_build_texture")
    bl_idname = "GROVE22_PT_BuildTexture"
    bl_parent_id = "GROVE22_PT_Build"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties
        layout = self.layout

        if context.preferences.addons[__package__].preferences.textures_path == '':
            row = layout.row(align=True)
            row.scale_y = 1.6
            row.operator("the_grove_22.set_textures_path", text=t("set_textures_path"), icon='NEWFOLDER')

        layout.prop(properties, "texture_bark")
        layout.prop(properties, "texture_repeat")


class PanelBuildWind(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_build_wind")
    bl_idname = "GROVE22_PT_BuildWind"
    bl_parent_id = "GROVE22_PT_Build"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties

        row = self.layout.row(align=True)
        row.scale_y = 1.6
        if context.preferences.addons[__package__].preferences.edition != 'STARTER':
            row.operator(
                "the_grove_22.animate_wind",
                icon_value=PanelSimulate.icons["IconAnimate"].icon_id,
                depress=properties.is_tool_active_animate_wind)

        self.layout.prop(properties, "wind_breeze")


class PanelBuildMesh(GroveBasePanel, bpy.types.Panel):

    bl_label = t("panel_build_mesh")
    bl_idname = "GROVE22_PT_BuildMesh"
    bl_parent_id = "GROVE22_PT_Build"
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        super().draw(context)

        properties = context.collection.GROVE22_Properties
        layout = self.layout
        
        flow = layout.grid_flow(row_major=True, columns=0, even_columns=True, even_rows=False, align=False)
        col = flow.column()
        col.label(
            icon="DOT",
            text=t('polygons_info').format(
                properties.number_of_polygons))
        col = flow.column()
        if properties.number_of_branches == 1:
            col.label(
                icon="DOT",
                text=t('branch_info').format(
                    properties.number_of_branches, properties.number_of_polygons))
        else:
            col.label(
                icon="DOT",
                text=t('branches_info').format(
                    properties.number_of_branches, properties.number_of_polygons))
        layout.separator()

        starter = context.preferences.addons[__package__.split('.')[0]].preferences.edition == 'STARTER'
        
        if not starter:
            col = layout.column(align=True)
            col.prop(properties, "build_resolution")
            col.prop(properties, "build_resolution_reduce")
            
            col = self.layout.column()
            col.prop(properties, "build_blend")
            col.prop(properties, "build_end_cap")
            # col.prop(properties, "detail_simplify")
            col.prop(properties, "build_triangulate")
            
            layout.separator()
            layout.label(text=t('label_cutoff') + ':')
            col = self.layout.column()
            col.prop(properties, "build_cutoff_age")
            col.prop(properties, "build_cutoff_thickness")
        else:
            layout.separator()
            layout.label(text=t('label_cutoff') + ':')
            col = self.layout.column()
            col.prop(properties, "build_cutoff_age")


class PanelEdit(GroveBasePanel, bpy.types.Panel):

    bl_label = t('grove')
    bl_idname = "GROVE22_PT_Edit"

    @classmethod
    def poll(cls, context):
        return (
            context.mode == 'EDIT_MESH' and
            context.preferences.addons[__package__].preferences.edition != 'STARTER')

    def draw(self, context):
        super().draw(context)

        layout = self.layout

        if 'grove' in context.active_object:
            row = layout.row()
            row.scale_y = 1.4
            row.operator(
                "the_grove_22.select_linked_branches", text=t('select_linked_branches'), icon="LINKED")
            row = layout.row()
            row.scale_y = 1.4
            row.operator(
                "the_grove_22.select_thicker", text=t('select_thicker'), icon="LINKED")
        else:
            row = layout.row()
            row.scale_y = 1.4
            row.operator(
                "the_grove_22.add", text=t('add_new_grove'),
                icon_value=PanelGrove.icons["IconAdd"].icon_id)
