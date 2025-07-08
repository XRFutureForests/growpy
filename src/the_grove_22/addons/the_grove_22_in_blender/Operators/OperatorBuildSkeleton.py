
""" Build a skeleton with an optimized number of bones.
Assign weights to the tree's points.
Apply noise modifiers to deform the tree.
The strength of the deformation is modulated by the branch radius.

Copyright 2024 - 2025, Wybren van Keulen, The Grove """


import bpy
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d

from ..Interface.Interface import Interface, TouchPanel, TouchProgress, TouchButton, TouchSlider, TouchTurntable, TouchToggle
from ..Interface.Canvas import Canvas
from ..Languages.Translation import t
from ..File import load_grove
from .OperatorBuild import clean_grove, build
from .OperatorReplant import replant
from ..Turntable import turn_the_table

import numpy as np
import random


def draw_2d(self, context):

    if self.space_data != context.space_data:  # Only draw in the active 3D view.
        return

    if context.screen.is_animation_playing:
        self.interface.draw()
        return

    region = context.region
    region_data = context.region_data
    path_2d = []
    thicknesses = []
    simulation_scale = self.grove_properties.simulation_scale
    zero_vector = Vector((0.0, 0.0))

    # Slightly faster drawing for many bones.
    if len(self.lines) > 3000:
        for line in self.lines:
            path_2d.append([
                location_3d_to_region_2d(region, region_data, Vector(line[0]) * simulation_scale, default=zero_vector),
                location_3d_to_region_2d(region, region_data, Vector(line[1]) * simulation_scale, default=zero_vector)])
            thicknesses.append([1.4, 0.2])
    else:
        for line in self.lines:
            extra_point = Vector(line[0]) + (Vector(line[1]) - Vector(line[0])) * 0.15
            path_2d.append([
                location_3d_to_region_2d(region, region_data, Vector(line[0]) * simulation_scale, default=zero_vector),
                location_3d_to_region_2d(region, region_data, extra_point * simulation_scale, default=zero_vector),
                location_3d_to_region_2d(region, region_data, Vector(line[1]) * simulation_scale, default=zero_vector)])
            thicknesses.append([0.2, 1.4, 0.2])

    self.canvas.draw_thick_lines(path_2d, thickness=15, thicknesses=thicknesses, color=(1.0, 0.9, 0.4, 0.45))

    self.interface.draw()


def status_text_callback(header, _):
    """ Add shortcuts to the status bar. """

    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')
    header.layout.label(text=t('label_stop'), icon='EVENT_ESC')


class GROVE22_OT_BuildSkeleton(bpy.types.Operator):

    bl_idname = "the_grove_22.build_skeleton"
    bl_label = t('skeleton')
    bl_description = t('skeleton_tt')
    bl_options = {'REGISTER', 'UNDO'}

    canvas = Canvas()

    _timer = None
    _handle_draw_2d = None
    _turntable_timer = None

    rotation_offset = 0.0


    # Setup the interface. Class-wide, not per class instance like in __init__. This will make each instance
    # of the tool keep the set parameters and remember which tips have been clicked away.

    back_button = TouchButton(
        action='Back',
        label=t('close_button'), tooltip=t('close_button_tt'),
        icon='CHECKMARK')

    turntable = TouchTurntable(
        action='View',
        label=t('turntable'), tooltip=t('turntable_tt'),
        icon='VIEW')

    bones_panel = TouchPanel(label=t('skeleton_panel_bones'))
    
    connected_toggle = TouchToggle(
        action='Update',
        label=t('skeleton_connected'),
        tooltip=t('skeleton_connected_tt'))

    length_dial = TouchSlider(
        action='Update',
        label=t('skeleton_length'),
        tooltip=t('skeleton_length_tt'),
        value_min=0.0, value_max=5.0, value_default=2.0,
        step=0.1, step_precision=0.01, dots=32)

    # Reduce with a threshold thickness at the start of the branch.
    reduce_dial = TouchSlider(
        action='Update',
        label=t('skeleton_reduce'),
        tooltip=t('skeleton_reduce_tt'),
        value_min=0.0, value_max=1.0, value_default=0.4,
        step=0.01, step_precision=0.001, dots=32)

    bias_dial = TouchSlider(
        action='Update',
        label= t('skeleton_bias'),
        tooltip=t('skeleton_bias_tt'),
        value_min=0.0, value_max=1.0, value_default=0.5,
        step=0.05, step_precision=0.001, dots=32)

    wind_panel = TouchPanel(label=t('skeleton_panel_wind'))
    turbulence_dial = TouchSlider(
        action='Turbulence',
        label=t('wind_turbulence'),
        tooltip=t('wind_turbulence_tt'),
        value_min=0.0, value_max=1.0, value_default=0.5,
        step=0.05, step_precision=0.01, dots=32)

    progress_dial = TouchProgress(
        action='Animate',
        label=t('build_skeleton'), tooltip=t('build_skeleton_tt'),
        icon='SKELETON')

    interface = Interface()
    interface.widgets.append(back_button)
    interface.widgets.append(turntable)
    interface.add_spacer()
    wind_panel.widgets.append(turbulence_dial)
    interface.widgets.append(wind_panel)
    bones_panel.widgets.append(reduce_dial)
    bones_panel.widgets.append(bias_dial)
    # bones_panel.widgets.append(age_threshold_dial)
    bones_panel.widgets.append(length_dial)
    bones_panel.widgets.append(connected_toggle)
    interface.widgets.append(bones_panel)
    interface.widgets.append(progress_dial)

    for widget in wind_panel.widgets + bones_panel.widgets:
        widget.minimal = True

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grove = None
        self.grove_properties = None

        self.calculating = False
        self.done = False
        self.tree_objects = []

        self.lines = []

        self.mouse = Vector((0, 0))
        self.space_data = None  # Used to only draw in the active 3D view.

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the operator is greyed out. """
        return context.mode == 'OBJECT'

    def modal(self, context, event):
        """ Event handling. """

        properties = context.collection.GROVE22_Properties
        win_man = context.window_manager

        if self.done:
            self.done = False
            self.calculating = False
            self.progress_dial.progress = -1.0

            if self._timer:
                win_man.event_timer_remove(self._timer)

            # Start animation playback automatically - there's no way you won't want to see it immediately.
            # Put all none-important things in a try, because something like this is prone to change in Blender.
            if self.turbulence_dial.value > 0.0:
                try:
                    context.window.cursor_modal_restore()
                    if not context.screen.is_animation_playing:
                        bpy.ops.screen.animation_play()
                    context.scene.frame_set(1)
                except AttributeError:
                    pass

            context.area.tag_redraw()
            return{'RUNNING_MODAL'}

        if event.type in ['MOUSEMOVE', 'LEFTMOUSE']:
            self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))

        if event.type == 'MOUSEMOVE':
            if self._turntable_timer is not None:
                # When interpolating with the timer, prevent a double redraw.
                return {"RUNNING_MODAL"}

            if self.interface.event_touch_move(self.mouse):
                if self.interface.action == 'View':
                    if self.turntable.modal:
                        turn_the_table(
                            context, self.turntable.vector,
                            self.grove_properties.height * self.grove_properties.simulation_scale,
                            self.interface, offset=self.rotation_offset)
                        if self._turntable_timer is None:
                            self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)
                if self.interface.action in ['Update_DECREASE', 'Update_INCREASE', 'Update']:
                    self.update()

            context.area.tag_redraw()
            return {"RUNNING_MODAL"}

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
                        self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)

                context.region.tag_redraw()
                return {"RUNNING_MODAL"}

        if event.type in ['RIGHTMOUSE', 'ESC'] and event.value == 'PRESS':
            if self.calculating:
                self.done = True
                self.calculating = False
                context.area.tag_redraw()
                if self._timer:
                    win_man.event_timer_remove(self._timer)

                return{'RUNNING_MODAL'}
            else:
                if self.interface.find_modal():
                    self.interface.cancel()
                    context.region.tag_redraw()
                    return {"RUNNING_MODAL"}
                else:
                    self.cancel(context)
                    return {'FINISHED'}

        # Allow for viewport navigation.
        if event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            context.area.tag_redraw()
            if self.interface.event_mouse_wheel(self.mouse, event.type == 'WHEELUPMOUSE'):
                if self.interface.action == 'View':
                    turn_the_table(
                        context, self.turntable.vector,
                        self.grove_properties.height * self.grove_properties.simulation_scale,
                        self.interface, offset=self.rotation_offset)
                if self.interface.action in ['Update_DECREASE', 'Update_INCREASE', 'Update']:
                    self.update()
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}
                # To allow viewport zooming.

        elif event.type in ['MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'ACCENT_GRAVE']:
            return {"PASS_THROUGH"}

        elif event.type == 'Z':
            # Enable the use of the shading pie.
            if not event.ctrl and not event.oskey:
                return {"PASS_THROUGH"}
            else:
                # Undo.
                pass

        elif event.type in ['LEFTMOUSE'] and event.value == 'PRESS':
            self.interface.event_touch_down(self.mouse)
            context.region.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type in ['LEFTMOUSE'] and event.value == 'RELEASE':
            if self.interface.event_touch_release(self.mouse):
                context.area.tag_redraw()  # To also redraw the UI region.

            if self.interface.action == 'Animate':
                context.window.cursor_modal_set('WAIT')
                self.build_skeleton()

                # Start animation playback automatically - there's no way you won't want to see it immediately.
                # Put all none-important things in a try, because something like this is prone to change in Blender.
                try:
                    context.window.cursor_modal_restore()
                    if not context.screen.is_animation_playing:
                        bpy.ops.screen.animation_play()
                    context.scene.frame_set(1)
                except AttributeError:
                    pass

                self.done = True

                if context.screen.is_animation_playing:
                    bpy.ops.screen.animation_cancel()

            elif self.interface.action == 'Update':
                self.update()

            elif self.interface.action == 'Back':
                self.cancel(context)
                return {'FINISHED'}

            context.region.tag_redraw()
            return {'RUNNING_MODAL'}

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

            if self.calculating:
                if self._timer:
                    win_man.event_timer_remove(self._timer)

                # ...

        return {'RUNNING_MODAL'}

    def create_bones(self):
        return self.grove.tag_bone_id(
            self.length_dial.value,
            self.reduce_dial.value ** 2,
            self.bias_dial.value,
            self.connected_toggle.value)

    def update(self):
        if bpy.context.screen.is_animation_playing:
            bpy.ops.screen.animation_cancel()

        self.lines = []

        bones = self.create_bones()
        # print("Number of bones: " + str(len(bones))) # WIP

        for bone in bones:
            self.lines.append
            self.lines.append([
                bone[2].as_tuple(),
                bone[3].as_tuple()])

        # self.bones_panel.label = str(len(bones)) + ' Bones'

        if len(self.interface.info_bar):
            self.interface.info_bar[0] = str(self.grove_properties.number_of_branches) + ' Branches'
            self.interface.info_bar[1] = str(len(bones)) + ' Bones'

    def invoke(self, context, _):
        """ Initialize. """

        self.grove_properties = context.collection.GROVE22_Properties

        self.grove = load_grove(context.collection)
        if not self.grove:
            self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
            return {'CANCELLED'}

        # If animation is playing, it can cause jittery updates in the viewport, so stop it.
        # Try it because stuff like this is prone to change in Blender's Python API.
        try:
            if context.screen.is_animation_playing:
                bpy.ops.screen.animation_cancel()
        except AttributeError:
            pass

        context.window_manager.modal_handler_add(self)

        self.done = False
        self.calculating = False
        self.grove_properties.is_tool_active_build_skeleton = True

        replant(context.collection, self.grove_properties, self.grove)

        self.interface.info_bar = []
        self.interface.info_bar.append('Branches')
        self.interface.info_bar.append('Bones')

        self.update()

        context.workspace.status_text_set(status_text_callback)
        self.interface.update()
        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        """ Cleanup. """

        context.workspace.status_text_set(text=None)
        context.window.cursor_modal_restore()

        self.done = True
        self.calculating = False
        context.collection.GROVE22_Properties.is_tool_active_build_skeleton = False

        bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')
        if self._turntable_timer:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None

        if self._timer:
            context.window_manager.event_timer_remove(self._timer)

        bpy.ops.screen.animation_cancel()

        context.area.tag_redraw()

    def build_skeleton(self):

        simulation_scale = self.grove_properties.simulation_scale
        context = bpy.context
        # Build with bone attributes.
        bones = self.create_bones()
        clean_grove(context.collection)
        build(context,
            self.grove_properties,
            self.grove,
            context.collection,
            rebuild=True)

        skeleton = bpy.data.armatures.new('Skeleton')
        skeleton.display_type = 'STICK'
        obj = bpy.data.objects.new(skeleton.name, skeleton)
        obj['grove_skeleton'] = True
        context.collection.objects.link(obj)
        bpy.context.view_layer.objects.active = obj

        bpy.ops.object.mode_set(mode='EDIT', toggle=False)
        edit_bones = obj.data.edit_bones

        # print("Number of bones: " + str(len(bones))) # WIP
        for i in range(len(bones)):
            bone = edit_bones.new(str(i))
            bone.head = bones[i][2].as_tuple()
            bone.tail = bones[i][3].as_tuple()
            bone.head_radius = (bones[i][4])
            bone.tail_radius = (bones[i][4])

            # print("bone: " + str(bone.tail - bone.head))

            parent_bone_name = str(bones[i][1])
            if parent_bone_name in edit_bones:
                parent_bone = edit_bones[parent_bone_name]
                bone.parent = parent_bone

        bpy.ops.object.mode_set(mode='OBJECT', toggle=False)

        if self.turbulence_dial.value > 0.0:
            self.apply_wind_noise(obj)

        tree_objects = [tree for tree in context.collection.objects if 'grove_tree_id' in tree]
        for tree_object in tree_objects:
            bpy.context.view_layer.objects.active = tree_object

            # Convert the bone_id attribute to a numpy list.
            bone_data = tree_object.data.attributes["gr_bone_id"].data
            values = np.empty(len(tree_object.data.vertices), dtype=np.int32)
            bone_data.foreach_get("value", values)

            # Convert the bone_id attribute to vertex groups for each individual bone.
            for i in range(len(bones)):
                vertex_group = tree_object.vertex_groups.new(name=str(i))
                indices = np.where(values == i)[0]
                vertex_group.add(indices.tolist(), 1.0, 'REPLACE')

            # tree_object.parent = obj
            # tree_object.parent_type = 'ARMATURE'
            # Instead of the above object parenting, use armature modifiers.
            armature_modifier = tree_object.modifiers.new(name="Skeleton", type='ARMATURE')
            armature_modifier.object = obj
            tree_object.modifiers.move(len(tree_object.modifiers) - 1, 1)
            
            obj.scale = (simulation_scale, simulation_scale, simulation_scale)


    def apply_wind_noise(self, obj):
        bpy.ops.object.mode_set(mode='POSE')

        turbulence = self.turbulence_dial.value
        if turbulence < 1.0:
            turbulence = pow(turbulence, 1.5)

        for bone in obj.pose.bones:
            bone.rotation_mode = 'XYZ'
            bone.keyframe_insert(data_path="rotation_euler", frame=1, index=0)  # X
            bone.keyframe_insert(data_path="rotation_euler", frame=1, index=1)  # Y
            bone.keyframe_insert(data_path="rotation_euler", frame=1, index=2)  # Z

            curves = obj.animation_data.action.fcurves

            flexibility = bone.bone.head_radius ** 0.9
            flexibility = 1.0 / flexibility / 100.0

            deform_strength = flexibility * turbulence

            for curve in curves:
                if curve.data_path == bone.path_from_id("rotation_euler"):
                    noise_mod = curve.modifiers.new(type='NOISE')
                    # higher frequency on thin branches
                    noise_mod.scale = 17.0 * (1.0 / flexibility) ** 0.3
                    noise_mod.strength = deform_strength
                    noise_mod.phase = random.uniform(0, 20 * 3.14159)

        bpy.ops.object.mode_set(mode='OBJECT')
