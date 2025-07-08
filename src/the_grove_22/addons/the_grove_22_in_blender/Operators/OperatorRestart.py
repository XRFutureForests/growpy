
""" Delete all trees and start over.
    A new tree is planted at the scene origin.
    Or if empty objects are present, each one is converted to a new tree.

    Copyright 2014 - 2025, Wybren van Keulen, The Grove """


import bpy
from mathutils import Vector

from ..Languages.Translation import t
from ..File import save_grove
from .OperatorBuild import build, clean_grove, clean_record
from ..Interface.Interface import Interface, TouchButton
from ..Presets import read_preset
from .OperatorPlant import delete_existing_empties
from .OperatorPlant import add_single_placeholder

from ..Core import import_core
the_grove_core = import_core()


def draw_2d(self, context):
    """ Draw the interface. """

    if self.space_data != context.space_data:  # Prevent drawing in other 3D views.
        return

    if self._double_click_timer is not None:
        return

    self.interface.draw()


def status_text_callback(header, _):
    """ Add shortcuts to Blender's status bar. """

    header.layout.label(text="Rotate View", icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')


class GROVE22_OT_Restart(bpy.types.Operator):

    bl_idname = "the_grove_22.restart"
    bl_label = t('restart')
    bl_description = t('restart_tt')
    bl_options = {'REGISTER', 'UNDO'}

    _handle_draw = None
    _double_click_timer = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mouse = Vector((0.0, 0.0))
        self.mouse_start = Vector((0.0, 0.0))
        self.space_data = None  # Used to only draw in the active 3D view.
        self.grove_properties = None

    # Interface
    interface = Interface()
    interface.widgets.append(
        TouchButton(
            action='Back',
            label=t('close_button'), tooltip=t('close_button_tt'),
            icon='CHECKMARK'))
    interface.widgets.append(
        TouchButton(
            action='Revert',
            label=t('restart_revert'), tooltip=t('restart_revert_tt'),
            icon='CHECKMARK'))
    interface.widgets.append(
        TouchButton(
            action='SingleTree',
            label=t('restart_single_tree'), tooltip=t('restart_single_tree_tt'),
            icon='CHECKMARK'))

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the operator is greyed out."""

        return context.mode == 'OBJECT'

    def modal(self, context, event):
        """ Event handling. """
        if event.type in ['MOUSEMOVE', 'LEFTMOUSE']:
            self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))

            if self._double_click_timer is not None:
                if (self.mouse - self.mouse_start).length > 80.0:
                    # This allows a longer double click time. Without this it can be annoying if you're working fast.
                    self.cancel(context)
                    return {'FINISHED'}

        if event.type == 'TIMER':
            if self._double_click_timer is not None:
                self.cancel(context)
                return {'FINISHED'}

        elif event.type == 'MOUSEMOVE':
            if self.interface.event_touch_move(self.mouse):
                context.area.tag_redraw()
            return {"RUNNING_MODAL"}

        if event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            return {'PASS_THROUGH'}
            # To allow viewport zooming.

        # Allow viewport navigation. Previously drawn lines will be removed, because they make no sense in another view.
        elif event.type in [
                'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'ACCENT_GRAVE', 'Z']:
            if event.type in 'Z' and event.ctrl:
                pass
            else:
                return {"PASS_THROUGH"}

        elif event.type in ['LEFTMOUSE'] and event.value == 'PRESS':
            if self.interface.event_touch_down(self.mouse) or self.interface.find_modal():
                context.region.tag_redraw()
                return {"RUNNING_MODAL"}

        elif event.type in ['LEFTMOUSE'] and event.value == 'RELEASE':
            if self._double_click_timer is not None:
                context.window_manager.event_timer_remove(self._double_click_timer)
                self._double_click_timer = None
                context.workspace.status_text_set(status_text_callback)
                context.area.tag_redraw()

            if self.interface.event_touch_release(self.mouse):
                if self.interface.action != 'NONE':
                    if self.interface.action == 'Back':
                        self.cancel(context)
                        return {'FINISHED'}
                    elif self.interface.action == 'Revert':
                        self.revert()
                        self.cancel(context)
                        return {'FINISHED'}
                    elif self.interface.action == 'SingleTree':
                        self.single_tree()
                        self.cancel(context)
                        return {'FINISHED'}

            context.region.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type in ['RIGHTMOUSE', 'ESC'] and event.value == 'PRESS':
            if self.interface.find_modal():
                self.interface.cancel()
                context.region.tag_redraw()
                return {"RUNNING_MODAL"}
            else:
                self.cancel(context)
                return {'FINISHED'}

        return {"RUNNING_MODAL"}

    def execute(self, context):
        restart()
        return {'FINISHED'}

    def invoke(self, context, event):
        """ Initialize. """

        self.grove_properties = context.collection.GROVE22_Properties
        self.grove_properties.is_tool_active_restart = True

        restart()

        win_man = context.window_manager
        win_man.modal_handler_add(self)

        self._handle_draw = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        self.interface.update()
        context.region.tag_redraw()

        self.mouse_start = Vector((event.mouse_region_x, event.mouse_region_y))

        self._double_click_timer = win_man.event_timer_add(0.35, window=bpy.context.window)

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        """ Clean up. """

        if self._double_click_timer is not None:
            context.window_manager.event_timer_remove(self._double_click_timer)

        self.grove_properties.is_tool_active_restart = False
        bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw, 'WINDOW')

        context.workspace.status_text_set(text=None)  # To release the status bar for new use.
        context.area.tag_redraw()
        context.window.cursor_modal_restore()

    def single_tree(self):
        """ Remove all previously planted placeholders and restart with a single tree at the origin. """

        context = bpy.context
        clean_grove(context.collection, roots=True)
        clean_record(context.collection)
        delete_existing_empties()
        add_single_placeholder()
        restart()

    def revert(self):
        """ First revert all properties that are not saved with a preset. Then reload the active preset. """

        props = self.grove_properties
        props.twig_menu = t('twig_pick_objects')
        props.twig_object_end = None
        props.twig_object_side = None
        props.twig_object_upward = None
        props.twig_object_dead = None
        props.simulation_flushes = 7
        props.record_enabled = False
        props.record_interval = 5
        props.record_start_frame = 1
        props.react_enabled = False
        props.react_block_object = None
        props.react_deflect_object = None
        props.react_attract_object = None
        props.react_shade_object = None
        props.wind_breeze = 0.2
        props.build_resolution = 16
        props.build_resolution_reduce = 0.8
        props.texture_repeat = 3

        read_preset(self.grove_properties.presets_menu, self.grove_properties)

        self.single_tree()


def restart():
    """ Remove all trees and plant new ones at each placeholder empty object. """

    context = bpy.context
    clean_grove(context.collection, roots=True)
    clean_record(context.collection)

    properties = context.collection.GROVE22_Properties
    properties.age_of_last_grown_tree = properties.age * 1
    grove = create_new_trees(context, context.collection, properties)
    build(context, properties, grove, context.collection, rebuild=True)


def create_new_trees(context, collection, properties):
    """ Create new branches at the position of empty objects. """

    properties.age = 0
    properties.height = 0.0
    properties.number_of_branches = 0
    properties.number_of_polygons = 0

    grove = the_grove_core.Grove()
    grove.clear_trees()
    grove.set_properties(properties.convert_to_core_properties())

    # Look for empty objects in the collection. Use them as starting points.
    empties = []
    for obj in collection.objects:
        if obj.type == 'EMPTY':
            empties.append(obj)

    # If there's no empty object, add one at the scene origin.
    if not len(empties):
        empties.append(add_single_placeholder())

    positions = []
    directions = []
    delays = []

    for obj in empties:
        positions.append(obj.location / properties.simulation_scale)
        directions.append(
            obj.matrix_world @ Vector((0.0, 0.002, properties.grow_length / properties.grow_nodes)) - obj.location)
        # If the empty object has a custom property grove_delay, the tree will only start to grow
        # after this number of flushes has passed.
        if 'grove_delay' not in obj:
            obj['grove_delay'] = 0
        delays.append(obj['grove_delay'])

    # Plant the trees.
    for i, pos in enumerate(positions):
        # Add the beginnings of a trunk.
        pos = positions[i]
        direction = directions[i]

        v_pos = the_grove_core.Vector(pos.x, pos.y, pos.z)
        v_direction = the_grove_core.Vector(direction.x, direction.y, direction.z)
        grove.add_new_tree(v_pos, v_direction, delays[i])
        properties.number_of_branches += 1

    save_grove(grove, context.collection)

    return grove
