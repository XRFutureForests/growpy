
""" Curve operator that bends branch segements, inspired by the bonsai wire bend technique.

    Copyright 2019 - 2025, Wybren van Keulen, The Grove """


from math import cos, sin
from itertools import chain

import bpy
import numpy as np
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d, region_2d_to_vector_3d

from ..Interface.Interface import Interface, TouchButton, TouchSlider, TouchTurntable, TouchDragable, TouchPie, stop_animation_playback
from ..Interface.Canvas import Canvas
from ..Turntable import turn_the_table
from ..Languages.Translation import t
from .OperatorBuild import build
from ..File import load_grove, save_grove
from .OperatorReplant import replant

from ..Core import import_core
the_grove_core = import_core()


distance_min = 150
distance_max = 300


def draw_2d(self, context):

    if self.space_data != context.space_data:  # Prevent drawing in other 3D views.
        return

    # Draw original branch segment for reference.
    path_3d = self.segment
    path_2d = []
    thicknesses = []
    for point in path_3d:
        path_2d.append(location_3d_to_region_2d(context.region, context.region_data, point, default=Vector((0.0, 0.0))))
        thicknesses.append(1.0)
    if len(thicknesses) > 1:
        thicknesses[1] = thicknesses[-2] = 0.7
    thicknesses[0] = thicknesses[-1] = 0.3
    self.canvas.draw_thick_lines([path_2d], thickness=6, thicknesses=[thicknesses], color=(0.0, 0.0, 0.0, 0.7))

    # Draw the bent branch preview.
    path_3d = self.segment_bent
    path_2d = []
    thicknesses = []
    for point in path_3d:
        path_2d.append(location_3d_to_region_2d(context.region, context.region_data, point, default=Vector((0.0, 0.0))))
        thicknesses.append(1.0)
    if len(thicknesses) > 1:
        thicknesses[1] = thicknesses[-2] = 0.7
    thicknesses[0] = thicknesses[-1] = 0.3
    self.canvas.draw_thick_lines([path_2d], thickness=6, thicknesses=[thicknesses], color=(0.8, 0.4, 0.2, 1.0))

    path_3d = self.segment_bent[:self.node_reach]
    path_2d = []
    thicknesses = []
    for point in path_3d:
        path_2d.append(location_3d_to_region_2d(context.region, context.region_data, point, default=Vector((0.0, 0.0))))
        thicknesses.append(1.0)
    if len(thicknesses) > 1:
        thicknesses[1] = thicknesses[-2] = 0.7
    thicknesses[0] = thicknesses[-1] = 0.3
    self.canvas.draw_thick_lines([path_2d], thickness=15, thicknesses=[thicknesses], color=(1.0, 0.8, 0.4, 1.0))

    if self.viewing or self.interface.find_modal():
        self.interface.draw()
        return

    # Draw snapped node.
    if self.snapped_co:
        self.canvas.draw_donut(Vector(self.snapped_co), 16, 8, color=(1.0, 0.8, 0.4, 1.0))
    else:
        if not (self.interface.touch or self.interface.hovering):
            self.canvas.draw_circle_filled(self.mouse, 40.0, color=(0.0, 0.0, 0.0, 0.2))
            self.canvas.draw_icon('SNAP', self.mouse + Vector((75.0, 0.0)), 40.0, color=(0.8, 0.8, 0.8, 1.0))

    origin = self.origin

    if self.mode > 0:
        # Flexible and S-curve
        teeth = int((self.distance + distance_min) * 0.2 + 34)
        teeth *= 2
        rot = self.angle / 1.5708

        self.canvas.draw_donut_dial(
            origin, self.distance + distance_min + 6, self.distance + distance_min - 6,
            color=(1.0, 1.0, 1.0, 0.5), width=4, rotation=rot, resolution=teeth)

        # Inner and outer circle line.
        alpha = self.distance / (distance_max - distance_min)
        alpha *= 0.04
        alpha += 0.04

        if self.rotate_button.touch:
            alpha *= 2

        self.canvas.draw_donut(origin, distance_max, distance_min, color=(1.0, 1.0, 1.0, alpha))

    else:
        self.canvas.draw_donut_dial(
            origin, distance_min + 6, distance_min - 6,
            color=(0.8, 0.8, 0.8, 0.5), width=4, rotation=self.angle / 2.0, resolution=128)

    if self.rotate_button.touch or self.rotate_button.hovering:
        if self.rotate_button.touch:
            self.canvas.draw_circle_filled(self.rotate_button.location, 40, color=(0.8, 0.8, 0.8, 1.0))
            point_a = self.rotate_button.location
            point_b = self.mouse
            self.canvas.draw_arrow(point_a, point_b, min_radius=10)
        else:
            self.canvas.draw_circle_filled(self.rotate_button.location, 40, color=(0.8, 0.8, 0.8, 1.0))
            self.canvas.draw_circle_filled(self.rotate_button.location, 20, color=(1.0, 1.0, 1.0, 1.0))
    else:
        self.canvas.draw_circle_filled(self.rotate_button.location, 30, color=(0.8, 0.8, 0.8, 1.0))

    self.interface.draw()


def status_text_callback(header, _):
    """ Add shortcuts to the status bar. """
    header.layout.label(text=t('bend_status_select_node'), icon='MOUSE_LMB')
    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')


class GROVE22_OT_Bend(bpy.types.Operator):

    bl_idname = "the_grove_22.bend"
    bl_label = t('manual_bend')
    bl_description = t('manual_bend_tt')
    bl_options = {'REGISTER', 'UNDO'}

    mode = 0
    _turntable_timer = None
    _handle_draw_2d = None
    canvas = Canvas()

    rotation_offset = 0.0

    interface = Interface()

    interface.widgets.append(
        TouchButton(action='Back', label=t('close_button'), tooltip=t('close_button_tt'), icon='CHECKMARK'))  # DOT

    turntable = TouchTurntable(action='View', label=t('turntable'), tooltip=t('turntable_tt'), icon='VIEW')
    interface.widgets.append(turntable)

    interface.add_spacer()

    curve_pie = TouchPie(
        action='Curve',
        label=t('bend_tool_curve'),
        slices=[t('bend_tool_curve_simple'), t('bend_tool_curve_flexible'), t('bend_tool_curve_s_curve')],
        tooltip=t('bend_tool_curve_tt'),
        icon='BEND_CURVE',
        is_enum=True)
    interface.widgets.append(curve_pie)

    distance_dial = TouchSlider(
        action='new_distance',
        label=t('bend_tool_distance'),
        tooltip=t('bend_tool_distance_tt'),
        value_min=0.0, value_max=10.0, value_default=2.0,
        step=0.5, step_precision=0.1, dots=32, digits=1)
    interface.widgets.append(distance_dial)

    rotate_button = TouchDragable(action='Rotate', label='')
    rotate_button.free = True
    interface.widgets.append(rotate_button)

    bend_button = TouchButton(action='Bend', label=t('bend_tool_bend_button'), tooltip=t('bend_tool_bend_button_tt'), icon='BEND')
    interface.widgets.append(bend_button)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.branch = None
        self.segment = []  # The continuation of the branch from the selected node to the end.
        self.segment_bent = []  # The bent version of self.segment.
        self.grove = None
        self.grove_properties = None
        self.node_start = 2
        self.node_reach = 12
        self.angle = 0.0
        self.distance = 50
        self.turns = 0
        self.exponent = 0.0

        self.mouse = Vector((0.0, 0.0))
        self.mouse_start = Vector((0.0, 0.0))
        self.origin = Vector((0.0, 0.0))
        self.current_view_matrix = 1

        self.space_data = None  # Used to only draw in the active 3D view.

        self.pile_of_branches = []
        self.node_coordinates = []
        self.node_thicknesses = []
        self.snapped_co = None
        self.snapped_co_index = 0
        self.branch_index = 0
        self.node_coordinates_numpy = None
        self.branch_segment = None

        self.viewing = False


    def find_branch_by_node_index(self):
        branch_index = 0
        index = 0
        for branch in self.pile_of_branches:
            if self.snapped_co_index > index + len(branch.nodes):
                # The snapped node isn't in this branch yet, so skip it for speed.
                index += len(branch.nodes)
                branch_index += 1
                continue

            # The snapped node is in this branch, now find the specific node.
            for node_index, _ in enumerate(branch.nodes):
                if index == self.snapped_co_index:
                    self.branch = branch
                    self.node_start = node_index
                    if self.node_start >= (len(self.branch.nodes) - 1):
                        self.node_start = len(self.branch.nodes) - 2
                index += 1
            self.branch_index = branch_index
            break

    def do_manual_bend(self, context):
        """ Bend the branch, rebuild and save. """

        origin_2d = location_3d_to_region_2d(
            context.region, context.region_data, self.segment[0], default=Vector((0.0, 0.0)))
        axis = region_2d_to_vector_3d(context.region, context.region_data, origin_2d)
        axis = the_grove_core.Vector(axis.x, axis.y, axis.z)
        exponent = self.calculate_exponent(context)

        # self.calculate_reach()

        self.grove.manual_bend(self.branch_index, self.node_start, self.node_reach, self.angle, axis, exponent, self.mode == 2)

        build(context, self.grove_properties, self.grove, context.collection, rebuild=True)
        save_grove(self.grove, context.collection)

        self.pile_of_branches = []
        for tree in self.grove.trees:
            self.list_branches(self.pile_of_branches, tree)

        self.find_branch_by_node_index()

        self.angle = 0.0
        self.turns = 0
        self.update_branch_segment_preview(context)
        self.update_wire_bent_preview(context)

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the add object menu entry is greyed out. """
        return context.mode == 'OBJECT'

    def update_branch_segment_preview(self, context):
        """ Create a new branch starting from node_start, all the way to the tip.
            This is the unbent branch to show what will be bent.
            This is shown in dark orange. """

        self.branch_segment = self.branch.get_segment(self.node_start, len(self.branch.nodes))

        self.segment = []
        scale = self.grove_properties.simulation_scale
        for node in self.branch_segment.nodes:
            self.segment.append(Vector((node.pos.x, node.pos.y, node.pos.z)) * scale)

        self.origin = location_3d_to_region_2d(
            context.region, context.region_data, self.segment[0], default=Vector((0.0, 0.0)))

    def calculate_exponent(self, context):
        """ Instead of just bending in a boring circle, create a beautiful curve. """

        if self.mode == 0:
            # Instead of bending in on itself, with big angles increase bending further on to create a sea shell curve.
            exponent = 1.0
            if abs(self.angle) > 2.0:
                reduced_angle = abs(self.angle) - 2.0
                exponent = 1.0 + reduced_angle * 0.2
                if exponent > 1.42:
                    exponent = 1.42

            self.exponent = exponent
            return exponent

        else:
            # Or instead, modulate the exponent by the distance the mouse is from the starting point.
            origin = location_3d_to_region_2d(
                context.region, context.region_data,
                Vector(self.branch_segment.nodes[0].pos.as_list()) * self.grove_properties.simulation_scale,
                default=Vector((0.0, 0.0)))
            distance = abs((self.rotate_button.location - origin).length)
            distance -= distance_min
            if distance < 0.0:
                distance = 0.0
            distance /= 100
            distance = min(distance, 2.0)
            exponent = 2.0 - distance
            exponent += 0.3

            self.exponent = exponent
            return exponent

    def calculate_reach(self):
        """ Convert the distance in meters to the number of nodes that have to be bent. """

        distance = 0.0
        reach = 0
        scale = self.grove_properties.simulation_scale

        for i in range(self.node_start, len(self.branch.nodes)):
            if distance > self.distance_dial.value:
                break
            distance += self.branch.nodes[i].direction.length() * scale  # TODO: this line is incredibly slow! takes 0.004 seconds, which quickly adds up to 0.3 seconds.
            reach += 1

        if reach == 0:
            reach = 1

        self.node_reach = reach

    def update_wire_bent_preview(self, context):
        """ Create a preview of the bent branch.
            This is showed in yellow and grey. """

        self.segment_bent = []
        origin_2d = location_3d_to_region_2d(
            context.region, context.region_data, self.segment[0], default=Vector((0.0, 0.0)))
        axis = region_2d_to_vector_3d(context.region, context.region_data, origin_2d)
        axis = the_grove_core.Vector(axis.x, axis.y, axis.z)

        self.branch_segment.bend_down(
            self.grove.get_properties(),
            self.branch_segment.nodes[0].pos,
            the_grove_core.Rotation(the_grove_core.Vector(1.0, 0.0, 0.0), 0.0), # no rotation
            the_grove_core.Vector(1.0, 0.0, 0.0), 1, False,
            the_grove_core.Randomizer())

        branch_segment_bent = self.branch_segment.get_segment(0, len(self.branch_segment.nodes))
        exponent = self.calculate_exponent(context)
        self.calculate_reach()
        branch_segment_bent.manual_bend(0, self.node_reach, self.angle, axis, exponent, scurve=self.mode == 2)

        pos = self.branch_segment.nodes[0].pos
        pos = Vector((pos.x, pos.y, pos.z))
        for node in branch_segment_bent.nodes:
            self.segment_bent.append(pos * self.grove_properties.simulation_scale)
            pos += Vector((node.direction.x, node.direction.y, node.direction.z))

    def update_status(self, context):
        """ Set the status bar text. """

        context.workspace.status_text_set(status_text_callback)

    def snap(self, x, y, hover=False):
        """ Find the thickest node close to the mouse pointer.
            The list of node coordinates in screen space is created in initialize(),
            and updated every time the view matrix changes.
            Using numpy is almost 5 times as fast, from 0.24 seconds to 0.05 seconds for an average tree. """

        self.snapped_co = None

        offsets = self.node_coordinates_numpy - np.array([x, y])  # Distance from mouse for every node coordinate.
        offsets = np.abs(offsets)  # Absolute distance.
        offsets = offsets.transpose()  # [[x, y], [x,y], ...] -> [[x, x, ...], [y, y, ...]]
        hits = offsets < 20  # Boolean list of hits closer than 20 pixels to the mouse.
        hits = np.logical_and(hits[0], hits[1])  # Boolean list of hits in both x and y directions.
        hits_indices = np.nonzero(hits)[0]  # From true or false, create a list of indices where true.

        if np.size(hits_indices):  # At least one hit.
            hits_thicknesses = np.array(self.node_thicknesses)[hits_indices]  # List of thicknesses only for the hits.
            index_thickest = np.argmax(hits_thicknesses)  # Thickest node in the hits.
            snapped_co_index = hits_indices[index_thickest]  # Index of the best hit.
            if not hover:
                self.snapped_co_index = snapped_co_index
            self.snapped_co = self.node_coordinates[snapped_co_index]

    def update_angle(self):
        """ Calculate the angle from the change in position of the angle widget. """

        veca = Vector((100, 0))
        vecb = self.mouse - self.origin
        angle = veca.angle_signed(vecb) * 1.0

        # Allow twisting multiple turns in one direction.
        if (self.angle - 3.1415 * self.turns) < -2 and angle > 2:
            self.turns -= 1
        elif (self.angle - 3.1415 * self.turns) > 2 and angle < -2:
            self.turns += 1

        if self.turns != 0:
            if (self.angle - 3.1415 * (self.turns + 1)) < -2 and angle > 2:
                self.turns -= 1
            elif (self.angle - 3.1415 * (self.turns - 1)) > 2 and angle < -2:
                self.turns += 1

        self.angle = self.turns * (3.1415) + angle

    def update_angle_button(self):
        """ Update the location of the draggable angle widget. """

        bpy.context.region_data.update()
        self.origin = location_3d_to_region_2d(
            bpy.context.region, bpy.context.region_data, self.segment[0], default=Vector((0.0, 0.0)))

        if self.mode == 0:
            self.distance = 1
            c = self.distance
            a = Vector((cos(-self.angle), sin(-self.angle))) * distance_min + self.origin
            b = Vector((cos(-self.angle), sin(-self.angle))) * c + a
            self.rotate_button.location = b

        if self.mode > 0:
            if self.rotate_button.touch:
                c = (self.mouse - self.origin).length - distance_min
                c = min(distance_max - distance_min, c)
                c = max(0.0, c)
                self.distance = c
            c = self.distance

            a = Vector((cos(-self.angle), sin(-self.angle))) * distance_min + self.origin
            b = Vector((cos(-self.angle), sin(-self.angle))) * c + a
            self.rotate_button.location = b

    def modal(self, context, event):
        """ Event loop. """

        win_man = context.window_manager

        self.update_angle_button()

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

                elif action in ['new_distance_INCREASE', 'new_distance_DECREASE']:
                    self.calculate_reach()

                elif action == 'Curve':
                    if self.curve_pie.active_slice == 'Simple':
                        self.mode = 0
                    elif self.curve_pie.active_slice == 'Flexible':
                        self.mode = 1
                    elif self.curve_pie.active_slice == 'S-Curve':
                        self.mode = 2

                self.update_branch_segment_preview(context)
                self.update_wire_bent_preview(context)
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            else:
                context.region.tag_redraw()
                if event.type == 'WHEELUPMOUSE':
                    context.region_data.view_distance *= 0.8
                else:
                    context.region_data.view_distance *= 1.2
                self.initialize(context)
                self.viewing = True
                return {"RUNNING_MODAL"}

        elif event.type in ['MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE',
                            'ACCENT_GRAVE', 'Z']:
            if event.type in 'Z' and (event.ctrl or event.oskey):
                pass
            else:
                self.viewing = True
                context.window.cursor_modal_set('CROSSHAIR')
                return {"PASS_THROUGH"}

        elif event.type == 'MOUSEMOVE':

            if self._turntable_timer is not None:
                # When interpolating with the timer, prevent a double redraw.
                return {"RUNNING_MODAL"}

            if self.interface.touch or \
                    self.interface.hovering or \
                    self.interface.find_modal:
                context.window.cursor_modal_set('DEFAULT')
            else:
                context.window.cursor_modal_set('CROSSHAIR')

            if self.interface.event_touch_move(self.mouse):
                if self.interface.action in ['new_distance_INCREASE', 'new_distance_DECREASE']:
                    self.calculate_reach()

                if self.interface.action == 'View':
                    if self.turntable.modal:
                        turn_the_table(
                            context, self.turntable.vector,
                            self.grove_properties.height * self.grove_properties.simulation_scale,
                            self.interface, offset=self.rotation_offset)
                        if self._turntable_timer is None:
                            self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)

                # self.update_branch_segment_preview(context)
                # self.update_wire_bent_preview(context)

            if not self.interface.touch and not self.interface.hovering and not self.turntable.modal:
                # When the view has changed, update the selection lists and previews.
                if self.current_view_matrix != np.sum(np.array(context.region_data.view_matrix)):
                    self.current_view_matrix = np.sum(np.array(context.region_data.view_matrix))
                    self.initialize(context)
                self.snap(event.mouse_region_x, event.mouse_region_y, hover=True)

            if self.rotate_button.touch:
                self.update_angle()
                self.update_branch_segment_preview(context)
                self.update_wire_bent_preview(context)

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

            else:  # Not clicking the interface.
                self.snap(event.mouse_region_x, event.mouse_region_y)
                self.update_branch_segment_preview(context)
                self.update_wire_bent_preview(context)
                context.region.tag_redraw()

                # If there's a snapped coordinate, go find the corresponding branch and starting node.
                if self.snapped_co:
                    self.find_branch_by_node_index()

                    self.angle = 0.0
                    self.turns = 0
                    self.mouse_start = Vector((event.mouse_region_x, event.mouse_region_y))
                    self.mouse = self.mouse_start

            context.region.tag_redraw()

            return {"RUNNING_MODAL"}

        elif event.type in ['LEFTMOUSE'] and event.value == 'RELEASE':

            self.calculate_reach()
            self.update_branch_segment_preview(context)  # To update the origin and dot location.
            self.update_wire_bent_preview(context)
            context.region.tag_redraw()

            if self.interface.find_modal():
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

                elif action == 'Curve':
                    if self.curve_pie.active_slice == 'Simple':
                        self.mode = 0
                    elif self.curve_pie.active_slice == 'Flexible':
                        self.mode = 1
                    elif self.curve_pie.active_slice == 'S-Curve':
                        self.mode = 2
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

                    elif action == 'Bend':
                        context.window.cursor_modal_set('WAIT')
                        self.do_manual_bend(context)
                        self.angle = 0.0
                        self.turns = 0
                        self.update_angle_button()
                        self.initialize(context)
                        return {"RUNNING_MODAL"}

        elif event.type in ['PLUS', 'EQUAL'] and event.value == 'PRESS':
            if event.shift:
                self.node_start += 1
                if self.node_start >= (len(self.branch.nodes) - 1):
                    self.node_start = len(self.branch.nodes) - 2

            self.update_status(context)
            self.update_branch_segment_preview(context)
            self.update_wire_bent_preview(context)

            context.region.tag_redraw()

        elif event.type in ['MINUS'] and event.value == 'PRESS':
            if event.shift:
                self.node_start -= 1
                if self.node_start < 0:
                    self.node_start = 0

            self.update_status(context)
            self.update_branch_segment_preview(context)
            self.update_wire_bent_preview(context)

            context.region.tag_redraw()

        elif event.type in ['RIGHTMOUSE', 'ESC'] and event.value == 'PRESS':
            if self.interface.find_modal():
                self.interface.cancel()
                context.region.tag_redraw()
                return {"RUNNING_MODAL"}
            else:
                self.cancel(context)
                return {'FINISHED'}

        elif event.type in ['SPACE', 'RET', 'NUMPAD_ENTER'] and event.value == 'PRESS':
            context.window.cursor_modal_set('WAIT')
            self.do_manual_bend(context)
            self.angle = 0.0
            self.turns = 0
            self.initialize(context)
            self.update_angle_button()

            context.region.tag_redraw()
            return {'RUNNING_MODAL'}

        if self.viewing:
            self.viewing = False

            context.window.cursor_modal_set('CROSSHAIR')

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

        # self.node_coordinates, self.node_thicknesses, _, _ = self.grove.get_snapping_points()
        # for i in range(len(self.node_coordinates)):
        #     self.node_coordinates[i] = location_3d_to_region_2d(
        #         context.region, context.region_data,
        #         Vector(self.node_coordinates[i]) * scale,
        #         default=Vector((0.0, 0.0)))

        m = bpy.context.area.spaces.active.region_3d.perspective_matrix
        m = (tuple(m.col[0]), tuple(m.col[1]), tuple(m.col[2]), tuple(m.col[3]))
        self.node_coordinates, self.node_thicknesses, _, _ = self.grove.get_snapping_points(
                m,
                bpy.context.region.width,
                bpy.context.region.height,
                self.grove_properties.simulation_scale)

        # self.node_coordinates_numpy = np.array(self.node_coordinates)
        # Below line is almost 20x faster than the above.
        self.node_coordinates_numpy = np.fromiter(
            chain.from_iterable(self.node_coordinates),
            np.array(self.node_coordinates[0][0]).dtype, -1).reshape((len(self.node_coordinates), -1))

        context.window.cursor_modal_set('CROSSHAIR')

        self.update_branch_segment_preview(context)
        self.update_wire_bent_preview(context)

    def invoke(self, context, event):
        """ Initialize. """

        self.grove_properties = context.collection.GROVE22_Properties

        self.grove = load_grove(context.collection)
        if not self.grove:
            self.cancel(context)
            self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
            return {'CANCELLED'}

        replanted = replant(context.collection, self.grove_properties, self.grove)

        stop_animation_playback()

        # Check if the tree has animation. This tool does not work well with deformed branches.
        if replanted or self.grove_properties.has_wind_animation:
            build(context, self.grove_properties, self.grove, context.collection, rebuild=True)

        # If recording growth, make sure the frame is set to the tree's current state.
        if self.grove_properties.record_enabled:
            context.scene.frame_set((
                self.grove_properties.age
                * self.grove_properties.record_interval
                + self.grove_properties.record_interval - 1
                + self.grove_properties.record_start_frame))

        self.segment = []
        self.branch = self.grove.trees[0]
        self.node_start = int(len(self.branch.nodes) / 2)
        if self.node_start > 8:
            self.node_start = 8
        self.mouse_start = Vector((event.mouse_region_x, event.mouse_region_y))

        self.initialize(context)

        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.window_manager.modal_handler_add(self)

        self.current_view_matrix = np.sum(np.array(context.region_data.view_matrix))

        self.grove_properties.is_tool_active_bend = True
        self.interface.update()

        if self.curve_pie.active_slice == 'Simple':
            self.mode = 0
        elif self.curve_pie.active_slice == 'Flexible':
            self.mode = 1
        elif self.curve_pie.active_slice == 'S-Curve':
            self.mode = 2

        context.window.cursor_modal_set('CROSSHAIR')
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        """ Cleanup. """

        if self._handle_draw_2d:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')
        context.workspace.status_text_set(text=None)
        context.collection.GROVE22_Properties.is_tool_active_bend = False

        self.interface.action = 'NONE'
        if self._turntable_timer is not None:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None

        self.interface.cancel()

        context.window.cursor_modal_restore()
        context.area.tag_redraw()
