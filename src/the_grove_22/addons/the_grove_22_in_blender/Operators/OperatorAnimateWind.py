
""" Rebuild the trees in the active grove with wind animation.
    First remove all trees in the active grove, then build with wind and add the newly built trees to the active grove.

    Copyright 2014 - 2025, Wybren van Keulen, The Grove """


import bpy
from mathutils import Vector
import numpy as np

from ..Interface.Interface import Interface, TouchProgress, TouchVector, TouchButton, TouchSlider, TouchTurntable
from ..Languages.Translation import t
from ..File import load_grove
from .OperatorBuild import clean_grove, create_tree_object, add_spring_shape, record, retime
from .OperatorBuild import do_twig_hide, update_twigs, tag_tree_object, update_wind_breeze
from .OperatorReplant import replant
from ..Turntable import turn_the_table

from ..Core import import_core
the_grove_core = import_core()


def draw_2d(self, context):

    if self.space_data != context.space_data:  # Only draw in the active 3D view.
        return

    self.interface.draw()


def status_text_callback(header, _):
    """ Add shortcuts to the status bar. """

    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')
    header.layout.label(text=t('label_stop'), icon='EVENT_ESC')


class GROVE22_OT_AnimateWind(bpy.types.Operator):

    bl_idname = "the_grove_22.animate_wind"
    bl_label = t('calculate_wind')
    bl_description = t('calculate_wind_tt')
    bl_options = {'REGISTER', 'UNDO'}

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

    shape_keys_dial = TouchSlider(
        action='ShapeKeys',
        label=t('wind_shapes'), tooltip=t('wind_shapes_tt'),
        value_min=10, value_max=240, value_default=50,
        step=10, step_precision=1, dots=20, digits=0)

    turbulence_dial = TouchSlider(
        action='Turbulence',
        label=t('wind_turbulence'),
        tooltip=t('wind_turbulence_tt'),
        value_min=0.0, value_max=5.0, value_default=1.0,
        step=0.1, step_precision=0.01, dots=32)

    wind_vector = TouchVector(
        action='WindVector',
        label=t('wind_vector'), tooltip=t('wind_vector_tt'))
    wind_vector.vector = Vector((0.5, 0.0))
    wind_vector.dots = 16
    wind_vector.rotation_labels = ['X', 'Y', '-X', '-Y']
    wind_vector.rotation_icons = ['WIND_EAST', 'WIND_NORTH', 'WIND_WEST', 'WIND_SOUTH']

    progress_dial = TouchProgress(
        action='Animate',
        label=t('calculate_wind'), tooltip=t('escape_to_stop'),
        icon='WIND')

    interface = Interface()
    interface.widgets.append(back_button)
    interface.widgets.append(turntable)
    interface.add_spacer()
    interface.widgets.append(shape_keys_dial)
    interface.widgets.append(turbulence_dial)
    interface.widgets.append(wind_vector)
    interface.widgets.append(progress_dial)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grove = []
        self.grove_properties = None
        self.current_shape = 0

        self.calculating = False
        self.done = False
        self.tree_objects = []

        self.mouse = Vector((0, 0))
        self.space_data = None  # Used to only draw in the active 3D view.

        self.interval = 2  # Space between keyframes.
        self.width = 2  # Falloff frames for each keyframe, both to the left and the right of the current keyframe.

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
                if self.calculating:
                    # If a calculation is already in progress, stop it.
                    self.done = True
                    self.calculating = False
                    context.area.tag_redraw()

                    if self._timer:
                        win_man.event_timer_remove(self._timer)

                    return{'RUNNING_MODAL'}

                clean_grove(context.collection)

                context.window.cursor_modal_set('WAIT')
                self.current_shape = 0
                self.done = False
                self.calculating = True

                if context.screen.is_animation_playing:
                    bpy.ops.screen.animation_cancel()

                self._timer = win_man.event_timer_add(0.1, window=context.window)

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

                if self.current_shape == 0:
                    # First build the tree and insert a base key without wind.

                    self.grove.remember_orig_pos()
                    self.tree_objects = []
                    models = self.grove.build_models({
                            "resolution": properties.build_resolution,
                            "resolution_reduce": properties.build_resolution_reduce,
                            "texture_repeat": properties.texture_repeat,
                            "build_cutoff_age": properties.build_cutoff_age,
                            "build_blend": properties.build_blend,
                            "build_end_cap": properties.build_end_cap,
                        })
                    for i, model in enumerate(models):
                        tree_object = create_tree_object(model, properties, context)
                        context.collection.objects.link(tree_object)
                        tree_object.shape_key_add(name='Base', from_mix=False)
                        properties.has_wind_animation = True

                        tag_tree_object(tree_object, properties, i)
                        update_twigs(properties, context.collection)
                        do_twig_hide(properties, context)
                        update_wind_breeze(properties, bpy.context)
                        self.tree_objects.append(tree_object)
                
                wind_vector = the_grove_core.Vector(self.wind_vector.vector[0], self.wind_vector.vector[1], 0.0)
                
                models = self.grove.build_wind_shape(
                    {
                        "resolution": properties.build_resolution,
                        "resolution_reduce": properties.build_resolution_reduce,
                        "texture_repeat": properties.texture_repeat,
                        "build_cutoff_age": properties.build_cutoff_age,
                        "build_blend": properties.build_blend,
                        "build_end_cap": properties.build_end_cap,
                    },
                    self.shape_keys_dial.value,
                    self.current_shape,
                    wind_vector,
                    self.turbulence_dial.value)
                
                for i in range(len(models)):
                    add_wind_shape(
                        models[i], self.tree_objects[i], self.current_shape,
                        self.interval, self.width,
                        wind_shapes=self.shape_keys_dial.value)

                self.current_shape += 1
                if self.current_shape == self.shape_keys_dial.value:
                    # Last shape for this tree, finish up by making each f-curve cyclic, to loop the animation.
                    for i in range(len(models)):
                        for curve in self.tree_objects[i].data.shape_keys.animation_data.action.fcurves:
                            mod = curve.modifiers.new('CYCLES')
                            mod.active = True  # This shouldn't be necessary, but it is at the time of writing.

                    # If recording:
                    # WIP TODO.
                    # Hide last record step.
                    # Add spring shape and time it.
                    if properties.record_enabled:
                        add_spring_shape(properties, models[i], self.tree_objects[i])

                        year = self.tree_objects[i]['grove_tree_age']
                        record_interval = properties.record_interval
                        frame_this_year = year * record_interval
                        frame_last_year = frame_this_year - record_interval

                        fcurve = self.tree_objects[i].data.shape_keys.animation_data.action.fcurves[-1]
                        fcurve.keyframe_points[-1].co.x = frame_this_year - 1
                        fcurve.keyframe_points[0].co.x = frame_last_year - 1
                        fcurve.keyframe_points[0].interpolation = 'LINEAR'

                        # Keyframe vis
                        record(context.collection, properties)
                        retime(context.collection, properties)
                        #for fcurve in self.tree_objects[i].animation_data.action.fcurves:
                        #    fcurve.keyframe_points[0].co.x = 0
                        #   fcurve.keyframe_points[-1].co.x = frame_this_year
                        #   fcurve.keyframe_points[1].co.x = frame_last_year

                        #    if year == properties.age:
                        #        fcurve.keyframe_points[-1].co.x = 5000
                    # End WIP TODO.

                    if self.current_shape == self.shape_keys_dial.value:  # Last tree.
                        self.done = True
                        self._timer = win_man.event_timer_add(0.05, window=context.window)
                        context.scene.frame_set(1)
                        context.area.tag_redraw()
                        return{'RUNNING_MODAL'}

                progress = self.current_shape / self.shape_keys_dial.value
                if progress < 0.01:
                    progress = 0.01
                self.progress_dial.progress = progress

                self._timer = win_man.event_timer_add(0.05, window=context.window)
                context.scene.frame_set(self.current_shape * self.interval - self.interval)
                context.area.tag_redraw()

                return {'RUNNING_MODAL'}

        return {'RUNNING_MODAL'}

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
        self.grove_properties.is_tool_active_animate_wind = True

        replant(context.collection, self.grove_properties, self.grove)

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
        context.collection.GROVE22_Properties.is_tool_active_animate_wind = False

        bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')
        if self._turntable_timer:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None

        if self._timer:
            context.window_manager.event_timer_remove(self._timer)

        bpy.ops.screen.animation_cancel()

        context.area.tag_redraw()


def add_wind_shape(model, obj, current_shape, interval, width, wind_shapes=50):
    """ Add wind animation shape key to the current tree. """

    j = current_shape

    shape_key = obj.shape_key_add(name='WindShape', from_mix=False).data
    flat = np.array(model.get_shape_as_tuples()).ravel()
    shape_key.foreach_set("co", flat)

    # Insert keyframes for this shape.
    channel = obj.data.shape_keys.key_blocks[-1]
    channel.value = 1.0
    channel.keyframe_insert("value", frame=j * interval + 0)
    channel.value = 0.0
    channel.keyframe_insert("value", frame=j * interval - width)
    channel.keyframe_insert("value", frame=j * interval + width)

    # Add a last zero keyframe to define the channel length for looping.
    channel.keyframe_insert("value", frame=(j * interval + interval * wind_shapes - width))
