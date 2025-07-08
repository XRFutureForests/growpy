
""" Simulate all groves together, to mix species of trees.
    The combined foliage casts shade and trees compete for light.

    Copyright 2021 - 2025, Wybren van Keulen, The Grove """

import bpy
from mathutils import Vector

from ..Interface.Interface import Interface, TouchButton, TouchSlider, TouchProgress, TouchTurntable
from ..Languages.Translation import t
from .OperatorBuild import build
from .OperatorRestart import clean_grove, clean_record, create_new_trees
from ..File import load_grove, save_grove
from ..Turntable import turn_the_table


def draw_2d(self, context):
    # Prevent drawing in other 3D views.
    if self.space_data != context.space_data:
        return

    self.interface.draw()


def status_text_callback(header, _):
    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')


class GROVE22_OT_GrowTogether(bpy.types.Operator):

    bl_idname = "the_grove_22.grow_together"
    bl_label = t('grow_together')
    bl_description = t('grow_together_tt')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    _handle_draw_2d = None
    _timer = None
    _turntable_timer = None

    # Setup the interface in the class and not per class instance like in __init__.
    # So that each instance of the tool remember the same settings.
    interface = Interface()

    close_button = TouchButton(action='Back', label=t('close_button'), tooltip=t('close_button_tt'), icon='CHECKMARK')
    close_button.icon_over = 'CLOSE_OVER'
    close_button.icon_down = 'CLOSE_DOWN'

    turntable = TouchTurntable(action='View', label=t('turntable'), tooltip=t('turntable_tt'), icon='VIEW')

    restart_button = TouchButton(action='Restart', label=t('restart_all'), tooltip=t('restart_all_tt'), icon='RESTART')

    simulation_flushes_dial = TouchSlider(
        action='GrowYears', label=t('simulation_flushes'), tooltip=t(''), icon='NONE',
        value_min=1, value_max=20, value_default=5,
        step=1, step_precision=1, dots=20, digits=0)

    progress_dial = TouchProgress(
        action='Progress', label=t('grow_together'), tooltip=t('grow_together_tt_short'), icon='GROW')
    progress_dial.hidden = False

    interface.widgets.append(close_button)
    interface.widgets.append(turntable)
    interface.add_spacer()
    interface.widgets.append(restart_button)
    interface.widgets.append(simulation_flushes_dial)
    interface.widgets.append(progress_dial)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grove = None

        self.list_of_collections = []
        self.list_of_properties = []
        self.list_of_groves = []

        self.grove_properties = None
        self.mouse = Vector((0.0, 0.0))
        self.space_data = None  # Used to only draw in the active 3D view.

        self.viewing = False

        self.simulation_flushes = 1
        self.temp_auto_prune_low = 0.0
        self.growing = False
        self.building = False
        self.current_year = 0

        self.rotation_offset = 0.0

        self.done = False
        self.build_step = False

    def after_growing(self, context):

        self.growing = False
        self.building = False

        self.current_year = 0
        self.progress_dial.progress = -1.0
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)

        for i, grove in enumerate(self.list_of_groves):
            build(context, self.list_of_properties[i], grove, self.list_of_collections[i], rebuild=False)
            save_grove(grove, self.list_of_collections[i])

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the add object menu entry is greyed out. """

        return context.mode == 'OBJECT'

    def update_status(self, context):
        """ Set the status bar text. """

        context.workspace.status_text_set(status_text_callback)

    def modal(self, context, event):
        """ The main event loop. """

        win_man = context.window_manager

        if event.type in ['MOUSEMOVE', 'LEFTMOUSE']:
            self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))

        if event.type != 'TIMER':
            if self.viewing:
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

            if self._timer:
                if self.done:
                    self.progress_dial.progress = -1.0
                    self.done = False
                    self.current_year = 0

                    self.progress_dial.label = t('Grow All')
                    self.progress_dial.icon = 'GROW'

                    win_man.event_timer_remove(self._timer)
                    self._timer = None
                    context.window.cursor_modal_restore()
                    context.area.tag_redraw()

                    return {'RUNNING_MODAL'}

                if self.build_step:
                    progress = self.progress_dial.progress + (100 - self.progress_dial.progress) / 2.0
                    self.progress_dial.progress = progress / 100.0

                    for i, grove in enumerate(self.list_of_groves):
                        build(context, self.list_of_properties[i], grove, self.list_of_collections[i], rebuild=False)
                        save_grove(grove, self.list_of_collections[i])

                    self.progress_dial.progress = 1.0
                    context.area.tag_redraw()

                    self.build_step = False
                    self.done = True
                    self.growing = False

                    return {'RUNNING_MODAL'}

                win_man.event_timer_remove(self._timer)

                if self.current_year != self.simulation_flushes_dial.value:
                    self.current_year += 1

                    # vectors = []
                    # for i, grove in enumerate(self.list_of_groves):
                    #     grove.set_properties(self.list_of_properties[i].convert_to_core_properties())
                    #     vectors.extend(grove.create_shade_geometry())

                    # coords = []
                    # for vector in vectors:
                    #     coords.extend([vector.x, vector.y, vector.z])

                    # So much faster!
                    coords = []
                    for i, grove in enumerate(self.list_of_groves):
                        grove.set_properties(self.list_of_properties[i].convert_to_core_properties())
                        coords.extend(grove.create_shade_geometry_coords())

                    for i, grove in enumerate(self.list_of_groves):
                        grove.calculate_shade_together(coords)

                        grove.simulate(1)

                        # if self.grove_properties.record_enabled:
                        #     build(context, self.grove_properties, self.grove, context.collection, rebuild=False)

                        if self.current_year > 0:
                            # Calculate progress in an exponential fashion, it's pretty accurate.
                            exponent = 1
                            if self.simulation_flushes_dial.value > 4:
                                exponent = 1.8
                            # Plus one for build step.
                            progress = pow(self.current_year / (self.simulation_flushes_dial.value + 1), exponent)
                            self.progress_dial.progress = max(1, int(progress * 100)) / 100.0

                        # grove_properties['height'] = find_highest_point(self.grove)

                else:
                    self.build_step = True
                    self.progress_dial.label = t('grow_tool_building')
                    self.progress_dial.icon = 'BUILD'

                context.area.tag_redraw()

                self._timer = win_man.event_timer_add(0.02, window=context.window)

                return {'RUNNING_MODAL'}

        # Allow viewport navigation.
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
                self.viewing = True
                context.window.cursor_modal_set('SCROLL_XY')
                return {'PASS_THROUGH'}
                # To allow viewport zooming.

        elif event.type in ['MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'ACCENT_GRAVE']:
            self.viewing = True
            context.window.cursor_modal_set('SCROLL_XY')
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
                context.window.cursor_modal_set('DEFAULT')

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
            self.interface.event_touch_release(self.mouse)
            action = self.interface.action

            if action == 'View_CLICK':
                turn_the_table(
                    context, self.turntable.vector,
                    self.grove_properties.height * self.grove_properties.simulation_scale,
                    self.interface, offset=self.rotation_offset)
                return {"RUNNING_MODAL"}

            elif action == 'Restart':
                for i, grove in enumerate(self.list_of_groves):
                    collection = self.list_of_collections[i]
                    properties = self.list_of_properties[i]
                    clean_grove(collection)
                    clean_record(collection)
                    grove = create_new_trees(context, collection, properties)
                    self.list_of_groves[i] = grove
                    build(context, properties, grove, collection, rebuild=False)
                    save_grove(grove, collection)

                return {'RUNNING_MODAL'}

            elif action == 'Back':
                self.cancel(context)
                return {'FINISHED'}

            elif action == 'Progress':
                context.window.cursor_modal_set('WAIT')
                self._timer = win_man.event_timer_add(0.02, window=context.window)
                self.growing = True

            context.workspace.status_text_set(text=None)  # To release the status bar for new use.

            context.region.tag_redraw()
            return {"RUNNING_MODAL"}


        elif event.type in ['RIGHTMOUSE', 'ESC', 'SPACE', 'RET', 'NUMPAD_ENTER'] and event.value == 'PRESS':
            if self.growing:
                self.after_growing(context)
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
        """ Initialize. """

        # First check if the user has moved around trees and if so, then replant them.
        bpy.ops.the_grove_22.replant('EXEC_DEFAULT')

        self.grove_properties = context.collection.GROVE22_Properties
        self.grove_properties.is_tool_active_grow_together = True

        # Load all groves.
        for collection in bpy.data.collections:
            if 'GROVE22_Properties' in collection and collection.GROVE22_Properties.unique_id != '':
                grove = load_grove(collection)
                if grove:
                    self.list_of_groves.append(grove)
                    self.list_of_collections.append(collection)
                    self.list_of_properties.append(collection.GROVE22_Properties)

        # The active collection sets the number of years to grow.
        properties = context.collection.GROVE22_Properties
        self.simulation_flushes = properties.simulation_flushes

        self.update_status(context)

        self.interface.info_bar = []
        if properties.auto_prune_enabled and properties.auto_prune_low != 0:
            # self.interface.info_bar.append('Prune Low: ' + str(properties.auto_prune_low) + 'm')
            self.interface.info_bar.append('Auto Prune')
        if properties.surround_enabled and properties.surround_density != 0:
            self.interface.info_bar.append('Surround disabled')
        if properties.record_enabled:
            self.interface.info_bar.append('Record disabled')
        if properties.react_block_object or properties.react_shade_object or \
            properties.react_attract_object or properties.react_deflect_object:
            if properties.react_enabled:
                self.interface.info_bar.append('React disabled')
        
        self.grove_properties.record_enabled = False  # Doesn't work well!

        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.window_manager.modal_handler_add(self)

        self.interface.update()

        context.window.cursor_modal_set('CROSSHAIR')
        return {"RUNNING_MODAL"}

    def cancel(self, context):
        """ Cleanup. """

        self.interface.action = 'NONE'

        bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')
        context.workspace.status_text_set(text=None)

        context.collection.GROVE22_Properties.is_tool_active_grow_together = False

        if self._turntable_timer:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None
        if self._timer:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None

        context.window.cursor_modal_restore()
        context.area.tag_redraw()
