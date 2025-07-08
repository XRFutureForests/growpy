
""" Manually draw new growth.

    Copyright 2020 - 2025, Wybren van Keulen, The Grove """


from itertools import chain

import bpy

from mathutils import Vector
from bpy_extras.view3d_utils import region_2d_to_location_3d, location_3d_to_region_2d
from gpu.shader import from_builtin
from gpu_extras.batch import batch_for_shader
import numpy as np

from ..Interface.Interface import Interface, TouchButton, TouchTurntable, stop_animation_playback
from ..Interface.Canvas import Canvas
from ..Languages.Translation import t
from .OperatorBuild import build
from ..File import load_grove, save_grove
from ..Turntable import turn_the_table
from .OperatorReplant import replant

from ..Core import import_core
the_grove_core = import_core()


def draw_2d(self, context):
    """ Draw the interface, sketch the tree's live and dead branches, show the path that is drawn and draw points that are snapped to. """

    # Prevent drawing in other 3D views.
    if self.space_data != context.space_data:
        return

    self.interface.draw()
    if self.viewing or self.interface.find_modal():
        return

    # Drawn path.
    color_bright_yellow = (1.0, 0.8, 0.4, 1.0)
    if self.path_3d:
        path_2d = []
        thicknesses = []
        for point in self.path_3d:
            path_2d.append(
                location_3d_to_region_2d(context.region, context.region_data, point, default=Vector((0.0, 0.0))))
            thicknesses.append(1.0)
        last_distance = (self.path_3d[-1] - self.path_3d[-2]).length
        if last_distance < 0.001:
            path_2d = path_2d[:-1]
            thicknesses = thicknesses[:-1]
        thicknesses[0] = thicknesses[-1] = 0.3
        if len(self.path_3d) > 2:
            last_distance = (self.path_3d[-2] - self.path_3d[-3]).length
            thicknesses[-2] = 0.3 + 0.3 * (last_distance / self.internode_length)
        self.canvas.draw_thick_lines([path_2d], thickness=13, thicknesses=[thicknesses], color=color_bright_yellow)

    if self.snapped_co:
        if not self.drawing:
            self.canvas.draw_donut(Vector(self.snapped_co), 16, 8, color=color_bright_yellow)
    else:
        if not (self.interface.touch or self.interface.hovering):
            self.canvas.draw_circle_filled(self.mouse, 40.0, color=(0.0, 0.0, 0.0, 0.2))
            self.canvas.draw_icon('SNAP', self.mouse + Vector((75.0, 0.0)), 40.0, color=(0.8, 0.8, 0.8, 1.0))

    # Draw a quick sketch of the tree.
    color_live = (1.0, 0.8, 0.4, 0.6)
    color_dead = (1.0, 0.1, 0.0, 0.6)
    shader = from_builtin('UNIFORM_COLOR')
    shader.bind()
    shader.uniform_float("color", color_live)
    batch = batch_for_shader(shader, 'TRI_STRIP', {"pos": self.tri_strip})
    batch.draw(shader)
    shader.uniform_float("color", color_dead)
    batch = batch_for_shader(shader, 'TRI_STRIP', {"pos": self.tri_strip_dead})
    batch.draw(shader)

    # Draw drag line if going too fast.
    if len(self.path_3d) > 2:
        fast_line = []
        fast_line.append(
            [location_3d_to_region_2d(context.region, context.region_data, self.path_3d[-1], default=Vector((0.0, 0.0))),
             location_3d_to_region_2d(context.region, context.region_data, self.mouse_3d, default=Vector((0.0, 0.0)))])
        self.canvas.draw_thick_lines(
            fast_line,
            thickness=6,
            multiplier=1.0, color=(0.5, 0.3, 0.1, 1.0))


def status_text_callback(header, _):
    """ Add shortcuts to the status bar. """

    header.layout.label(text=t('Find Snap Point'), icon='MOUSE_MOVE')
    header.layout.label(text=t('Draw'), icon='MOUSE_LMB_DRAG')
    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')


class GROVE22_OT_Draw(bpy.types.Operator):

    bl_idname = "the_grove_22.draw"
    bl_label = t('draw')
    bl_description = t('draw_tt')
    bl_options = {'REGISTER', 'UNDO'}

    mode = 0
    rotation_offset = 0.0

    _handle_draw_2d = None
    _turntable_timer = None
    canvas = Canvas()

    # Setup the interface. Class-wide, not per class instance like in __init__. This will make each instance
    # of the tool keep the set parameters and remember which tips have been clicked away.
    interface = Interface()

    close_button = TouchButton(action='Back', label=t('close_button'), tooltip=t('close_button_tt'), icon='CHECKMARK')
    # close_button.icon_over = 'CLOSE_OVER'
    # close_button.icon_down = 'CLOSE_DOWN'
    interface.widgets.append(close_button)

    turntable = TouchTurntable(action='View', label=t('turntable'), tooltip=t('turntable_tt'), icon='VIEW')
    interface.widgets.append(turntable)

    interface.add_spacer()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.drawing = False
        self.internode_length = 0.1
        self.path_3d = []
        self.branch = 0
        self.circle_lines = []
        self.grove = None
        self.grove_properties = None
        self.node_start = 2
        self.mouse = Vector((0.0, 0.0))
        self.mouse_3d = Vector((0.0, 0.0, 0.0))
        self.space_data = None  # Used to only draw in the active 3D view.

        self.pile_of_branches = []
        self.node_coordinates = []
        self.node_coordinates_numpy = None
        self.node_dead = []
        self.node_has_no_parent = []
            # If the snapped point is the first node of a branch, prefer drawing from its parent node.
        self.node_thicknesses = []
        self.snapped_co = None
        self.snapped_co_index = 0

        self.tri_strip = []
        self.tri_strip_dead = []

        self.multiplier = 1.0
        self.viewing = False
        self.tag_initialize = False
        self.growing = False
        self.building = False

    def grow(self):
        """ Create a new temporary tree branch and add to it the drawn path as a guide along which to grow. """

        guide = []
        for point in self.path_3d:
            scaled_point = point / self.grove_properties.simulation_scale
            guide.append(the_grove_core.Vector(scaled_point.x, scaled_point.y, scaled_point.z))

        self.grove.manual_draw(self.snapped_co_index, guide)

        self.growing = False
        self.building = False

        # Below causes:
        # With dead branch preview on, you see a lot of recently cut back branches die after using the Draw tool.
        # Do lateral takeover in case of drawing at the end of a branch.
        #if self.node_start == len(self.branch.nodes) - 1:
        #    if len(self.branch.nodes[self.node_start].side_branches) == 1:
        #        self.branch.nodes[self.node_start].dead = True
        #        lateral_takeover(self.grove, self.grove_properties)

        # shade_and_prune(self.grove, self.grove_properties, times=1)
        context = bpy.context
        build(context, self.grove_properties, self.grove, context.collection, rebuild=True)
        save_grove(self.grove, context.collection)

        self.simulation_flushes = 0

        if self.grove_properties.age == 0:
            self.grove_properties.age = 1

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the add object menu entry is greyed out. """

        return context.mode == 'OBJECT'

    def update_status(self, context):
        """ Set the status bar text. """

        context.workspace.status_text_set(status_text_callback)

    def snap(self, x_co, y_co):
        """ Find the thickest node close to the mouse pointer.
            The list of node coordinates in screen space is created in initialize(),
            and updated every time the view matrix changes.
            I use numpy because it is almost 5 times as fast,
            from 0.24 seconds to 0.05 seconds for an average tree.

            TODO: This can be improved by weighting the closeness against the thickness.
            And then the radius can be enlarged. """

        self.snapped_co = None

        offsets = self.node_coordinates_numpy - np.array([x_co, y_co])  # Distance from mouse for every node coordinate.
        offsets = np.abs(offsets)  # Absolute distance.
        offsets = offsets.transpose()  # [[x, y], [x, y], ...] -> [[x, x, ...], [y, y, ...]]
        hits = offsets < 20  # Boolean list of hits closer than 20 pixels to the mouse.
        hits = np.logical_and(hits[0], hits[1])  # Boolean list of hits in both x and y directions.
        hits = np.logical_and(hits, np.logical_not(self.node_dead)) # Filter out dead nodes.
        hits = np.logical_and(hits, self.node_has_no_parent)
            # Further filter out nodes with a parent node, because then take the parent node.
        hits_indices = np.nonzero(hits)[0]  # From true or false, create a list of indices where true.

        if not np.size(hits_indices):
            # If there have been no hits within 20 pixels of the cursor, try 40 pixels.
            # You might think that this could be done in the first try, but that will quickly select
            # a thicker node if it is within radius.
            hits = offsets < 70  # Boolean list of hits closer than 40 pixels to the mouse.
            hits = np.logical_and(hits[0], hits[1])  # Boolean list of hits in both x and y directions.
            hits = np.logical_and(hits, np.logical_not(self.node_dead)) # Filter out dead nodes.
            hits = np.logical_and(hits, self.node_has_no_parent)
                # Further filter out nodes with a parent node, because then take the parent node.
            hits_indices = np.nonzero(hits)[0]  # From true or false, create a list of indices where true.

        if np.size(hits_indices):  # At least one hit.
            hits_thicknesses = np.array(self.node_thicknesses)[hits_indices]  # List of thicknesses only for the hits.
            index_thickest = np.argmax(hits_thicknesses)  # Thickest node in the hits.
            self.snapped_co_index = hits_indices[index_thickest]  # Index of the best hit.
            self.snapped_co = self.node_coordinates[self.snapped_co_index]

    def mouse_to_3d(self, context):
        """ Get the 3d coordinates projected from the current view at the mouse position
            to the depth of the first point in the drawn line. """

        depth_location = self.path_3d[0]
        return region_2d_to_location_3d(context.region, context.region_data, self.mouse, depth_location)

    def modal(self, context, event):
        """ The main event loop. """

        win_man = context.window_manager
        bpy.context.region_data.update()

        if event.type in ['MOUSEMOVE', 'LEFTMOUSE']:
            self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))

        if event.type != 'TIMER':
            if self.viewing:
                self.initialize(context)
                self.viewing = False

        elif event.type == 'TIMER':
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

            return {'RUNNING_MODAL'}

        # Allow viewport navigation.
        if event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            if self.interface.event_mouse_wheel(self.mouse, event.type == 'WHEELUPMOUSE'):
                if self.interface.action == 'View':
                    turn_the_table(
                        context, self.turntable.vector,
                        self.grove_properties.height * self.grove_properties.simulation_scale,
                        self.interface, offset=self.rotation_offset)
                    self.initialize(context)
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            else:
                if event.type == 'WHEELUPMOUSE':
                    context.region_data.view_distance *= 0.9
                else:
                    context.region_data.view_distance *= 1.1
                self.initialize(context)
                context.region.tag_redraw()
                self.viewing = True
                return {'RUNNING_MODAL'}

        elif event.type in ['MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'ACCENT_GRAVE']:
            self.viewing = True
            context.window.cursor_modal_set('SCROLL_XY')
            return {"PASS_THROUGH"}

        elif event.type == 'Z':
            # Enable the use of the shading pie.
            if not event.ctrl and not event.oskey:
                return {"PASS_THROUGH"}

        elif event.type == 'MOUSEMOVE':
            if self.drawing:
                self.path_3d[-1] = self.mouse_to_3d(context)
                self.mouse_3d = self.path_3d[-1]
                if (self.path_3d[-2] - self.path_3d[-1]).length > self.internode_length:
                    # self.path_3d.append(self.path_3d[-1])
                    self.path_3d[-1] = \
                        self.path_3d[-2] + (self.path_3d[-1] - self.path_3d[-2]).normalized() * self.internode_length
                    self.path_3d.append(self.path_3d[-1])
            else:
                if self._turntable_timer is not None:
                    # When interpolating with the timer, prevent a double redraw.
                    return {"RUNNING_MODAL"}

                if self.interface.event_touch_move(self.mouse):
                    self.snapped_co = None
                    context.window.cursor_modal_set('DEFAULT')

                    if self.interface.action == 'View':
                        if self.turntable.modal:
                            turn_the_table(
                                context, self.turntable.vector,
                                self.grove_properties.height * self.grove_properties.simulation_scale,
                                self.interface, offset=self.rotation_offset)
                            if self._turntable_timer is None:
                                self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)

                else:
                    if not self.interface.touch and not self.interface.hovering:
                        self.snap(event.mouse_region_x, event.mouse_region_y)
                        if self.snapped_co is None:
                            context.window.cursor_modal_set('CROSSHAIR')
                        else:
                            context.window.cursor_modal_set('PAINT_BRUSH')

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

            # Snap, in case of touch screen, where a snap isn't detected because of no mouse move.
            if not self.snapped_co:
                self.snap(event.mouse_region_x, event.mouse_region_y)

            if self.snapped_co and self.node_dead[self.snapped_co_index]:
                self.snapped_co = None

            if not self.drawing and self.snapped_co:
                self.path_3d = []
                # If there's a snapped coordinate, go find the corresponding branch and starting node.
                if self.snapped_co:
                    count = 0
                    for branch in self.pile_of_branches:
                        for i, _ in enumerate(branch.nodes):
                            if count == self.snapped_co_index:
                                self.branch = branch
                                self.node_start = i
                            count += 1

                po = self.branch.nodes[self.node_start].pos
                po = Vector((po.x, po.y, po.z))
                start_3d = po * self.grove_properties.simulation_scale
                self.path_3d.extend([start_3d, start_3d])
                self.drawing = True

                context.region.tag_redraw()
                return {"RUNNING_MODAL"}


        elif event.type in ['LEFTMOUSE'] and event.value == 'RELEASE':

            if not self.drawing:
                self.interface.event_touch_release(self.mouse)
                action = self.interface.action

                if action == 'View_CLICK':
                    turn_the_table(
                        context, self.turntable.vector,
                        self.grove_properties.height * self.grove_properties.simulation_scale,
                        self.interface, offset=self.rotation_offset)
                    if not self.turntable.modal:
                        self.initialize(context)
                    return {"RUNNING_MODAL"}

                elif action == 'Back':
                    self.cancel(context)
                    return {'FINISHED'}

            else:
                self.drawing = False
                self.path_3d[-1] = self.mouse_to_3d(context)

                if len(self.path_3d) > 1:
                    if (self.path_3d[-2] - self.path_3d[-1]).length > self.internode_length:
                        self.path_3d[-1] = (
                            self.path_3d[-2] +
                            (self.path_3d[-1] - self.path_3d[-2]).normalized() * self.internode_length)
                        self.path_3d.append(self.path_3d[-1])

                if len(self.path_3d) > 1:
                    if (self.path_3d[-1] - self.path_3d[-2]).length < self.internode_length / 3.0:
                        self.path_3d.pop()

                if len(self.path_3d) < 2:
                    self.path_3d = []
                    self.initialize(context)
                    context.region.tag_redraw()
                    return {"RUNNING_MODAL"}

                self.interface.update()
                context.window.cursor_modal_set('WAIT')

                # Grow.
                self.grow()
                self.path_3d = []
                self.initialize(context)

            context.region.tag_redraw()
            return {"RUNNING_MODAL"}


        elif event.type in ['RIGHTMOUSE', 'ESC', 'SPACE', 'RET', 'NUMPAD_ENTER'] and event.value == 'PRESS':
            if self.drawing and not self.growing:
                self.drawing = False
                self.path_3d = []
                self.initialize(context)
                self.snap(event.mouse_region_x, event.mouse_region_y)
                context.region.tag_redraw()
            elif self.growing:
                context.region.tag_redraw()
            else:
                if self.interface.find_modal():
                    self.interface.cancel()
                    context.region.tag_redraw()
                    return {"RUNNING_MODAL"}
                else:
                    self.cancel(context)
                    return {'FINISHED'}

        if self.tag_initialize:
            self.initialize(context)
            self.tag_initialize = False

        return {"RUNNING_MODAL"}

    def list_branches(self, pile_of_branches, current_branch):
        pile_of_branches.append(current_branch)
        for node in current_branch.nodes:
            if node.side_branches:
                for side_branch in node.side_branches:
                    self.list_branches(pile_of_branches, side_branch)

    def initialize(self, context):
        """ Create lists of branches, node coordinates in screen space, and node thicknesses.
            These are used for selecting nodes / branches near the mouse cursor. """

        context.window.cursor_modal_set('WAIT')

        scale = self.grove_properties.simulation_scale
        self.pile_of_branches = []
        for tree in self.grove.trees:
            self.list_branches(self.pile_of_branches, tree)

        m = bpy.context.area.spaces.active.region_3d.perspective_matrix
        m = (tuple(m.col[0]), tuple(m.col[1]), tuple(m.col[2]), tuple(m.col[3]))
        self.node_coordinates, self.node_thicknesses, self.node_dead, self.node_has_no_parent = self.grove.get_snapping_points(
                m,
                bpy.context.region.width,
                bpy.context.region.height,
                self.grove_properties.simulation_scale)

        # from time import time
        # start = time()
        # for i in range(len(self.node_coordinates)):
        #     self.node_coordinates[i] = location_3d_to_region_2d(
        #         context.region, context.region_data,
        #         Vector(self.node_coordinates[i]) * scale,
        #         default=Vector((0.0, 0.0)))
        # print("to 2d: " + str(time() - start))

        # self.node_coordinates_numpy = np.array(self.node_coordinates)
        # Below line is almost 20x faster than the above.
        self.node_coordinates_numpy = np.fromiter(
            chain.from_iterable(self.node_coordinates),
            np.array(self.node_coordinates[0][0]).dtype, -1).reshape((len(self.node_coordinates), -1))

        m = bpy.context.area.spaces.active.region_3d.perspective_matrix
        m = (tuple(m.col[0]), tuple(m.col[1]), tuple(m.col[2]), tuple(m.col[3]))
        (self.tri_strip, self.tri_strip_dead) = self.grove.build_sketch_2d(0, self.grove_properties.simulation_scale, m, bpy.context.region.width, bpy.context.region.height)

        context.window.cursor_modal_set('CROSSHAIR')

    def invoke(self, context, _):
        """ Initialize. """

        self.grove_properties = context.collection.GROVE22_Properties

        self.grove = load_grove(context.collection)
        if not self.grove:
            self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
            return {'CANCELLED'}

        replanted = replant(context.collection, self.grove_properties, self.grove)

        # Check if the tree has animation. This tool does not work well with deformed branches.
        if replanted or self.grove_properties.has_wind_animation:
            build(context, self.grove_properties, self.grove, context.collection, rebuild=True)

        stop_animation_playback()

        # If recording growth, make sure the frame is set to the tree's current state.
        if self.grove_properties.record_enabled:
            context.scene.frame_set((
                self.grove_properties.age
                * self.grove_properties.record_interval
                + self.grove_properties.record_interval - 1
                + self.grove_properties.record_start_frame))

        self.branch = 0  # self.grove[0]

        self.internode_length = (
            self.grove_properties.grow_length
            / self.grove_properties.grow_nodes
            * self.grove_properties.simulation_scale)

        self.initialize(context)
        self.update_status(context)
        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.window_manager.modal_handler_add(self)

        self.grove_properties.is_tool_active_draw = True
        self.interface.update()

        GROVE22_OT_Draw.mode = 0

        context.window.cursor_modal_set('CROSSHAIR')
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        """ Cleanup. """

        self.interface.action = 'NONE'

        bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')
        context.workspace.status_text_set(text=None)  # To release the status bar for new use.

        self.node_coordinates_numpy = None

        context.collection.GROVE22_Properties.is_tool_active_draw = False

        if self._turntable_timer:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None

        context.window.cursor_modal_restore()
        context.area.tag_redraw()
