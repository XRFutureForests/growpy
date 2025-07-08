
""" View the tree easily while constraining to how you would experience the tree in real life - from eye level.
    This gives you a good sense of the true scale of the tree.
    The tool turns, zooms and tilts all at the same time.

    Copyright 2020 - 2025, Wybren van Keulen, The Grove """


from math import asin, sin

from mathutils import Vector, Matrix
from bpy_extras.view3d_utils import region_2d_to_location_3d

from .Operators.OperatorZoom import calculate_bounding_box, calculate_mid_point


def turn_the_table(
        context, view_vector, height, interface, set_view_top=False,
        offset=0.0,
        look_at_offset=0.0,
        look_at=None):

    if height < 2:
        height = 2

    # Fix that the first time always didn't work well after zooming.
    view = context.region_data
    view.view_perspective = 'PERSP'

    # Zoom parameters are tweaked for a 50mm lens.
    # Either adjust the zoom for the lens used, or set the lens to 50mm.
    # zoom /= 50.0 / context.space_data.lens
    context.space_data.lens = 43

    view.view_distance = 1.0
    view.update()

    zoom = view_vector.length

    # Flatten out the area between 1 and 1.5, for a less wobbly experience.
    inner = 1.0
    outer = 1.0

    zoom = view_vector.length
    if zoom <= inner:
        zoom /= inner
    else:
        if zoom > inner and zoom < outer:
            zoom = 1.0
        else:
            zoom = zoom - outer + 1.0

    # Then smooth out the transition for an even smoother experience.
    # if zoom > 1.0:
    #     zoom -= 1.0
    #     zoom = (zoom ** 1.5) / 2
    #     zoom += 1
    if zoom > 1.0:
        e = 1.71828
        zoom = 0.96 + 0.65 / (1 + e**(-8 * zoom + 13))  # 1.0 + 0.65/(1+e^(-8x+13))
    elif zoom < 1.0:
        # Could also be an s-curve sigmoid.
        zoom = 0.35 * sin(zoom * 3.1415 - 1.56) + 0.65

    z_rotation = 0.0
    if view_vector.length:
        z_rotation = view_vector.angle_signed(Vector((1.0, 0.0))) - offset

    invert = False
    if invert:
        z_rotation -= 1.57079
        z_rotation = -z_rotation

    # look_at_height = height / 2  # Half the height of the tree.

    objects = context.collection.objects
    # Also include the object in the record collection if it exists.
    for collection in context.collection.children:
        if collection.name.startswith('Record'):
            objects = []
            objects.extend(context.collection.objects)
            objects.extend(collection.objects)
            break

    # bounding_box = calculate_bounding_box(context, context.collection.objects)
    bounding_box = calculate_bounding_box(context, objects)
    mid_point = calculate_mid_point(bounding_box)
    look_at_height = mid_point[2]

    zoom *= height
    zoom *= 1.0

    # Look more upward when zooming out, to give more space above for future growth.
    if zoom > height:
        look_at_height += (zoom - height) * 0.3

    look_at_height -= look_at_offset

    if look_at:
        mid_point = look_at

    # An asin domain error occurs if the longest side isn't the longest side.
    # So when zoom is shorter than look_at_height - 2.
    #if (look_at_height - 2) > zoom:
    #    look_at_height = zoom + 2

    # Below is a blend to the top view when getting close to the middle.
    """
    x_rotation = -1.57079

    if zoom < 0.5 :
        zooma = 0.5 - zoom
        zooma *= 2
        x_rotation = -1.57079 - 1.57079 * zooma
        z_rotation = (1.0 - zooma) * z_rotation
        zoom = 0.5 + (0.5 - zoom)
        zoom *= height
    elif zoom > 0.0:
        l = 1.0
        if ((look_at_height - 2)) / zoom > l:
            look_at_height = zoom * l
        else:
            x_rotation = -asin((look_at_height - 2) / zoom) - 1.57079"""

    # Top view.
    # if zoom == 0.0:
    if set_view_top:
        x_rotation = 0
        zoom = height

        mid_point[2] = look_at_height

        view.view_matrix = Matrix.Rotation(x_rotation, 4, 'X') @ Matrix.Rotation(0, 4, 'Z')
        view.view_distance = zoom
        # view.view_location = Vector((0.0, 0.0, look_at_height))
        view.view_location = mid_point
        view.update()

        # Shift to account for the UI region width.
        full_width_mid_3d = region_2d_to_location_3d(
            context.region, view,
            Vector(((interface.view_width + interface.ui_width) / 2.0, interface.view_height / 2.0)),
            mid_point)
        width_mid_3d = region_2d_to_location_3d(
            context.region, view,
            Vector(((interface.view_width) / 2.0, interface.view_height / 2.0)),
            mid_point)
        mid_point = mid_point + (full_width_mid_3d - width_mid_3d)
        view.view_location = mid_point
        view.update()
        return

    # Turn the table.
    eye_level = 1.6

    if zoom < 0:  # < o is the absolute minimum.
        zoom = 0  # < o.

    if zoom < 0.3 * height:
        zoom = 0.3 * height

    # Last adjustment to get some more space.
    zoom *= 1.2

    # TODO: Zoom out when the aspect ratio is not 1.
    # view_aspect = interface.view_width / interface.view_height
    # tree_aspect

    # Rotate the camera to look up to the tree.
    # SOSCASTOA trigonometry : sine(angle) = opposite side / hypothonuse.
    opposite = eye_level - look_at_height
    hypothonuse = zoom
    o_div_h = opposite / hypothonuse

    if o_div_h < -1.0:
        o_div_h = -1.0
    elif o_div_h > 1.0:
        o_div_h = 1.0
    x_rotation = asin(o_div_h) - 1.57079

    view.view_matrix = Matrix.Rotation(x_rotation, 4, 'X') @ Matrix.Rotation(z_rotation, 4, 'Z')
    view.view_distance = zoom

    view.view_location = mid_point  # Necessary before shifting left to account for the UI region.
    view.update()

    # Shift left to account for the UI region.
    # mid_point = Vector((0.0, 0.0, look_at_height))
    mid_point[2] = look_at_height

    full_width_mid_3d = region_2d_to_location_3d(
        context.region, view,
        Vector(((interface.view_width + interface.ui_width) / 2.0, interface.view_height / 2.0)),
        mid_point)
    width_mid_3d = region_2d_to_location_3d(
        context.region, view,
        Vector(((interface.view_width) / 2.0, interface.view_height / 2.0)),
        mid_point)
    mid_point = mid_point + (full_width_mid_3d - width_mid_3d)
    view.view_location = mid_point

    # Below line is without shifting.
    # view.view_location = Vector((0.0, 0.0, look_at_height))

    view.update()
