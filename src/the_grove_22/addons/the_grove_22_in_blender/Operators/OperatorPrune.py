
""" Draw lines to cut branches.

    Copyright 2014 - 2025, Wybren van Keulen, The Grove """


import bpy
from mathutils import Vector
from bpy_extras.view3d_utils import region_2d_to_location_3d

from ..Languages.Translation import t
from .OperatorBuild import build
from ..File import load_grove, save_grove
from ..Interface.Interface import Interface, TouchButton, TouchTurntable, stop_animation_playback
from ..Interface.Canvas import Canvas
from ..Turntable import turn_the_table
from .OperatorReplant import replant

from ..Core import import_core
the_grove_core = import_core()


def build_lines_bvh(properties, lines, view):
    """ Build mesh from drawn lines by extruding them from the 3D view's camera out. """

    vertices = []
    polygons = []

    view_matrix = view.view_matrix
    view_origin = view_matrix.inverted().translation

    scale_compensation = properties.simulation_scale

    if view.view_perspective == 'ORTHO':
        # In an orthogonal view without perspective, extrude the stroke toward the camera direction.
        extrude_vector = view.view_rotation @ Vector((0.0, 0.0, 20.0))
        for i, stroke in enumerate(lines):
            vertices.extend([stroke[0] / scale_compensation - extrude_vector,
                             stroke[0] / scale_compensation + extrude_vector,
                             stroke[1] / scale_compensation + extrude_vector,
                             stroke[1] / scale_compensation - extrude_vector])

            offset = i * 4
            polygons.append((offset + 0,
                             offset + 1,
                             offset + 2))
            polygons.append((offset + 0,
                             offset + 2,
                             offset + 3))
    else:
        for i, stroke in enumerate(lines):
            # In a perspective or camera view, scale the triangle down toward  the view origin.
            vertices.extend([view_origin / scale_compensation,
                             (stroke[0] + (stroke[0] - view_origin) * 20.0) / scale_compensation,
                             (stroke[1] + (stroke[1] - view_origin) * 20.0) / scale_compensation])

            offset = i * 3
            polygons.append((offset + 0,
                             offset + 1,
                             offset + 2))

    floats = []
    for face in polygons:
        for index in face:
            vert = vertices[index]
            floats.extend([vert.x, vert.y, vert.z])

    ray_tree = the_grove_core.RayTree()
    ray_tree.add_triangles_from_coords(floats)
    ray_tree.build_tree()

    # Debug: Enable the next bit for a visual representation of the cut mesh.
    # mesh = bpy.data.meshes.new("TheGrovePruneFaces")
    # mesh.from_pydata(vertices, [], polygons)
    # shade_preview_object = bpy.data.objects.new("TheGrovePruneFaces", mesh)
    # bpy.context.collection.objects.link(shade_preview_object)

    return ray_tree


def draw_2d(self, context):
    """ Draw cutting lines in white to indicate Prune mode. """

    if self.space_data != context.space_data:  # Prevent drawing in other 3D views.
        return

    if self.lines:
        line = self.lines.copy()
        if line and line[-1] != self.mouse:
            if self.drawing:
                line.append(self.mouse)

        thicknesses = []
        for i in range(len(line)):
            thicknesses.append(i / len(line) * 1 + 0.5)
            # Pointy ends.
            if i == len(line) - 2:
                thicknesses[i] = 0.6
            if i == 0 or i == len(line) - 1:
                thicknesses[i] = 0.3
            # Fade the thickness from the start to the end.
            if i < pow(max(0, (self.fade - 0.2)) * len(line), 1.5):
                thicknesses[i] *= 0.6

        color = (1.0, 0.9, 0.4, 1.0 - pow(self.fade, 2))
        self.canvas.draw_thick_lines([line], thickness=12, thicknesses=[thicknesses], color=color)

    self.interface.draw()


def status_text_callback(header, _):
    """ Add shortcuts to the status bar. """
    header.layout.label(text=t('prune_status_draw_lines'), icon='MOUSE_LMB_DRAG')
    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')


class GROVE22_OT_Prune(bpy.types.Operator):

    bl_idname = "the_grove_22.prune"
    bl_label = t('manual_prune')
    bl_description = t('manual_prune_tt')
    bl_options = {'REGISTER', 'UNDO'}

    _handle_draw = None
    _turntable_timer = None
    _fade_timer = None
    canvas = Canvas()

    fade = 0.0
    rotation_offset = 0.0

    interface = Interface()

    interface.widgets.append(
        TouchButton(action='Back', label=t('close_button'), tooltip=t('close_button_tt'), icon='CHECKMARK'))

    turntable = TouchTurntable(action='View', label=t('turntable'), tooltip=t('turntable_tt'), icon='VIEW')
    interface.widgets.append(turntable)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.drawing = False
        self.viewing = False
        self.lines = []

        self.mouse = Vector((0.0, 0.0))
        self.space_data = None  # Used to only draw in the active 3D view.

        self.grove_properties = None

    def do_prune(self, context):
        """ Prune the trees with the drawn line. """

        properties = context.collection.GROVE22_Properties

        grove = load_grove(context.collection)
        if not grove:
            self.report({"ERROR"}, "The Grove in Blender - Simulation file not found, restart to continue growing.")
            return {'CANCELLED'}

        replant(context.collection, properties, grove)

        lines_list = []
        for i in range(len(self.lines) - 1):
            point_a = region_2d_to_location_3d(
                context.region, context.region_data, self.lines[i], Vector((0.0, 0.0, 0.0)))
            point_b = region_2d_to_location_3d(
                context.region, context.region_data, self.lines[i + 1], Vector((0.0, 0.0, 0.0)))
            lines_list.append([point_a, point_b])

        raytree = build_lines_bvh(properties, lines_list, context.region_data)
        grove.manual_prune(raytree)
        build(context, properties, grove, context.collection, rebuild=True)
        save_grove(grove, context.collection)

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
            if self._fade_timer is not None:
                self.fade += 0.1
                if self.fade >= 1.0:
                    win_man.event_timer_remove(self._fade_timer)
                    self._fade_timer = None
                    self.fade = 0.0
                    self.lines = []
                context.region.tag_redraw()

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

        elif event.type == 'MOUSEMOVE':

            if self.drawing:
                lines = self.lines

                if not lines:
                    return {"RUNNING_MODAL"}

                segment_length = 10
                max_segment = segment_length * 10

                direction = self.mouse - lines[-1]
                if direction.length > segment_length:
                    if direction.length > max_segment:
                        if len(lines) > 1:
                            previous_direction = lines[-1] - lines[-2]
                        else:
                            previous_direction = direction
                        intermediate_direction = (
                            (previous_direction + direction).normalized() * (direction.length * 0.33))
                        lines.append(lines[-1] + intermediate_direction)

                        previous_direction = lines[-1] - lines[-2]
                        direction = self.mouse - lines[-1]
                        intermediate_direction = (
                            (previous_direction + direction).normalized() * (direction.length * 0.33))
                        lines.append(lines[-1] + intermediate_direction)

                    lines.append(self.mouse)

                context.area.tag_redraw()

            else:
                if self._turntable_timer is not None:
                    # When interpolating with the timer, prevent a double redraw.
                    return {"RUNNING_MODAL"}

                if self.interface.event_touch_move(self.mouse):
                    context.window.cursor_modal_set('DEFAULT')

                    if self.interface.action == 'View':
                        if self.turntable.modal:
                            turn_the_table(
                                context, self.turntable.vector,
                                self.grove_properties.height * self.grove_properties.simulation_scale,
                                self.interface, offset=self.rotation_offset)
                            if self._turntable_timer is None:
                                self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)

                    context.area.tag_redraw()

                else:
                    if not self.interface.touch and not self.interface.hovering:
                        context.window.cursor_modal_set('PAINT_BRUSH')

            return {"RUNNING_MODAL"}

        # This makes zooming with the mouse wheel possible.
        if event.type != 'TIMER':
            if self.viewing:
                self.viewing = False

        if event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            if self.interface.event_mouse_wheel(self.mouse, event.type == 'WHEELUPMOUSE'):
                if self.interface.action == 'View':
                    turn_the_table(
                        context, self.turntable.vector,
                        self.grove_properties.height * self.grove_properties.simulation_scale,
                        self.interface, offset=self.rotation_offset)
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}
                # To allow viewport zooming.

        # Allow viewport navigation. Previously drawn lines will be removed, because they make no sense in another view.
        elif event.type in [
                'MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'ACCENT_GRAVE', 'Z']:
            if event.type in 'Z' and (event.ctrl or event.oskey):
                pass
            else:
                self.viewing = True
                self.lines = []
                self.drawing = False

                context.window.cursor_modal_set('SCROLL_XY')
                return {"PASS_THROUGH"}

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

            if not self.drawing:
                self.fade = 0.0
                if self._fade_timer:
                    context.window_manager.event_timer_remove(self._fade_timer)
                    self._fade_timer = None
                self.lines = []
                # self.lines.extend([self.mouse, self.mouse])
                self.lines.extend([self.mouse])
                self.drawing = True
                return {"RUNNING_MODAL"}

        elif event.type in ['LEFTMOUSE'] and event.value == 'RELEASE':
            if self.drawing:
                if self.lines:
                    self.lines[-1] = Vector((event.mouse_region_x, event.mouse_region_y))

                # Don't prune when accidentally clicking the mouse without dragging.
                if len(self.lines) == 2 and (self.lines[1] - self.lines[0]).length < 4:
                    pass
                else:
                    context.window.cursor_modal_set('WAIT')
                    self.do_prune(context)
                    context.window.cursor_modal_set('PAINT_BRUSH')

                    self._fade_timer = win_man.event_timer_add(0.07, window=bpy.context.window)

                self.drawing = False

            else:
                if self.interface.event_touch_release(self.mouse):
                    if self.interface.action != 'NONE':
                        if self.interface.action == 'Back':
                            self.cancel(context)
                            return {'FINISHED'}

                        elif self.interface.action == 'View_CLICK':
                            turn_the_table(
                                context, self.turntable.vector,
                                self.grove_properties.height * self.grove_properties.simulation_scale,
                                self.interface, offset=self.rotation_offset)
                            return {"RUNNING_MODAL"}

            context.region.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type in ['RIGHTMOUSE', 'SPACE', 'RET', 'NUMPAD_ENTER'] and event.value == 'PRESS':
            if self.drawing:
                self.lines = []
                self.drawing = False
                context.region.tag_redraw()

            else:
                if self.interface.find_modal():
                    self.interface.cancel()
                    context.region.tag_redraw()
                    return {"RUNNING_MODAL"}
                else:
                    self.cancel(context)
                    return {'FINISHED'}

        return {"RUNNING_MODAL"}

    def invoke(self, context, _):
        """ Called when the operator starts. """

        # First check if the user has moved around trees and if so, then replant them.
        bpy.ops.the_grove_22.replant('EXEC_DEFAULT')

        self.grove_properties = context.collection.GROVE22_Properties

        stop_animation_playback()

        # If recording growth, make sure the frame is set to the tree's current state.
        if self.grove_properties.record_enabled:
            context.scene.frame_set((
                self.grove_properties.age
                * self.grove_properties.record_interval
                + self.grove_properties.record_interval - 1
                + self.grove_properties.record_start_frame))

        # Check if the tree has animation. This tool does not work well with deformed branches.
        if self.grove_properties.has_wind_animation:
            grove = load_grove(context.collection)
            if not grove:
                self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
                return {'CANCELLED'}
            build(context, self.grove_properties, grove, context.collection, rebuild=True)

        context.workspace.status_text_set(status_text_callback)

        self.lines = []
        self._handle_draw = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.window_manager.modal_handler_add(self)

        self.interface.update()

        self.grove_properties.is_tool_active_prune = True

        context.window.cursor_modal_set('PAINT_BRUSH')
        context.region.tag_redraw()
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        """ Clean up. """

        bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw, 'WINDOW')
        self.drawing = False

        if self._turntable_timer:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None

        if self._fade_timer:
            context.window_manager.event_timer_remove(self._fade_timer)
            self._fade_timer = None

        context.workspace.status_text_set(text=None)
        context.collection.GROVE22_Properties.is_tool_active_prune = False
        context.window.cursor_modal_restore()
        context.area.tag_redraw()
