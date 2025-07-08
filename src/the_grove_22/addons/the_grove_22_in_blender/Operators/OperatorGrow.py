
""" Simulate growth for the active grove by the number of flushes specified.

    Copyright 2014 - 2025, Wybren van Keulen, The Grove """


from gc import disable as disable_garbage_collection
from gc import enable as enable_garbage_collection

import bpy
from mathutils import Vector
from bpy_extras.view3d_utils import location_3d_to_region_2d
from gpu.shader import from_builtin
from gpu_extras.batch import batch_for_shader

from ..Interface.Interface import Interface, TouchProgress
from ..Interface.Canvas import Canvas
from ..File import load_grove, save_grove
from ..Languages.Translation import t
from .OperatorRestart import create_new_trees, clean_grove
from .OperatorBuild import build, clean_record
from .OperatorReplant import replant

from ..Core import import_core
the_grove_core = import_core()


def mesh_to_coords(obj, properties):
    """ Convert a Blender mesh to triangles and then to a list of coordinates. """

    environment_transform = obj.matrix_world
    coords = []
    obj.data.calc_loop_triangles()
    for triangle in obj.data.loop_triangles:
        for vert_index in triangle.vertices:
            co = environment_transform @ obj.data.vertices[vert_index].co / properties.simulation_scale
            coords.append(co.x)
            coords.append(co.y)
            coords.append(co.z)
    return coords


def draw_2d(self, context):

    if self.space_data != context.space_data:  # Prevent drawing in other 3D views.
        return

    properties = context.collection.GROVE22_Properties
    scale = properties.simulation_scale

    region = context.region
    region_data = context.region_data
    vector_zero = Vector((0.0, 0.0))

    # Draw transparent overlay to fade the existing tree.
    if not properties.record_enabled:
        # Fade in a background fade.
        alpha = 0.4
        if self.simulation_flushes > 6:
            alpha = self.current_year / self.simulation_flushes
            from math import sin
            alpha = sin(alpha**2 * 2.0) * 0.125
            alpha = alpha**0.3 * 0.8
        self.canvas.draw_fade(alpha=alpha)

    self.canvas.draw_scale_figure()

    # Draw surround preview.
    scale = properties.simulation_scale
    if properties.surround_grow:
        height = properties.height
    else:
        height = properties.surround_height

    m = bpy.context.area.spaces.active.region_3d.perspective_matrix
    m = (tuple(m.col[0]), tuple(m.col[1]), tuple(m.col[2]), tuple(m.col[3]))
    (points, indices) = self.grove.build_surround_preview_2d(
        height, m, bpy.context.region.width, bpy.context.region.height)
    flat_shader = from_builtin('UNIFORM_COLOR')
    color_dark = (0.3, 0.3, 0.3, 0.25)
    flat_shader.uniform_float("color", color_dark)
    flat_shader.bind()
    # blend_set('ALPHA')
    batch = batch_for_shader(flat_shader, 'TRIS', {"pos": points}, indices=indices)
    batch.draw(flat_shader)

    # Draw a sketch of the tree.
    if not properties.record_enabled:
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

        # Show newly added trees.
        for tree in self.grove.trees:
            if tree.nodes[0].dead:
                loc = Vector((tree.nodes[0].pos.as_tuple()))
                point_2d = location_3d_to_region_2d(
                    region, region_data, loc * scale, default=vector_zero)
                color_dead = (1.0, 0.1, 0.0, 0.3)
                self.canvas.draw_circle_filled(point_2d, 15, color=color_dead)
            elif tree.nodes[0].age < 5:
                loc = Vector((tree.nodes[0].pos.as_tuple()))
                point_2d = location_3d_to_region_2d(
                    region, region_data, loc * scale, default=vector_zero)
                alpha = (5 - tree.nodes[0].age) * 0.2
                alpha = alpha**1.5
                alpha *= 0.7
                color_green = color_green = (0.2, 0.6, 0.05, alpha)
                self.canvas.draw_circle_filled(point_2d + Vector((0, (1.0 - alpha) * 20)), 5 + alpha * 15, color=color_green)

    self.interface.draw()


def status_text_callback(header, context):
    header.layout.label(text=t('label_stop'), icon='EVENT_ESC')
    header.layout.separator_spacer()


class GROVE22_OT_Grow(bpy.types.Operator):

    bl_idname = "the_grove_22.grow"
    bl_label = t('simulate')
    bl_description = t('simulate_tt')
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    do_regrow: bpy.props.BoolProperty(
        name='', description='',
        default=False,
        options={'HIDDEN'})

    # Below allows changing simulation_flushes from Python.
    # bpy.ops.the_grove_22.grow('INVOKE_DEFAULT', simulation_flushes=10)
    # simulation_flushes: bpy.props.IntProperty(default=1, options={'HIDDEN'})

    # Interface
    interface = Interface()
    progress_dial = TouchProgress(
        action='Progress',
        label=t('grow_tool_growing'),
        tooltip=t('grow_tool_growing_tt'),
        icon='GROW')
    interface.widgets.append(progress_dial)

    _handle_draw_2d = None
    _timer = None

    canvas = Canvas()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.grove = None
        self.current_year = 0
        self.simulation_flushes = 1
        self.build_step = False
        self.done = False

        self.mouse = Vector((0, 0))
        self.space_data = None  # Used to only draw in the active 3D view.

        self.tri_strip = []
        self.tri_strip_dead = []
        # from time import time
        # self.start_time = time()

    @classmethod
    def poll(cls, context):
        """ Check if in object mode. If not, the operator is greyed out."""

        return context.mode == 'OBJECT'

    def build_sketch(self):
        """ Create a quick sketch of the tree. """

        m = bpy.context.area.spaces.active.region_3d.perspective_matrix
        m = (tuple(m.col[0]), tuple(m.col[1]), tuple(m.col[2]), tuple(m.col[3]))
        (self.tri_strip, self.tri_strip_dead) = self.grove.build_sketch_2d(0, self.grove.get_properties().simulation_scale, m, bpy.context.region.width, bpy.context.region.height)

    def modal(self, context, event):
        """ Handle events """

        properties = context.collection.GROVE22_Properties
        win_man = context.window_manager

        if event.type == 'MOUSEMOVE':
            # Essential to keep the Grow button in hover state, so that you can
            # repeatedly click Grow without first having to move the mouse.
            return {'PASS_THROUGH'}

        if self.done:
            self.progress_dial.progress = 1.0

            # if self._handle_draw_2d:
            #     bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')

            properties.is_tool_active_grow = False
            properties.is_tool_active_regrow = False
            properties.is_tool_active_grow_together = False

            win_man.event_timer_remove(self._timer)

            context.workspace.status_text_set(text=None)
            # context.area.tag_redraw()

            enable_garbage_collection()

            return {'FINISHED'}

        if self.build_step:
            # print("build step")
            self.progress_dial.progress = 1.0
            win_man.event_timer_remove(self._timer)

            # Save one extra draw call.
            if self._handle_draw_2d:
                bpy.types.SpaceView3D.draw_handler_remove(self._handle_draw_2d, 'WINDOW')

            progress = self.progress_dial.progress + (100 - self.progress_dial.progress) / 2.0
            self.progress_dial.progress = progress / 100.0

            save_grove(self.grove, context.collection)

            if properties.record_enabled:
                # When recording growth animation, building is done every year,
                # so no need to build at the end.
                pass
            else:
                build(
                    context,
                    properties,
                    self.grove,
                    context.collection,
                    rebuild=True)

            self.progress_dial.progress = 1.0

            context.window.cursor_modal_restore()
            # context.area.tag_redraw()

            self.done = True
            self._timer = win_man.event_timer_add(0.02, window=context.window)

            return {'RUNNING_MODAL'}

        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))
            self.interface.event_touch_down(self.mouse)
            context.region.tag_redraw()

        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            # A simplified interface just recording the left mouse release.
            # Almost no overhead and it allows to cancel growing with touch,
            # pen or mouse without a keyboard.

            self.interface.event_touch_release(self.mouse)
            action = self.interface.action
            if action == 'Progress':
                self.build_step = True
                self.progress_dial.label = t('grow_tool_building')
                self.progress_dial.icon = 'BUILD'

                context.region.tag_redraw()

                return {'RUNNING_MODAL'}

        elif event.type in ['RIGHTMOUSE', 'ESC'] and event.value == 'PRESS':
            self.build_step = True
            context.area.tag_redraw()

            return {'RUNNING_MODAL'}

        elif event.type == 'TIMER':
            win_man.event_timer_remove(self._timer)

            if self.current_year != self.simulation_flushes:

                step = 1  # Was 3.
                if not properties.record_enabled:
                    if self.grove.age > 15:
                        step = 1  # Was 2.
                    if self.grove.age > 25:
                        step = 1
                    if properties.record_enabled:
                        step = 1

                    if self.current_year + step >= self.simulation_flushes:
                        step = self.simulation_flushes - self.current_year

                self.grove.simulate(step)
                self.current_year += step
                properties.age += step

                # from time import time
                # print("total time: " + str(time() - self.start_time))
                # self.start_time = time()

                # print("year: " + str(self.current_year))

                # Record growth rings.
                # if True:
                #     radius = self.grove.trees[0].nodes[0].radius
                #     bpy.ops.mesh.primitive_circle_add(
                #         radius=radius,
                #         enter_editmode=False,
                #         align='WORLD',
                #         location=(0, 0, 0),
                #         scale=(1, 1, 1),
                #         vertices=128)

                if properties.record_enabled:
                    build(context, properties, self.grove, context.collection, rebuild=True)
                else:
                    # The final step before building gets more detail.
                    # self.build_sketch(self.current_year == self.simulation_flushes)
                    self.build_sketch()

                if properties.sow_enabled:
                    # Update the preview of Surround.
                    self.surround_lines = self.grove.build_surround_preview()

                if self.current_year > 0:
                    # Calculate progress in an exponential fashion, it's pretty accurate.
                    exponent = 2.0
                    # Plus one for build step.
                    progress = pow((self.current_year + 1) / (self.simulation_flushes + 1), exponent)
                    self.progress_dial.progress = max(1, int(progress * 100)) / 100.0

                properties['height'] = self.grove.height
                properties.number_of_branches = self.grove.number_of_branches

            if self.current_year == self.simulation_flushes:
                self.build_step = True
                self.progress_dial.label = t('grow_tool_building')
                self.progress_dial.icon = 'BUILD'

            context.area.tag_redraw()

            self._timer = win_man.event_timer_add(0.02, window=context.window)

            return {'RUNNING_MODAL'}

        return {'RUNNING_MODAL'}

    def execute(self, context):
        """ Run without yearly updates. """

        properties = context.collection.GROVE22_Properties

        if self.simulation_flushes > 0:
            self.grove.simulate(self.simulation_flushes)

        properties['height'] = self.grove.height
        properties.number_of_branches = self.grove.number_of_branches
        save_grove(self.grove, context.collection)
        build(context, properties, self.grove, context.collection, rebuild=True)

        context.window.cursor_modal_restore()
        return {'FINISHED'}

    def invoke(self, context, event):
        """ Initialize """

        context.window.cursor_modal_set('WAIT')

        properties = context.collection.GROVE22_Properties

        clean_grove(context.collection, roots=True)

        self.simulation_flushes = properties.simulation_flushes
        if self.do_regrow:
            self.simulation_flushes = properties.age
            if properties.age == 0:
                self.simulation_flushes = properties.age_of_last_grown_tree
            create_new_trees(context, context.collection, properties)

        # Restart so that a possible change in the number of trees is handled.
        # Also, a user could have added empties before growing.
        else:
            if properties.age == 0:
                # Age can be 0 when the user has drawn a tree from scratch.
                # Without this check, a drawn tree would be reset.
                if properties.number_of_branches == 1:
                    create_new_trees(context, context.collection, properties)

        # print('The Grove in Blender - Grow')

        self.grove = load_grove(context.collection)
        self.grove.set_properties(properties.convert_to_core_properties())

        if not self.grove:
            context.window.cursor_modal_restore()
            self.report({"ERROR"}, "Simulation file not found - restart to continue growing.")
            return {'CANCELLED'}

        if self.do_regrow:
            clean_record(context.collection)

        if properties.age != 0:
            replant(context.collection, properties, self.grove)

        # Build shade trees for each of the react objects.
        if properties.react_enabled:
            if properties.react_block_object:
                self.grove.set_react_block_triangles_from_coords(
                    mesh_to_coords(properties.react_block_object, properties))
            if properties.react_shade_object:
                self.grove.set_react_shade_triangles_from_coords(
                    mesh_to_coords(properties.react_shade_object, properties))
            if properties.react_attract_object:
                self.grove.set_react_attract_triangles_from_coords(
                    mesh_to_coords(properties.react_attract_object, properties))
            if properties.react_deflect_object:
                self.grove.set_react_deflect_triangles_from_coords(
                    mesh_to_coords(properties.react_deflect_object, properties))

        if self.simulation_flushes == 1 and not properties.record_enabled:
            return self.execute(context)

        # self.grove.set_random_seed(1)  # For testing purposes.

        self.interface.info_bar = []
        if properties.auto_prune_enabled and properties.auto_prune_low != 0:
            self.interface.info_bar.append('Auto Prune')
        if properties.stake_enabled:
            self.interface.info_bar.append('Stake')
        if properties.surround_enabled and properties.surround_density != 0:
            self.interface.info_bar.append('Surround')
        if properties.record_enabled:
            self.interface.info_bar.append('Record')
        if properties.sow_enabled:
            self.interface.info_bar.append('Sow')
        if properties.react_enabled:
            if properties.react_block_object or properties.react_shade_object or \
                properties.react_attract_object or properties.react_deflect_object:
                self.interface.info_bar.append('React')

        self.progress_dial.progress = 0.0
        self.progress_dial.label = t('grow_tool_growing')
        self.progress_dial.icon = 'GROW'
        self.interface.update()

        win_man = context.window_manager
        win_man.modal_handler_add(self)

        # Show the grow or regrow buttons depressed while growing.
        if self.do_regrow:
            properties.is_tool_active_regrow = True
        else:
            properties.is_tool_active_grow = True
        self.current_year = 0
        self._timer = win_man.event_timer_add(0.02, window=context.window)

        context.workspace.status_text_set(status_text_callback)
        self._handle_draw_2d = bpy.types.SpaceView3D.draw_handler_add(
            draw_2d, (self, context), 'WINDOW', 'POST_PIXEL')
        context.area.tag_redraw()
        self.space_data = context.space_data

        disable_garbage_collection()
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        """ When closing the tool, set some things back to how they were. """

        context.window.cursor_modal_restore()
        context.workspace.status_text_set(text=None)
