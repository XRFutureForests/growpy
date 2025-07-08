
""" Create an exposed root system.

    Roots are usually tucked away underground, but they can be exposed when the soil erodes.
    These roots are visually pleasing and are an important aspect in the art of Bonsai, where they are called nebari.

    It makes no sense to try to simulate real root growth. Only very few roots will ever be visible, and it would be a
    waste of time to simulate the rest. On top of that, root growth is a dark spot in science, much is unknown.
    Finally, root growth is very dependent on the soil structure and distribution of water.

    So this is a fake, very fast tool to generate root structures.

    Copyright 2021 - 2025, Wybren van Keulen, The Grove """


import bpy
from mathutils import Vector
from numpy import empty, array
from os.path import dirname, join

from ..Interface.Interface import Interface, TouchPanel, TouchButton, TouchSlider, TouchToggle, TouchTurntable
from ..Interface.Canvas import Canvas
from ..Languages.Translation import t
from ..Turntable import turn_the_table
from .OperatorBuild import clean_grove, create_tree_object
from ..File import load_grove

from ..Core import import_core
the_grove_core = import_core()


def draw_2d(self, context):
    """ Draw the interface and preview. """

    if self.space_data != context.space_data:
        # Prevent drawing in other 3D views.
        return

    self.interface.draw()


def add_scale_geometry_nodes(properties, obj):
    """ Append the geometry nodes modifiers from an external file. """

    # TODO: This is a copy from OperatorBuild.py. Maybe use that function in a generalized version.

    parent_dir = dirname(dirname(__file__))
    file = join(join(parent_dir, "Resources"), "GeometryNodes.blend")

    grove_id = str(properties.unique_id)

    node_trees = ['GroveGNScale']  # 'GroveGNThicken'

    for node_tree in node_trees:
        if node_tree + grove_id not in bpy.data.node_groups:
            # Use existing node group.
            with bpy.data.libraries.load(file) as (library_file, this_file):
                if node_tree in library_file.node_groups:
                    i = library_file.node_groups.index(node_tree)
                    this_file.node_groups.append(library_file.node_groups[i])

            for group in this_file.node_groups:
                group.name = group.name.split('.')[0] + grove_id

        modifier = obj.modifiers.new(type='NODES', name=node_tree.split('GroveGN')[1])
        modifier.node_group = bpy.data.node_groups[node_tree + grove_id]
        modifier.show_in_editmode = False


def roots(self):
    """ Create roots. """

    # First remove old roots, to prevent terrain drop for seeing them.
    clean_grove(bpy.context.collection, roots=True)

    props = the_grove_core.Properties()
    props.roots_turn_down = self.turn_down_dial.value * 4.0
    props.roots_random_heading = self.random_heading_dial.value * 2.0
    props.roots_random_pitch = self.random_pitch_dial.value / 4.0
    props.roots_internode_length = self.length_dial.value
    props.roots_number = self.number_dial.value
    props.roots_nodes = self.nodes_dial.value
    props.roots_climb = self.climb_dial.value
    if props.roots_climb > 9:
        props.roots_climb = 9
        self.climb_dial.value = 9
    props.roots_generations = self.generations_dial.value
    props.roots_density = self.density_dial.value
    props.roots_angle = self.angle_dial.value
    props.roots_add_down = self.add_down_dial.value
    props.roots_random_seed = self.random_seed.value
    props.roots_thickness = self.thickness_dial.value
    props.roots_thickness_random = self.thickness_random_dial.value
    props.roots_thickness_reduce = self.thickness_reduce_dial.value
    props.roots_terrain_drop = self.terrain_drop_toggle.value
    self.grove.set_properties(props)

    self.grove.grow_roots()
    models = self.grove.build_roots({
            "resolution": 16,
            "resolution_reduce": 0.8,
            "texture_repeat": 1,
            "build_cutoff_age": 0,
            "build_blend": True,
            "build_end_cap": True,
        })
    if not len(models):
        # print("No roots")
        return
    
    for i, model in enumerate(models):
        roots_object = create_tree_object(model, self.grove_properties, bpy.context, roots=True)
        roots_object['grove'] = 'Roots'
        roots_object['grove_roots'] = 'Roots'
        roots_object['grove_tree_id'] = 0  # root_id
        bpy.context.collection.objects.link(roots_object)
        
        add_scale_geometry_nodes(self.grove_properties, roots_object)

        scale = self.grove_properties.simulation_scale
        location = Vector((self.grove.trees[i].nodes[0].pos.x, self.grove.trees[i].nodes[0].pos.y, self.grove.trees[i].nodes[0].pos.z))
        roots_object.location = location * scale
        roots_object.scale = Vector((scale, scale, scale))  # TODO: Change this to the scale modifier.

        origin = Vector((model.location.x, model.location.y, model.location.z))
        
        # Building automatically sets the origin at the base of the tree,
        # but roots start further along the trunk of the parent tree.
        # It's nice to have the same origin for the tree and its roots.
        # So offset each vertex in the mesh, then shift back the object origin.
        origin_node = self.grove.roots[i].nodes[0]
        origin = Vector((
            origin_node.pos.x,
            origin_node.pos.y,
            origin_node.pos.z))
        offset = origin - location

        # Numpy is ten times as fast as a for loop.
        coords = empty(len(roots_object.data.vertices) * 3)
        roots_object.data.vertices.foreach_get('co', coords)
        coords = coords.reshape(len(roots_object.data.vertices), 3)
        coords += array(offset)
        coords = coords.flatten()
        roots_object.data.vertices.foreach_set('co', coords)

        roots_object.name = 'Root'
    bpy.context.view_layer.objects.active = roots_object


def update_interface(self):
    """ Hide all widgets and then show the ones for the selected layout type. """

    self.interface.update()
    roots(self)


def status_text_callback(header, _):
    """ Add shortcuts to Blender's status bar. """

    header.layout.label(text='Rotate View', icon='MOUSE_MMB')
    header.layout.label(text=t('close'), icon='MOUSE_RMB')


class GROVE22_OT_Roots(bpy.types.Operator):

    bl_idname = "the_grove_22.roots"
    bl_label = t('roots')
    bl_description = t('roots_tt')
    bl_options = {'REGISTER', 'UNDO'}

    _handle_draw_2d = None
    _turntable_timer = None
    _build_timer = None

    canvas = Canvas()

    rotation_offset = 0.0
    look_at_offset = 3.0
    look_at = Vector((0.0, 0.0, 0.0))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.roots = []

        self.tree = None
        # self.grove_tree_id = 0
        self.grove_properties = None

        self.lines = []

        self.mouse = Vector((0, 0))
        self.space_data = None  # Used to only draw in the active 3D view.

    tweaking = False

    # Setup the interface. Class-wide, not per class instance like in __init__. This will make each instance
    # of the tool keep the set parameters and remember which tips have been clicked away.

    interface = Interface()

    interface.widgets.append(
        TouchButton(action='Back', label=t('close_button'), tooltip=t('close_button_tt'), icon='CHECKMARK'))

    turntable = TouchTurntable(action='View', label=t('turntable'), tooltip=t('turntable_tt'), icon='VIEW')
    interface.widgets.append(turntable)

    interface.add_spacer()

    # Roots panel
    roots_panel = TouchPanel(label=t('roots_roots_panel'))

    number_dial = TouchSlider(
        action='tweak',
        label=t('roots_number'), tooltip=t('roots_number_tt'),
        value_min=1, value_max=16, value_default=8,
        step=1, step_precision=1, dots=16, digits=0)

    nodes_dial = TouchSlider(
        action='tweak',
        label=t('roots_nodes'), tooltip=t('roots_nodes_tt'),
        value_min=0, value_max=20, value_default=8,
        step=1, step_precision=1, dots=16, digits=0)

    length_dial = TouchSlider(
        action='tweak', label=t('roots_length'),
        tooltip=t('roots_length_tt'),
        value_min=0.05, value_max=.4, value_default=0.2,
        step=0.01, step_precision=0.01, dots=32, digits=1)

    climb_dial = TouchSlider(
        action='tweak',
        label=t('roots_climb'), tooltip=t('roots_climb_tt'),
        value_min=0, value_max=5, value_default=3,
        step=1, step_precision=1, dots=5, digits=0)

    turn_down_dial = TouchSlider(
        action='tweak',
        label=t('roots_turn_down'), tooltip=t('roots_turn_down_tt'),
        value_min=0.0, value_max=1.0, value_default=0.3,
        step=0.1, step_precision=0.01, dots=10, digits=1)

    roots_panel.widgets.append(number_dial)
    roots_panel.widgets.append(nodes_dial)
    roots_panel.widgets.append(length_dial)
    roots_panel.widgets.append(climb_dial)
    roots_panel.widgets.append(turn_down_dial)

    # Thicken panel
    thicken_panel = TouchPanel(label=t('roots_thickness_panel'))

    thickness_dial = TouchSlider(
        action='tweak',
        label=t('roots_thickness'), tooltip=t('roots_thickness_tt'),
        value_min=0.02, value_max=1.0, value_default=0.3,
        step=0.01, step_precision=0.01, dots=32, digits=1)

    thickness_reduce_dial = TouchSlider(
        action='tweak',
        label=t('roots_thickness_reduce'), tooltip=t('roots_thickness_reduce_tt'),
        value_min=0.0, value_max=0.9, value_default=0.5,
        step=0.05, step_precision=0.01, dots=64, digits=1)

    thickness_random_dial = TouchSlider(
        action='tweak',
        label=t('roots_thickness_random'), tooltip=t('roots_thickness_random_tt'),
        value_min=0.0, value_max=1.0, value_default=0.2,
        step=0.05, step_precision=0.01, dots=32, digits=1)

    thicken_panel.widgets.append(thickness_dial)
    thicken_panel.widgets.append(thickness_random_dial)
    thicken_panel.widgets.append(thickness_reduce_dial)


    # Terrain widgets
    terrain_panel = TouchPanel(label=t('roots_terrain_panel'))

    terrain_drop_toggle = TouchToggle(
        action='tweak',
        label=t('roots_drop'), tooltip=t('roots_drop_tt'))

    terrain_panel.widgets.append(terrain_drop_toggle)


    # Variation widgets
    variation_panel = TouchPanel(label=t('roots_variation_panel'))

    random_heading_dial = TouchSlider(
        action='tweak',
        label=t('roots_random_heading'), tooltip=t('roots_random_heading_tt'),
        value_min=0.0, value_max=1.0, value_default=0.7,
        step=0.05, step_precision=0.01, dots=10, digits=1)

    random_pitch_dial = TouchSlider(
        action='tweak',
        label=t('roots_random_pitch'), tooltip=t('roots_random_pitch_tt'),
        value_min=0.0, value_max=1.0, value_default=0.3,
        step=0.05, step_precision=0.01, dots=16, digits=2)

    random_seed = TouchSlider(
        action='tweak',
        label=t('roots_random_seed'), tooltip=t('roots_random_seed_tt'),
        value_min=1, value_max=100, value_default=5,
        step=1, step_precision=1, dots=24, digits=0)

    variation_panel.widgets.append(random_heading_dial)
    variation_panel.widgets.append(random_pitch_dial)
    variation_panel.widgets.append(random_seed)

    # Branches widgets
    branches_panel = TouchPanel(label=t('roots_branches_panel'))

    generations_dial = TouchSlider(
        action='tweak',
        label=t('roots_generations'), tooltip=t('roots_generations_tt'),
        value_min=0, value_max=4, value_default=1,
        step=1, step_precision=1, dots=8, digits=0)

    density_dial = TouchSlider(
        action='tweak',
        label=t('roots_density'), tooltip=t('roots_density_tt'),
        value_min=0.0, value_max=1.0, value_default=1.0,
        step=0.1, step_precision=0.01, dots=10, digits=1)

    angle_dial = TouchSlider(
        action='tweak',
        label=t('roots_add_angle'), tooltip=t('roots_add_angle_tt'),
        value_min=0.0, value_max=1.0, value_default=0.7,
        step=0.05, step_precision=0.01, dots=10, digits=1)

    add_down_dial = TouchSlider(
        action='tweak',
        label=t('roots_add_down'), tooltip=t('roots_add_down_tt'),
        value_min=0.0, value_max=1.0, value_default=0.2,
        step=0.1, step_precision=0.01, dots=10, digits=1)

    branches_panel.widgets.append(generations_dial)
    branches_panel.widgets.append(density_dial)
    branches_panel.widgets.append(angle_dial)
    branches_panel.widgets.append(add_down_dial)

    for widget in roots_panel.widgets + terrain_panel.widgets + variation_panel.widgets + \
            branches_panel.widgets + thicken_panel.widgets:
        widget.minimal = True

    # Build up the interface.
    interface.widgets.append(thicken_panel)
    interface.widgets.append(variation_panel)
    interface.widgets.append(branches_panel)
    interface.widgets.append(roots_panel)
    interface.add_spacer()

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the operator is greyed out. """

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
                if self.turntable.do_interpolate:
                    self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)
                turn_the_table(
                    context, self.turntable.vector,
                    self.grove_properties.height * self.grove_properties.simulation_scale,
                    self.interface, offset=self.rotation_offset,
                    look_at_offset=self.look_at_offset,
                    look_at=self.look_at)

                context.region.tag_redraw()
                return {"RUNNING_MODAL"}

        elif event.type == 'MOUSEMOVE':
            if self._turntable_timer is not None:
                # When interpolating with the timer, prevent a double redraw.
                return {"RUNNING_MODAL"}

            if self.interface.event_touch_move(self.mouse):
                action = self.interface.action
                if action == 'View':
                    if self.turntable.modal:
                        turn_the_table(
                            context, self.turntable.vector,
                            self.grove_properties.height * self.grove_properties.simulation_scale,
                            self.interface, offset=self.rotation_offset,
                            look_at_offset=self.look_at_offset,
                            look_at=self.look_at)
                        if self._turntable_timer is None:
                            self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)
                elif action.endswith('INCREASE') or action.endswith('DECREASE') or action.endswith('TOGGLE'):
                    roots(self)
                    self.tweaking = True

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
                        self.interface, offset=self.rotation_offset,
                        look_at_offset=self.look_at_offset,
                        look_at=self.look_at)
                    if self._turntable_timer is None:
                        # Enable this for animation at the start.
                        self._turntable_timer = win_man.event_timer_add(0.05, window=bpy.context.window)
                context.region.tag_redraw()
                return {"RUNNING_MODAL"}

        if event.type in ['RIGHTMOUSE', 'ESC'] and event.value == 'PRESS':
            if self.interface.find_modal():
                self.interface.cancel()
                roots(self)
                context.region.tag_redraw()
                return {"RUNNING_MODAL"}
            else:
                self.cancel(context)
                return {'FINISHED'}

        # Allow for viewport navigation.
        if event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            turning = self.turntable.modal
            if turning:
                if event.type == 'WHEELUPMOUSE':
                    self.rotation_offset += 0.3
                else:
                    self.rotation_offset -= 0.3
                return {'RUNNING_MODAL'}
            if self.interface.event_mouse_wheel(self.mouse, event.type == 'WHEELUPMOUSE'):
                if self.interface.action == 'View':
                    turn_the_table(
                        context, self.turntable.vector,
                        self.grove_properties.height * self.grove_properties.simulation_scale,
                        self.interface, offset=self.rotation_offset,
                        look_at_offset=self.look_at_offset,
                        look_at=self.look_at)
                if self.interface.action.startswith('layout'):
                    update_interface(self)
                roots(self)
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
            do_roots = False

            if self.interface.event_touch_release(self.mouse):
                do_roots = True
                self.interface.update()
                context.area.tag_redraw()  # To also redraw the UI region.
                self.tweaking = False

            action = self.interface.action

            if self.interface.action == 'Back':
                roots(self)
                self.cancel(context)
                return {'FINISHED'}
            elif self.interface.action == 'rows_diagonal_toggle':
                roots(self)
                return {"RUNNING_MODAL"}

            if do_roots:
                roots(self)

            self.interface.update()

            context.region.tag_redraw()
            return {'RUNNING_MODAL'}

        elif event.type in ['SPACE', 'RET', 'NUMPAD_ENTER'] and event.value == 'PRESS':
            # if self.roots:
            #     build(
            #         context, self.grove_properties, self.roots,
            #         context.collection, rebuild=False, root_id=self.grove_tree_id,
            #         origin=self.tree.nodes[0].pos)
            self.cancel(context)
            return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, _):
        """ When the tool starts. """

        # First check if the user has moved around trees and if so, then replant them.
        bpy.ops.the_grove_22.replant('EXEC_DEFAULT')

        self.grove_properties = context.collection.GROVE22_Properties
        self.grove_properties.is_tool_active_roots = True

        self.grove = load_grove(context.collection)

        if not self.grove:
            context.window.cursor_modal_restore()
            self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
            return {'CANCELLED'}

        # self.grove_tree_id = context.active_object['grove_tree_id']

        self.tree = self.grove.trees[0]
        v = self.tree.nodes[0].pos
        self.look_at = Vector((v.x, v.y, v.z)) * self.grove_properties.simulation_scale

        clean_grove(bpy.context.collection, roots=True)

        context.window_manager.modal_handler_add(self)

        context.workspace.status_text_set(status_text_callback)
        update_interface(self)
        roots(self)
        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        self.space_data = context.space_data
        context.area.tag_redraw()

        return {'RUNNING_MODAL'}

    def cancel(self, context):
        """ When closing the tool, reset some things back to how they were. """

        context.workspace.status_text_set(text=None)
        context.collection.GROVE22_Properties.is_tool_active_roots = False

        bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')
        if self._turntable_timer:
            context.window_manager.event_timer_remove(self._turntable_timer)
            self._turntable_timer = None

        self.interface.cancel()
        context.area.tag_redraw()
