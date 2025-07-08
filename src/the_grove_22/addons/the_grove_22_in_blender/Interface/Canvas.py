# coding=utf-8

""" Draw graphical primitives.

    Copyright 2021 - 2025, Wybren van Keulen, The Grove """


import bpy

from gpu.state import blend_set, line_width_set
from gpu.shader import from_builtin
from gpu_extras.batch import batch_for_shader

import blf
from bpy_extras.view3d_utils import location_3d_to_region_2d
from numpy import array

from math import cos, sin
from mathutils import Vector, Matrix

from .Font import char_vertices, char_indices
from .Icons import icon_vertices, icon_indices


class Canvas():

    if not bpy.app.background:
        flat_shader = from_builtin('UNIFORM_COLOR')

    widget_color = (0.0, 0.0, 0.0, 0.72)
    circle_points_16 = array((
        (1.0, 0.0), (0.924, 0.383), (0.707, 0.707), (0.383, 0.924),
        (0.0, 1.0), (-0.383, 0.924), (-0.707, 0.707), (-0.924, 0.383),
        (-1.0, 0.0), (-0.924, -0.383), (-0.707, -0.707), (-0.383, -0.924),
        (-0.0, -1.0), (0.383, -0.924), (0.707, -0.707), (0.924, -0.383),
        (1.0, -0.0)))
    circle_points_32 = array((
        (1.0, 0.0), (0.98, 0.195), (0.924, 0.383), (0.83, 0.556),
        (0.707, 0.707), (0.556, 0.83), (0.383, 0.924), (0.195, 0.98),
        (0.0, 1.0), (-0.195, 0.98), (-0.383, 0.924), (-0.556, 0.83),
        (-0.707, 0.707), (-0.83, 0.556), (-0.924, 0.383), (-0.98, 0.195),
        (-1.0, 0.0), (-0.98, -0.195), (-0.924, -0.383), (-0.83, -0.556),
        (-0.707, -0.707), (-0.556, -0.83), (-0.383, -0.924), (-0.195, -0.98),
        (-0.0, -1.0), (0.195, -0.98), (0.383, -0.924), (0.556, -0.83),
        (0.707, -0.707), (0.83, -0.556), (0.924, -0.383), (0.98, -0.195),
        (1.0, -0.0)))
    circle_points_64 = array((
        (1.0, 0.0), (0.995, 0.098), (0.98, 0.195), (0.957, 0.29),
        (0.924, 0.383), (0.882, 0.47), (0.83, 0.556), (0.773, 0.634),
        (0.707, 0.707), (0.634, 0.773), (0.556, 0.83), (0.47, 0.882),
        (0.383, 0.924), (0.29, 0.957), (0.195, 0.98), (0.098, 0.995),
        (0.0, 1.0), (-0.098, 0.995), (-0.195, 0.98), (-0.29, 0.957),
        (-0.383, 0.924), (-0.47, 0.882), (-0.556, 0.83), (-0.634, 0.773),
        (-0.707, 0.707), (-0.773, 0.634), (-0.83, 0.556), (-0.882, 0.47),
        (-0.924, 0.383), (-0.957, 0.29), (-0.98, 0.195), (-0.995, 0.098),
        (-1.0, 0.0), (-0.995, -0.098), (-0.98, -0.195), (-0.957, -0.29),
        (-0.924, -0.383), (-0.882, -0.47), (-0.83, -0.556), (-0.773, -0.634),
        (-0.707, -0.707), (-0.634, -0.773), (-0.556, -0.83), (-0.47, -0.882),
        (-0.383, -0.924), (-0.29, -0.957), (-0.195, -0.98), (-0.098, -0.995),
        (-0.0, -1.0), (0.098, -0.995), (0.195, -0.98), (0.29, -0.957),
        (0.383, -0.924), (0.47, -0.882), (0.556, -0.83), (0.634, -0.773),
        (0.707, -0.707), (0.773, -0.634), (0.83, -0.556), (0.882, -0.47),
        (0.924, -0.383), (0.957, -0.29), (0.98, -0.195), (0.995, -0.098),
        (1.0, -0.0)))

    def draw_passepartout_new(self, x, y, w, h):
        b = 64
        b_inner = 24
        o = 12

        color = (0.7, 0.7, 0.7, 1.0)

        self.draw_donut(
            Vector((x + w - b - o, y + b + o)), b, b_inner, color=color, pie_slice=0.27, rotation=1.57079, rounded=False)
        self.draw_donut(
            Vector((x + b + o, y + b + o)), b, b_inner, color=color, pie_slice=0.27, rotation=3.14159, rounded=False)
        self.draw_donut(
            Vector((x + o + b, y + h - b - o)), b, b_inner, color=color, pie_slice=0.27, rotation=4.71239, rounded=False)
        self.draw_donut(
            Vector((x + w - b - o, y + h - b - o)), b, b_inner, color=color, pie_slice=0.27, rotation=0, rounded=False)

        vertices = [
            (x + b + o, b + o - b_inner),
            (x + w - b - o, b + o - b_inner),
            (x + w - b - o, o),
            (x + b + o, o)]
        indices = [
            (0, 1, 3),
            (1, 2, 3)
        ]

        blend_set('ALPHA')
        batch = batch_for_shader(self.flat_shader, 'TRIS', {"pos": vertices}, indices=indices)
        self.flat_shader.bind()
        self.flat_shader.uniform_float("color", color)
        batch.draw(self.flat_shader)

    def draw_passepartout(self, x, y, w, h):
        """ A modal operator blocks the rest of the interface but this is not clear.
            I don't think I can grey out the rest of the interface, but I can draw a frame for focus. """

        vertices = []
        indices = []

        b = 24
        b_inner = 16
        o = 0

        w += 20  # Blender 3.0 no longer draws panel backgrounds. This compensates for it.

        vertices = [
            (o, o), (x + b, y + b), (x + w - b, y + b), (x + w - o + 1000, y + o),
            (o, y + h - o), (x + w - o + 1000, y + h - o), (x + b, y + h - b), (x + w - b, y + h - b)]
        indices = [
            (0, 1, 2), (2, 3, 0), (4, 5, 6), (6, 5, 7),
            (0, 4, 1), (1, 4, 6), (2, 7, 5), (5, 3, 2)]

        # Rounded.
        corner = (x + w - b, h - b)
        corner_index = len(vertices) - 1
        for i in range(32):

            if i < 8:
                c = -b_inner
                d = -b_inner
            elif i < 16:
                c = b_inner
                d = -b_inner
            elif i < 24:
                c = b_inner
                d = b_inner
            else:
                c = -b_inner
                d = b_inner

            vertices.append((
                corner[0] + b_inner * cos(i / 32 * 6.283185) + c,
                corner[1] + b_inner * sin(i / 32 * 6.283185) + d
            ))

            indices.append((len(vertices) - 2, len(vertices) - 1, corner_index))

            if i in [0, 7, 15, 31]:
                vertices.append((
                    corner[0] + b_inner * cos((i + 1) / 32 * 6.283185) + c,
                    corner[1] + b_inner * sin((i + 1) / 32 * 6.283185) + d
                ))
                indices.append((len(vertices) - 2, len(vertices) - 1, corner_index))

            if i == 0:
                corner = (x + w - b, h - b)
                vertices.append(corner)
                corner_index = len(vertices) - 1
            elif i == 7:
                corner = (x + b, h - b)
                vertices.append(corner)
                corner_index = len(vertices) - 1
            elif i == 15:
                corner = (x + b, b)
                vertices.append(corner)
                corner_index = len(vertices) - 1
            elif i == 23:
                corner = (x + w - b, b)
                vertices.append(corner)
                corner_index = len(vertices) - 1

        color = (0.0, 0.0, 0.0, 0.28)
        blend_set('ALPHA')
        shader = self.flat_shader
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    def draw_fade(self, alpha=1.0):
        """ Draw a transparent fog over the 3D view to fade the existing trees. """

        region = bpy.context.region
        color = (0.5, 0.5, 0.5, 0.6)

        try:
            # Just in case something changes in Blender.
            if bpy.context.screen.areas[2].spaces[0].shading.background_type == 'VIEWPORT':
                color = bpy.context.area.spaces[0].shading.background_color
                # Fix 2.2 gamma.
                color = (color[0] ** 0.4545, color[1] ** 0.4545, color[2] ** 0.4545, 0.4)
            else:
                color = bpy.context.preferences.themes['Default'].view_3d.space.gradients.high_gradient
                color = (color[0], color[1], color[2], 0.7)
        except:
            color = (0.5, 0.5, 0.5, 0.6)

        if alpha != 1.0:
            color = (color[0], color[1], color[2], alpha)

        vertices = [
            (0, 0),
            (0, region.height),
            (region.width, region.height),
            (region.width, 0)]
        indices = [
            (0, 1, 2),
            (2, 3, 0)]

        blend_set('ALPHA')
        shader = self.flat_shader
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
        shader.bind()
        shader.uniform_float("color", color)
        batch.draw(shader)

    def draw_icon(self, icon_id, loc, size, color=(1.0, 1.0, 1.0, 1.0)):
        """ Draw an vector graphic, consisting of triangles.
            Icons are stored in InterfaceIcons.py as two dictionaries.
            The first has all the vertex locations, and the second has all the face indices. """

        if not icon_vertices[icon_id]:
            return

        vertices = array(icon_vertices[icon_id])
        vertices *= size
        vertices += loc
        vertices = vertices.tolist()

        shader = self.flat_shader
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=icon_indices[icon_id])
        shader.bind()
        shader.uniform_float("color", color)
        blend_set('ALPHA')
        batch.draw(shader)

    def draw_number_text(self, loc, text, color=(1.0, 1.0, 1.0, 1.0), size=1.0, align='LEFT', do_not_draw=False):
        """ Number texts are similar to icons.
            They are vector graphic that are built up with triangles. """

        size *= 0.4
        if size < 12:
            size = 12
            # Prevent numbers that are too small, because there's more than enough room in the dial to display larger text.
        spacing = size * 0.63
        width = len(text) * spacing
        if '.' in text:
            width -= spacing / 2

        """ width = 0.0
        last_character = '~'
        for character in text:
            if character in ['.', 'I', 'i', 'l', ' '] or last_character in ['I', 'i', 'l', ' ']:
                width -= spacing / 4
            if last_character.islower():
                width -= spacing / 8
            width += spacing
            if character == '.':
                width -= spacing / 4
            last_character = character """

        if align == 'CENTER':
            pos = loc - Vector((width / 2, 0.0))
        elif align == 'LEFT':
            pos = loc
        elif align == 'RIGHT':
            pos = loc - Vector((width, 0.0))
        pos[0] += spacing / 2  # Because characters in my font are drawn centered.

        blend_set('ALPHA')
        # glEnable(GL_POLYGON_SMOOTH)

        if not do_not_draw:
            last_character = '!'
            for character in text:
                """
                if character in ['.', 'I', 'i', 'l', ' '] or last_character in ['I', 'i', 'l', ' ']:
                    pos[0] -= spacing / 4
                if last_character.islower():
                    pos[0] -= spacing / 8
                """

                if character == '.':
                    pos -= Vector((spacing / 4, 0))

                vertices = []
                for i in range(len(char_vertices[character])):
                    vertices.append(Vector(char_vertices[character][i]) * Vector((size, size * 0.8)) + pos)

                shader = self.flat_shader
                batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=char_indices[character])
                shader.bind()
                shader.uniform_float("color", color)
                batch.draw(shader)

                pos += Vector((spacing, 0))
                if character == '.':
                    pos -= Vector((spacing / 4, 0))

                last_character = character

            blend_set('NONE')
            # glDisable(GL_POLYGON_SMOOTH)

        return Vector((width, 0))

    def draw_circle_filled(self, loc, radius, color=(0.0, 0.0, 0.0, 0.7)):
        """ A filled circle as a triangle fan from the center. """

        # circle_points = []
        # circle_points.append(loc)
        # for i in range(65):
        #     angle = i / 64 * 6.283185
        #     circle_points.append(Vector((cos(angle), sin(angle))) * radius + loc)

        # Only slightly faster.
        if radius < 30:
            circle_points = (self.circle_points_16 * radius + loc).tolist()
        else:
            circle_points = (self.circle_points_64 * radius + loc).tolist()

        shader = self.flat_shader
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": circle_points})
        shader.bind()
        shader.uniform_float("color", color)
        blend_set('ALPHA')
        batch.draw(shader)

    def draw_dial(self, loc, radius, color=widget_color, width=4, rotation=0.0, resolution=64, pie=False, number_of_petals=8):
        """ Circle with star spikes. """

        circle_points = []
        circle_points.append(loc)
        for i in range(resolution + 1):
            angle = i / resolution * 6.283185 - rotation * 1.5
                # Increase the last number to 6.283 for reality, but it's too fast.
            radius_adjusted = radius
            if pie:
                radius_adjusted -= width
            if not pie and i % 2:
                radius_adjusted += width
            if pie:
                radius_adjusted += width * 0.5 * abs(sin(number_of_petals / 2 * angle + 1.57)) ** 0.8 + 2
            circle_points.append(Vector((cos(angle), sin(angle))) * radius_adjusted + loc)

        shader = self.flat_shader
        shader.bind()
        shader.uniform_float("color", color)
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": circle_points})
        line_width_set(width)
        blend_set('ALPHA')
        batch.draw(shader)

    def draw_donut_dial(self, loc, radius, inner_radius, color=widget_color, width=4, resolution=64, rotation=0.0):
        """ Circle with star spikes. """

        circle_points = []
        circle_points.append(loc)
        for i in range(resolution + 1):
            a = i / resolution * 6.283185 - rotation * 1.5
                # Increase the last number to 6.283 for reality, but it's too fast.
            r = radius
            if not i % 2:
                r += width
            circle_points.append(Vector((cos(a), sin(a))) * r + loc)
            circle_points.append(Vector((cos(a), sin(a))) * inner_radius + loc)

        shader = self.flat_shader
        batch = batch_for_shader(shader, 'TRI_STRIP', {"pos": circle_points})
        shader.bind()
        shader.uniform_float("color", color)
        line_width_set(width)
        blend_set('ALPHA')
        batch.draw(shader)

    def draw_donut(
            self,
            loc, radius, inner_radius, color=widget_color, pie_slice=1.0, pie_slice_overshoot=0.0,
            rotation=0.0, rounded=True):
        """ Circle with a hole. """

        # With rounded corners, squeeze it.
        if rounded and pie_slice < 1.0:
            rounded_radius = (radius - inner_radius) / 2
            median_radius = inner_radius + (radius - inner_radius) / 2
            rounded_angle = rounded_radius / (6.2832 * median_radius)
            amount = 0.67
            pie_slice -= 2 * rounded_angle * amount
            rotation += 6.2832 * rounded_angle * amount

        circle_points = []
        circle_points.append(loc)
        for i in range(int(64 * pie_slice) + 1):
            angle = i / 64 * 6.283185
            angle = -angle + 0.5 * 3.1415 - rotation
            circle_points.append(Vector((cos(angle), sin(angle))) * (radius + 48 * pie_slice_overshoot) + loc)
            circle_points.append(Vector((cos(angle), sin(angle))) * inner_radius + loc)

            # Rounded end.
            if rounded:
                if i == 0 or i == (int(64 * pie_slice) + 1) - 1:
                    if pie_slice != 1.0:
                        self.draw_circle_filled(
                            Vector((cos(angle), sin(angle))) * (inner_radius + (radius - inner_radius) / 2) + loc,
                            (radius - inner_radius) / 2, color=color)

        shader = self.flat_shader
        batch = batch_for_shader(shader, 'TRI_STRIP', {"pos": circle_points})
        shader.bind()
        shader.uniform_float("color", color)
        blend_set('ALPHA')
        batch.draw(shader)

    def draw_bar(self, x, y, w, r=12, shrink=0, color=(0.0, 0.0, 0.0, 0.7)):
        """ A pill shape, basically a rectangle with rounded corners where the radius equals the height. """

        self.draw_box_rounded(
            x,
            y + r - shrink,
            w,
            r * 2 - shrink * 2,
            color=color,
            r=r)

    def draw_box_rounded(self, x, y, w, h, color=(0.0, 0.0, 0.0, 0.7), r=12):
        """ A rectangle with round corners. """

        vertices = []
        indices = []
        o = -1

        pi = 3.14159265
        precision = 8
        if r * 2 > h:
            r = int(h / 2)

        startx = x + w
        starty = w

        for j in range(4):  # Four rounded corners.
            if j == 3:
                startx = x + w
                starty = y - h + r
            elif j == 2:
                startx = x
                starty = y - h + r
            elif j == 1:
                startx = x
                starty = y - r
            elif j == 0:
                startx = x + w
                starty = y - r

            vertices.append((startx, starty))
            o += 1
            o_corner = o
            for i in range(precision + 1):  # Draw this corner.
                inow = i + precision * j
                xa = startx + cos(2 * pi / (precision * 4) * inow) * r
                ya = starty + sin(2 * pi / (precision * 4) * inow) * r
                vertices.append((xa, ya))
                o += 1
                if i != 0:
                    indices.append((o, o - 1, o_corner))

        # Main rectangle.
        vertices.extend([(x + w, y - h),
                        (x, y - h),
                        (x, y),
                        (x + w, y)])
        o += 4
        indices.extend([(o, o - 1, o - 2),
                        (o, o - 2, o - 3)])

        # Left fill rectangle.
        vertices.extend([(x - r, y - r),
                        (x, y - r),
                        (x, y - h + r),
                        (x - r, y - h + r)])
        o += 4
        indices.extend([(o, o - 1, o - 2),
                        (o, o - 2, o - 3)])

        # Right fill rectangle.
        vertices.extend([(x + w, y - r),
                        (x + w + r, y - r),
                        (x + w + r, y - h + r),
                        (x + w, y - h + r)])
        o += 4
        indices.extend([(o, o - 1, o - 2),
                        (o, o - 2, o - 3)])

        shader = self.flat_shader
        batch = batch_for_shader(shader, 'TRIS', {"pos": vertices}, indices=indices)
        shader.bind()
        shader.uniform_float("color", color)
        blend_set('ALPHA')
        batch.draw(shader)

    def draw_text(
            self,
            pos, text, color=(1.0, 1.0, 1.0, 1.0), align='LEFT', vertical_align=False, size='regular',
            do_not_draw=False, shadow=True, radius=60):
        """ A text label. """

        pos = pos.copy()

        font_id = 0
        if size == 'regular':
            font_size = 27
            blf.color(font_id, color[0], color[1], color[2], color[3])
        elif size == 'large':
            font_size = 32
            blf.color(font_id, color[0], color[1], color[2], color[3])
        else:  # small
            font_size = 24
            blf.color(font_id, color[0] * 0.8, color[1] * 0.8, color[2] * 0.8, color[3])

        font_size = int(font_size * (radius / 60))
        blf.size(font_id, font_size)
        if shadow:
            blf.enable(font_id, blf.SHADOW)

        # return draw_number_text(pos, text, color=color, align =align, size=s, do_not_draw=do_not_draw)

        text = text.split('\n')
        offset = [0.0, 0.0]
        height = 0.0
        for line in text:
            dim = blf.dimensions(font_id, line)
            if vertical_align:
                offset[1] = font_size / 4  # Vertical align.

            if align == 'RIGHT':
                offset[0] = dim[0]
            elif align == 'LEFT':
                offset[0] = 0.0
            else:  # 'CENTER'
                offset[0] = dim[0] / 2

            blf.position(font_id, pos[0] - offset[0], pos[1] - offset[1], 0)

            if not do_not_draw:
                blf.draw(font_id, line)

            offset[1] += font_size * 1.5

        height = font_size * 1.5 * len(text)

        if not text:  # same as not len(text):
            dim = (0, 0)

        return Vector((dim[0], height))

    def draw_arrow(self, a, b, min_radius=10, color=(1.0, 1.0, 1.0, 1.0)):
        """ A spoke to indicate the rotation around a center point. """

        radius_a = 10
        radius_b = (b - a).length / 200 * radius_a * 2
        if radius_b < min_radius:
            radius_b = min_radius

        a_b = (b - a).length / (min_radius * 2)
        if a_b > 1.0:
            a_b = 1.0
        blend = a_b
        radius_a = blend * radius_a + (1.0 - blend) * min_radius

        rotation = (b - a).angle_signed(Vector((1.0, 0.0)), 0.0)
        matrix = Matrix.Rotation(rotation, 2, 'Z')

        circle_points = []
        circle_points.append(b)
        for i in range(65):
            r = i / 64 * 6.283 + 1.57079632
            if i == 64:
                circle_points.append(matrix @ Vector((cos(r), sin(r))) * radius_a + a)
            elif i < 32:
                circle_points.append(matrix @ Vector((cos(r), sin(r))) * radius_a + a)
            else:
                circle_points.append(matrix @ Vector((cos(r), sin(r))) * radius_b + b)

        shader = self.flat_shader
        batch = batch_for_shader(shader, 'TRI_FAN', {"pos": circle_points})
        shader.bind()
        shader.uniform_float("color", color)
        blend_set('ALPHA')
        batch.draw(shader)

    def draw_thick_lines(
        self, lines, thickness=4, thicknesses=[], multiplier=1.0, color=(1.0, 1.0, 1.0, 0.7)):
        """ OpenGL thick lines are ugly, have limited thickness and this thickness even depends on the system.
            The have ugly ends and are interrupted at angles.

            I wrote this function to be able to draw beautiful lines with varying thickness. """

        shader = self.flat_shader
        shader.bind()
        shader.uniform_float("color", color)
        blend_set('ALPHA')

        vertices = []

        do_thicknesses = False
        if thicknesses:
            do_thicknesses = True

        for j, line in enumerate(lines):
            if j > 0:
                # New branch/line, add a degenerate triangle.
                if len(vertices):
                    vertices.extend([vertices[-1], vertices[-1]])

            for i, point in enumerate(line):
                point = Vector(point)
                if i == len(line) - 1:
                    direction = point - Vector(line[i - 1])
                else:
                    direction = Vector(line[i + 1]) - point

                if direction.length < 1:
                    continue

                # Skip points behind the camera.
                if point.x == 0.0 and point.y == 0.0:
                    continue

                if i > 0:
                    previous_direction = point - Vector(line[i - 1])
                    direction = direction + previous_direction / 2

                offset = Vector((-direction.y, direction.x)).normalized() * thickness / 2.0

                if do_thicknesses:
                    offset *= thicknesses[j][i] * multiplier

                if i == 0:
                    # Complete the degenerate triangle.
                    vertices.append(point + offset)
                vertices.extend([point + offset, point - offset])

            # This was the old code before adding degenerate triangles.
            # batch = batch_for_shader(shader, 'TRI_STRIP', {"pos": vertices})
            # batch.draw(shader)
            # vertices = []

        batch = batch_for_shader(shader, 'TRI_STRIP', {"pos": vertices})
        batch.draw(shader)

    def draw_scale_figure(self, alpha_multiplier=1.0):
        """ Draw a figure for scale in the turntabel operator. """

        region = bpy.context.region
        region_data = bpy.context.region_data
        default_vector = Vector((0.0, 0.0))

        toe = location_3d_to_region_2d(
            region, region_data, Vector((2.0, 0.0, 0.0)), default=default_vector)
        tip = location_3d_to_region_2d(
            region, region_data, Vector((2.0, 0.0, 1.75)), default=default_vector)

        # Below is less precise but a lot faster.
        waist = toe + (tip - toe) * 0.46  # 0.8 meter
        neck = toe + (tip - toe) * 0.83  # 1.45 meter

        if toe[0] == 0 and toe[1] == 0:
            return

        alpha = 1.0 - (tip - toe).length / region.height
        alpha *= alpha_multiplier
        color = (1.0, 0.9, 0.4, alpha * 0.1)

        lines = [[toe, waist], [neck, tip], [waist, neck]]  # Legs, head and torso.

        thickness = int((toe - waist).length) * 0.3
        thickness_multipliers = [[1, 1], [1, 1], [2, 2]]
        self.draw_thick_lines(
            lines,
            thickness=thickness,
            thicknesses=thickness_multipliers,
            color=color)
