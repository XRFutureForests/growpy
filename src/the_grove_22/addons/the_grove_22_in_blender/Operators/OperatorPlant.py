
""" Plant groups of trees in a variety of layouts.
    Create orchards, plantations, hedgerows, a ring or clump of trees.
    Or create a larger and more natural grove with islands of trees.

    This tool creates empty objects that are converted to trees when restarting your grove.

    Copyright 2021 - 2025, Wybren van Keulen, The Grove """


import bpy
from mathutils import Vector, Quaternion
from bpy_extras.view3d_utils import location_3d_to_region_2d

from ..Languages.Translation import t
from ..Interface.Interface import Interface, TouchPanel, TouchButton, TouchPie, TouchSlider, TouchToggle, stop_animation_playback
from ..Interface.Canvas import Canvas
from .OperatorBuild import clean_grove
from ..File import load_grove

from ..Core import import_core
the_grove_core = import_core()


class Placeholder():

    def __init__(self, location, direction):
        self.location = location
        self.direction = direction
        self.delay = 0


def draw_2d(self, context):
    """ Draw the interface and placeholder lines in the active 3D view. """

    # Prevent drawing in other 3D views.
    if self.space_data != context.space_data:
        return

    region = context.region
    region_data = context.region_data
    path_2d = []
    thicknesses = []
    for line in self.lines:
        path_2d.append([
            location_3d_to_region_2d(region, region_data, line[0], default=Vector((0.0, 0.0))),
            location_3d_to_region_2d(region, region_data, line[1], default=Vector((0.0, 0.0)))])
        thicknesses.append([0.8, 0.6])

    self.canvas.draw_thick_lines(path_2d, thickness=15, thicknesses=thicknesses, color=(1.0, 0.9, 0.4, 0.45))

    self.interface.draw()


def add_single_placeholder():
    context = bpy.context

    bpy.ops.object.empty_add(type="SINGLE_ARROW", location=Vector((0.0, 0.0, 0.0)))
    new_empty = context.selected_objects[-1]
    new_empty.name = 'Placeholder'
    new_empty['grove_delay'] = 0
    new_empty.empty_display_size = 0.5

    return new_empty


def project_placeholder_to_terrain(location=Vector((0.0, 0.0, 0.0)), slant=0.0, normal=Vector((0.0, 0.0, 1.0))):
    """ Drop the trees down onto scene objects. """

    tree_normal = normal * 1.0
    original_magnitude = tree_normal.length
    depsgraph = bpy.context.evaluated_depsgraph_get()
    ray_cast = bpy.context.scene.ray_cast

    # Cast a ray from 1km high down on the scene.
    result = ray_cast(depsgraph, location + Vector((0.0, 0.0, 1000.0)), Vector((0.0, 0.0, -1.0)))
    if result[0]:
        location.z += result[1].z
        tree_normal = (1.0 - slant) * normal + slant * result[2]

    tree_normal = tree_normal.normalized() * original_magnitude

    return location, tree_normal


def plant(self):
    """ Plant the trees by creating placeholder objects in the chosen arrangement. """

    layout = self.layout_pie.active_slice
    if layout == t('plant_layout_clump'):
        positions = the_grove_core.tree_math.plant_clump(
            int(self.clump_trees_dial.value),
            self.clump_space_dial.value,
            0.0
        )

    elif layout == t('plant_layout_islands'):
        positions = the_grove_core.tree_math.plant_islands(
            int(self.islands_dial.value),
            self.islands_space_dial.value,
            int(self.islands_trees_dial.value),
            self.islands_trees_space_dial.value,
            self.islands_randomize_dial.value,
            self.random_shift_dial.value,
            self.islands_clearing_dial.value,
            self.random_seed.value
        )

    elif layout == t('plant_layout_ring'):
        positions = the_grove_core.tree_math.plant_ring(
            int(self.ring_trees_dial.value),
            self.ring_radius_dial.value
        )

    elif layout == t('plant_layout_rows'):
        positions = the_grove_core.tree_math.plant_rows(
            int(self.rows_trees_dial.value),
            self.rows_space_dial.value,
            int(self.rows_rows_dial.value),
            self.rows_rows_space_dial.value,
            self.rows_diagonal_toggle.value)

    (positions, directions, delays) = the_grove_core.tree_math.add_variation(
        positions,
        self.random_shift_dial.value,
        self.diverge_dial.value,
        self.delay_dial.value,
        self.random_seed.value
    )

    self.placeholders = []

    for i in range(len(positions)):
        location = Vector((positions[i].x, positions[i].y, positions[i].z))
        direction = Vector((directions[i].x, directions[i].y, directions[i].z))

        self.placeholders.append(Placeholder(location, direction))
        self.placeholders[i].delay = delays[i]

    # Terrain
    if self.terrain_drop_toggle.value:
        for placeholder in self.placeholders:
            placeholder.location, placeholder.direction = project_placeholder_to_terrain(
                location=placeholder.location, slant=self.terrain_slope_dial.value)

    # Convert placeholders to lines for the viewport preview.
    self.lines = []
    for placeholder in self.placeholders:
        self.lines.append([
            placeholder.location,
            placeholder.location + 0.7 * placeholder.direction * (1.0 + (self.delay_dial.value - placeholder.delay) / 3)])


def delete_existing_empties():
    """ Remove all placeholders to make room for new ones."""

    grove_collection = bpy.context.collection

    empties = []
    for obj in grove_collection.objects:
        if obj.type == 'EMPTY':
            empties.append(obj)

    for empty in empties:
        grove_collection.objects.unlink(empty)
        bpy.data.objects.remove(empty)


def create_empties(placeholders):
    """ Create an empty object for each placeholder. """

    grove_collection = bpy.context.collection

    delete_existing_empties()

    for placeholder in placeholders:
        empty = bpy.data.objects.new('Placeholder', None)
        empty.empty_display_type = "SINGLE_ARROW"
        empty.empty_display_size = 0.5
        empty.location = placeholder.location

        direction_vector = placeholder.direction
        flat_vector = Vector((direction_vector[0], direction_vector[1], 0.0))
        angle = 1.57 - flat_vector.angle(direction_vector, 1.57)
        axis = direction_vector.cross(Vector((0.0, 0.0, 1.0)))

        empty.rotation_euler = Quaternion(-axis, angle).to_euler()
        grove_collection.objects.link(empty)
        empty.select_set(True)
        empty['grove_delay'] = int(placeholder.delay)


def recreate_empties():
    """ After importing trees from a file, the empty object placeholders they were grown from are not there yet.
        So create new placeholder empty objects at the base of each tree. """

    grove = load_grove(bpy.context.collection)
    if not grove:
        return

    placeholders = []

    (positions, directions) = grove.get_tree_positions_and_directions()

    scale = bpy.context.collection.GROVE22_Properties.simulation_scale

    for i, position in enumerate(positions):
        direction = directions[i]
        direction_v = Vector((direction.x, direction.y, direction.z))
        position_v = Vector((position.x, position.y, position.z)) * scale
        placeholders.append(Placeholder(position_v, direction_v))
        placeholders[-1].delay = 0

    create_empties(placeholders)


def update_interface(self):
    """ Hide all widgets and then show the ones for the selected layout type. """

    layout = self.layout_pie.active_slice

    self.clump_panel.hidden = (layout != t('plant_layout_clump'))
    self.rows_panel.hidden = (layout != t('plant_layout_rows'))
    self.ring_panel.hidden = (layout != t('plant_layout_ring'))
    self.islands_panel.hidden = (layout != t('plant_layout_islands'))

    self.interface.update()
    plant(self)


def status_text_callback(header, _):
    """ Fill the status bar with keyboard and mouse shortcuts. """
    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')


class GROVE22_OT_Plant(bpy.types.Operator):

    bl_idname = "the_grove_22.plant"
    bl_label = t('plant')
    bl_description = t('plant_tt')
    bl_options = {'REGISTER', 'UNDO'}

    _handle_draw_2d = None
    canvas = Canvas()

    # Setup the interface. Class-wide, not per class instance like in __init__. This will make each instance
    # of the tool keep the set parameters and remember which tips have been clicked away.

    interface = Interface()

    interface.widgets.append(
        TouchButton(action='Back', label=t('close_button'), tooltip=t('close_button_tt'), icon='CHECKMARK'))

    interface.add_spacer()

    layout_pie = TouchPie(
        action='layout_pie', label=t('plant_layout'),
        slices=[t('plant_layout_clump'), t('plant_layout_rows'), t('plant_layout_ring'), t('plant_layout_islands')],
        tooltip=t('plant_layout_tt'),
        icon='PATTERN',
        is_enum=True)

    interface.add_spacer()

    # Islands widgets
    islands_panel = TouchPanel(label=t('plant_islands'))

    islands_randomize_dial = TouchSlider(
        action='islands_randomize', label=t('plant_islands_randomize'), tooltip=t('plant_islands_randomize_tt'),
        value_min=0.0, value_max=1.0, value_default=0.5,
        step=0.1, step_precision=0.01, dots=24, digits=1)

    islands_clearing_dial = TouchSlider(
        action='Islandsspace', label=t('plant_islands_clearing'), tooltip=t('plant_islands_clearing_tt'),
        value_min=0.0, value_max=1.0, value_default=0.0,
        step=0.1, step_precision=0.01, dots=10, digits=1)

    islands_space_dial = TouchSlider(
        action='Islandsspace', label=t('plant_islands_space'), tooltip=t('plant_islands_space_tt'),
        value_min=0.1, value_max=20, value_default=5.0,
        step=0.1, step_precision=0.01, dots=32, digits=1)

    islands_dial = TouchSlider(
        action='Islands', label=t('plant_islands'), tooltip=t('plant_islands_tt'),
        value_min=1, value_max=20, value_default=5,
        step=1, step_precision=1, dots=24, digits=0)

    islands_trees_space_dial = TouchSlider(
        action='islands_trees_space_dial', label=t('plant_space'), tooltip=t('plant_space_tt'),
        value_min=0.1, value_max=5.0, value_default=1.0,
        step=0.1, step_precision=0.01, dots=32, digits=1)

    islands_trees_dial = TouchSlider(
        action='islands_trees_dial', label=t('plant_trees'), tooltip=t('plant_islands_trees_tt'),
        value_min=1, value_max=50, value_default=7,
        step=1, step_precision=1, dots=24, digits=0)

    islands_panel.widgets.append(islands_dial)
    islands_panel.widgets.append(islands_space_dial)
    islands_panel.widgets.append(islands_clearing_dial)
    islands_panel.widgets.append(islands_trees_dial)
    islands_panel.widgets.append(islands_randomize_dial)
    islands_panel.widgets.append(islands_trees_space_dial)


    # Rows widgets
    rows_panel = TouchPanel(label='Rows')

    rows_diagonal_toggle = TouchToggle(
        action='rows_diagonal_toggle', label=t('plant_rows_diagonal'), tooltip=t('plant_rows_diagonal_tt'))
    rows_diagonal_toggle.value = True

    rows_rows_space_dial = TouchSlider(
        action='RowsSpace', label=t('plant_rows_space'), tooltip=t('plant_rows_space_tt'),
        value_min=0.1, value_max=20.0, value_default=3.0,
        step=0.1, step_precision=0.01, dots=32, digits=1)

    rows_rows_dial = TouchSlider(
        action='Rows', label=t('plant_rows'), tooltip=t('plant_rows_tt'),
        value_min=1, value_max=20, value_default=4,
        step=1, step_precision=1, dots=19, digits=0)

    rows_space_dial = TouchSlider(
        action='Space', label=t('plant_space'), tooltip=t('plant_space_tt'),
        value_min=0.1, value_max=5.0, value_default=4.0,
        step=0.1, step_precision=0.01, dots=32, digits=1)

    rows_trees_dial = TouchSlider(
        action='Trees', label=t('plant_trees'), tooltip=t('plant_rows_trees_tt'),
        value_min=1, value_max=50, value_default=8,
        step=1, step_precision=1, dots=24, digits=0)

    rows_panel.widgets.append(rows_trees_dial)
    rows_panel.widgets.append(rows_space_dial)
    rows_panel.widgets.append(rows_rows_dial)
    rows_panel.widgets.append(rows_rows_space_dial)
    rows_panel.widgets.append(rows_diagonal_toggle)


    # Ring widgets
    ring_panel = TouchPanel(label='Ring')

    ring_radius_dial = TouchSlider(
        action='ring_radius_dial', label=t('plant_ring_radius'), tooltip=t('plant_ring_radius_tt'),
        value_min=0.1, value_max=50.0, value_default=8.0,
        step=0.5, step_precision=0.1, dots=50, digits=1)

    ring_trees_dial = TouchSlider(
        action='ring_trees_dial', label=t('plant_trees'), tooltip=t('plant_trees_tt'),
        value_min=1, value_max=100, value_default=16,
        step=1, step_precision=1, dots=24, digits=0)

    ring_panel.widgets.append(ring_trees_dial)
    ring_panel.widgets.append(ring_radius_dial)


    # Clump widgets
    clump_panel = TouchPanel(label=t('plant_layout_clump'))

    clump_trees_dial = TouchSlider(
        action='Trees', label=t('plant_trees'), tooltip=t('plant_trees_tt'),
        value_min=1, value_max=50, value_default=3,
        step=1, step_precision=1, dots=24, digits=0)

    clump_space_dial = TouchSlider(
        action='Space', label=t('plant_space'), tooltip=t('plant_space_tt'),
        value_min=0.1, value_max=10.0, value_default=0.5,
        step=0.2, step_precision=0.01, dots=32, digits=1)

    clump_panel.widgets.append(clump_trees_dial)
    clump_panel.widgets.append(clump_space_dial)


    # Terrain widgets
    terrain_panel = TouchPanel(label=t('plant_terrain_panel'))

    terrain_drop_toggle = TouchToggle(
        action='Terrain',
        label=t('plant_terrain_drop'),
        tooltip=t('plant_terrain_drop_tt'))

    terrain_slope_dial = TouchSlider(
        action='terrain_slope_dial',
        label=t('plant_terrain_slope'),
        tooltip=t('plant_terrain_slope_tt'),
        value_min=0.0, value_max=1.0, value_default=0.2,
        step=0.1, step_precision=0.01, dots=10, digits=1)

    terrain_panel.widgets.append(terrain_drop_toggle)
    terrain_panel.widgets.append(terrain_slope_dial)


    # Variation widgets
    variation_panel = TouchPanel(label=t('plant_variation_panel'))

    random_shift_dial = TouchSlider(
        action='random_shift_dial', label=t('plant_random_shift'), tooltip=t('plant_random_shift_tt'),
        value_min=0.0, value_max=5.0, value_default=0.2,
        step=0.2, step_precision=0.01, dots=10, digits=1)

    random_seed = TouchSlider(
        action='Seed', label=t('plant_random_seed'), tooltip=t('plant_random_seed_tt'),
        value_min=1, value_max=10, value_default=5,
        step=1, step_precision=1, dots=24, digits=0)

    delay_dial = TouchSlider(
        action='Delay', label=t('plant_delay'), tooltip=t('plant_delay_tt'),
        value_min=0, value_max=20, value_default=2,
        step=1, step_precision=1, dots=24, digits=0)

    diverge_dial = TouchSlider(
        action='diverge_dial', label=t('plant_diverge'), tooltip=t('plant_diverge_tt'),
        value_min=0.0, value_max=1.0, value_default=0.4,
        step=0.1, step_precision=0.01, dots=10, digits=1)

    variation_panel.widgets.append(random_shift_dial)
    variation_panel.widgets.append(random_seed)
    variation_panel.widgets.append(delay_dial)
    variation_panel.widgets.append(diverge_dial)

    for widget in clump_panel.widgets + terrain_panel.widgets + variation_panel.widgets + \
            ring_panel.widgets + rows_panel.widgets + islands_panel.widgets:
        widget.minimal = True

    # Build up the interface.
    interface.widgets.append(terrain_panel)
    terrain_panel.collapsed = True
    interface.widgets.append(variation_panel)
    variation_panel.collapsed = False
    interface.widgets.append(ring_panel)
    interface.widgets.append(clump_panel)
    interface.widgets.append(islands_panel)
    interface.widgets.append(rows_panel)
    interface.add_spacer()
    interface.widgets.append(layout_pie)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grove_properties = None
        self.lines = []
        self.mouse = Vector((0, 0))
        self.space_data = None  # Used to only draw in the active 3D view.

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the operator is greyed out. """
        return context.mode == 'OBJECT'

    def modal(self, context, event):
        """ Event handling. """

        if event.type in ['MOUSEMOVE', 'LEFTMOUSE']:
            self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))

        if event.type == 'MOUSEMOVE':
            if self.interface.event_touch_move(self.mouse):
                action = self.interface.action
                if action.endswith('INCREASE') or action.endswith('DECREASE') or action.endswith('TOGGLE'):
                    plant(self)

            context.area.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type in ['LEFTMOUSE'] and event.value == 'PRESS':
            if self.interface.event_touch_down(self.mouse):
                context.region.tag_redraw()
                return {"RUNNING_MODAL"}

        if event.type in ['ESC'] and event.value == 'PRESS':
            if self.interface.find_modal():
                self.interface.cancel()
                plant(self)
                context.region.tag_redraw()
                return {"RUNNING_MODAL"}

            self.cancel(context)
            bpy.ops.ed.undo()
            return {'FINISHED'}

        # Allow for viewport navigation.
        if event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            if self.interface.event_mouse_wheel(self.mouse, event.type == 'WHEELUPMOUSE'):
                if self.interface.action.startswith('layout'):
                    update_interface(self)
                plant(self)
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            else:
                return {'PASS_THROUGH'}
                # To allow viewport zooming.

        elif event.type in ['MIDDLEMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'MOUSEROTATE', 'ACCENT_GRAVE', 'Z']:
            if event.type in 'Z' and (event.ctrl or event.oskey):
                pass
            else:
                return {"PASS_THROUGH"}

        elif event.type in ['LEFTMOUSE'] and event.value == 'PRESS':
            self.interface.event_touch_down(self.mouse)
            context.region.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type in ['LEFTMOUSE'] and event.value == 'RELEASE':
            do_plant = False

            if self.interface.event_touch_release(self.mouse):
                do_plant = True
                self.interface.update()
                context.area.tag_redraw()  # To also redraw the UI region.

            action = self.interface.action
            if action == 'layout_pie':
                update_interface(self)
                return {"RUNNING_MODAL"}
            elif action == 'Back':
                create_empties(self.placeholders)
                bpy.ops.the_grove_22.restart('EXEC_DEFAULT')
                self.cancel(context)
                return {'FINISHED'}
            elif action == 'rows_diagonal_toggle':
                plant(self)
                return {"RUNNING_MODAL"}

            if do_plant:
                plant(self)

            self.interface.update()

            context.region.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type in ['RIGHTMOUSE', 'SPACE', 'RET', 'NUMPAD_ENTER'] and event.value == 'PRESS':
            if self.interface.find_modal():
                self.interface.cancel()
                context.region.tag_redraw()
                return {"RUNNING_MODAL"}
            else:
                create_empties(self.placeholders)
                bpy.ops.the_grove_22.restart('EXEC_DEFAULT')
                self.cancel(context)
                return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, _):
        """ Initialize. """

        self.lines = [
            Vector((0.0, 0.0, 0.0)), Vector((0.0, 0.0, 1.0)),
            Vector((1.0, 0.0, 0.0)), Vector((1.0, 0.0, 1.0))
        ]

        self.grove_properties = context.collection.GROVE22_Properties
        self.grove_properties.is_tool_active_plant = True

        stop_animation_playback()

        clean_grove(context.collection)
        delete_existing_empties()

        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set(status_text_callback)
        update_interface(self)
        plant(self)
        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        """ Cleanup. """

        context.workspace.status_text_set(text=None)
        context.collection.GROVE22_Properties.is_tool_active_plant = False

        bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')

        self.interface.cancel()
        context.area.tag_redraw()
