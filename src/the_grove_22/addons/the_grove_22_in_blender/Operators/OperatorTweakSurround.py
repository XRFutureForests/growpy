
""" A simple UI operator for tweaking the surround shade object.

    Copyright 2019 - 2025, Wybren van Keulen, The Grove """


import bpy
from mathutils import Vector
from numpy import array, sum
from gpu.shader import from_builtin
from gpu.state import blend_set
from gpu_extras.batch import batch_for_shader

from ..Interface.Interface import Interface, TouchButton, TouchSlider, TouchTurntable, TouchToggle
from ..Interface.Canvas import Canvas
from ..Turntable import turn_the_table
from ..Languages.Translation import t
from ..File import load_grove


def draw_2d(self, context):
    """ Draw the tool's interface and preview. """

    if self.space_data != context.space_data:  # Prevent drawing in other 3D views.
        return

    scale = self.grove_properties.simulation_scale
    if self.grove_properties.surround_grow:
        height = self.grove_properties.height
    else:
        height = self.grove_properties.surround_height

    color = (1.0, 0.9, 0.4, 0.3)
    m = bpy.context.area.spaces.active.region_3d.perspective_matrix
    m = (tuple(m.col[0]), tuple(m.col[1]), tuple(m.col[2]), tuple(m.col[3]))
    (points, indices) = self.grove.build_surround_preview_2d(
        height, m, bpy.context.region.width, bpy.context.region.height)
    flat_shader = from_builtin('UNIFORM_COLOR')
    flat_shader.uniform_float("color", color)
    flat_shader.bind()
    blend_set('ALPHA')
    batch = batch_for_shader(flat_shader, 'TRIS', {"pos": points}, indices=indices)
    batch.draw(flat_shader)

    self.interface.draw()


def status_text_callback(header, _):
    """ Fill Blender's status bar with shortcuts. """

    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')


class GROVE22_OT_TweakSurround(bpy.types.Operator):

    bl_idname = "the_grove_22.tweak_surround"
    bl_label = t('tweak')
    bl_description = t('tweak_tt')
    bl_options = {'REGISTER', 'UNDO'}

    mode = 0
    rotation_offset = 0.0

    _turntable_timer = None
    _handle_draw_2d = None
    canvas = Canvas()

    interface = Interface()

    interface.widgets.append(
        TouchButton(action='Back', label=t('close_button'), tooltip=t('close_button_tt'), icon='DOT'))

    turntable = TouchTurntable(action='View', label=t('turntable'), tooltip=t('turntable_tt'), icon='VIEW')
    interface.widgets.append(turntable)

    interface.add_spacer()

    density_dial = TouchSlider(
        action='update',
        label=t('surround_density'),
        tooltip=t('surround_density_tt'),
        value_min=0.0, value_max=1.0, value_default=0.7,
        step=0.1, step_precision=0.01, dots=10, digits=1)

    distance_dial = TouchSlider(
        action='update',
        label=t('surround_distance'),
        tooltip=t('surround_distance_tt'),
        value_min=2.0, value_max=15.0, value_default=4.0,
        step=0.5, step_precision=0.1, dots=16, digits=1)

    height_dial = TouchSlider(
        action='update',
        label=t('surround_height'),
        tooltip=t('surround_height_tt'),
        value_min=0.0, value_max=50.0, value_default=5.0,
        step=0.5, step_precision=0.1, dots=32, digits=1)

    auto_height_dial = TouchToggle(
        action='update',
        label=t('surround_grow'),
        tooltip=t('surround_grow_tt'))

    auto_height_dial.minimal = True
    height_dial.minimal = True
    distance_dial.minimal = True
    density_dial.minimal = True

    interface.widgets.append(auto_height_dial)
    interface.widgets.append(height_dial)
    interface.widgets.append(distance_dial)
    interface.widgets.append(density_dial)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.surround_lines = []
        self.grove = None
        self.grove_properties = None

        self.mouse = Vector((0.0, 0.0))
        self.mouse_start = Vector((0.0, 0.0))
        self.origin = Vector((0.0, 0.0))
        self.current_view_matrix = 1

        self.space_data = None  # Used to only draw in the active 3D view.

        self.viewing = False

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the add object menu entry is greyed out. """

        return context.mode == 'OBJECT'

    def modal(self, context, event):
        """ Event loop. """

        win_man = context.window_manager

        if event.type in ['MOUSEMOVE', 'LEFTMOUSE']:
            self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))

        if event.type == 'TIMER':
            if self._turntable_timer is not None:
                win_man.event_timer_remove(self._turntable_timer)
                self._turntable_timer = None

            if self.turntable.modal:
                self.turntable.event_touch_move(self.mouse)
                if self.turntable.do_interpolate:
                    self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)
                turn_the_table(
                    context, self.turntable.vector,
                    self.grove_properties.height * self.grove_properties.simulation_scale,
                    self.interface, offset=self.rotation_offset)

                context.region.tag_redraw()
                return {"RUNNING_MODAL"}

        # Allow viewport navigation.
        elif event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            if self.interface.event_mouse_wheel(self.mouse, event.type == 'WHEELUPMOUSE'):
                action = self.interface.action
                if action == 'View':
                    turn_the_table(
                        context, self.turntable.vector,
                        self.grove_properties.height * self.grove_properties.simulation_scale,
                        self.interface, offset=self.rotation_offset)

                self.grove_properties.surround_density = self.density_dial.value
                self.grove_properties.surround_distance = self.distance_dial.value
                self.grove_properties.surround_height = self.height_dial.value
                self.grove_properties.surround_grow = self.auto_height_dial.value
                context.area.tag_redraw()
                self.grove.set_properties(self.grove_properties.convert_to_core_properties())
                self.surround_lines = self.grove.build_surround_preview()

                context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            else:
                context.region.tag_redraw()
                if event.type == 'WHEELUPMOUSE':
                    context.region_data.view_distance *= 0.8
                else:
                    context.region_data.view_distance *= 1.2
                return {"RUNNING_MODAL"}

        elif event.type in ['MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'ACCENT_GRAVE']:
            self.viewing = True
            return {"PASS_THROUGH"}

        elif event.type == 'Z':
            # Enable the use of the shading pie.
            if not event.ctrl and not event.oskey:
                return {"PASS_THROUGH"}
            else:
                # Undo.
                pass

        elif event.type == 'MOUSEMOVE':

            if self._turntable_timer is not None:
                # When interpolating with the timer, prevent a double redraw.
                return {"RUNNING_MODAL"}

            if self.interface.event_touch_move(self.mouse):
                self.grove_properties.surround_density = self.density_dial.value
                self.grove_properties.surround_distance = self.distance_dial.value
                self.grove_properties.surround_height = self.height_dial.value
                self.grove_properties.surround_grow = self.auto_height_dial.value
                context.area.tag_redraw()
                self.grove.set_properties(self.grove_properties.convert_to_core_properties())
                self.surround_lines = self.grove.build_surround_preview()

                if self.interface.action == 'View':
                    if self.turntable.modal:
                        turn_the_table(
                            context, self.turntable.vector,
                            self.grove_properties.height * self.grove_properties.simulation_scale,
                            self.interface, offset=self.rotation_offset)
                        if self._turntable_timer is None:
                            self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)
                    self.grove.set_properties(self.grove_properties.convert_to_core_properties())
                    self.surround_lines = self.grove.build_surround_preview()

            context.region.tag_redraw()

        elif event.type in ['LEFTMOUSE'] and event.value == 'PRESS':
            turning = self.turntable.modal
            if self.interface.event_touch_down(self.mouse) or self.interface.find_modal():
                if self.interface.action == 'View':
                    if not turning:
                        view = bpy.context.region_data
                        view.update()

                        rotation = view.view_rotation @ Vector((1.0, 0.0, 0.0))
                        rotation = Vector((rotation.x, rotation.y))
                        self.rotation_offset = rotation.angle_signed(Vector((1.0, 0.0)))

                    turn_the_table(
                        context, self.turntable.vector,
                        self.grove_properties.height * self.grove_properties.simulation_scale,
                        self.interface, offset=self.rotation_offset)
                    if self._turntable_timer is None:
                        # Enable this for animation at the start.
                        self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)

            context.region.tag_redraw()

            return {"RUNNING_MODAL"}

        elif event.type in ['LEFTMOUSE'] and event.value == 'RELEASE':

            if self.interface.find_modal():
                self.interface.event_touch_release(self.mouse)
                action = self.interface.action

                if action == 'View_CLICK':
                    turn_the_table(
                        context, self.turntable.vector,
                        self.grove_properties.height * self.grove_properties.simulation_scale,
                        self.interface, offset=self.rotation_offset)
                    return {"RUNNING_MODAL"}

                context.region.tag_redraw()
                self.interface.action = 'NONE'
                return {"RUNNING_MODAL"}
            else:
                self.interface.event_touch_release(self.mouse)
                if self.interface.action != 'NONE':
                    action = self.interface.action
                    if action == 'Back':
                        self.cancel(context)
                        return {'FINISHED'}

            self.grove_properties.surround_density = self.density_dial.value
            self.grove_properties.surround_distance = self.distance_dial.value
            self.grove_properties.surround_height = self.height_dial.value
            self.grove_properties.surround_grow = self.auto_height_dial.value
            context.area.tag_redraw()

        elif event.type in ['RIGHTMOUSE', 'ESC'] and event.value == 'PRESS':
            if self.interface.find_modal():
                self.interface.cancel()
                context.region.tag_redraw()
                return {"RUNNING_MODAL"}
            else:
                self.cancel(context)
                return {'FINISHED'}

        if self.viewing:
            self.viewing = False

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        """ When starting the tool, do some initialization. """

        # First check if the user has moved around trees and if so, then replant them.
        bpy.ops.the_grove_22.replant('INVOKE_DEFAULT')

        self.grove_properties = context.collection.GROVE22_Properties
        self.grove_properties.is_tool_active_tweak_surround = True

        self.grove = load_grove(context.collection)
        if not self.grove:
            self.cancel(context)
            self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
            return {'CANCELLED'}

        # If recording growth, make sure the frame is set to the tree's current state.
        if self.grove_properties.record_enabled:
            context.scene.frame_set((
                self.grove_properties.age
                * self.grove_properties.record_interval
                + self.grove_properties.record_interval - 1
                + self.grove_properties.record_start_frame))

        self.mouse_start = Vector((event.mouse_region_x, event.mouse_region_y))
        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.window_manager.modal_handler_add(self)

        context.workspace.status_text_set(status_text_callback)

        self.current_view_matrix = sum(array(context.region_data.view_matrix))
        self.density_dial.value = self.grove_properties.surround_density
        self.distance_dial.value = self.grove_properties.surround_distance
        self.height_dial.value = self.grove_properties.surround_height
        self.auto_height_dial.value = self.grove_properties.surround_grow
        self.grove.set_properties(self.grove_properties.convert_to_core_properties())
        self.surround_lines = self.grove.build_surround_preview()
        self.interface.update()

        return {"RUNNING_MODAL"}

    def cancel(self, context):
        """ When closing the tool, set things back to the way they were. """

        self.grove_properties.is_tool_active_tweak_surround = False
        if self._handle_draw_2d:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')
        context.workspace.status_text_set(text=None)

        self.interface.action = 'NONE'
        if self._turntable_timer is not None:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None

        self.interface.cancel()

        context.window.cursor_modal_restore()
        context.area.tag_redraw()
