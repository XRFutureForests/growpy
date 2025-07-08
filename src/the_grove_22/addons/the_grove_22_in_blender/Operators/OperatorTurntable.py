
""" It has a UI with only one floating widget, a turntable that is always in modal mode.

    Copyright 2018 - 2025, Wybren van Keulen, The Grove """


from time import time

import bpy
from mathutils import Vector

from ..Interface.Interface import Interface, TouchTurntable
from ..Interface.Canvas import Canvas
from ..Languages.Translation import t
from ..Turntable import turn_the_table


def draw_2d(self, context):
    """ Draw the turntable widget. """

    if self.space_data == context.space_data:  # Prevents drawing in other 3D views.
        self.interface.draw()


def status_text_callback(header, _):
    """ Add shortcuts to the status bar. """

    header.layout.label(text=t('View'), icon='MOUSE_MOVE')


class GROVE22_OT_Turntable(bpy.types.Operator):

    bl_idname = "the_grove_22.turntable"
    bl_label = t('operator_turntable')
    bl_description = t('operator_turntable_tt')
    bl_options = {'INTERNAL'}

    _handle_draw_2d = None
    _timer = None
    _turntable_timer = None
    canvas = Canvas()

    start_time = 0
    rotation_offset = 0.0
    initialized = False

    # Setup the interface. Class-wide, not per class instance like in __init__. This will make each instance
    # of the tool keep the set parameters and remember which tips have been clicked away.
    interface = Interface()

    turntable = TouchTurntable(action='View', label='', tooltip='View', icon='VIEW')
    turntable.free = True
    interface.widgets.append(turntable)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grove_properties = None
        self.mouse = Vector((0.0, 0.0))
        self.space_data = None  # Used to only draw in the active 3D view.
        self.look_at_offset = 0.0

    @classmethod
    def poll(cls, context):
        """ Check if the conditions are met for running this operator. """

        # Only region.type == 'WINDOW', because while hovering over the 'UI' region will cause trouble.
        if not context.collection.GROVE22_Properties:
            return False

        return context.region.type == 'WINDOW' and context.mode == 'OBJECT'

    def modal(self, context, event):
        """ Event loop. """

        win_man = context.window_manager

        if event.type in ['LEFTMOUSE', 'RIGHTMOUSE', 'ESC'] and event.value == 'RELEASE':

            if time() - self.start_time < 0.4:
                self.cancel(context)
                bpy.ops.the_grove_22.zoom('INVOKE_DEFAULT')
                return {'FINISHED'}

            self.cancel(context)
            return {'FINISHED'}

        if time() - self.start_time < 0.2:
            return {"RUNNING_MODAL"}

        if not self.initialized:
            self.turntable.vector = Vector((1.0, 0.0)) * self.turntable.vector.length

            view = bpy.context.region_data
            view.update()
            rotation = view.view_rotation @ Vector((1.0, 0.0, 0.0))
            rotation = Vector((rotation.x, rotation.y))
            self.rotation_offset = rotation.angle_signed(Vector((1.0, 0.0)))
            self.initialized = True

        if event.type in ['MOUSEMOVE', 'LEFTMOUSE']:
            self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))

        elif event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            if event.type == 'WHEELUPMOUSE':
                self.look_at_offset -= 0.2
            else:
                self.look_at_offset += 0.2
            turn_the_table(
                context, self.turntable.vector,
                self.grove_properties.height * self.grove_properties.simulation_scale,
                self.interface, offset=self.rotation_offset,
                look_at_offset=self.look_at_offset)
            context.region.tag_redraw()

        if event.type == 'TIMER':
            if self._turntable_timer is not None:
                win_man.event_timer_remove(self._turntable_timer)
                self._turntable_timer = None

            if self.turntable.modal:
                self.interface.event_touch_move(self.mouse)
                turn_the_table(
                    context, self.turntable.vector,
                    self.grove_properties.height * self.grove_properties.simulation_scale,
                    self.interface, offset=self.rotation_offset,
                    look_at_offset=self.look_at_offset)
                if self.turntable.do_interpolate:
                    self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)

                context.region.tag_redraw()
                return {"RUNNING_MODAL"}

        elif event.type == 'MOUSEMOVE':
            if self._turntable_timer is not None:
                # When interpolating with the timer, prevent a double redraw.
                return {"RUNNING_MODAL"}

            if self.interface.event_touch_move(self.mouse):
                if self.interface.action == 'View' and self.turntable.modal:
                    turn_the_table(
                        context, self.turntable.vector,
                        self.grove_properties.height * self.grove_properties.simulation_scale,
                        self.interface, offset=self.rotation_offset,
                        look_at_offset=self.look_at_offset)
                    if self._turntable_timer is None:
                        self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)

                context.region.tag_redraw()

        return {"RUNNING_MODAL"}

    def invoke(self, context, event):
        """ Initialize. """

        self.grove_properties = context.collection.GROVE22_Properties

        context.workspace.status_text_set(status_text_callback)
        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.window_manager.modal_handler_add(self)

        self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        self.turntable.location = self.mouse
        self.turntable.center = self.mouse - Vector((self.turntable.radius * 5.0, 0.0))

        self.turntable.modal = True
        self.turntable.do_interpolate = True
        self.turntable.scale_figure_alpha = 0.2
        self.interface.update()

        self.initialized = False

        if self._turntable_timer is None:
            # Enable this for animation at the start.
            self._turntable_timer = bpy.context.window_manager.event_timer_add(0.05, window=bpy.context.window)

        self.start_time = time()

        return {"RUNNING_MODAL"}

    def cancel(self, context):
        """ Cleanup. """

        bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')
        context.workspace.status_text_set(text=None)  # To release the status bar for new use.

        self.interface.action = 'NONE'
        if self._turntable_timer:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None

        self.interface.cancel()

        if self._timer:
            context.window_manager.event_timer_remove(self._timer)

        self.turntable.vector = Vector((1.0, 0.0)) * self.turntable.vector.length

        self.turntable.modal = False
        bpy.context.region_data.update()

        context.window.cursor_modal_restore()
        context.area.tag_redraw()
