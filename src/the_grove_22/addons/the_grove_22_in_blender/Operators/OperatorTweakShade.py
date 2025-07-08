
""" A simple UI operator for tweaking the shade object.

    Copyright 2019 - 2025, Wybren van Keulen, The Grove """


import bpy
from mathutils import Vector
from numpy import array, sum
from gpu.state import blend_set as gpu_blend_set
from gpu.shader import from_builtin as shader_from_builtin
from gpu_extras.batch import batch_for_shader

from ..Interface.Interface import Interface, TouchButton, TouchSlider, TouchTurntable, TouchToggle, TouchPanel
from ..Turntable import turn_the_table
from ..Languages.Translation import t
from .OperatorBuild import build
from ..File import load_grove


def draw_2d(self, context):
    """ Draw the interface. """

    if self.space_data != context.space_data:
        # Prevent drawing in other 3D views.
        return

    self.interface.draw()


def draw_3d(self, context):
    """ Draw leaf areas. """

    # Prevent drawing in other 3D views.
    if self.space_data != context.space_data:
        return

    gpu_blend_set('ALPHA')

    # Draw the leaf areas.
    shader = self.shader
    shader.bind()
    shader.uniform_float("color", (1.0, 0.9, 0.4, 0.45))
    self.leaf_areas_batch.draw(shader)


def status_text_callback(header, _):
    """ Add shortcuts to Blender's status bar. """

    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')


class GROVE22_OT_TweakShade(bpy.types.Operator):

    bl_idname = "the_grove_22.tweak_shade"
    bl_label = t('tweak')
    bl_description = t('tweak_tt')
    bl_options = {'REGISTER', 'UNDO'}

    rotation_offset = 0.0

    _turntable_timer = None
    _handle_draw_3d = None
    _handle_draw_2d = None

    interface = Interface()

    interface.widgets.append(
        TouchButton(action='Back', label=t('close_button'), tooltip=t('close_button_tt'), icon='DOT'))

    turntable = TouchTurntable(
        action='View',
        label=t('turntable'), tooltip=t('turntable_tt'),
        icon='VIEW')
    interface.widgets.append(turntable)

    interface.add_spacer()

    # Leaves panel
    leaves_panel = TouchPanel(label=t('shade_leaves_panel'))

    leaf_area_dial = TouchSlider(
        action='update',
        label=t('shade_area'), tooltip=t('shade_area_tt'),
        value_min=0.01, value_max=20.0, value_default=8.0,
        step=1.0, step_precision=0.1, dots=20, digits=1)

    leaf_area_decrease_dial = TouchSlider(
        action='update',
        label=t('shade_area_reduce'), tooltip=t('shade_area_reduce_tt'),
        value_min=0.0, value_max=1.0, value_default=0.5,
        step=0.1, step_precision=0.1, dots=10, digits=1)

    depth_dial = TouchSlider(
        action='update',
        label=t('shade_area_depth'), tooltip=t('shade_area_depth_tt'),
        value_min=-1.0, value_max=1.0, value_default=0.5,
        step=0.1, step_precision=0.01, dots=20, digits=1)

    sides_toggle = TouchToggle(
        action='update',
        label=t('shade_leaf_sides'),
        tooltip=t('shade_leaf_sides'))

    # Branches panel
    branches_panel = TouchPanel(label=t('shade_branches_panel'))

    branches_toggle = TouchToggle(
        action='update',
        label=t('shade_branches'),
        tooltip=t('shade_branches_tt'))

    alongside_dial = TouchSlider(
        action='update',
        label=t('shade_alongside'), tooltip=t('shade_alongside_tt'),
        value_min=0, value_max=10, value_default=2,
        step=1.0, step_precision=0.1, dots=10, digits=0)

    alongside_diameter_dial = TouchSlider(
        action='update',
        label=t('shade_alongside_diameter'), tooltip=t('shade_alongside_diameter_tt'),
        value_min=0.05, value_max=1.0, value_default=0.2,
        step=0.02, step_precision=0.01, dots=20, digits=2)

    leaf_area_dial.minimal = True
    leaf_area_decrease_dial.minimal = True
    depth_dial.minimal = True
    sides_toggle.minimal = True
    branches_toggle.minimal = True
    alongside_dial.minimal = True
    alongside_diameter_dial.minimal = True

    branches_panel.widgets.append(branches_toggle)
    branches_panel.widgets.append(alongside_dial)
    branches_panel.widgets.append(alongside_diameter_dial)

    leaves_panel.widgets.append(leaf_area_dial)
    leaves_panel.widgets.append(leaf_area_decrease_dial)
    leaves_panel.widgets.append(depth_dial)
    # leaves_panel.widgets.append(sides_toggle)

    interface.widgets.append(branches_panel)
    interface.widgets.append(leaves_panel)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grove = None
        self.grove_properties = None

        self.mouse = Vector((0.0, 0.0))
        self.mouse_start = Vector((0.0, 0.0))
        self.origin = Vector((0.0, 0.0))
        self.current_view_matrix = 1

        self.space_data = None  # Used to only draw in the active 3D view.
        self.viewing = False

        self.shader = shader_from_builtin('UNIFORM_COLOR')
        self.leaf_areas_batch = batch_for_shader(self.shader, 'TRIS', {"pos": []}, indices=[])

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
                elif action.startswith('update'):
                    self.update_preview()
                    self.grove_properties.shade_area = self.leaf_area_dial.value
                    self.grove_properties.shade_area_reduce = self.leaf_area_decrease_dial.value
                    self.grove_properties.shade_area_depth = self.depth_dial.value
                    self.grove_properties.shade_leaf_sides = self.sides_toggle.value
                    self.grove_properties.shade_alongside = int(self.alongside_dial.value)
                    self.grove_properties.shade_alongside_diameter = self.alongside_diameter_dial.value
                    context.area.tag_redraw()

                context.region.tag_redraw()
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
                if self.interface.action.startswith('update'):
                    self.update_preview()
                    self.grove_properties.shade_area = self.leaf_area_dial.value
                    self.grove_properties.shade_area_reduce = self.leaf_area_decrease_dial.value
                    self.grove_properties.shade_area_depth = self.depth_dial.value
                    self.grove_properties.shade_leaf_sides = self.sides_toggle.value
                    self.grove_properties.shade_branches = self.branches_toggle.value
                    self.grove_properties.shade_alongside = int(self.alongside_dial.value)
                    self.grove_properties.shade_alongside_diameter = self.alongside_diameter_dial.value
                    context.area.tag_redraw()

                if self.interface.action == 'View':
                    if self.turntable.modal:
                        turn_the_table(
                            context, self.turntable.vector,
                            self.grove_properties.height * self.grove_properties.simulation_scale,
                            self.interface, offset=self.rotation_offset)
                        if self._turntable_timer is None:
                            self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)

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

            self.grove_properties.shade_area = self.leaf_area_dial.value
            self.grove_properties.shade_area_reduce = self.leaf_area_decrease_dial.value
            self.grove_properties.shade_area_depth = self.depth_dial.value
            self.grove_properties.shade_leaf_sides = self.sides_toggle.value
            self.grove_properties.shade_branches = self.branches_toggle.value
            self.grove_properties.shade_alongside = int(self.alongside_dial.value)
            self.grove_properties.shade_alongside_diameter = self.alongside_diameter_dial.value
            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

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

    def update_preview(self):
        """ Rebuild the shade preview. """

        self.grove.set_properties(self.grove_properties.convert_to_core_properties())

        vertices = []
        polygons = []

        vectors = self.grove.build_shade_preview()
        vectors = array(vectors) * self.grove_properties.simulation_scale

        i = 0
        while i < len(vectors):
            vertices.extend([vectors[i], vectors[i + 1], vectors[i + 2]])
            polygons.append((i, i + 1, i + 2))
            i += 3

        for v in vertices:
            v = (v[0], v[1], v[2])

        self.leaf_areas_batch = batch_for_shader(self.shader, 'TRIS', {"pos": vertices}, indices=polygons)

    def invoke(self, context, event):
        """ Initialize. """

        # First check if the user has moved around trees and if so, then replant them.
        bpy.ops.the_grove_22.replant('INVOKE_DEFAULT')

        self.grove_properties = context.collection.GROVE22_Properties

        self.grove_properties.is_tool_active_tweak_shade = True

        self.grove = load_grove(context.collection)
        if not self.grove:
            self.cancel(context)
            self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
            return {'CANCELLED'}

        # Check if the tree has animation. This tool does not work well with deformed branches.
        if self.grove_properties.has_wind_animation:
            build(context, self.grove_properties, self.grove, context.collection, rebuild=True)

        # If recording growth, make sure the frame is set to the tree's current state.
        if self.grove_properties.record_enabled:
            context.scene.frame_set((
                self.grove_properties.age
                * self.grove_properties.record_interval
                + self.grove_properties.record_interval - 1
                + self.grove_properties.record_start_frame))

        self.mouse_start = Vector((event.mouse_region_x, event.mouse_region_y))

        self._handle_draw_3d = bpy.types.SpaceView3D.draw_handler_add(draw_3d, (self, context), 'WINDOW', 'POST_VIEW')
        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.window_manager.modal_handler_add(self)

        context.workspace.status_text_set(status_text_callback)

        self.current_view_matrix = sum(array(context.region_data.view_matrix))

        self.leaf_area_dial.value = self.grove_properties.shade_area
        self.leaf_area_decrease_dial.value = self.grove_properties.shade_area_reduce
        self.depth_dial.value = self.grove_properties.shade_area_depth
        self.sides_toggle.value = self.grove_properties.shade_leaf_sides
        self.branches_toggle.value = self.grove_properties.shade_branches
        self.alongside_dial.value = self.grove_properties.shade_alongside
        self.alongside_diameter_dial.value = self.grove_properties.shade_alongside_diameter

        self.interface.update()

        self.update_preview()

        return {"RUNNING_MODAL"}

    def cancel(self, context):
        """ Cleanup. """

        self.grove_properties.is_tool_active_tweak_shade = False
        if self._handle_draw_3d:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_3d, 'WINDOW')
        if self._handle_draw_2d:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')

        self.interface.action = 'NONE'
        if self._turntable_timer:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None
        self.interface.cancel()

        context.workspace.status_text_set(text=None)
        context.window.cursor_modal_restore()
        context.area.tag_redraw()
