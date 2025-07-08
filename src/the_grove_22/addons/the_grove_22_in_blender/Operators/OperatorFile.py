
""" Save and load trees to and from a file.

    Copyright 2020 - 2025, Wybren van Keulen, The Grove """


from os.path import basename

import bpy
from mathutils import Vector

from ..Languages.Translation import t
from ..Interface.Interface import Interface, TouchButton, TouchTurntable, TouchPanel, stop_animation_playback
from ..Turntable import turn_the_table
from .OperatorImportExport import recent_files, import_path


def draw_2d(self, context):
    if self.space_data == context.space_data:
        self.interface.draw()


def status_text_callback(header, _):
    """ Add shortcuts to Blender's status bar. """

    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')


class GROVE22_OT_File(bpy.types.Operator):

    bl_idname = "the_grove_22.file"
    bl_label = t('file')
    bl_description = t('file_tt')
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _handle_draw_2d = None
    _turntable_timer = None
    rotation_offset = 0.0

    # Setup the interface. Class-wide, not per class instance like in __init__. This will make each instance
    # of the tool keep the set parameters and remember which tips have been clicked away.

    close_button = TouchButton(action='Back', label=t('close_button'), tooltip=t('close_button_tt'), icon='CHECKMARK')
    import_button = TouchButton(action='import', label=t('file_import'), tooltip=t('file_import_tt'), icon='IMPORT')
    export_button = TouchButton(action='export', label=t('file_export'), tooltip=t('file_export_tt'), icon='EXPORT')

    recent_1 = TouchButton(
        action='import_recent_1',
        label='Import recent 1',
        tooltip=t('close_button_tt'),
        icon='FILE')
    recent_2 = TouchButton(
        action='import_recent_2',
        label='Import recent 2',
        tooltip=t('close_button_tt'),
        icon='FILE')
    recent_3 = TouchButton(
        action='import_recent_3',
        label='Import recent 3',
        tooltip=t('close_button_tt'),
        icon='FILE')
    recent_4 = TouchButton(
        action='import_recent_4',
        label='Import recent 4',
        tooltip=t('close_button_tt'),
        icon='FILE')
    recent_5 = TouchButton(
        action='import_recent_5',
        label='Import recent 5',
        tooltip=t('close_button_tt'),
        icon='FILE')

    turntable = TouchTurntable(
        action='View',
        label=t('turntable'),
        tooltip=t('turntable_tt'),
        icon='VIEW')

    interface = Interface()
    interface.widgets.append(close_button)
    interface.widgets.append(turntable)
    interface.add_spacer()
    interface.widgets.append(export_button)
    interface.widgets.append(import_button)
    interface.add_spacer()
    interface.widgets.append(recent_1)
    interface.widgets.append(recent_2)
    interface.widgets.append(recent_3)
    interface.widgets.append(recent_4)
    interface.widgets.append(recent_5)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grove = []
        self.grove_properties = None
        self.current_tree = 0
        self.current_shape = 0

        self.mouse = Vector((0, 0))
        self.space_data = None  # Used to only draw in the active 3D view.

    @classmethod
    def poll(cls, context):
        """ Check if the context is right to run this operator. """

        return context.mode == 'OBJECT'

    def modal(self, context, event):
        """ Event handling. """

        win_man = context.window_manager

        if event.type in ['MOUSEMOVE', 'LEFTMOUSE']:
            self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))

        if event.type == 'TIMER':
            if self._turntable_timer is not None:
                win_man.event_timer_remove(self._turntable_timer)
                self._turntable_timer = None

            if self.turntable.modal:
                self.turntable.event_touch_move(self.mouse)
                turn_the_table(
                    context, self.turntable.vector,
                    self.grove_properties.height * self.grove_properties.simulation_scale,
                    self.interface, offset=self.rotation_offset)
                if self.turntable.do_interpolate:
                    self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)

                context.region.tag_redraw()
                return {"RUNNING_MODAL"}

        elif event.type == 'MOUSEMOVE':
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

            return {'RUNNING_MODAL'}

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
                        # Animation at the start.
                        self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)

                context.region.tag_redraw()
                return {"RUNNING_MODAL"}

        elif event.type in ['RIGHTMOUSE', 'SPACE', 'RET', 'NUMPAD_ENTER'] and event.value == 'PRESS':
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

            action = self.interface.action
            if action == 'Back':
                self.cancel(context)
                return {'FINISHED'}

            elif action == 'import':
                bpy.ops.the_grove_22.import_grove("INVOKE_DEFAULT")
                self.cancel(context)
                return {'FINISHED'}

            elif action == 'import_recent_1':
                context.window.cursor_modal_set('WAIT')
                import_path(recent_files()[-1])
                context.window.cursor_modal_restore()
            elif action == 'import_recent_2':
                context.window.cursor_modal_set('WAIT')
                import_path(recent_files()[-2])
                context.window.cursor_modal_restore()
            elif action == 'import_recent_3':
                context.window.cursor_modal_set('WAIT')
                import_path(recent_files()[-3])
                context.window.cursor_modal_restore()
            elif action == 'import_recent_4':
                context.window.cursor_modal_set('WAIT')
                import_path(recent_files()[-4])
                context.window.cursor_modal_restore()
            elif action == 'import_recent_5':
                context.window.cursor_modal_set('WAIT')
                import_path(recent_files()[-5])
                context.window.cursor_modal_restore()

            elif action == 'export':
                bpy.ops.the_grove_22.export_grove("INVOKE_DEFAULT")
                self.cancel(context)
                return {'FINISHED'}

            context.region.tag_redraw()
            return {'RUNNING_MODAL'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, _):
        """ When starting the tool, do some initialization. """

        self.grove_properties = context.collection.GROVE22_Properties
        self.grove_properties.is_tool_active_file = True

        stop_animation_playback()

        context.window_manager.modal_handler_add(self)

        files = recent_files()
        self.recent_1.hidden = not len(files)
        self.recent_2.hidden = not len(files) > 1
        self.recent_3.hidden = not len(files) > 2
        self.recent_4.hidden = not len(files) > 3
        self.recent_5.hidden = not len(files) > 4
        if not self.recent_1.hidden:
            self.recent_1.label = t("file_recent") + ": " + basename(files[-1].split('.grove')[0])
            self.recent_1.tooltip = files[-1]
        if not self.recent_2.hidden:
            self.recent_2.label = t("file_recent") + ": " + basename(files[-2].split('.grove')[0])
            self.recent_2.tooltip = files[-2]
        if not self.recent_3.hidden:
            self.recent_3.label = t("file_recent") + ": " + basename(files[-3].split('.grove')[0])
            self.recent_3.tooltip = files[-3]
        if not self.recent_4.hidden:
            self.recent_4.label = t("file_recent") + ": " + basename(files[-4].split('.grove')[0])
            self.recent_4.tooltip = files[-4]
        if not self.recent_5.hidden:
            self.recent_5.label = t("file_recent") + ": " + basename(files[-5].split('.grove')[0])
            self.recent_5.tooltip = files[-5]

        context.workspace.status_text_set(status_text_callback)
        self.interface.update()
        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        """ When closing the tool, return some things to how they were before. """

        context.workspace.status_text_set(text=None)
        context.collection.GROVE22_Properties.is_tool_active_file = False

        if self._handle_draw_2d:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')
        if self._turntable_timer:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None

        if self._timer:
            context.window_manager.event_timer_remove(self._timer)

        self.interface.cancel()
        context.area.tag_redraw()
