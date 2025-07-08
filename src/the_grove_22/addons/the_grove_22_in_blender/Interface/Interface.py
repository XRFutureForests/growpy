# coding=utf-8

""" The Grove in Blender has two separate interfaces.
    The first is the default Blender interface with panels created in Panels.py,
    which are filled with properties defined in Properties.py.

    The second interface is this one used for interactive tool in the 3D view.
    These user interface elements designed to work well on small touch screens,
    with tablets and that are also fun to use with a mouse.

    Copyright 2021 - 2025, Wybren van Keulen, The Grove """


from math import cos, sin
from time import time

import bpy
from mathutils import Vector, Matrix, Quaternion

from .Canvas import Canvas


canvas = Canvas()
widget_color = (0.0, 0.0, 0.0, 0.72)


def stop_animation_playback():
    # If animation is playing, it can cause jittery updates in the viewport, so stop it.
    # Blender's Python API is prone to changes, so be careful with these calls.
    if hasattr(bpy.context.screen, 'is_animation_playing'):
        if bpy.context.screen.is_animation_playing:
            if hasattr(bpy.ops.screen, 'animation_cancel'):
                bpy.ops.screen.animation_cancel()


def format_tooltip(tooltip):
    if tooltip != '':
        tooltip += '.'
    
    words = tooltip.split(' ')
    
    line = ''
    count = 0
    for word in words:
        if count < 45:
            if line:
                line = line + ' '
            line = line + word
            count += len(word) + 1
        else:
            if line[-1] == ' ':
                line = line[:-1]
            line = line + '\n' + word
            count = len(word) + 1
    
    return line


class Interface(object):
    """ """

    def __init__(self):
        self.widgets = []
        self.touch = False
        self.hovering = False

        self.info_bar = []

        self.action = 'NONE'

        self.location = Vector((0, 0))
        self.radius = 60

        self.view_width = 0
        self.view_height = 0
        self.ui_width = 0
        self.view_start_x = 0
        self.view_start_y = 0

        self.region_width = 0
        self.region_height = 0

    def cancel(self):
        """ When the user cancels a tool with Escape or RMB, avoid modal widgets to get stuck when
            the tool gets called again. Also make sure the mouse cursor is restored. """

        for widget in self.widgets:
            if hasattr(widget, 'modal'):
                if widget.modal:
                    widget.modal = False
                    if hasattr(widget, 'value_pre_modal'):
                        widget.value = widget.value_pre_modal
                    # TODO: make all widget types have a value and value_pre_modal, instead of vector_pre_modal.
                    if hasattr(widget, 'vector_pre_modal'):
                        widget.vector = widget.vector_pre_modal
                        
            # if type(widget) == TouchPanel: // this does not work after reloading scripts!
            if hasattr(widget, 'type') and widget.type == 'touch_panel':
                widget.cancel()
        bpy.context.window.cursor_modal_restore()

    def find_modal(self):
        """ See if there is an active widget. """

        for widget in self.widgets:
            if widget.modal:
                return widget
            # if type(widget) == TouchPanel: // this does not work after reloading scripts!
            if hasattr(widget, 'type') and widget.type == 'touch_panel':
                modal_widget = widget.find_modal()
                if modal_widget:
                    return modal_widget
        return False

    def add_spacer(self):
        """ Use a spacer to visually group widgets. """

        self.widgets.append(TouchSpacer())

    def get_height(self, radius):
        """ Calculate the total height of all widgets. """

        view_height = 0
        for widget in self.widgets:
            if widget.hidden or widget.free:
                continue

            view_height += widget.get_height(self.radius)

        return view_height

    def update(self):
        """ Scale the interface and put widgets in the correct place. """

        self.radius = bpy.context.preferences.system.dpi * 0.39 * bpy.context.preferences.addons[__package__.split('.')[0]].preferences.widget_scale

        # Reduce radius if the view height is low.
        view_height = self.get_height(self.radius)
        self.region_width = bpy.context.region.width
        self.region_height = bpy.context.region.height
        self.view_height = view_height

        radius = self.radius

        if self.view_height > bpy.context.region.height:
            ratio = bpy.context.region.height / self.view_height
            radius *= ratio
            if radius < 40.0:
                radius = 40.0

        self.view_width = bpy.context.region.width
        locx = bpy.context.region.width - 1.5 * radius - 20

        # Center the interface.
        locy = (bpy.context.region.height * 0.5) - (self.view_height * 0.5)
        locy -= 2.5 * radius  # A bit more to the bottom.
        if locy < 0:
            locy = 0

        if locy > 280:
            locy = 280  # For a bottom oriented interface.

        location = Vector((locx, locy))
        # Shift the interface left if the UI area is open.
        if bpy.context.preferences.system.use_region_overlap:
            for region in bpy.context.area.regions:
                if region.type == 'UI':
                    locx -= region.width
                    location = Vector((locx, locy))
                    self.view_width -= region.width
                    self.ui_width = region.width
                elif region.type == 'HEADER':
                    locy -= region.height
                    location = Vector((locx, locy))
                    self.view_height -= region.height
                elif region.type == 'TOOLS':
                    location = Vector((locx, locy))
                    self.view_width -= region.width
                    self.view_start_x = region.width

        for widget in self.widgets:
            if widget.hidden or widget.free:
                continue
            height = widget.get_height(radius)
            location[1] += height
            widget.location = location - Vector((0.0, height * 0.5))

            # if type(widget) == TouchPanel: // this does not work after reloading scripts!
            if hasattr(widget, 'type') and widget.type == 'touch_panel':
                widget.radius = self.radius
                widget.update()

    def event_touch_move(self, mouse):
        """ Dispatch that event to the proper widget. """

        # self.action = 'NONE'
        action = False
        self.hovering = False

        modal_widget = self.find_modal()
        if modal_widget:
            widgets = [modal_widget]
        else:
            widgets = self.widgets

        for widget in widgets:
            if widget.hidden:
                continue
            if widget.event_touch_move(mouse):
                self.action = widget.action + widget.action_plus
                action = True
                # break  # With this, other widgets can be stuck in hovering state when the mouse moves too fast.
                if widget.modal:
                    break

            if widget.hovering:
                self.hovering = True

        return action

    def event_touch_down(self, mouse):
        """ Dispatch that event to the proper widget. """

        self.touch = False

        widget = self.find_modal()
        if widget:
            if widget.event_touch_down(mouse):
                self.action = widget.action + widget.action_plus
                self.touch = True
                return True
        else:
            for widget in self.widgets:
                if widget.hidden:
                    continue
                if widget.event_touch_down(mouse):
                    self.action = widget.action + widget.action_plus
                    self.touch = True
                    return True

        return False

    def event_touch_release(self, mouse):
        """ Dispatch that event to the proper widget. """

        self.touch = False
        self.action = 'NONE'

        modal_widget = self.find_modal()
        if modal_widget:
            widgets = [modal_widget]
        else:
            widgets = self.widgets

        for widget in widgets:
            if widget.hidden:
                continue
            if widget.event_touch_release(mouse):
                self.action = widget.action + widget.action_plus
                self.update()
                return True

        self.update()
        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        """ Dispatch that event to the proper widget. """

        # If modal. Prevent leaking to invisible, non-modal widgets.
        modal_widget = self.find_modal()
        if modal_widget:
            widgets = [modal_widget]
        else:
            widgets = self.widgets

        for widget in widgets:
            if widget.hidden:
                continue
            if widget.event_mouse_wheel(mouse, up_or_down):
                self.action = widget.action + widget.action_plus
                return True

        return False

    def draw(self):
        """ Draw all widgets. """

        # canvas.draw_passepartout(self.view_start_x, self.view_start_y, self.view_width, bpy.context.region.height)

        # Infobar
        location = Vector((self.view_width, 60))
        location.x -= self.radius
        for info in self.info_bar:
            canvas.draw_icon('DOT', location, self.radius * 0.7, color=(1.0, 0.9, 0.4, 0.5))  # CHECKMARK
            location.x -= self.radius * 0.5
            text_width = canvas.draw_text(
                location, info, color=(1.0, 1.0, 1.0, 1.0),
                align='RIGHT', do_not_draw=True, radius=self.radius)[0]

            canvas.draw_text(
                location, info, color=(1.0, 0.9, 0.4, 1.0),
                align='RIGHT', vertical_align=True, radius=self.radius)
            # location.x -= self.radius * 1.2
            location.x -= text_width + self.radius * 1.0

        # If there's an active dial, don't draw the rest of the interface.
        modal_widget = self.find_modal()
        if modal_widget:
            # if (widget.type == 'slider' or widget.type == 'vector' or widget.type == 'turntable') and widget.modal:
            modal_widget.draw()
            return

        for widget in self.widgets:
            if widget.hidden:
                continue
            widget.draw()


class TouchPanel(object):
    """ A widget that visually groups together other widgets.
        It has a title and it can be collapsed. """

    def __init__(self, label=''):
        self.type = 'touch_panel'
        self.free = False
        self.hidden = False
        self.modal = False
        self.minimal = False
        self.collapsed = False

        self.widgets = []
        self.touch = False
        self.hovering = False
        self.hovering_header = False

        self.action = ''
        self.action_plus = ''
        self.label = label
        self.tooltip = ''

        self.action = 'NONE'

        self.location = Vector((0, 0))
        self.radius = 60

        self.view_width = 0
        self.view_height = 0
        self.ui_width = 0
        self.view_start_x = 0
        self.view_start_y = 0

        self.region_width = 0
        self.region_height = 0

    def cancel(self):
        """ When the user cancels a tool with Escape or RMB, avoid modal widgets to get stuck when
            the tool gets called again. Also make sure the mouse cursor is restored. """
        for widget in self.widgets:
            if hasattr(widget, 'modal'):
                if widget.modal:
                    widget.modal = False
                    if hasattr(widget, 'value_pre_modal'):
                        widget.value = widget.value_pre_modal
                    # TODO: make all widget types have a value and value_pre_modal, instead of vector_pre_modal.
                    if hasattr(widget, 'vector_pre_modal'):
                        widget.vector = widget.vector_pre_modal
        
        bpy.context.window.cursor_modal_restore()

    def find_modal(self):
        """ See if there is an active widget in this panel. """
        for widget in self.widgets:
            if widget.modal:
                return widget
        return False

    def add_spacer(self):
        """ Add white space. """
        self.widgets.append(TouchSpacer())

    def get_height(self, radius):
        """ Get the height of all the widgets plus the panel header. """

        self.radius = radius

        # Space for header.
        view_height = int(self.radius * 2.3333 / 2.5) + 1

        # Padding top and bottom.
        if not self.collapsed:
            view_height += 0.15 * self.radius * 2

        if self.collapsed:
            return view_height

        # view_height = 0
        for widget in self.widgets:
            if widget.hidden or widget.free:
                continue

            view_height += widget.get_height(self.radius)

        return view_height

    def update(self):
        location = self.location.copy()
        if self.widgets:
            if self.widgets[0].minimal:
                location[1] += self.get_height(self.radius) * 0.5
            else:
                location[1] += self.get_height(self.radius) / 1.6
        location[1] -= 0.15 * self.radius

        # Space for header.
        # location[1] -= int(self.radius * 2.3333 / 2.5) + 1

        for widget in self.widgets:
            if widget.hidden or widget.free:
                continue
            height = widget.get_height(self.radius)
            location[1] -= height
            widget.location = location - Vector((0.0, height * 0.5))

    def event_touch_move(self, mouse):
        self.update()
        hovering_inside = False
        self.hovering = False

        for widget in self.widgets:
            if widget.hidden:
                continue
            widget.hovering = False
            if widget.event_touch_move(mouse):
                self.action = widget.action + widget.action_plus
                if widget.hovering:
                    self.hovering = True
                    hovering_inside = True
                # break  # With this, other widgets can be stuck in hovering state when the mouse moves too fast.
                if widget.modal:
                    break

        if hovering_inside:
            return True

        # Hovering over panel header.
        previous_hovering_header = self.hovering_header == True
        top = (self.location[1] + self.get_height(self.radius) * 0.5)
        self.hovering_header = (
            mouse[1] < top and
            mouse[1] > top - self.radius and
            mouse[0] > self.location[0] - self.radius * 6)

        # Only redraw if there are changes.
        return False
        # return previous_hovering_header == self.hovering_header

    def event_touch_down(self, mouse):
        if self.collapsed:
            return False

        self.touch = False

        widget = self.find_modal()
        if widget:
            if widget.event_touch_down(mouse):
                self.action = widget.action + widget.action_plus
                self.touch = True
                return True
        else:
            for widget in self.widgets:
                if widget.hidden:
                    continue
                if widget.event_touch_down(mouse):
                    self.action = widget.action + widget.action_plus
                    self.touch = True
                    return True

        return False

    def event_touch_release(self, mouse):
        self.touch = False
        self.action = 'NONE'

        widget = self.find_modal()
        if widget:
            if widget.event_touch_release(mouse):
                self.action = widget.action + widget.action_plus
                return True
        else:

            top = (self.location[1] + self.get_height(self.radius) * 0.5)
            if mouse[1] < top and mouse[1] > top - self.radius:
                if mouse[0] > self.location[0] - self.radius * 6:
                    self.collapsed = not self.collapsed
                    self.update()
                    return True

            if self.collapsed:
                return False

            for widget in self.widgets:
                if widget.hidden:
                    continue
                if widget.event_touch_release(mouse):
                    self.action = widget.action + widget.action_plus
                    return True

        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        for widget in self.widgets:
            if widget.hidden:
                continue
            if widget.event_mouse_wheel(mouse, up_or_down):
                self.action = widget.action + widget.action_plus
                return True

        return False

    def draw(self):
        """ Draw the widget. """

        # Debug panel location
        # canvas.draw_box_rounded(
        #     self.location[0] - 500, self.location[1] + 5, 10, 10, color=(0.0, 0.0, 0.0, 1.0), r=self.radius * 0.5)
        # canvas.draw_box_rounded(
        #     self.location[0] - 500, self.location[1] + self.get_height(self.radius) * 0.5, 10,
        #     self.get_height(self.radius), color=(0.0, 0.0, 0.0, 0.2), r=self.radius * 0.5)

        # Header
        location = self.location + Vector((0, self.get_height(self.radius) * 0.5))
        location[1] -= int(self.radius * 0.416667) + 1  # Same as slider.

        text_width, text_height = canvas.draw_text(
            location, self.label, color=(1.0, 1.0, 1.0, 1.0),
            align='RIGHT', vertical_align=False, size='regular', do_not_draw=True, radius=self.radius)

        if self.collapsed:
            left = self.location[0] - self.radius * 2.2
            right_text = location[0] + self.radius * 0.8
            if left > right_text - text_width - self.radius * 1:
                left = right_text - text_width - self.radius * 1

            if self.hovering_header:
                left -= 0.3 * self.radius
                right_text -= 0.3 * self.radius
                canvas.draw_box_rounded(
                    left, location[1] + self.radius * 0.42, self.radius * 7, self.radius * 0.833,
                    color=(0.0, 0.0, 0.0, 0.45), r=self.radius * 0.5)
                canvas.draw_text(
                    Vector((right_text, location[1] - text_height / 6)), self.label,
                    color=(1.0, 1.0, 1.0, 0.9), align='RIGHT', radius=self.radius)
            else:
                canvas.draw_box_rounded(
                    left, location[1] + self.radius * 0.42, self.radius * 7, self.radius * 0.833,
                    color=(0.0, 0.0, 0.0, 0.35), r=self.radius * 0.5)
                canvas.draw_text(
                    Vector((right_text, location[1] - text_height / 6)), self.label, color=(1.0, 1.0, 1.0, 0.4),
                    align='RIGHT', radius=self.radius)
        else:
            left = self.location[0] - self.radius * 6
            right_text = location[0] - self.radius * 2
            if left > right_text - text_width - self.radius:
                left = right_text - text_width - self.radius

            if self.hovering_header:
                canvas.draw_box_rounded(
                    left, location[1] + self.radius * 0.355, self.radius * 7.3, self.radius * 0.833,
                    color=(0.0, 0.0, 0.0, 0.35), r=self.radius * 0.5)
                canvas.draw_text(
                    Vector((right_text, location[1] - text_height / 6)), self.label, color=(1.0, 1.0, 1.0, 1.0),
                    align='RIGHT', vertical_align=True, radius=self.radius)
            else:
                canvas.draw_box_rounded(
                    left, location[1] + self.radius * 0.355, self.radius * 7.3, self.radius * 0.833,
                    color=(0.0, 0.0, 0.0, 0.35), r=self.radius * 0.5)
                canvas.draw_text(
                    Vector((right_text, location[1] - text_height / 6)), self.label, color=(1.0, 1.0, 1.0, 0.7),
                    align='RIGHT', vertical_align=True, radius=self.radius)

        if self.collapsed:
            return

        # If there's an active dial, don't draw the rest of the interface.
        for widget in self.widgets:
            if type(widget) in [TouchSlider, TouchVector, TouchTurntable] and widget.modal:
                widget.draw()
                return

        for widget in self.widgets:
            if widget.hidden:
                continue
            widget.draw()


class TouchSpacer(object):
    """ White space that can group together similar items. """

    def __init__(self):
        self.free = False
        self.hidden = False
        self.modal = False
        self.hovering = False
        self.minimal = False

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius * 0.66
        spacing = int(self.radius) + 1

        return spacing

    def event_touch_down(self, mouse):
        return False

    def event_touch_move(self, mouse):
        return False

    def event_touch_release(self, mouse):
        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        return False

    def draw(self):
        """ Draw the widget. Not much to draw for white space. """
        return


class TouchButton(object):
    """ A simple button to start an action. """

    def __init__(
            self,
            action='NONE',
            label='',
            tooltip='',
            location=Vector((0.0, 0.0)),
            icon='NONE'):

        self.free = False
        self.hidden = False
        self.modal = False
        self.minimal = False

        self.radius = 60.0
        self.location = location

        self.icon = icon
        self.icon_over = icon
        self.icon_down = icon
        self.action = action
        self.action_plus = ''
        self.label = label
        self.tooltip = format_tooltip(tooltip)

        self.hovering = False
        self.touch = False

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius
        spacing = int(self.radius * 2.3333) + 1
        if self.minimal:
            spacing /= 2.5

        return spacing

    def event_touch_down(self, mouse):
        self.touch = (mouse - self.location).length < self.radius
        return self.touch

    def event_touch_move(self, mouse):
        """ Check if within the button. """

        # Only return True when hover state changes, to save redraws and CPU usage.
        hovering = (mouse - self.location).length < self.radius
        if self.hovering is not hovering:
            self.hovering = hovering
            return True

        return False

    def event_touch_release(self, mouse):
        if self.touch:
            self.touch = False
            return (mouse - self.location).length < self.radius

        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        return False

    def draw(self):
        """ Draw the button. """

        if self.hidden:
            return

        if self.touch:
            canvas.draw_circle_filled(self.location, self.radius * 1.2, color=(0.1, 0.1, 0.1, 0.7))
            canvas.draw_icon(self.icon_down, self.location, self.radius * 1.2, color=(0.8, 0.8, 0.8, 1.0))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0.0)), self.label,
                color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
            if self.label != '':
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)
            else:
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 0.0)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
        elif self.hovering:
            canvas.draw_circle_filled(self.location, self.radius * 1.033, color=(0.1, 0.1, 0.1, 0.7))
            canvas.draw_icon(self.icon_over, self.location, self.radius * 1.0833, color=(0.9, 0.9, 0.9, 1.0))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0.0)), self.label,
                color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
            if self.label != '':
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)
            else:
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 0.0)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
        else:
            canvas.draw_circle_filled(self.location, self.radius, color=widget_color)
            canvas.draw_icon(self.icon, self.location, self.radius, color=(0.8, 0.8, 0.8, 0.5))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0.0)), self.label,
                color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)


class TouchInfo(object):
    """ """

    def __init__(
            self,
            action='NONE',
            label='',
            tooltip='',
            location=Vector((0.0, 0.0)),
            icon='NONE'):

        self.hidden = False
        self.modal = False
        self.minimal = False

        self.radius = 60.0
        self.location = location
        self.free = False

        self.icon = icon
        self.icon_over = icon
        self.icon_down = icon
        self.action = action
        self.action_plus = ''
        self.label = label
        self.text = label
        self.tooltip = format_tooltip(tooltip)

        self.hovering = False
        self.touch = False

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius * 0.66
        spacing = int(self.radius * 2.3333) + 1
        if self.minimal:
            spacing /= 2.5

        return spacing

    def event_touch_down(self, mouse):
        """ Mouse down. """

        self.touch = (mouse - self.location).length < self.radius
        return self.touch

    def event_touch_move(self, mouse):
        """ Check if within the button. """

        if (mouse - self.location).length < self.radius:
            self.hovering = True
            return True
        else:
            if self.touch:
                self.touch = False
            else:
                self.hovering = False
            return False

    def event_touch_release(self, mouse):
        """ Mouse up. """

        if self.touch:
            self.touch = False
            if (mouse - self.location).length < self.radius:
                self.hidden = True
                return True
            return False
        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        return False

    def draw(self):
        """ Draw the widget. """

        if self.hidden:
            return

        if self.touch:
            canvas.draw_circle_filled(self.location, self.radius * 1.2, color=(0.1, 0.1, 0.1, 0.7))

            dim = Vector((0, 0))
            for i, line in enumerate(self.text):
                dim[1] += 40
                line_dim = canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 40 * (i + 1))), line,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', do_not_draw=True, radius=self.radius)
                # dim[1] += line_dim[1]
                if line_dim[0] > dim[0]:
                    dim[0] = line_dim[0]
            dim[1] += 40
            canvas.draw_box_rounded(
                self.location[0] - dim[0] - (self.radius * 2.0),
                self.location[1] + (dim[1] * 0.5),
                dim[0] + (self.radius * 2.0),
                dim[1],
                color=(0.0, 0.0, 0.0, 0.7),
                r=(dim[1] * 0.5))
            for i, line in enumerate(self.text):
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 40 * (i + 1))) + Vector((0, (dim[1] * 0.5))),
                    line,
                    color=(1.0, 1.0, 1.0, 1.0),
                    align='RIGHT',
                    size='small')

            canvas.draw_icon(self.icon_down, self.location, self.radius + 12, color=(0.8, 0.8, 0.8, 1.0))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0.0)), self.label,
                color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)

        elif self.hovering:
            canvas.draw_circle_filled(self.location, self.radius + 2.0, color=(0.1, 0.1, 0.1, 0.7))

            dim = Vector((0, 0))
            for i, line in enumerate(self.text):
                dim[1] += 40
                line_dim = canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 40 * (i + 1))), self.text[i],
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', do_not_draw=True, radius=self.radius)
                # line_dim *= 75
                # dim[1] += line_dim[1]
                if line_dim[0] > dim[0]:
                    dim[0] = line_dim[0]
            dim[1] += 40
            canvas.draw_box_rounded(
                self.location[0] - dim[0] - (self.radius * 2.0),
                self.location[1] + (dim[1] * 0.5),
                dim[0] + (self.radius * 2.0),
                dim[1],
                color=(0.0, 0.0, 0.0, 0.7),
                r=(dim[1] * 0.5))
            for i, line in enumerate(self.text):
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 40 * (i + 1))) + Vector((0, (dim[1] * 0.5))),
                    self.text[i],
                    color=(1.0, 1.0, 1.0, 1.0),
                    align='RIGHT', size='small', radius=self.radius)

            canvas.draw_icon(self.icon_over, self.location, self.radius * 1.0833, color=(0.9, 0.9, 0.9, 1.0))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0.0)), self.label,
                color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)

        else:
            canvas.draw_circle_filled(self.location, self.radius, color=widget_color)
            canvas.draw_icon(self.icon, self.location, self.radius, color=(0.8, 0.8, 0.8, 0.5))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0.0)), self.label,
                color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)


class TouchToggle(object):
    """ A boolean toggle switch. """

    def __init__(
            self,
            action='NONE',
            label='',
            tooltip='',
            location=Vector((0.0, 0.0)),
            icon='NONE'):

        self.hidden = False
        self.modal = False
        self.pre_modal = False
        self.minimal = True

        self.click_time = 0.0

        self.radius = 60.0
        self.location = location
        self.free = False

        self.value = False
        self.value_default = self.value

        self.mouse_start_x = 0

        self.icon = icon
        self.icon_over = icon
        self.icon_down = icon
        self.action = action
        self.action_plus = ''
        self.label = label
        self.tooltip = format_tooltip(tooltip)

        self.hovering = False
        self.touch = False

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius
        spacing = int(self.radius * 2.3333) + 1
        if self.minimal:
            spacing /= 2.5

        return spacing

    def over(self, mouse):
        if self.minimal:
            return (
                (mouse - self.location).length < self.radius * 1.6 and
                abs(mouse[1] - self.location[1]) < self.radius / 2.2
                )

        else:
            return (mouse - self.location).length < self.radius

    def event_touch_down(self, mouse):
        self.touch = self.over(mouse)
        if self.touch:
            self.mouse_start_x = mouse.x
            # pre_modal allows clicking to toggle the value and dragging to actually drag the slider.
            self.pre_modal = True

        return self.touch

    def event_touch_move(self, mouse):
        """ Check if within the button. """
        if self.pre_modal:
            self.modal = True
        if self.modal:
            distance = mouse.x - self.mouse_start_x
            if distance < -50:
                self.value = False
                self.mouse_start_x = mouse.x
                # self.action_plus = 'TOGGLE'
                return True
            if distance > 50:
                self.value = True
                self.mouse_start_x = mouse.x
                # self.action_plus = 'TOGGLE'
                return True
        else:
            self.hovering = self.over(mouse)
            # return self.hovering
            return False

    def event_touch_release(self, mouse):
        if self.touch:
            if not self.modal:
                self.value = not self.value
            self.touch = False
            self.modal = False
            self.pre_modal = False
            return True
        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        if not self.over(mouse):
            return False

        # # Prevent double scroll behavior.
        # if time() - self.click_time < 0.2:
        #     self.click_time = time()
        #     return True
        # self.click_time = time()

        self.value = up_or_down  # not self.value
        return True

    def draw(self):
        """ Draw the toggle widget. """

        if self.hidden:
            return

        else:
            if self.minimal:
                radius_x = self.radius * 1.3
                radius_y = self.radius * 0.42

                canvas.draw_bar(
                    self.location[0] - radius_x,
                    self.location[1],
                    radius_x * 2,
                    r=radius_y,
                    color=(0.0, 0.0, 0.0, 0.7))

                canvas.draw_bar(
                    self.location[0] - radius_x,
                    self.location[1],
                    radius_x * 2,
                    r=radius_y,
                    shrink=0.8 * radius_y,
                    color=(1.0, 1.0, 1.0, 0.1))

                if self.modal:
                    indicator_bar_color = (0.8, 0.8, 0.8, 1.0)
                elif self.hovering:  # Was pre_modal.
                    indicator_bar_color = (0.7, 0.7, 0.7, 1.0)
                else:
                    indicator_bar_color = (0.5, 0.5, 0.5, 1.0)

                if self.value:
                    canvas.draw_bar(
                        self.location[0] + 0.2 * radius_x,
                        self.location[1],
                        radius_x * 0.8,
                        r=radius_y,
                        shrink=int(radius_y * 0.25),
                        color=indicator_bar_color)
                else:
                    canvas.draw_bar(
                        self.location[0] - radius_x,
                        self.location[1],
                        radius_x - 0.2 * self.radius,
                        r=radius_y,
                        shrink=int(radius_y * 0.25),
                        color=indicator_bar_color)

                if self.hovering:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2, 0)), self.label,
                        color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
                else:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2, 0)), self.label,
                        color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)

                if self.modal:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2, self.radius / 1.5)), self.tooltip,
                        color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)
            else:
                canvas.draw_donut(self.location, self.radius, self.radius * 0.0, color=widget_color)
                if self.value:
                    canvas.draw_circle_filled(self.location, self.radius * 0.7, color=(0.8, 0.8, 0.8, 0.5))
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 0.0)), self.label,
                    color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)

            if self.hovering and not self.minimal:
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)


class TouchDragable(object):
    """ """

    def __init__(
            self,
            action='NONE',
            label='',
            tooltip='',
            location=Vector((0.0, 0.0)),
            icon='NONE'):

        self.free = False
        self.hidden = False
        self.modal = False
        self.minimal = False

        self.radius = 60.0
        self.location = location

        self.icon = icon
        self.icon_over = icon
        self.icon_down = icon
        self.action = action
        self.action_plus = ''
        self.label = label
        self.tooltip = format_tooltip(tooltip)

        self.hovering = False
        self.touch = False

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius
        spacing = int(self.radius * 2.3333) + 1
        if self.minimal:
            spacing /= 2.5

        return spacing

    def event_touch_down(self, mouse):
        """ Mouse down. """
        self.touch = (mouse - self.location).length < self.radius
        return self.touch

    def event_touch_move(self, mouse):
        """ Check if within the button. """

        self.hovering = (mouse - self.location).length < self.radius
        return self.hovering

    def event_touch_release(self, mouse):
        """ Mouse up. """
        if self.touch:
            self.touch = False
            if (mouse - self.location).length < self.radius:
                return True
            return False
        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        """ Mouse wheel up or down. """
        return False

    def draw(self):
        """ Draw the draggable widget. """

        if self.hidden:
            return

        if self.touch:
            if self.label != '':
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)
            else:
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 0.0)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
            canvas.draw_icon(self.icon_down, self.location, self.radius * 1.2, color=(0.8, 0.8, 0.8, 1.0))
        elif self.hovering:
            if self.label != '':
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)
            else:
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 0.0)),
                    self.tooltip, color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
            canvas.draw_icon(self.icon_over, self.location, self.radius * 1.0833, color=(0.9, 0.9, 0.9, 1.0))
        else:
            canvas.draw_icon(self.icon, self.location, self.radius, color=(0.8, 0.8, 0.8, 1.0))


class TouchProgress(object):
    """ """

    def __init__(self, action='NONE', label='', tooltip='', location=Vector((0.0, 0.0)), icon='NONE'):

        self.hidden = False
        self.free = False
        self.modal = False
        self.minimal = False

        self.radius = 60.0
        self.location = location

        self.icon = icon
        self.action = action
        self.action_plus = ''
        self.label = label
        self.tooltip = format_tooltip(tooltip)

        self.hovering = False
        self.touch = False

        self.progress = -1.0

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius
        spacing = int(self.radius * 2.3333) + 1
        if self.minimal:
            spacing /= 2.5

        return spacing

    def event_touch_down(self, mouse):
        if (mouse - self.location).length < self.radius:
            self.touch = True
            return True
        else:
            self.touch = False
            return False

    def event_touch_move(self, mouse):
        """ Check if within the button. """

        self.hovering = (mouse - self.location).length < self.radius
        return self.hovering

    def event_touch_release(self, mouse):
        if self.touch:
            self.touch = False
            return (mouse - self.location).length < self.radius

        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        return False

    def draw(self):
        """ Draw the progress widget. """

        if self.hidden and self.progress == 0.0:
            return

        color_white = (1.0, 1.0, 1.0, 1.0)

        if self.touch:
            canvas.draw_circle_filled(self.location, self.radius * 1.0833, color=(1.0, 0.8, 0.4, 0.3))
            canvas.draw_icon(self.icon, self.location, self.radius * 1.0833, color=(0.8, 0.8, 0.8, 1.0))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0.0)), self.label,
                color=color_white, align='RIGHT', radius=self.radius)
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                color=color_white, align='RIGHT', size='small', radius=self.radius)
        elif self.hovering and self.progress == -1.0:
            canvas.draw_circle_filled(self.location, self.radius * 1.033, color=(0.1, 0.1, 0.1, 0.7))
            canvas.draw_icon(self.icon, self.location, self.radius * 1.0833, color=(0.9, 0.9, 0.9, 1.0))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0.0)), self.label,
                color=color_white, align='RIGHT', radius=self.radius)
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                color=color_white, align='RIGHT', size='small', radius=self.radius)
        elif self.progress != -1.0:
            canvas.draw_circle_filled(self.location, self.radius * 0.933, color=(0.4, 0.4, 0.4, 0.8))
            canvas.draw_icon(self.icon, self.location, self.radius, color=color_white)
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0)), self.label,
                color=color_white, align='RIGHT', radius=self.radius)

            r = self.radius
            canvas.draw_donut(self.location, r * 0.933, r * 1.133, color=(1.0, 1.0, 1.0, 0.05), pie_slice=1.0)
            canvas.draw_donut(self.location, r * 0.933, r * 1.133, color=color_white, pie_slice=self.progress)

            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                color=color_white, align='RIGHT', size='small', radius=self.radius)
        else:
            canvas.draw_circle_filled(self.location, self.radius, color=widget_color)
            canvas.draw_icon(self.icon, self.location, self.radius, color=(0.8, 0.8, 0.8, 0.5))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0)), self.label,
                color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)


class TouchSlider(object):
    """ """

    def __init__(
            self,
            action='',
            label='',
            tooltip='',
            location=Vector((0.0, 0.0)),
            icon='NONE',
            value_min=0,
            value_max=100,
            value_default=0,
            rotation=1,
            icon_center='NONE',
            step=0.1,
            step_precision=0.01,
            dots=32,
            digits=1):

        self.hidden = False
        self.free = False
        self.minimal = False

        self.radius = 60.0
        self.location = location

        self.click_time = time()

        self.mouse = location
        self.mouse_start = location

        self.icon = icon
        if icon_center != '':
            self.icon_center = icon_center
        else:
            self.icon_center = self.icon
        self.action = action
        self.action_plus = ''

        self.label = label
        self.tooltip = format_tooltip(tooltip)

        self.hovering = False
        self.touch = False
        self.modal = False
        self.modal_horizontal = False
        self.undecided = False
        self.center = Vector((0, 0))

        self.dots = dots
        self.precision = False

        self.vector_previous = Vector((0, 0))

        self.value_default = value_default
        self.value = self.value_default
        self.value_min = value_min
        self.value_max = value_max
        self.value_max_original = value_max
        self.value_pre_modal = 0.0
        self.overshoot = 0
        self.step = step
        self.step_precision = step_precision
        self.unit = ''
        self.digits = digits

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius
        spacing = int(self.radius * 2.3333) + 1
        if self.minimal:
            spacing /= 2.5

        return spacing

    def over(self, mouse):
        if self.minimal:
            return (
                (mouse - self.location).length < self.radius * 1.6 and
                abs(mouse[1] - self.location[1]) < self.radius / 2.2
                )

        else:
            if (mouse - self.location).length > self.radius:
                return False
            else:
                return True

    def event_touch_down(self, mouse):
        if self.over(mouse):
            if not self.modal:
                self.mouse = mouse * 1.0
                self.mouse_start = mouse * 1.0
                self.click_time = time()
                self.touch = True
                self.modal = True

                if self.minimal:
                    if self.mouse[0] < self.location[0] + self.radius * 0.9:
                        self.modal_horizontal = True
                        self.precision = False
                    self.undecided = True

                self.hovering = False

                self.value_pre_modal = self.value

                self.center = mouse - Vector((130, 0))
                self.previous_rotation = 0.0
                self.rotation = 0.0
                self.overshoot = 0

                self.vector_previous = mouse - self.center

                self.event_touch_move(mouse)  # To update the rotation.
                # bpy.context.window.cursor_modal_set('NONE')
                return True
            else:
                return False
        else:
            self.touch = False
            return False

    def increase_value(self):
        if self.overshoot < 0:
            self.overshoot = 0

        step = self.step * 1
        # step *= self.value_max / self.value_max_original

        if self.precision:
            self.value += self.step_precision
        else:
            # First keep numbers rounded to the step size.
            rest = self.value % step
            if rest > 0.00001 and rest < (step - 0.00001):
                self.value -= rest
            self.value += step

        if self.value > self.value_max:
            self.overshoot += 1
            if self.overshoot < self.dots:
                self.value = self.value_max
            else:
                self.value_max *= 2
                self.overshoot = 0

    def decrease_value(self):
        if self.overshoot > 0:
            self.overshoot = 0

        step = self.step * 1
        # step *= self.value_max / self.value_max_original

        if self.precision:
            self.value -= self.step_precision
        else:
            # First keep numbers rounded to the step size.
            rest = self.value % step
            if rest > 0.00001 and rest < (step - 0.00001):
                self.value -= rest
            else:
                self.value -= step

        if self.value_max > self.value_max_original and self.value < self.value_max_original:
            self.value_max -= step
            if self.value_max < self.value_max_original:
                self.value_max = self.value_max_original

        if self.value < self.value_min:
            self.overshoot -= 1
            self.value = self.value_min

    def event_touch_move(self, mouse):
        """ Check if within the button. """

        self.action_plus = ''

        if self.modal:
            # Horizontal mode.
            if self.modal_horizontal:
                horizontal_travel = mouse[0] - self.mouse[0]
                # Switch to radial mode if the first move is more along the Y-axis.
                if self.undecided:
                    vertical_travel = mouse[1] - self.mouse[1]
                    travel = abs(vertical_travel) + abs(horizontal_travel)
                    if abs(vertical_travel) > (abs(horizontal_travel) * 3) and travel > 10:
                        self.modal_horizontal = False
                        # self.undecided = False
                        self.mouse = mouse * 1.0
                        self.mouse_start = mouse * 1.0
                        self.center = mouse - Vector((130, 0))
                        self.previous_rotation = 0.0
                        self.rotation = 0.0
                        self.vector_previous = mouse - self.center
                        self.event_touch_move(mouse)  # To update the rotation.
                    if abs(mouse.x - self.mouse_start.x) > 15:
                        self.undecided = False
                    return False

                total_steps = (self.value_max - self.value_min) / self.step
                step = (self.radius / 1.0) / total_steps
                step = max(step, 10)
                if self.precision is not (self.mouse_start.y - mouse.y > self.radius * 0.8):
                    self.precision = not self.precision
                    return True
                if horizontal_travel < -step:
                    self.action_plus = '_DECREASE'
                    self.decrease_value()
                    # bpy.context.window.cursor_warp(self.mouse_start.x, self.mouse_start.y)
                    self.mouse = mouse * 1.0
                    return True
                elif horizontal_travel > step:
                    self.action_plus = '_INCREASE'
                    self.increase_value()
                    # bpy.context.window.cursor_warp(self.mouse_start.x, self.mouse_start.y)
                    self.mouse = mouse * 1.0
                    return True
                else:
                    return False

            # Radial mode.
            else:
                self.mouse = mouse
                vector = self.mouse - self.center

                # Center button.
                hovering = vector.length < self.radius * 0.8
                if self.hovering is not hovering:
                    self.hovering = hovering
                    return True
                if self.hovering:
                    return False

                # Used to determine if it's needed to redraw.
                previous_precision = self.precision

                self.precision = vector.length > 250
                dot_angle = 6.283185 / self.dots
                if self.precision:
                    dot_angle = 6.283185 / (self.dots * 4)

                angle_moved = self.vector_previous.angle_signed(vector)
                # dots_moved = int(angle_moved / dot_angle)
                dots_moved = round(angle_moved / dot_angle)

                if angle_moved < -dot_angle * 0.5:
                    self.action_plus = '_DECREASE'
                    self.decrease_value()

                    mat = Matrix.Rotation(-dot_angle * dots_moved, 2)
                    self.vector_previous = mat @ self.vector_previous
                    # self.vector_previous = vector
                    return True
                elif angle_moved > dot_angle * 0.5:
                    self.action_plus = '_INCREASE'
                    self.increase_value()

                    mat = Matrix.Rotation(-dot_angle * dots_moved, 2)
                    self.vector_previous = mat @ self.vector_previous
                    # self.vector_previous = vector
                    return True

                if self.precision is not previous_precision:
                    return True
                else:
                    return False

        else:
            # Only return True when hover state changes, to save redraws and CPU usage.
            self.hovering = self.over(mouse)
            return False

            if self.hovering is not hovering:
                self.hovering = hovering
                return True
            else:
                return False

    def event_touch_release(self, mouse):
        if time() - self.click_time < 0.25:
            self.undecided = False
            self.modal_horizontal = False
            return False

        self.touch = False
        bpy.context.window.cursor_modal_restore()
        if self.modal:
            if not self.modal_horizontal and (mouse - self.center).length < self.radius:
                self.value = self.value_default
                self.value_max = self.value_max_original
                self.action_plus = '_CENTER'
            else:
                self.action_plus = '_CLICK'
            self.modal = False
            self.modal_horizontal = False
            self.precision = False
            return True
        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        if not (self.over(mouse) or self.modal):
            return False

        if up_or_down:
            self.action_plus = '_INCREASE'
            self.increase_value()
        else:
            self.action_plus = '_DECREASE'
            self.decrease_value()
        return True

    def draw(self):
        """ Draw the slider widget. """

        # Used later on for arrow to mouse position drawing.
        center = self.center
        value = self.value

        value_string = '{:.1f}'.format(value)
        if value % 0.1 > 0.005 and value % 0.1 < 0.095 or self.precision:
            value_string = '{:.2f}'.format(value)
        if self.digits == 0:
            value_string = '{:.0f}'.format(value)

        value_default_string = '{:.1f}'.format(self.value_default)
        if self.digits == 0:
            value_default_string = '{:.0f}'.format(self.value_default)

        if self.modal and not self.modal_horizontal:
            # The wheel.
            dots = self.dots
            # draw_precision_dial = self.precision
            draw_precision_dial = True
            if draw_precision_dial:
                dots = self.dots * 4

            distance = (self.mouse - center).length
            distance -= 200  # Start at this radius.
            distance /= 200  # Change this number to get a better transition
            distance = min(distance, 1)
            distance = max(distance, 0)
            alpha = distance
            alpha = alpha ** 2
            # Precision circle.
            alpha2 = alpha

            # This makes the precision dots draw as closely to the current rotation as possible.
            angle_offset = -Vector((1.0, 0.0)).angle_signed(self.vector_previous)

            for i in range(dots + 1):
                angle = (i / dots) * 6.283185
                offset = Vector((cos(angle + angle_offset), sin(angle + angle_offset))) * self.radius * 3
                if draw_precision_dial:
                    offset = Vector((cos(angle + angle_offset), sin(angle + angle_offset))) * 300

                radius = 4
                if i % 4 and not self.dots % 4 or not self.dots == dots:
                    radius = 4
                    # Fade the dots further from the mouse.
                    loc = center + offset
                    dist = (self.mouse - loc).length
                    alpha = dist / 300
                    alpha = min(1.0, alpha)
                    alpha = 1.0 - alpha
                alpha = min(alpha2, alpha)
                color = (1.0, 1.0, 1.0, alpha * 0.7)

                # Draw the closest dot big and bright.
                if self.precision:
                    # if abs(1.0 - self.rotation - (i / dots)) < 1 / (2 * dots):
                    if i == 0:
                        color = (1.0, 1.0, 1.0, 1.0)
                        radius *= 3
                        a = center + offset

                if alpha > 0.01:  # No need to waste time drawing invisible circles.
                    if draw_precision_dial:
                        canvas.draw_circle_filled(center + offset, radius, color=(1.0, 1.0, 1.0, color[3]))

            # canvas.draw_circle_filled(self.location, self.radius - 5.0, color=(0.0, 0.0, 0.0, 0.2))

            if not self.hovering:
                canvas.draw_donut_dial(
                    center, self.radius * 1.2 - 5.0, 0,
                    color=(0.1, 0.1, 0.1, 0.7), width=self.radius / 18.75,
                    rotation=self.rotation * 1.5 * 3.14159, resolution=64)

                if self.icon == 'NONE':
                    canvas.draw_number_text(
                        center, value_string + self.unit,
                        color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size=self.radius * 1.2)

                # Draw a value indicator donut.
                if self.value_max > self.value_min:
                    part = (self.value - self.value_min) / (self.value_max - self.value_min)
                    # Overshoot allows to extend the range.
                    # part_overshoot = self.overshoot / (self.value_max - self.value_min)
                    # part_overshoot = part_overshoot ** 2 * 1.5
                    part_overshoot = self.overshoot / self.dots
                    a = min(0.1, (1 - part) ** 8)
                    canvas.draw_donut(
                        self.center,
                        self.radius * 2 - 2,
                        self.radius * 2 + 2,
                        color=(0.9, 0.9, 0.9, a), pie_slice=1.0)
                    canvas.draw_donut(
                        center,
                        self.radius * 2.0 + (1 * part + self.radius * 0.27),
                        self.radius * 2.0 - (1 * part + self.radius * 0.27),
                        color=(1.0, 1.0, 1.0, 1.0),
                        pie_slice=part,
                        pie_slice_overshoot=part_overshoot)
                    if part < 0.01:
                        canvas.draw_circle_filled(
                            self.center + Vector((0.0, self.radius * 2)), 16, color=(1.0, 1.0, 1.0, 1.0))

            else:
                canvas.draw_circle_filled(center, self.radius * 2.0 - 5.0, color=(0.0, 0.0, 0.0, 0.8))
                if self.icon == 'NONE':
                    canvas.draw_number_text(
                        center, value_default_string,
                        color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size=self.radius * 1.4)

            canvas.draw_icon(self.icon_center, center, self.radius * 1.4 - 5.0, color=(1.0, 1.0, 1.0, 1.0))

            # Test run to get the height.
            width, height = canvas.draw_text(
                self.center + Vector((1.0, 1.0)), self.tooltip,
                color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius, do_not_draw=True)

            canvas.draw_text(
                self.center + Vector((self.radius * 2.0, self.radius * 2.4 + height)), self.tooltip,
                color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)
            canvas.draw_text(
                self.center + Vector((self.radius * 2.0, self.radius * 3.0 + height)), self.label,
                color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)

            # Rotation indicator.
            if not self.hovering:
                radius_1 = 0.9
                radius_2 = 1.1

                rotation = Vector((1.0, 0.0)).angle_signed(self.center - self.mouse) / 6.283185 + 0.5
                quat = Quaternion(Vector((0.0, 0.0, 1.0)), -rotation * 6.283185)
                point_a = quat @ Vector((self.radius * radius_1, 0.0, 0.0))
                point_a = Vector((point_a[0], point_a[1])) + self.center
                point_b = quat @ Vector((self.radius * radius_2, 0.0, 0.0))
                point_b = Vector((point_b[0], point_b[1])) + self.center
                canvas.draw_arrow(point_a, point_b)  # Extra mouse dragging cursor.

        elif self.hovering:
            part = (self.value - self.value_min) / (self.value_max - self.value_min)
            if self.minimal:
                radius_x = self.radius * 1.3
                radius_y = self.radius * 0.42
                canvas.draw_box_rounded(
                    self.location[0] - radius_x, self.location[1] + radius_y, radius_x * 2, radius_y * 2,
                    color=(0.0, 0.0, 0.0, 0.7), r=self.radius * 0.5)
                canvas.draw_box_rounded(
                    self.location[0] - radius_x, self.location[1] + radius_y - 4, radius_x * 2 * part, radius_y * 2 - 8,
                    color=(1.0, 1.0, 1.0, 0.3), r=self.radius * 0.5)
                canvas.draw_text(
                    self.location - Vector((self.radius * 2, 0)), self.label,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', vertical_align=True,
                    radius=self.radius)
                canvas.draw_number_text(
                    self.location, value_string, color=(1.0, 1.0, 1.0, 1.0), size=self.radius, align='CENTER')
                canvas.draw_donut_dial(
                    self.location + Vector((self.radius * 1.28, 0.0)), self.radius * 0.18, self.radius * 0.12,
                    color=(1.0, 1.0, 1.0, 0.8), width=3, resolution=18)
            else:
                canvas.draw_dial(self.location, self.radius * 1.035, color=(0.1, 0.1, 0.1, 0.7), width=self.radius / 18.75)
                canvas.draw_icon(self.icon, self.location, self.radius * 1.0833, color=(0.9, 0.9, 0.9, 1.0))
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 0)), self.label,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)

                if self.value_max > self.value_min:
                    canvas.draw_donut(
                        self.location, self.radius * 0.92, self.radius * 1.24, color=(0.9, 0.9, 0.9, 1.0), pie_slice=part)

                if self.icon == 'NONE':
                    canvas.draw_number_text(
                        self.location, value_string, color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size=self.radius)
        else:
            part = (self.value - self.value_min) / (self.value_max - self.value_min)
            if self.minimal:
                radius_x = self.radius * 1.3
                radius_y = self.radius * 0.42
                canvas.draw_box_rounded(
                    self.location[0] - radius_x, self.location[1] + radius_y, radius_x * 2, radius_y * 2,
                    color=(0.0, 0.0, 0.0, 0.7), r=self.radius * 0.5)
                if self.modal and self.modal_horizontal:
                    canvas.draw_box_rounded(
                        self.location[0] - radius_x,
                        self.location[1] + radius_y * 0.84,
                        radius_x * 2 * part,
                        radius_y * 1.68,
                        color=(1.0, 1.0, 1.0, 0.4),
                        r=self.radius * 0.5)
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2, self.radius / 1.5)), self.tooltip,
                        color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)

                    l = Vector((self.mouse.x - self.mouse.x % (self.radius / 3), self.location.y))
                    if self.precision:
                        rad = self.radius * 0.07
                        canvas.draw_circle_filled(
                            l + Vector((0.0, -self.radius * 1.3)), self.radius * 0.12, color=(1.0, 1.0, 1.0, 0.5))
                        canvas.draw_circle_filled(
                            l + Vector((self.radius / 3, -self.radius * 1.3)), rad, color=(1.0, 1.0, 1.0, 0.1))
                        canvas.draw_circle_filled(
                            l + Vector((-self.radius / 3, -self.radius * 1.3)), rad, color=(1.0, 1.0, 1.0, 0.1))
                        canvas.draw_circle_filled(
                            l + Vector((self.radius / 3 * 2, -self.radius * 1.3)), rad, color=(1.0, 1.0, 1.0, 0.1))
                        canvas.draw_circle_filled(
                            l + Vector((-self.radius / 3 * 2, -self.radius * 1.3)), rad, color=(1.0, 1.0, 1.0, 0.1))
                        canvas.draw_circle_filled(
                            l + Vector((self.radius / 3 * 3, -self.radius * 1.3)), rad, color=(1.0, 1.0, 1.0, 0.05))
                        canvas.draw_circle_filled(
                            l + Vector((-self.radius / 3 * 3, -self.radius * 1.3)), rad, color=(1.0, 1.0, 1.0, 0.05))
                        canvas.draw_circle_filled(
                            l + Vector((self.radius / 3 * 4, -self.radius * 1.3)), rad, color=(1.0, 1.0, 1.0, 0.03))
                        canvas.draw_circle_filled(
                            l + Vector((-self.radius / 3 * 4, -self.radius * 1.3)), rad, color=(1.0, 1.0, 1.0, 0.03))
                else:
                    canvas.draw_box_rounded(
                        self.location[0] - radius_x,
                        self.location[1] + radius_y * 0.84,
                        radius_x * 2 * part,
                        radius_y * 1.68,
                        color=(1.0, 1.0, 1.0, 0.1),
                        r=self.radius * 0.5)

                canvas.draw_text(
                    self.location - Vector((self.radius * 2, 0)), self.label,
                    color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', vertical_align=True,
                    radius=self.radius)
                canvas.draw_number_text(
                    self.location, value_string,
                    color=(1.0, 1.0, 1.0, 0.65), size=self.radius, align='CENTER')
            else:
                # canvas.draw_circle_filled(self.location, self.radius, color=(0.0, 0.0, 0.0, 0.5))
                canvas.draw_dial(self.location, self.radius, color=widget_color, width=self.radius / 18.75)
                canvas.draw_icon(self.icon, self.location, self.radius, color=(0.8, 0.8, 0.8, 0.5))
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 0)), self.label,
                    color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)

                if self.value_max > self.value_min:
                    canvas.draw_donut(self.location, self.radius * 0.96, self.radius * 1.14, color=(0.8, 0.8, 0.8, 1.0), pie_slice=part)

                if self.icon == 'NONE':
                    canvas.draw_number_text(
                        self.location, value_string, color=(1.0, 1.0, 1.0, 0.5), size=self.radius, align='CENTER')


class TouchVector(object):
    """ A joystick controller that can be used for wind direction. """

    def __init__(
            self,
            action='',
            label='',
            tooltip='',
            location=Vector((0.0, 0.0)),
            icon='NONE',
            value_min=0,
            value_max=100,
            vector=Vector((1.0, 0.0)),
            icon_center=''):

        self.hidden = False
        self.free = False
        self.minimal = False

        self.click_time = time()

        self.radius = 60.0
        self.location = location
        self.center = self.location * 1.0

        self.mouse = location

        self.icon = icon
        if icon_center != '':
            self.icon_center = icon_center
        else:
            self.icon_center = self.icon
        self.action = action
        self.action_plus = ''

        self.label = label
        self.tooltip = format_tooltip(tooltip)
        self.rotation_labels = ['Y', 'X', '-Y', '-X']
        self.rotation_icons = None

        self.hovering = False
        self.touch = False
        self.modal = False

        self.mouse_previous = Vector((0.0, 0.0))

        self.rotation = 0.0
        self.previous_rotation = 0.0
        self.dots = 32

        self.vector = vector
        self.vector_pre_modal = self.vector * 1.0
        self.target_vector = vector
        self.previous_vector = vector
        self.do_interpolate = False

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius
        spacing = int(self.radius * 2.3333) + 1
        if self.minimal:
            spacing /= 2.5

        return spacing

    def event_touch_down(self, mouse):
        if (mouse - self.location).length < self.radius:
            if not self.modal:
                self.click_time = time()
            self.touch = True
            self.modal = True

            self.vector_pre_modal = self.vector * 1.0

            # Save the offset. WIP but not worth it I think.
            self.center = mouse - Vector((self.radius * 4.33, 0.0))

            self.hovering = False
            self.event_touch_move(mouse)  # To update the rotation.
            return True
        else:
            self.touch = False
            return False

    def event_touch_move(self, mouse):
        """ Check if within the button. """

        self.mouse = mouse
        self.action_plus = ''

        self.previous_vector = self.vector

        if self.modal:
            self.vector = mouse - self.center

            magnitude = self.vector.length - self.radius
            magnitude /= self.radius * 2

            self.vector = self.vector.normalized() * magnitude

            self.hovering = (mouse - self.center).length < self.radius
            if self.hovering:
                self.vector = Vector((0.0, 0.0))
                return True

            # Try to interpolate.
            if self.do_interpolate:
                self.target_vector = self.vector
                self.vector = 0.2 * self.target_vector + 0.8 * self.previous_vector

            return True

        else:
            # Only return True when hover state changes, to save redraws and CPU usage.
            hovering = (mouse - self.location).length < self.radius
            if self.hovering is not hovering:
                self.hovering = hovering
                return True
            else:
                return False

    def event_touch_release(self, mouse):
        if time() - self.click_time < 0.25:
            return False

        self.touch = False
        bpy.context.window.cursor_modal_restore()
        if self.modal:
            if (mouse - self.center).length < self.radius:
                self.action_plus = '_CENTER'
            else:
                self.action_plus = '_CLICK'
            self.modal = False
            return True
        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        if (mouse - self.location).length < self.radius:
            if up_or_down:
                self.action_plus = '_INCREASE'
                self.vector = (self.vector.length + 0.1) * self.vector.normalized()
            else:
                self.action_plus = '_DECREASE'
                self.vector = (self.vector.length - 0.1) * self.vector.normalized()
            return True
        return False

    def draw(self):
        """ Draw the vector widget. """

        center = self.center

        if self.modal:

            labels_alpha = self.vector.length - 0.5
            if labels_alpha > 1:
                labels_alpha = 1
            labels_alpha *= 0.1

            # Background
            canvas.draw_donut(center, self.radius * 3, self.radius, color=(1.0, 1.0, 1.0, 0.1), pie_slice=1.0)

            magnitude = self.radius + self.vector.length * (self.radius * 2.0)
            pos = center + self.vector.normalized() * magnitude

            # Distance rings.
            distance = (self.mouse - self.center).length
            alpha = distance - self.radius * 4  # Start at this radius.
            alpha = max(alpha, 0)
            alpha /= 200  # Change this number to get a better transition
            alpha = min(alpha, 1)
            alpha = alpha ** 2

            if alpha > 0:
                canvas.draw_donut(
                    center, self.radius * 7, self.radius * 5,
                    color=(1.0, 1.0, 1.0, min(0.07, alpha * 0.5)), pie_slice=1.0)

                alpha = distance - self.radius * 7  # Start at this radius.
                alpha = max(alpha, 0)
                alpha /= 400  # Change this number to get a better transition
                alpha = min(alpha, 1)
                alpha = alpha ** 2

                if alpha > 0:
                    canvas.draw_donut(
                        center, self.radius * 11, self.radius * 9,
                        color=(1.0, 1.0, 1.0, min(0.03, alpha * 0.5)), pie_slice=1.0)

                    alpha = distance - self.radius * 11  # Start at this radius.
                    alpha = max(alpha, 0)
                    alpha /= 600  # Change this number to get a better transition
                    alpha = min(alpha, 1)
                    alpha = alpha ** 2

                    if alpha > 0:
                        canvas.draw_donut(
                            center, self.radius * 15, self.radius * 13,
                            color=(1.0, 1.0, 1.0, min(0.02, alpha * 0.5)), pie_slice=1.0)

            # Dots.
            dots = self.dots

            for i in range(dots):
                angle = (i / dots) * 6.283
                offset = Vector((cos(angle), sin(angle))) * self.radius * 2.5
                radius = 7
                if i % 4 and not self.dots % 4 or not self.dots == dots:
                    radius = 4
                color = (1.0, 1.0, 1.0, 0.8)
                canvas.draw_circle_filled(center + offset, radius, color=color)

            # Inner button.
            if not self.hovering and self.icon == 'NONE':
                canvas.draw_circle_filled(center, self.radius * 1, color=(0.0, 0.0, 0.0, 0.5))
                # canvas.draw_text(
                #     center, '{:.1f}'.format(self.vector.length),
                #     color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size='regular', radius=self.radius)
                canvas.draw_number_text(
                    center, '{:.1f}'.format(self.vector.length),
                    color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size=self.radius * 1.4)
            else:
                canvas.draw_circle_filled(center, self.radius * 1.2, color=(0.0, 0.0, 0.0, 0.3))
                # canvas.draw_text(
                #     center, '{:.1f}'.format(self.vector.length),
                #     color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size='regular', radius=self.radius)
                if not self.vector.length:
                    canvas.draw_circle_filled(pos, 12, color=(1.0, 1.0, 1.0, 1.0))

            canvas.draw_icon(self.icon_center, center, self.radius * 1.4 - 5.0, color=(1.0, 1.0, 1.0, 1.0))

            # Vector
            if self.vector.length > 0.0:
                a = center + self.vector.normalized() * self.radius
                b = pos
                canvas.draw_arrow(a, b)

            # Labels
            rotation = 6.2832 / len(self.rotation_labels)
            for i in range(len(self.rotation_labels)):
                location = self.center + Vector((cos(rotation * i), sin(rotation * i))) * (self.radius * 4.33)
                if self.rotation_icons:
                    canvas.draw_icon(self.rotation_icons[i], location, self.radius * 0.8, color=(1.0, 1.0, 1.0, 0.8))
                else:
                    canvas.draw_text(
                        location, self.rotation_labels[i],
                        color=(1.0, 1.0, 1.0, labels_alpha * 10.0), align='CENTER')

        elif self.hovering:
            canvas.draw_dial(self.location, self.radius * 1.033, color=(0.1, 0.1, 0.1, 0.7))
            canvas.draw_icon(self.icon, self.location, self.radius * 1.0833, color=(0.9, 0.9, 0.9, 1.0))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0)), self.label,
                color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
            if self.label != '':
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)
            else:
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 0)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)

            pos = self.location + self.vector.normalized() * (self.radius * 1.033)
            canvas.draw_circle_filled(pos, 14, color=(1.0, 1.0, 1.0, 1.0))
            if self.vector.length and self.icon == 'NONE':
                # canvas.draw_text(
                #     self.location, '{:.1f}'.format(self.vector.length),
                #     color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size='regular', radius=self.radius)
                canvas.draw_number_text(
                    self.location, '{:.1f}'.format(self.vector.length),
                    color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size=self.radius)

        else:
            canvas.draw_dial(self.location, self.radius, color=widget_color)
            canvas.draw_icon(self.icon, self.location, self.radius, color=(0.8, 0.8, 0.8, 0.5))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0)), self.label,
                color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)

            pos = self.location + self.vector.normalized() * self.radius
            canvas.draw_circle_filled(pos, 12, color=(0.8, 0.8, 0.8, 1.0))
            if self.vector.length and self.icon == 'NONE':
                # canvas.draw_text(
                #     self.location, '{:.1f}'.format(self.vector.length),
                #     color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size='regular', radius=self.radius)
                canvas.draw_number_text(
                    self.location, '{:.1f}'.format(self.vector.length),
                    color=(1.0, 1.0, 1.0, 0.5), align='CENTER', size=self.radius)


class TouchPie(object):
    """ A joystick controller that can be used for wind direction. """

    def __init__(
            self,
            action='',
            slices=[],
            label='',
            tooltip='',
            location=Vector((0.0, 0.0)),
            icon='NONE',
            icon_center='',
            is_enum=True):

        self.hidden = False
        self.free = False
        self.is_enum = is_enum
        self.minimal = False

        self.radius = 60.0
        self.location = location

        self.mouse = location
        self.mouse_start = location
        self.center = location

        self.click_time = time()

        self.icon = icon
        if icon_center != '':
            self.icon_center = icon_center
        else:
            self.icon_center = self.icon
        self.action = action
        self.action_plus = ''

        self.label = label
        self.tooltip = format_tooltip(tooltip)
        self.slices = slices
        self.active_slice = self.slices[0]
        self.active_slice_index = 0
        self.rotation_icons = None

        self.hovering = False
        self.touch = False
        self.modal = False

        self.mouse_previous = Vector((0.0, 0.0))

        self.rotation = 0.0
        self.previous_rotation = 0.0
        self.dots = len(self.slices)
        self.vector = Vector((1.0, 0.0))

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius
        spacing = int(self.radius * 2.3333) + 1
        if self.minimal:
            spacing /= 2.5

        return spacing

    def event_touch_down(self, mouse):
        if not self.modal:
            self.mouse_start = mouse

        if (mouse - self.location).length < self.radius:
            if not self.modal:
                self.click_time = time()
            self.touch = True
            self.modal = True

            # Offset based on where the widget is clicked.
            self.center = mouse - Vector((self.radius * 3.83, -self.radius * 0.5))

            self.hovering = False
            self.event_touch_move(mouse)  # To update the rotation.

            return True
        else:
            self.touch = False
            return False

    def event_touch_move(self, mouse):
        """ Check if within the button. """

        self.mouse = mouse
        self.action_plus = ''

        if self.modal:
            center_radius = self.radius
            self.vector = mouse - self.center

            magnitude = self.vector.length - center_radius
            magnitude /= self.radius * 2

            self.vector = self.vector.normalized() * magnitude

            self.hovering = (mouse - self.center).length < center_radius * 1.0
            if self.hovering:
                self.vector = Vector((0.0, 0.0))
                return True

            # See which pie slice is active.
            self.rotation = Vector((1.0, 0.0)).angle_signed(self.center - mouse) / 6.283185
            self.rotation += 0.5
            self.rotation = 1.0 - self.rotation
            step = 1 / len(self.slices)
            deviation = (self.rotation - step * 0.5) % step - step
            slice_index = int((self.rotation - deviation) / step)
            if slice_index > len(self.slices) - 1:
                slice_index = 0
            # self.active_slice = self.slices[slice_index]
            self.active_slice_index = slice_index

            return True

        else:
            # Only return True when hover state changes, to save redraws and CPU usage.
            hovering = (mouse - self.location).length < self.radius
            if self.hovering is not hovering:
                self.hovering = hovering
                return True
            else:
                return False

    def event_touch_release(self, mouse):
        if (time() - self.click_time < 0.4) and ((self.mouse_start - mouse).length < 40):
            return False

        self.touch = False
        bpy.context.window.cursor_modal_restore()
        if self.modal:
            # if (mouse - (self.location - Vector((260, 0.0)))).length < self.radius:
            if self.vector.length < 0.5:
                self.action_plus = '_CENTER'
            else:
                self.action_plus = ''
                self.active_slice = self.slices[self.active_slice_index]
            self.modal = False
            return True
        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        if (mouse - self.location).length < self.radius:
            if up_or_down:
                self.active_slice_index += 1
                if self.active_slice_index > len(self.slices) - 1:
                    self.active_slice_index = 0
            else:
                self.active_slice_index -= 1
                if self.active_slice_index < 0:
                    self.active_slice_index = len(self.slices) - 1

            self.active_slice = self.slices[self.active_slice_index]
            self.action_plus = ''
            return True
        return False

    def draw(self):
        """ Draw the pie widget. """

        center = self.center

        if self.modal:
            # Background
            # canvas.draw_donut(center, self.radius * 3, self.radius, color=(1.0, 1.0, 1.0, 0.1), pie_slice=1.0)

            # Background
            option = 1
            if option == 1:
                # canvas.draw_donut(center, self.radius * 4.5, self.radius * 2, color=(1.0, 1.0, 1.0, 0.1), pie_slice=1.0)
                canvas.draw_donut(center, self.radius * 4.5, self.radius * 2, color=(0.3, 0.3, 0.3, 1.0), pie_slice=1.0)
                if self.vector.length > 0.5:
                    half_slice_angle = 6.283185 / len(self.slices) * 0.5
                    # Draw the active slice.
                    canvas.draw_donut(
                        center,
                        self.radius * 4.2,
                        self.radius * 2.3,
                        color=(0.4, 0.4, 0.4, 1.0),
                        pie_slice=1 / len(self.slices),
                        rotation=-self.active_slice_index * (2 * half_slice_angle) - half_slice_angle + 0.5 * 3.1415)
            if option == 2:
                canvas.draw_dial(
                    center, self.radius * 6, color=(1.0, 1.0, 1.0, 0.3), width=128,
                    pie=True, number_of_petals=len(self.slices))
                rotation = 6.2832 / len(self.slices)
                location = \
                    self.center + \
                    Vector((cos(rotation * self.active_slice_index), sin(rotation * self.active_slice_index))) * \
                    self.radius * 3.2
                canvas.draw_circle_filled(location, self.radius * 2, color=(0.0, 0.0, 0.0, 0.4))

            magnitude = self.radius + self.vector.length * (self.radius * 2.0)
            pos = center + self.vector.normalized() * magnitude

            a = 0.2 - self.vector.length
            if a < 0.0:
                a = 0.0
            a *= 0.2
            radius = a * 32 * self.radius
            radius = min(radius, self.radius * 1.2)
            canvas.draw_circle_filled(self.center, radius, color=(0.4, 0.4, 0.4, 1.0))

            # Inner button.
            if not self.hovering and self.icon == 'NONE':
                canvas.draw_circle_filled(center, self.radius * 3, color=(0.0, 0.0, 0.0, 0.5))
                canvas.draw_text(
                    center, self.active_slice, color=(1.0, 1.0, 1.0, 1.0),
                    align='CENTER', size='regular', radius=self.radius)
            else:
                # canvas.draw_circle_filled(center, self.radius * 1.2, color=(0.0, 0.0, 0.0, 0.3))
                # canvas.draw_text(
                #     center.copy(), '{:.1f}'.format(self.vector.length),
                #     color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size='regular')
                # if not self.vector.length:
                if self.vector.length < 0.4:
                    canvas.draw_circle_filled(pos, 12, color=(1.0, 1.0, 1.0, 1.0))

            # canvas.draw_icon(self.icon_center, center, self.radius * 1.4 - 5.0, color=(1.0,1.0, 1.0, 1.0))
            # canvas.draw_text(
            #     self.location - Vector((130.0, -220.0)), self.label,
            #     color=(1.0, 1.0, 1.0, 1.0), align='CENTER', radius=self.radius)

            # Labels
            rotation = 6.2832 / len(self.slices)
            for i in range(len(self.slices)):
                location = self.center + Vector((cos(rotation * i), sin(rotation * i))) * self.radius * 3.2
                if self.rotation_icons:
                    canvas.draw_icon(self.rotation_icons[i], location, self.radius * 0.8, color=(1.0, 1.0, 1.0, 0.8))
                else:
                    canvas.draw_text(location, self.slices[i], color=(1.0, 1.0, 1.0, 1.0), align='CENTER', radius=self.radius)

            canvas.draw_text(
                self.center + Vector((self.radius * 0.5, self.radius * 6.2)), self.label,
                color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)
            canvas.draw_text(
                self.center + Vector((self.radius * 0.5, self.radius * 5.5)), self.tooltip,
                color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)

        elif self.hovering:
            if self.minimal:
                radius_x = self.radius * 1.3
                radius_y = self.radius * 0.42
                canvas.draw_box_rounded(
                    self.location[0] - radius_x, self.location[1] + radius_y, radius_x * 2, radius_y * 2,
                    color=(0.0, 0.0, 0.0, 0.7), r=self.radius * 0.5)
                canvas.draw_text(
                    self.location - Vector((self.radius * 2, 0)), self.label,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
                canvas.draw_text(
                    self.location, self.active_slice,
                    color=(1.0, 1.0, 1.0, 1.0), align='CENTER', radius=self.radius)
            else:
                canvas.draw_dial(self.location, self.radius * 1.1, color=(0.1, 0.1, 0.1, 0.7), width=8, pie=True)
                canvas.draw_icon(self.icon, self.location, self.radius * 1.0833, color=(0.9, 0.9, 0.9, 1.0))
                if self.is_enum:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, 0)), self.label + ': ' + self.active_slice,
                        color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)
                else:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, 0)), self.label,
                        color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)

                if self.label != '':
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                        color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)
                else:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, 0)), self.tooltip,
                        color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)

                if self.vector.length and self.icon == 'NONE':
                    canvas.draw_text(
                        self.location, '{:.1f}'.format(self.vector.length), color=(1.0, 1.0, 1.0, 1.0),
                        align='CENTER', size='regular', radius=self.radius)

        else:
            if self.minimal:
                radius_x = self.radius * 1.3
                radius_y = self.radius * 0.42
                canvas.draw_box_rounded(
                    self.location[0] - radius_x, self.location[1] + radius_y, radius_x * 2, radius_y * 2,
                    color=(0.0, 0.0, 0.0, 0.7), r=self.radius * 0.5)
                canvas.draw_text(
                    self.location - Vector((self.radius * 2, 0)), self.label,
                    color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)
                canvas.draw_text(
                    self.location, self.active_slice,
                    color=(1.0, 1.0, 1.0, 0.7), align='CENTER', radius=self.radius)
            else:
                canvas.draw_dial(self.location, self.radius * 1.05, color=widget_color, width=8, pie=True)
                canvas.draw_icon(self.icon, self.location, self.radius, color=(0.8, 0.8, 0.8, 0.5))
                if self.is_enum:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, 0)), self.label + ': ' + self.active_slice,
                        color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)
                    # canvas.draw_text(
                    #     self.location - Vector((self.radius * 2.0, 0)),
                    #     elf.label + ': ' + self.slices[self.active_slice_index],
                    #     color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)
                else:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, 0)), self.label,
                        color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)

                if self.vector.length and self.icon == 'NONE':
                    canvas.draw_text(
                        self.location, '{:.1f}'.format(self.vector.length),
                        color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size='regular', radius=self.radius)


class TouchWidePie(object):
    """ A joystick controller that can be used for wind direction. """

    def __init__(
            self,
            action='',
            slices=[],
            label='',
            tooltip='',
            location=Vector((0.0, 0.0)),
            icon='NONE',
            min=0,
            max=100,
            vector=Vector((1.0, 0.0)),
            icon_center='',
            is_enum=True):

        self.hidden = False
        self.free = False
        self.is_enum = is_enum
        self.minimal = False

        self.radius = 60.0
        self.location = location

        self.mouse = location
        self.mouse_start = location
        self.center = location

        self.click_time = time()

        self.icon = icon
        if icon_center != '':
            self.icon_center = icon_center
        else:
            self.icon_center = self.icon
        self.action = action
        self.action_plus = ''

        self.label = label
        self.tooltip = format_tooltip(tooltip)
        self.slices = slices
        self.active_slice = self.slices[0]
        self.active_slice_index = 0
        self.rotation_icons = None

        self.hovering = False
        self.touch = False
        self.modal = False

        self.mouse_previous = Vector((0.0, 0.0))

        self.rotation = 0.0
        self.previous_rotation = 0.0
        self.dots = 32

        self.vector = vector
        self.hasntmoved = True

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius
        spacing = int(self.radius * 2.3333) + 1
        if self.minimal:
            spacing /= 2.5

        return spacing

    def event_touch_down(self, mouse):
        if not self.modal:
            self.mouse_start = mouse * 1.0
            self.hasntmoved = True

        if (mouse - self.location).length < self.radius:
            if not self.modal:
                self.click_time = time()
            self.touch = True
            self.modal = True

            # Offset based on where the widget is clicked.
            # self.center = mouse - Vector((230, -30))
            self.center = mouse - Vector((self.radius * 3.83, -self.radius * 2))
            self.center = self.location - Vector((self.radius * 2.8, -self.radius * 1))
            self.hovering = False
            self.event_touch_move(mouse)  # To update the rotation.

            return True
        else:
            self.touch = False
            return False

    def event_touch_move(self, mouse):
        """ Check if within the button. """

        self.mouse = mouse
        self.action_plus = ''

        if self.modal:
            if (self.mouse_start - mouse).length < 40:
                return False
            self.hasntmoved = False

            center_radius = self.radius
            self.vector = mouse - self.center

            magnitude = self.vector.length - center_radius
            magnitude /= self.radius * 2

            self.vector = self.vector.normalized() * magnitude

            self.hovering = (mouse - self.center).length < center_radius * 2.0
            if self.hovering:
                self.vector = Vector((0.0, 0.0))
                return True

            # See which pie slice is active.
            self.rotation = Vector((1.0, 0.0)).angle_signed(self.center - mouse) / 6.283185
            self.rotation += 0.5
            self.rotation = 1.0 - self.rotation
            step = 1 / len(self.slices)
            deviation = (self.rotation - step * 0.5) % step - step
            slice_index = int((self.rotation - deviation) / step)
            if slice_index > len(self.slices) - 1:
                slice_index = 0
            # self.active_slice = self.slices[slice_index]
            self.active_slice_index = slice_index

            return True

        else:
            # Only return True when hover state changes, to save redraws and CPU usage.
            hovering = (mouse - self.location).length < self.radius
            if self.hovering is not hovering:
                self.hovering = hovering
                return True
            else:
                return False

    def event_touch_release(self, mouse):
        if (time() - self.click_time < 0.4) and ((self.mouse_start - mouse).length < 40):
            return False

        self.touch = False
        bpy.context.window.cursor_modal_restore()
        if self.modal:
            # if (mouse - (self.location - Vector((260, 0.0)))).length < self.radius:
            if self.vector.length < 0.5:
                self.action_plus = '_CENTER'
            else:
                self.action_plus = ''
                self.active_slice = self.slices[self.active_slice_index]
            self.modal = False
            return True
        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        if (mouse - self.location).length < self.radius:
            if up_or_down:
                self.active_slice_index += 1
                if self.active_slice_index > len(self.slices) - 1:
                    self.active_slice_index = 0
            else:
                self.active_slice_index -= 1
                if self.active_slice_index < 0:
                    self.active_slice_index = len(self.slices) - 1

            self.active_slice = self.slices[self.active_slice_index]
            self.action_plus = ''
            return True
        return False

    def draw(self):
        """ Draw the pie widget. """

        center = self.center

        if self.modal:
            # Background
            # canvas.draw_donut(center, self.radius * 3, self.radius, color=(1.0, 1.0, 1.0, 0.1), pie_slice=1.0)

            # Background
            option = 1
            if option == 1:
                # canvas.draw_donut(center, self.radius * 5.4, self.radius * 4.5, color=(0.3, 0.3, 0.3, 0.3), pie_slice=1.0)
                canvas.draw_donut(center, self.radius * 4.5, self.radius * 2.0, color=(0.3, 0.3, 0.3, 0.3), pie_slice=1.0)
                if self.vector.length > 0.5 and not self.hasntmoved:
                    half_slice_angle = 6.283185 / len(self.slices) * 0.5
                    # Draw the active slice.
                    canvas.draw_donut(
                        center, self.radius * 5.0, self.radius * 4.5,
                        color=(1.0, 1.0, 1.0, 1.0), pie_slice=1 / len(self.slices),
                        rotation=-self.active_slice_index * (2 * half_slice_angle) - half_slice_angle + 0.5 * 3.1415)
            if option == 2:
                canvas.draw_dial(
                    center, self.radius * 6, color=(1.0, 1.0, 1.0, 0.3),
                    width=128, pie=True, number_of_petals=len(self.slices))
                rotation = 6.2832 / len(self.slices)
                location = (
                    self.center +
                    Vector((cos(rotation * self.active_slice_index), sin(rotation * self.active_slice_index))) *
                    self.radius * 3.2)
                canvas.draw_circle_filled(location, self.radius * 2, color=(0.0, 0.0, 0.0, 0.4))

            if self.vector.length < 0.4:
                canvas.draw_donut(center, self.radius * 1.8, self.radius * 1.4, color=(1.0, 1.0, 1.0, 1.0), pie_slice=1.0)

            # Labels
            rotation = 6.2832 / len(self.slices)
            for i in range(len(self.slices)):
                location = self.center + Vector((cos(rotation * i), sin(rotation * i))) * self.radius * 3.2
                if self.rotation_icons:
                    canvas.draw_icon(self.rotation_icons[i], location, self.radius * 0.8, color=(1.0, 1.0, 1.0, 0.8))
                else:
                    canvas.draw_text(location, self.slices[i], color=(1.0, 1.0, 1.0, 1.0), align='CENTER', radius=self.radius)

        elif self.hovering:
            if self.minimal:
                radius_x = self.radius * 1.3
                radius_y = self.radius * 0.42
                canvas.draw_box_rounded(
                    self.location[0] - radius_x, self.location[1] + radius_y, radius_x * 2, radius_y * 2,
                    color=(0.0, 0.0, 0.0, 0.7), r=self.radius * 0.5)
                canvas.draw_text(
                    self.location - Vector((self.radius * 2, 0)), self.label,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
                canvas.draw_text(
                    self.location, self.active_slice,
                    color=(1.0, 1.0, 1.0, 1.0), align='CENTER', radius=self.radius)
            else:
                canvas.draw_dial(self.location, self.radius * 1.1, color=(0.1, 0.1, 0.1, 0.7), width=8, pie=True)
                canvas.draw_icon(self.icon, self.location, self.radius * 1.0833, color=(0.9, 0.9, 0.9, 1.0))
                if self.is_enum:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, 0)), self.label + ': ' + self.active_slice,
                        color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)
                else:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, 0)), self.label,
                        color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)

                if self.label != '':
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                        color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)
                else:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, 0)), self.tooltip,
                        color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)

                if self.vector.length and self.icon == 'NONE':
                    canvas.draw_text(
                        self.location, '{:.1f}'.format(self.vector.length),
                        color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size='regular', radius=self.radius)

        else:
            if self.minimal:
                radius_x = self.radius * 1.3
                radius_y = self.radius * 0.42
                canvas.draw_box_rounded(
                    self.location[0] - radius_x, self.location[1] + radius_y, radius_x * 2, radius_y * 2,
                    color=(0.0, 0.0, 0.0, 0.7), r=self.radius * 0.5)
                canvas.draw_text(
                    self.location - Vector((self.radius * 2, 0)), self.label,
                    color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)
                canvas.draw_text(
                    self.location, self.active_slice,
                    color=(1.0, 1.0, 1.0, 0.7), align='CENTER', radius=self.radius)
            else:
                canvas.draw_dial(self.location, self.radius * 1.05, color=widget_color, width=8, pie=True)
                canvas.draw_icon(self.icon, self.location, self.radius, color=(0.8, 0.8, 0.8, 0.5))
                if self.is_enum:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, 0)),
                        self.label + ': ' + self.active_slice,
                        color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)
                else:
                    canvas.draw_text(
                        self.location - Vector((self.radius * 2.0, 0)), self.label,
                        color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)

                if self.vector.length and self.icon == 'NONE':
                    canvas.draw_text(
                        self.location, '{:.1f}'.format(self.vector.length),
                        color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size='regular', radius=self.radius)


class TouchTurntable(object):
    """ Same as TouchVector, but with modifications to make it specific for driving the viewport camera. """

    def __init__(
            self,
            action='',
            label='',
            rotation_labels=[],
            tooltip='',
            location=Vector((0.0, 0.0)),
            icon='NONE',
            vector=Vector((1.0, 0.0)),
            icon_center=''):

        self.hidden = False
        self.free = False
        self.minimal = False

        self.scale_figure_alpha = 0.0

        self.radius = 60.0
        self.location = location
        self.center = self.location - Vector((self.radius * 3.88, 0.0))

        self.mouse = location
        self.click_time = time()

        self.icon = icon
        if icon_center != '':
            self.icon_center = icon_center
        else:
            self.icon_center = self.icon
        self.action = action
        self.action_plus = ''

        self.label = label
        self.tooltip = format_tooltip(tooltip)
        self.rotation_labels = rotation_labels

        self.hovering = False
        self.touch = False
        self.modal = False

        self.mouse_previous = Vector((0.0, 0.0))

        self.rotation = 0.0
        self.previous_rotation = 0.0
        self.dots = 32

        self.vector = vector
        self.target_vector = vector
        self.previous_vector = vector
        self.do_interpolate = True
        self.do_interpolate_initial = True

        self.rotation_offset = 0.0
        self.vector_offset = vector

    def get_height(self, radius):
        """ The vertical space of this widget in pixels. """

        self.radius = radius
        spacing = int(self.radius * 2.3333) + 1
        if self.minimal:
            spacing /= 2.5

        return spacing

    def event_touch_down(self, mouse):
        if (mouse - self.location).length < self.radius:
            if not self.modal:
                self.click_time = time()
            self.touch = True
            self.modal = True
            self.center = mouse - Vector((self.radius * 3.88, 0.0))
            magnitude = self.vector.length
            self.scale_figure_alpha = 0.0
            self.vector = Vector((1.0, 0.0)) * magnitude
            self.target_vector = Vector((1.0, 0.0))
            self.hovering = False
            self.do_interpolate = False
            self.do_interpolate_initial = False
            return True
        else:
            self.touch = False
            return False

    def event_touch_move(self, mouse):
        """ Check if within the button. """

        self.action_plus = ''

        if self.modal:
            self.mouse = mouse
            self.previous_vector = self.vector
            center = self.center
            center_radius = self.radius * 0.5
            self.vector = mouse - center

            magnitude = self.vector.length - center_radius
            magnitude /= self.radius * 2.5
            magnitude = abs(magnitude)

            self.vector = self.vector.normalized() * magnitude

            self.hovering = (mouse - center).length < center_radius

            # Try to interpolate.
            # Interpolate near the center. The precision is very rough in there,
            # causing navigation to become jittery. Interpolation will make it buttery smooth.
            # Improved this interpolation by rotating instead of passing through the center.

            # if self.vector.length < 1.2:
            self.do_interpolate = True

            speed = 0.2
            speed = min(0.2, self.target_vector.length / 3)
            speed = speed ** 0.6
            if self.do_interpolate_initial:
                # Slower initial interpolation speed so you know where the view is coming from.
                speed = 0.2
            speed *= 1.0

            self.target_vector = self.vector
            length = (speed * self.target_vector).length + ((1.0 - speed) * self.previous_vector).length
            self.vector = self.previous_vector.slerp(self.target_vector, speed, self.vector) * length

            if (self.target_vector - self.vector).length < 0.05 and self.target_vector.angle(self.vector, 0.0) < 0.01:
                # Below line would be perfect, but that gives a little pop at the end of the interpolation.
                # So skip it - it's close enough to the target vector.
                # self.vector = self.target_vector
                self.do_interpolate = False
                self.do_interpolate_initial = False

            return True

        else:
            # Only return True when hover state changes, to save redraws and CPU usage.
            hovering = (mouse - self.location).length < self.radius
            if self.hovering is not hovering:
                self.hovering = hovering
                return True
            else:
                return False

    def event_touch_release(self, mouse):
        self.touch = False
        bpy.context.window.cursor_modal_restore()
        if self.modal:
            if (mouse - self.center).length < self.radius:
                self.action_plus = '_CENTER'
            else:
                self.action_plus = '_CLICK'

            # Keep modal when clicking the widget, no need to keep the button down and straining your hand.
            if time() - self.click_time > 0.25:
                self.modal = False

            return True
        return False

    def event_mouse_wheel(self, mouse, up_or_down):
        if (mouse - self.location).length < self.radius:
            angle = 3.1415 * 0.1
            if up_or_down:
                angle = -angle

            self.vector = Quaternion(Vector((0.0, 0.0, 1.0)), angle) @ Vector((self.vector[0], self.vector[1], 0.0))
            self.vector = Vector((self.vector[0], self.vector[1]))

            # if up_or_down:
            #     self.vector *= 0.9
            # else:
            #     self.vector *= 1.1

            return True
        return False

    def draw(self):
        """ Draw the turntable widget. """

        center = self.center

        if self.modal:
            self.scale_figure_alpha += 0.05
            if self.scale_figure_alpha > 0.8:
                self.scale_figure_alpha = 0.8
            alpha_multiplier = self.scale_figure_alpha - 0.0
            if alpha_multiplier < 0.0:
                alpha_multiplier = 0.0
            canvas.draw_scale_figure(alpha_multiplier=alpha_multiplier)

            turntable_alpha = self.vector.length - 0.5
            if self.vector.length > 1:
                turntable_alpha = 2.5 - self.vector.length
            turntable_alpha *= 0.1

            magnitude = self.radius + self.vector.length * (self.radius * 2.0)
            pos = center + self.vector.normalized() * magnitude

            # Vector
            if self.vector.length > 0.0:
                a = center + self.vector.normalized() * self.radius
                b = pos
                canvas.draw_arrow(a, b)

            # Labels
            if self.rotation_labels:
                rotation = 6.2832 / len(self.rotation_labels)
                for i in range(len(self.rotation_labels)):
                    location = center + Vector((cos(rotation * i), sin(rotation * i))) * self.radius * 3.7
                    canvas.draw_text(
                        location, self.rotation_labels[i],
                        color=(1.0, 1.0, 1.0, turntable_alpha * 5), align='CENTER', shadow=False, radius=self.radius)

            # Big circle when moving toward the center.
            c = self.target_vector.length
            e = 1.71828
            c = 1 - 1 / (1 + e**(-20 * c + 15))
            canvas.draw_circle_filled(center, (c * 1.2 * self.radius), color=(1.0, 1.0, 1.0, c * 0.2))

            # Biggest circle when moving out toward the highest zoom.
            a = self.vector.length
            e = 1.71828
            a = 1 / (1 + e**(-20 * a + 45))
            alpha_biggest = a ** 5 * 0.15
            canvas.draw_donut(
                center, 7 + (9 - a) * self.radius, a * 7.8 * self.radius,
                color=(1.0, 1.0, 1.0, alpha_biggest), pie_slice=1.0)

            o = self.vector.length
            e = 1.71828
            o = 1 / (1 + e**(-20 * o + 10))
            canvas.draw_donut(
                center, (4.3 - o) * self.radius, o * 3 * self.radius,
                color=(1.0, 1.0, 1.0, o ** 5 * 0.15 - alpha_biggest), pie_slice=1.0)

        elif self.hovering:
            canvas.draw_dial(self.location, self.radius * 1.033, color=(0.1, 0.1, 0.1, 0.7))
            canvas.draw_icon(self.icon, self.location, self.radius * 1.0833, color=(0.9, 0.9, 0.9, 1.0))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0)), self.label,
                color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)
            if self.label != '':
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, self.radius * 0.66)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', size='small', radius=self.radius)
            else:
                canvas.draw_text(
                    self.location - Vector((self.radius * 2.0, 0)), self.tooltip,
                    color=(1.0, 1.0, 1.0, 1.0), align='RIGHT', radius=self.radius)

            pos = self.location + self.vector.normalized() * (self.radius * 1.033)
            canvas.draw_circle_filled(pos, self.radius / 5, color=(1.0, 1.0, 1.0, 1.0))
            if self.vector.length and self.icon == 'NONE':
                canvas.draw_text(
                    self.location, '{:.1f}'.format(self.vector.length),
                    color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size='regular', radius=self.radius)

        else:
            canvas.draw_dial(self.location, self.radius, color=widget_color)
            canvas.draw_icon(self.icon, self.location, self.radius, color=(0.8, 0.8, 0.8, 0.5))
            canvas.draw_text(
                self.location - Vector((self.radius * 2.0, 0)), self.label,
                color=(1.0, 1.0, 1.0, 0.7), align='RIGHT', radius=self.radius)

            pos = self.location + self.vector.normalized() * self.radius
            canvas.draw_circle_filled(pos, self.radius / 5, color=(0.8, 0.8, 0.8, 1.0))
            if self.vector.length and self.icon == 'NONE':
                canvas.draw_text(
                    self.location, '{:.1f}'.format(self.vector.length),
                    color=(1.0, 1.0, 1.0, 1.0), align='CENTER', size='regular', radius=self.radius)
