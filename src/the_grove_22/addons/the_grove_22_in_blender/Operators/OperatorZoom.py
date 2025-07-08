
""" Switch to a front view and zoom and pan the view to frame all trees.
    Double click to start a turntable.

    Copyright 2018 - 2025, Wybren van Keulen, The Grove """

import bpy
from mathutils import Vector
from bpy_extras.view3d_utils import region_2d_to_location_3d

from ..Languages.Translation import t


def calculate_bounding_box(context, objects):
    """ Combine every bounding box into one big bounding box. """

    # First convert the bounding box to Vectors instead of Blender's unworkable format.
    box = [Vector((0.0, 0.0, 0.0))] * 8
    first_box_processed = False

    for obj in objects:

        if obj.type == 'MESH':
            if 'grove' not in obj.data:
                continue

            # Convert bounding box to Vectors.
            ob_box = [Vector((0.0, 0.0, 0.0))] * 8
            mat = obj.matrix_world
            for j, corner in enumerate(obj.bound_box):
                ob_box[j] = mat @ Vector((corner[0], corner[1], corner[2]))

            if not first_box_processed:
                box = ob_box.copy()
                first_box_processed = True
            else:
                for i in range(8):
                    if i < 4:  # Left four corners.
                        box[i].x = min(box[i].x, ob_box[i].x)
                    else:  # Right
                        box[i].x = max(box[i].x, ob_box[i].x)

                    if i in [0, 1, 4, 5]:  # Front
                        box[i].y = min(box[i].y, ob_box[i].y)
                    else:  # Back
                        box[i].y = max(box[i].y, ob_box[i].y)

                    if i in [1, 2, 5, 6]:  # Top
                        box[i].z = max(box[i].z, ob_box[i].z)
                    else:  # Bottom - 0, 3, 4, 7
                        box[i].z = min(box[i].z, ob_box[i].z)

        if not obj.data:
            # Empty objects.
            location = obj.location

            for i in range(8):
                if i < 4:  # Left four corners.
                    box[i].x = min(box[i].x, location.x)
                else:  # Right
                    box[i].x = max(box[i].x, location.x)

                if i in [0, 1, 4, 5]:  # Front
                    box[i].y = min(box[i].y, location.y)
                else:  # Back
                    box[i].y = max(box[i].y, location.y)

                if i in [1, 2, 5, 6]:  # Top
                    box[i].z = max(box[i].z, location.z)
                else:  # Bottom - 0, 3, 4, 7
                    box[i].z = min(box[i].z, location.z)

    # Add space for new growth step.
    properties = context.collection.GROVE22_Properties
    # future_space = properties.grow_length * properties.simulation_flushes * properties.simulation_scale
    future_space = properties.grow_length * 2 * properties.simulation_scale  # Just 2 years of extra space.
    for i in [1, 2, 5, 6]:
        box[i].z += future_space
        # Also add room for a twig? Seems unnecessary now.

    # WIP: Extra room at the bottom for the bend widget.
    for i in [0, 3, 4, 7]:
        box[i].z -= 0.1 * box[1].z + 0.3

    return box


def calculate_mid_point(box):
    """ Calculate midpoint of bounding box. """

    mid = Vector((0.0, 0.0, 0.0))
    for point in box:
        mid += point
    mid /= 8.0

    return mid


def bounding_box_to_view(box, mid_point, context):
    """ Determine the width, height and aspect ration of the box in screen space. """

    view_matrix = context.region_data.view_matrix

    top = 0.0
    bottom = 0.0
    left = 0.0
    right = 0.0

    for corner in box:
        projected_corner = view_matrix @ corner
        bottom = min(bottom, projected_corner.y)
        top = max(top, projected_corner.y)
        left = min(left, projected_corner.x)
        right = max(right, projected_corner.x)

    width = abs(right - left)
    height = abs(top - bottom)

    width_radius = max(
        abs((view_matrix @ mid_point).x - left),
        abs((view_matrix @ mid_point).x - right)
    )

    height_radius = max(
        abs((view_matrix @ mid_point).y - bottom),
        abs((view_matrix @ mid_point).y - top)
    )

    if height != 0.0:
        aspect_ratio = width / height
    else:
        aspect_ratio = 1.0

    return width_radius, height_radius, aspect_ratio


def zoom(context):
    """ Zoom into the trees. """

    # area_width = context.area.width
    # ui_width = context.area.regions[2].width
    # scale = (area_width - ui_width) / area_width
    # offset = (context.region_data.perspective_matrix @ Vector((14.0 / scale, 0.0, 0.0)))

    view = context.region_data

    # These 3 lines are there to fix that the first time always didn't work well after zooming.
    context.space_data.lens = 50.0
    view.view_location = Vector((0.0, 0.0, 0.0))
    view.view_distance = 1.0

    # Set front view.
    if view.view_perspective != 'ORTHO':
        view.view_perspective = 'ORTHO'
        bpy.ops.view3d.view_axis(type='FRONT')
        view.update()

    context.region_data.update()

    view_width = 0
    view_height = 0
    ui_width = 0

    for region in context.area.regions:
        if region.type == 'WINDOW':
            view_width = region.width
            view_height = region.height
        if region.type == 'UI':
            ui_width = region.width

    collection = context.collection
    if 'Record' in collection.children:
        if collection.children['Record'].objects:
            if context.collection.GROVE22_Properties.record_enabled:
                collection = collection.children['Record']

    something_to_zoom_to = False
    for obj in collection.objects:
        if not obj.data:
            # Skip empty objects.
            continue
        if 'grove' in obj.data:
            something_to_zoom_to = True
            break

    if something_to_zoom_to:
        bounding_box = calculate_bounding_box(context, collection.objects)
        mid_point = calculate_mid_point(bounding_box)

        full_width_mid_3d = region_2d_to_location_3d(
            context.region, context.region_data,
            Vector((view_width / 2, view_height / 2)),
            mid_point)
        width_mid_3d = region_2d_to_location_3d(
            context.region, context.region_data,
            Vector(((view_width - ui_width) / 2, view_height / 2)),
            mid_point)
        mid_point = mid_point + (full_width_mid_3d - width_mid_3d)

        width_radius, height_radius, aspect_box = bounding_box_to_view(bounding_box, mid_point, context)
    else:
        # If there's nothing to zoom to, set some defaults.
        mid_point = Vector((0.0, 0.0, 2.2))
        width_radius = 4.0
        height_radius = 4.0
        aspect_box = 1.0

    # aspect_view = (view_width - ui_width) / view_height
    aspect_view = view_width / view_height
    if aspect_view > aspect_box:  # Viewport wider than bounding box.
        if aspect_view > 1.0:  # Viewport wider than square.
            view.view_distance = height_radius * aspect_view
        else:
            view.view_distance = height_radius
    else:  # Bounding box wider than viewport.
        if aspect_view < 1.0:  # Viewport taller than square.
            view.view_distance = width_radius / aspect_view
        else:
            view.view_distance = width_radius

    # Some final adjustments, zoom out a bit and move the tree down.
    view.view_distance += 0.2
    mid_point.z += 0.15 * height_radius

    # Set the viewport lens.
    context.space_data.lens = 50.0
    # All of the above assumes a 35mm lens, and because we're setting a 50mm one, adjust for that.
    view.view_distance *= (context.space_data.lens / 35.0)

    view.view_location = mid_point

    # Offset the view to account for the UI area.
    # full_width_mid_3d = region_2d_to_location_3d(
    #     context.region, context.region_data, Vector((view_width / 2, view_height / 2)), mid_point)
    # width_mid_3d = region_2d_to_location_3d(
    #     context.region, context.region_data, Vector(((view_width - ui_width) / 2, view_height / 2)), mid_point)
    # view.view_location = mid_point + (full_width_mid_3d - width_mid_3d)


class GROVE22_OT_Zoom(bpy.types.Operator):

    bl_idname = "the_grove_22.zoom"
    bl_label = t('zoom')
    bl_description = t('zoom_tt')
    bl_options = {'INTERNAL'}

    _double_click_timer = None

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mouse = Vector((0.0, 0.0))

    def modal(self, context, event):
        """ Event handling. """

        if event.type in ['MOUSEMOVE', 'LEFTMOUSE']:
            if (Vector((event.mouse_region_x, event.mouse_region_y)) - self.mouse).length > 80.0:
                # This allows a longer double click time. Without this it can be annoying if you're working fast.
                zoom(context)
                self.cancel(context)
                return {'FINISHED'}

        if event.type == 'TIMER':
            zoom(context)
            self.cancel(context)
            return {'FINISHED'}

        elif event.type in ['LEFTMOUSE'] and event.value == 'RELEASE':
            self.cancel(context)
            bpy.ops.the_grove_22.turntable('INVOKE_DEFAULT')
            return {'FINISHED'}

        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        """ Initialize. """

        self.mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        context.collection.GROVE22_Properties.is_tool_active_zoom = True
        context.window_manager.modal_handler_add(self)
        self._double_click_timer = context.window_manager.event_timer_add(0.3, window=bpy.context.window)
        return {'RUNNING_MODAL'}

    def cancel(self, context):
        """ Cleanup. """

        if self._double_click_timer:
            context.window_manager.event_timer_remove(self._double_click_timer)
            self._double_click_timer = None
            context.collection.GROVE22_Properties.is_tool_active_zoom = False
